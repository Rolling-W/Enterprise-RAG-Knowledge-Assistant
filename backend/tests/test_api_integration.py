"""Real API/ingestion/retrieval checks using an isolated in-memory Qdrant store.

Run: python -m unittest discover -s backend/tests -v
Requires backend dependencies plus httpx (FastAPI TestClient).
"""

import unittest
import warnings
from unittest.mock import patch

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from backend import main


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        warnings.filterwarnings("ignore", message="Payload indexes have no effect in the local Qdrant.*")
        self.store = QdrantClient(":memory:")
        self.factory = patch.object(main, "create_client", return_value=self.store)
        self.factory.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.factory.stop()
        self.store.close()
        self.warning_context.__exit__(None, None, None)

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
                self.assertTrue(0 <= result["score"] <= 1)
                self.assertTrue(result["chunk_id"])

    def test_401_and_403_and_clearance_filter(self):
        self.assertEqual(self.client.post("/api/v1/search", json={"query": "leave"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/search", headers={"Authorization": "Bearer invalid"}, json={"query": "leave"}).status_code, 401)
        staff = self.login("staff@enterprise.local")
        response = self.client.post("/api/v1/upload", headers=staff, files={"file": ("policy.txt", b"leave", "text/plain")})
        self.assertEqual(response.status_code, 403)
        manager = self.login()
        self.upload(manager)
        forbidden = self.client.post("/api/v1/search", headers=manager, json={"query": "leave", "filters": {"department": "HR"}})
        self.assertEqual(forbidden.status_code, 403)
        response = self.client.post("/api/v1/search", headers=staff, json={"query": "leave"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

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


if __name__ == "__main__":
    unittest.main()
