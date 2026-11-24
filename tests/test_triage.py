"""Isolated SQLite fixtures only. No Meta, AI calls or writes to the project database."""
import json
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.api.v1.triage import router
from app.api.v1.meta import router as meta_router
from app.api.v1.cases import router as cases_router
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.meta_post import MetaPost
from app.models.user import User


class TriageTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda connection, record: connection.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([User(id="test-operator", email="operator@test.invalid", hashed_password="unused", full_name="Test operator", role="OPERADOR", is_active=True),
            User(id="test-secretary", email="secretary@test.invalid", hashed_password="unused", full_name="Test secretary", role="SECRETARIO", is_active=True)])
        self.comments = [{"id": "full-a-123456", "author": "Author A", "message": "Solicitud de revisión de una fuga", "time": "2026-11-24T12:00:00Z"},
            {"id": "full-b-123456", "author": "Author B", "message": "La fuga continúa", "time": "2026-11-24T12:05:00Z"},
            {"id": "full-c-123456", "author": "Author C", "message": "Otra solicitud", "time": "2026-11-24T12:06:00Z"}]
        self.db.add(MetaPost(id="test-post", title="Test publication", source="Facebook", published_at="2026-11-24", raw_comments_json=json.dumps(self.comments)))
        self.db.commit()
        app = FastAPI()
        for part in (router, meta_router, cases_router): app.include_router(part, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer " + create_access_token({"sub": "test-operator"})}

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def save(self, indexes, target=None, headers=None):
        payload = {"comments": [{"post_id": "test-post", "comment_id": self.comments[i]["id"]} for i in indexes]}
        if target: payload["target_case_id"] = target
        return self.client.post("/api/v1/triage/consolidate", json=payload, headers=self.headers if headers is None else headers)

    def test_creation_survives_new_session_and_repeat_is_idempotent(self):
        first = self.save([0, 1])
        self.assertEqual(first.status_code, 200)
        result = first.json()
        self.assertTrue(result["created"])
        self.assertEqual(result["linked"], 2)
        with Session(self.engine) as other:
            case = other.get(Case, result["case_id"])
            self.assertEqual(case.comments_count, 2)
            self.assertIsNone(case.institutional_radicado)
            self.assertIsNone(case.assigned_department)
            self.assertEqual(case.priority, "Media")
            links = other.query(CaseComment).all()
            self.assertEqual(len(links), 2)
            self.assertTrue(all(link.linked_by == "test-operator" for link in links))
            self.assertEqual(links[0].comment_json, self.comments[0])
        repeat = self.save([1, 0, 0]).json()
        self.assertFalse(repeat["created"])
        self.assertEqual(repeat["case_id"], result["case_id"])
        self.assertEqual(repeat["linked"], 0)
        self.assertEqual(repeat["comments_count"], 2)
        self.assertEqual(self.db.query(Case).count(), 1)

    def test_existing_case_association_does_not_double_count(self):
        case_id = self.save([0]).json()["case_id"]
        response = self.save([0, 1], case_id).json()
        self.assertEqual(response["linked"], 1)
        self.assertEqual(response["comments_count"], 2)
        self.assertEqual(self.save([0, 1], case_id).json()["comments_count"], 2)
        detail = self.client.get("/api/v1/cases/" + case_id).json()
        self.assertEqual(len(detail["linked_comments"]), 2)

    def test_conflicting_cases_do_not_move_or_partially_add_comments(self):
        first = self.save([0]).json()["case_id"]
        second = self.save([1]).json()["case_id"]
        self.assertEqual(self.save([1, 2], first).status_code, 409)
        self.assertEqual(self.db.query(CaseComment).count(), 2)
        self.assertEqual(self.db.query(CaseComment).filter_by(case_id=second).count(), 1)
        self.assertEqual(self.save([0, 1]).status_code, 409)
        self.assertEqual(self.db.query(Case).count(), 2)

    def test_missing_capture_rolls_back_entire_selection(self):
        response = self.client.post("/api/v1/triage/consolidate", headers=self.headers, json={"comments": [
            {"post_id": "test-post", "comment_id": self.comments[0]["id"]}, {"post_id": "test-post", "comment_id": "missing"}]})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query(Case).count(), 0)
        self.assertEqual(self.db.query(CaseComment).count(), 0)

    def test_legacy_exact_reference_reuses_case(self):
        legacy = Case(id="legacy", title="Legacy", author="Author A", source="Facebook", priority="Media", content="Existing request", category="General", sentiment="Sin evaluar", location="No especificada", date_time="2026-11-24", status="Pendiente", comments_count=1,
            internal_notes=f'[Post ID]: test-post\n[Comment ID]: {self.comments[0]["id"]}')
        self.db.add(legacy); self.db.commit()
        response = self.save([0, 1]).json()
        self.assertEqual(response["case_id"], "legacy")
        self.assertEqual(response["comments_count"], 2)
        self.assertEqual(self.db.query(Case).count(), 1)

    def test_pending_queue_has_exact_identifiers_and_excludes_linked(self):
        before = self.client.get("/api/v1/meta/triage-comments", headers=self.headers).json()
        self.assertEqual(len({c["id"] for c in before}), 3)
        self.assertEqual({c["comment_id"] for c in before}, {c["id"] for c in self.comments})
        self.assertTrue(all(c["aiConfidence"] is None and not c["metaDirectContactAllowed"] for c in before))
        self.save([0])
        after = self.client.get("/api/v1/meta/triage-comments", headers=self.headers).json()
        self.assertEqual(len(after), 2)

    def test_closed_case_and_nonexistent_target_are_rejected(self):
        case_id = self.save([0]).json()["case_id"]
        self.db.get(Case, case_id).status = "Resuelto"; self.db.commit()
        self.assertEqual(self.save([1], case_id).status_code, 409)
        self.assertEqual(self.save([1], "missing").status_code, 404)
        self.assertEqual(self.db.query(CaseComment).count(), 1)

    def test_authentication_and_role_are_required(self):
        for headers in ({}, {"Authorization": "Bearer demo-token-operador"}):
            self.assertEqual(self.save([0], headers=headers).status_code, 401)
            self.assertEqual(self.client.get("/api/v1/meta/triage-comments", headers=headers).status_code, 401)
        headers = {"Authorization": "Bearer " + create_access_token({"sub": "test-secretary"})}
        self.assertEqual(self.save([0], headers=headers).status_code, 403)
        self.assertEqual(self.db.query(Case).count(), 0)

    def test_unbounded_and_injected_payloads_are_rejected(self):
        reference = {"post_id": "test-post", "comment_id": self.comments[0]["id"]}
        for payload in ({"comments": []}, {"comments": [reference] * 101}, {"comments": [reference], "assigned_department": "invented"}):
            self.assertEqual(self.client.post("/api/v1/triage/consolidate", json=payload, headers=self.headers).status_code, 422)

    def test_deleting_case_preserves_capture_and_cascades_links(self):
        case_id = self.save([0]).json()["case_id"]
        self.db.delete(self.db.get(Case, case_id)); self.db.commit()
        self.assertEqual(self.db.query(CaseComment).count(), 0)
        self.assertEqual(json.loads(self.db.get(MetaPost, "test-post").raw_comments_json), self.comments)


if __name__ == "__main__": unittest.main()
