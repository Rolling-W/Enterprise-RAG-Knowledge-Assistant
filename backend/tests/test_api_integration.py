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


if __name__ == "__main__":
    unittest.main()
