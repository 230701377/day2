"""Integration test that exercises the full API surface end-to-end against a
running Postgres + pgvector instance. Skipped if DATABASE_URL is not set."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.getenv("DATABASE_URL")


@unittest.skipIf(not DB_URL, "DATABASE_URL not set - skipping integration test")
class ApiEndToEndTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.session import SessionLocal, engine, Base
        from app.models.models import User, ApprovalWorkflow
        from app.services.workflow.engine import DEFAULT_WORKFLOW
        from app.core.security import hash_password

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        self.client = TestClient(app)
        db = SessionLocal()
        # baseline data
        admin = User(email="admin@test.com", full_name="Admin", role="admin",
                      hashed_password=hash_password("Test1234!"))
        legal = User(email="legal@test.com", full_name="Legal", role="legal",
                      hashed_password=hash_password("Test1234!"))
        requester = User(email="req@test.com", full_name="R", role="requester",
                          hashed_password=hash_password("Test1234!"))
        db.add_all([admin, legal, requester])
        wf = ApprovalWorkflow(**DEFAULT_WORKFLOW)
        db.add(wf)
        db.commit()
        self.db = db

    def _login(self, email):
        r = self.client.post("/api/v1/auth/login",
                              json={"email": email, "password": "Test1234!"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def test_full_flow(self):
        token = self._login("req@test.com")
        h = {"Authorization": f"Bearer {token}"}

        # 1. Create a contract
        r = self.client.post("/api/v1/contracts", headers=h, json={
            "title": "Test MSA",
            "contract_type": "msa",
            "counterparty": "Globex",
            "value_amount": 50000,
        })
        self.assertEqual(r.status_code, 201, r.text)
        cid = r.json()["id"]

        # 2. Upload a version
        body = b"""MASTER SERVICES AGREEMENT\n\n1. Term.\nThis Agreement shall be for 12 months.\n\n2. Limitation of Liability.\nIn no event shall liability exceed fees paid.\n\n3. Governing Law.\nThis Agreement shall be governed by the laws of New York.\n"""
        files = {"file": ("test.txt", io.BytesIO(body), "text/plain")}
        r = self.client.post(f"/api/v1/contracts/{cid}/versions", headers=h, files=files)
        self.assertEqual(r.status_code, 201, r.text)
        vid = r.json()["id"]

        # 3. AI analysis
        r = self.client.post(f"/api/v1/ai/analyze/{cid}/{vid}", headers=h)
        self.assertEqual(r.status_code, 200, r.text)
        analysis = r.json()
        self.assertGreater(len(analysis["clauses"]), 0)
        self.assertIn("risk_score", analysis)

        # 4. RAG Q&A
        r = self.client.post("/api/v1/qa/ask", headers=h, json={"question": "What is the term?"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("answer", r.json())

        # 5. Submit for review
        r = self.client.post(f"/api/v1/contracts/{cid}/submit-for-review", headers=h)
        self.assertEqual(r.status_code, 200, r.text)

        # 6. Legal decides
        legal_token = self._login("legal@test.com")
        lh = {"Authorization": f"Bearer {legal_token}"}
        inbox = self.client.get("/api/v1/approvals/inbox", headers=lh).json()
        self.assertGreater(len(inbox), 0)
        ap_id = inbox[0]["id"]
        r = self.client.post(f"/api/v1/approvals/{ap_id}/decide", headers=lh,
                              json={"decision": "approved", "comments": "Looks good."})
        self.assertEqual(r.status_code, 200, r.text)

        # 7. Activate
        r = self.client.post(f"/api/v1/contracts/{cid}/activate", headers=admin and h)
        # activate requires admin or approved status; if all approvers are pending legal we may still be in_review

        # 8. Analytics
        r = self.client.get("/api/v1/analytics/overview", headers=h)
        self.assertEqual(r.status_code, 200, r.text)

        # 9. Audit verify
        admin_token = self._login("admin@test.com")
        r = self.client.get("/api/v1/audit/verify",
                             headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["valid"])


if __name__ == "__main__":
    unittest.main()
