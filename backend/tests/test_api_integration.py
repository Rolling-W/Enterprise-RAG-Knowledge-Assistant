"""Real API/ingestion/retrieval checks using an isolated in-memory Qdrant store.

Run: python -m unittest discover -s backend/tests -v
Requires backend dependencies plus httpx (FastAPI TestClient).
"""

import unittest
import warnings
from unittest.mock import patch
import math

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from backend import main

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.models import Base



class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        warnings.filterwarnings("ignore", message="Payload indexes have no effect in the local Qdrant.*")
        self.store = QdrantClient(":memory:")
        self.factory = patch.object(main, "create_client", return_value=self.store)
        self.factory.start()

        # Isolated SQLite database for each test.
        self.db_engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.db_engine, "connect")
        def enable_foreign_keys(connection, connection_record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(bind=self.db_engine)

        TestingSessionLocal = sessionmaker(
            bind=self.db_engine,
            autoflush=False,
            autocommit=False,
        )

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db] = override_get_db

        # Prevent background reindex tasks from accessing real services.
        self.reindex_patcher = patch.object(
            main,
            "run_document_reindex",
            return_value=None,
        )
        self.reindex_patcher.start()

        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.reindex_patcher.stop()
        self.factory.stop()
        self.store.close()
        self.warning_context.__exit__(None, None, None)

        main.app.dependency_overrides.pop(main.get_db, None)
        self.db_engine.dispose()


    def login(self, username="manager@enterprise.local"):
        response = self.client.post("/api/v1/auth/login", json={"username": username, "password": "demo123"})
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        self.assertEqual(len(token.split(".")), 3)
        return {"Authorization": f"Bearer {token}"}

    def upload(self, headers):
        response = self.client.post(
            "/api/v1/upload",
            headers=headers,
            files={"file": ("weekly-policy.md", b"# Leave policy\nEmployees receive 23 days of annual leave.\nContact HR for details.", "text/markdown")},
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "indexed")
        self.assertIn("Indexed 1 chunks", response.json()["message"])
        return response.json()["document_id"]

    def test_upload_then_search_real_content_in_all_modes(self):
        headers = self.login()
        document_id = self.upload(headers)
        for mode in ("keyword", "semantic", "hybrid"):
            with self.subTest(mode=mode):
                response = self.client.post("/api/v1/search", headers=headers, json={"query": "annual leave", "search_mode": mode})
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body["search_mode"], mode)
                self.assertEqual(body["total"], 1)
                result = body["results"][0]
                self.assertEqual(result["document_id"], document_id)
                self.assertEqual(result["title"], "weekly-policy.md")
                self.assertIn("23 days", result["content"])
                self.assertEqual(result["citation"], {"page": None, "line_start": 1, "line_end": 3})
                self.assertIsInstance(result["score"], (int, float))
                self.assertTrue(math.isfinite(result["score"]))
                self.assertTrue(result["chunk_id"])

    def test_401_and_403_and_clearance_filter(self):
        self.assertEqual(self.client.post("/api/v1/search", json={"query": "leave"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/search", headers={"Authorization": "Bearer invalid"}, json={"query": "leave"}).status_code, 401)
        staff = self.login("staff@enterprise.local")
        response = self.client.post("/api/v1/upload", headers=staff, files={"file": ("policy.txt", b"leave", "text/plain")})
        self.assertEqual(response.status_code, 403)
        manager = self.login()
        document_id = self.upload(manager)
        forbidden = self.client.post("/api/v1/search", headers=manager, json={"query": "leave", "filters": {"department": "HR"}})
        self.assertEqual(forbidden.status_code, 403)

        for mode in ("keyword", "semantic", "hybrid"):
            with self.subTest(mode=mode):
                response = self.client.post(
                    "/api/v1/search",
                    headers=staff,
                    json={
                        "query": "leave",
                        "search_mode": mode,
                    },
                )

                self.assertEqual(
                    response.status_code,
                    200,
                    response.text,
                )

                results = response.json()["results"]

                # Staff can read a General department document
                # requiring clearance level 1.
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["document_id"], document_id)
                self.assertEqual(results[0]["department_id"], "General")
                self.assertEqual(results[0]["permission_level"], 1)



    def test_empty_upload_and_openapi_contract(self):
        response = self.client.post("/api/v1/upload", headers=self.login(), files={"file": ("empty.txt", b"", "text/plain")})
        self.assertEqual(response.status_code, 400)
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        for path in ("/api/v1/auth/login", "/api/v1/upload", "/api/v1/search"):
            self.assertIn(path, spec["paths"])
        self.assertIn("score", spec["components"]["schemas"]["SearchResult"]["properties"])


    def test_multi_document_hybrid_retrieval(self):
        headers = self.login()

        documents = [
            (
                "leave-policy.md",
                b"# Leave Policy\nEmployees receive 23 days of annual leave.",
            ),
            (
                "warehouse-policy.md",
                b"# Warehouse Operations\nInventory is checked every Monday.",
            ),
            (
                "security-policy.md",
                b"# Security Policy\nAll employees must use multi-factor authentication.",
            ),
        ]

        for filename, content in documents:
            response = self.client.post(
                "/api/v1/upload",
                headers=headers,
                files={
                    "file": (
                        filename,
                        content,
                        "text/markdown",
                    )
                },
            )

            self.assertEqual(
                response.status_code,
                202,
                response.text,
            )

        response = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={
                "query": "How many vacation days do employees receive?",
                "search_mode": "hybrid",
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)

        results = response.json()["results"]

        self.assertGreater(len(results), 0)
        self.assertEqual(
            results[0]["title"],
            "leave-policy.md",
        )
        self.assertIn(
            "23 days",
            results[0]["content"],
        )

        print("\nHybrid search ranking:")
        for result in results:
            print(
                result["title"],
                "score=",
                round(result["score"], 4),
            )


    def test_txt_upload_and_citation(self):
        headers = self.login()

        response = self.client.post(
            "/api/v1/upload",
            headers=headers,
            files={
                "file": (
                    "employee-handbook.txt",
                    b"Employee Handbook\n"
                    b"All employees must complete safety training.\n"
                    b"Training is required every year.",
                    "text/plain",
                )
            },
        )

        self.assertEqual(response.status_code, 202, response.text)

        response = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={
                "query": "safety training",
                "search_mode": "hybrid",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)

        results = response.json()["results"]

        self.assertGreater(len(results), 0)

        result = results[0]

        self.assertEqual(
            result["title"],
            "employee-handbook.txt",
        )

        self.assertEqual(
            result["citation"],
            {
                "page": None,
                "line_start": 1,
                "line_end": 3,
            },
        )

        print("\nTXT Citation:", result["citation"])


    def test_pdf_upload_and_citation(self):
        from pathlib import Path

        headers = self.login()

        pdf_path = Path("sample_data/project_charter.pdf")
        pdf_content = pdf_path.read_bytes()

        response = self.client.post(
            "/api/v1/upload",
            headers=headers,
            files={
                "file": (
                    pdf_path.name,
                    pdf_content,
                    "application/pdf",
                )
            },
        )

        self.assertEqual(
            response.status_code,
            202,
            response.text,
        )

        print("\nPDF Upload:", response.json())

        response = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={
                "query": "Enterprise RAG Knowledge Assistant",
                "search_mode": "hybrid",
                "top_k": 3,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        results = response.json()["results"]

        self.assertGreater(len(results), 0)

        print("\nPDF Search Results:")
        for result in results:
            print({
                "title": result["title"],
                "score": round(result["score"], 4),
                "citation": result["citation"],
                "content": result["content"][:120],
            })

        self.assertEqual(
            results[0]["title"],
            "project_charter.pdf",
        )

        self.assertIsNotNone(
            results[0]["citation"]["page"],
        )

        self.assertIsNone(
            results[0]["citation"]["line_start"],
        )

        self.assertIsNone(
            results[0]["citation"]["line_end"],
        )


    def test_staff_handbook_pdf_retrieval(self):
        from pathlib import Path

        headers = self.login()
        pdf_path = Path("sample_data/staff_handbook_sample.pdf")

        response = self.client.post(
            "/api/v1/upload",
            headers=headers,
            files={
                "file": (
                    pdf_path.name,
                    pdf_path.read_bytes(),
                    "application/pdf",
                )
            },
        )

        self.assertEqual(response.status_code, 202, response.text)
        print("\nStaff Handbook Upload:", response.json())

        response = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={
                "query": "employee handbook policies",
                "search_mode": "hybrid",
                "top_k": 5,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)

        results = response.json()["results"]
        self.assertGreater(len(results), 0)

        print("\nStaff Handbook Search Results:")
        for result in results:
            print({
                "title": result["title"],
                "score": round(result["score"], 4),
                "citation": result["citation"],
                "content": result["content"][:150],
            })

        self.assertEqual(
            results[0]["title"],
            "staff_handbook_sample.pdf",
        )

        self.assertIsNotNone(
            results[0]["citation"]["page"],
        )

        self.assertIsNone(
            results[0]["citation"]["line_start"],
        )
        self.assertIsNone(
            results[0]["citation"]["line_end"],
        )


    def test_cross_document_hybrid_retrieval(self):
        from pathlib import Path

        headers = self.login()

        filenames = [
            "project_charter.pdf",
            "staff_handbook_sample.pdf",
            "annual_report_apple2025.pdf",
        ]

        for filename in filenames:
            path = Path("sample_data") / filename

            response = self.client.post(
                "/api/v1/upload",
                headers=headers,
                files={
                    "file": (
                        filename,
                        path.read_bytes(),
                        "application/pdf",
                    )
                },
            )

            self.assertEqual(
                response.status_code,
                202,
                response.text,
            )

            print("Indexed:", filename, response.json()["message"])

        queries = [
            (
                "What is the purpose of the Enterprise RAG Knowledge Assistant?",
                "project_charter.pdf",
            ),
            (
                "What is the purpose of the employee handbook?",
                "staff_handbook_sample.pdf",
            ),
            (
                "What was Apple's total net sales in fiscal 2025?",
                "annual_report_apple2025.pdf",
            ),
        ]

        correct = 0

        for query, expected_filename in queries:
            response = self.client.post(
                "/api/v1/search",
                headers=headers,
                json={
                    "query": query,
                    "search_mode": "hybrid",
                    "top_k": 5,
                },
            )

            self.assertEqual(
                response.status_code,
                200,
                response.text,
            )

            results = response.json()["results"]
            self.assertGreater(len(results), 0)

            top_result = results[0]
            actual_filename = top_result["title"]

            matched = actual_filename == expected_filename
            correct += int(matched)

            print("\nQuery:", query)
            print("Expected:", expected_filename)
            print("Top result:", actual_filename)
            print("Citation:", top_result["citation"])
            print("Matched:", matched)

        accuracy = correct / len(queries)

        print(
            f"\nTop-1 Document Accuracy: "
            f"{correct}/{len(queries)} ({accuracy:.0%})"
        )

        self.assertEqual(correct, len(queries))


    def test_conversation_message_generates_answer(self):
        headers = self.login()
        document_id = self.upload(headers)

        # Step 1: Create a conversation.
        response = self.client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "Leave Policy Discussion"},
        )

        self.assertEqual(response.status_code, 201, response.text)
        conversation_id = response.json()["conversation_id"]

        question = "How many annual leave days do employees receive?"
        expected_answer = "Employees receive 23 days of annual leave."

        # Step 2: Send a message and generate an AI answer.
        # Mock the LLM, but keep real retrieval and DB persistence.
        with patch.object(
            main,
            "generate_answer",
            return_value=expected_answer,
        ) as mock_generation:
            response = self.client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=headers,
                json={"content": question},
            )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["role"], "user")
        self.assertEqual(response.json()["content"], question)

        # The RAG pipeline should invoke answer generation once.
        mock_generation.assert_called_once()

        generation_args = mock_generation.call_args.kwargs
        self.assertEqual(generation_args["question"], question)
        self.assertIn("23 days", generation_args["context"])

        # Step 3: Reload the saved conversation.
        response = self.client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers=headers,
        )

        self.assertEqual(response.status_code, 200, response.text)

        conversation = response.json()
        messages = conversation["messages"]

        # Both user and assistant messages must be persisted.
        self.assertEqual(len(messages), 2)

        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], question)
        self.assertEqual(messages[0]["sequence"], 1)

        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], expected_answer)
        self.assertEqual(messages[1]["sequence"], 2)

        # Step 4: Verify saved source citations.
        citations = messages[1]["citations"]

        self.assertGreaterEqual(len(citations), 1)
        self.assertEqual(citations[0]["document_id"], document_id)
        self.assertEqual(citations[0]["title"], "weekly-policy.md")
        self.assertEqual(citations[0]["permission_level"], 1)
        self.assertTrue(citations[0]["chunk_id"])

        # Verify that the retrieval score survives conversation persistence.
        self.assertIn("score", citations[0])
        self.assertIsInstance(citations[0]["score"], (int, float))
        self.assertFalse(citations[0]["unavailable"])

        # Step 5: Revoke the manager's access by raising the document to L3.
        original_score = citations[0]["score"]
        executive_headers = self.login("executive@enterprise.local")

        response = self.client.patch(
            f"/api/v1/documents/{document_id}/permissions",
            headers=executive_headers,
            json={"permission_level": 3},
        )
        self.assertEqual(response.status_code, 200, response.text)

        # Step 6: Reload the conversation as the original manager.
        response = self.client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        revoked_citation = response.json()["messages"][1]["citations"][0]

        self.assertTrue(revoked_citation["unavailable"])
        self.assertIsNone(revoked_citation["score"])

        # Step 7: Restore L1 access and verify the original score survives.
        response = self.client.patch(
            f"/api/v1/documents/{document_id}/permissions",
            headers=executive_headers,
            json={"permission_level": 1},
        )
        self.assertEqual(response.status_code, 200, response.text)

        response = self.client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        restored_citation = response.json()["messages"][1]["citations"][0]

        self.assertFalse(restored_citation["unavailable"])
        self.assertEqual(restored_citation["score"], original_score)



    def test_conversation_generation_failure_and_retry(self):
        headers = self.login()
        self.upload(headers)

        response = self.client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "Generation Retry Test"},
        )
        self.assertEqual(response.status_code, 201, response.text)

        conversation_id = response.json()["conversation_id"]
        conversation_url = f"/api/v1/conversations/{conversation_id}"
        question = "How many annual leave days do employees receive?"

        # Step 1: Simulate an LLM service failure.
        with patch.object(
            main,
            "generate_answer",
            side_effect=RuntimeError("Simulated LLM failure"),
        ):
            response = self.client.post(
                f"{conversation_url}/messages",
                headers=headers,
                json={"content": question},
            )

        self.assertEqual(response.status_code, 503, response.text)

        # Step 2: The user message should remain saved.
        response = self.client.get(
            conversation_url,
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        messages = response.json()["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], question)

        # Step 3: Retry generation without adding another user message.
        expected_answer = "Employees receive 23 days of annual leave."

        with patch.object(
            main,
            "generate_answer",
            return_value=expected_answer,
        ) as mock_generation:
            response = self.client.post(
                f"{conversation_url}/generate",
                headers=headers,
            )

        self.assertEqual(response.status_code, 201, response.text)
        mock_generation.assert_called_once()

        # Step 4: Verify that the retry saved the assistant answer.
        response = self.client.get(
            conversation_url,
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)

        messages = response.json()["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(
            [message["role"] for message in messages],
            ["user", "assistant"],
        )
        self.assertEqual(messages[1]["content"], expected_answer)
        self.assertGreaterEqual(len(messages[1]["citations"]), 1)


    def test_citation_chunk_preview(self):
        # Upload a document using an authorized account.
        headers = self.login()
        document_id = self.upload(headers)

        # Find the actual chunk ID through the Search API.
        search_response = self.client.post(
            "/api/v1/search",
            headers=headers,
            json={
                "query": "annual leave",
                "search_mode": "hybrid",
            },
        )

        self.assertEqual(search_response.status_code, 200)
        chunk_id = search_response.json()["results"][0]["chunk_id"]

        # Authorized user should receive the original chunk.
        response = self.client.get(
            f"/api/v1/documents/{document_id}/chunks/{chunk_id}",
            headers=headers,
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["document_id"], document_id)
        self.assertEqual(response.json()["chunk_id"], chunk_id)
        self.assertIn("23 days", response.json()["content"])

        # Unauthenticated requests must be rejected.
        unauthorized = self.client.get(
            f"/api/v1/documents/{document_id}/chunks/{chunk_id}"
        )
        self.assertEqual(unauthorized.status_code, 401)

        # Unknown chunks must not expose document content.
        missing = self.client.get(
            f"/api/v1/documents/{document_id}/chunks/unknown_chunk",
            headers=headers,
        )
        self.assertEqual(missing.status_code, 404)


    def test_citation_chunk_preview_department_isolation(self):
        # Executive uploads a document to the Executive department.
        executive_headers = self.login(
            "executive@enterprise.local"
        )
        document_id = self.upload(executive_headers)

        # Executive retrieves the actual chunk ID.
        search_response = self.client.post(
            "/api/v1/search",
            headers=executive_headers,
            json={
                "query": "annual leave",
                "search_mode": "hybrid",
            },
        )

        self.assertEqual(
            search_response.status_code, 200,
            search_response.text,
        )
        chunk_id = search_response.json()["results"][0]["chunk_id"]

        # Executive can access the chunk.
        url = f"/api/v1/documents/{document_id}/chunks/{chunk_id}"

        executive_response = self.client.get(
            url,
            headers=executive_headers,
        )
        self.assertEqual(executive_response.status_code, 200)

        # Manager belongs to a different department.
        manager_headers = self.login(
            "manager@enterprise.local"
        )

        manager_response = self.client.get(
            url,
            headers=manager_headers,
        )

        # Cross-department access must be denied.
        self.assertEqual(
            manager_response.status_code,
            404,
            manager_response.text,
        )






if __name__ == "__main__":
    unittest.main()
