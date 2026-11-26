from tests.auth_helpers import prime_sessions, fixture_token
"""Complete HTTP workflow in isolated SQLite, never in the project's database."""
import json
import unittest
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_consolidation import CaseConsolidation
from app.models.case_provenance import CaseProvenanceReview
from app.models.meta_post import MetaPost
from app.models.user import User
from app.api.v1.case_consolidations import router
from app.api.v1.cases import router as case_router
from app.api.v1.triage import router as triage_router


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda con, rec: con.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        for key, role in (("admin", "ADMIN"), ("operator", "OPERADOR"), ("secretary", "SECRETARIO")):
            self.db.add(User(id=key, role=role, full_name="Isolated fixture", email=key+"@test.invalid", hashed_password="unused", is_active=True))
        raw = {"id": "comment-1", "message": "Isolated citizen request", "author": "Fixture author", "time": "2026-11-24T12:00:00Z"}
        self.db.add(MetaPost(id="post-1", title="Isolated publication", published_at="2026-11-24", raw_comments_json=json.dumps([raw])))
        for key in ("a", "b"):
            self.db.add(Case(id=key, title="Fixture " + key, author=raw["author"], content=raw["message"],
                date_time=raw["time"], source="Facebook", category="Por revisar", priority="Media", sentiment="Sin evaluar", location="No especificada",
                status="En Gestión" if key == "a" else "Pendiente", assigned_to="Fixture operator" if key == "a" else None,
                assigned_department="Fixture department" if key == "a" else None,
                internal_notes="[Post ID]: post-1" + ("\n[Comment ID]: comment-1" if key == "b" else "")))
        self.db.commit()
        prime_sessions(self.db)
        self.db.add(CaseComment(post_id="post-1", comment_id="comment-1", case_id="b", comment_json=raw, linked_by="operator"))
        self.db.add(CaseProvenanceReview(case_id="a", batch="fixture", status="needs_review", reason="comment_linked_to_other_case",
                                        evidence_json={"post_id": "post-1", "comment_id": "comment-1"}, reviewed_by="fixture"))
        self.db.commit()
        app = FastAPI()
        for item in (router, case_router, triage_router): app.include_router(item, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.headers = self.auth("admin")

    def auth(self, key):
        return {"Authorization": "Bearer " + fixture_token(self.db, key)}

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def compare(self, a="a", b="b"):
        return self.client.post("/api/v1/case-consolidations/compare", headers=self.headers,
                                json={"primary_case_id": a, "duplicate_case_id": b})

    def payload(self, **changes):
        data = dict(request_id=str(uuid.uuid4()), primary_case_id="a", duplicate_case_id="b", reason="Both histories reviewed in isolated test",
                    revision=self.compare().json()["revision"], confirmed_same_request=True)
        return {**data, **changes}

    def save(self, payload=None, headers=None):
        return self.client.post("/api/v1/case-consolidations", headers=headers or self.headers, json=payload or self.payload())

    def undo(self, key):
        return self.client.post(f"/api/v1/case-consolidations/{key}/undo", headers=self.headers, json={"reason": "Separate requests confirmed in isolated test"})

    def snapshot(self, model):
        self.db.expire_all()
        return [{col.name: getattr(row, col.name) for col in model.__table__.columns} for row in self.db.query(model).order_by(*model.__table__.primary_key.columns)]

    def test_comparison_returns_live_differences_full_notes_source_and_attention(self):
        result = self.compare().json()
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["attention_case_ids"], ["a"])
        self.assertIn("status", result["differences"])
        self.assertEqual(result["cases"][1]["internal_notes"], "[Post ID]: post-1\n[Comment ID]: comment-1")
        self.assertEqual(result["source"]["comment_id"], "comment-1")
        self.assertEqual(self.db.query(CaseConsolidation).count(), 0)

    def test_create_persist_retry_and_undo_keep_all_case_and_comment_data(self):
        before = self.snapshot(Case), self.snapshot(CaseComment), self.snapshot(CaseProvenanceReview)
        payload = self.payload()
        result = self.save(payload)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.save(payload).json()["id"], result.json()["id"])
        with Session(self.engine) as other:
            self.assertEqual(other.query(CaseConsolidation).count(), 1)
            self.assertTrue(other.get(CaseConsolidation, payload["request_id"]).evidence_json["confirmed_same_request"])
        self.assertEqual([row["id"] for row in self.client.get('/api/v1/cases').json()], ["a"])
        self.assertEqual(len(self.client.get('/api/v1/cases?include_duplicates=true').json()), 2)
        self.assertEqual(self.client.get('/api/v1/cases/b').json()["duplicate_of"], "a")
        self.assertEqual(self.client.get('/api/v1/cases/a').json()["provenance_status"], "consolidated")
        self.assertEqual(self.client.get('/api/v1/cases/a').json()["linked_comments"][0]["original_case_id"], "b")
        self.assertEqual(self.client.get('/api/v1/cases?provenance=needs_review').json(), [])
        self.assertEqual(before, (self.snapshot(Case), self.snapshot(CaseComment), self.snapshot(CaseProvenanceReview)))
        self.assertEqual(self.undo(payload["request_id"]).status_code, 200)
        self.assertEqual(self.undo(payload["request_id"]).status_code, 200)
        self.assertEqual(before, (self.snapshot(Case), self.snapshot(CaseComment), self.snapshot(CaseProvenanceReview)))
        self.assertEqual(len(self.client.get('/api/v1/cases').json()), 2)
        self.assertIsNone(self.client.get('/api/v1/cases/b').json()["duplicate_of"])
        self.assertEqual(self.client.get('/api/v1/cases/a').json()["linked_comments"], [])
        self.assertEqual(self.client.get('/api/v1/cases/a').json()["provenance_status"], "needs_review")
        self.assertEqual(len(self.client.get('/api/v1/cases?provenance=needs_review').json()), 1)
        history = self.client.get('/api/v1/case-consolidations/case/b', headers=self.headers).json()
        self.assertEqual(history[0]["undone_by"], "admin")

    def test_undo_never_overwrites_later_work_on_primary(self):
        key = self.save().json()["id"]
        self.client.post('/api/v1/cases/a/notes', headers=self.headers, json={"note": "Later real work", "author_name": "Fixture operator", "expected_revision": self.client.get("/api/v1/cases/a", headers=self.headers).json()["workflow_revision"]})
        self.undo(key)
        self.assertIn("Later real work", self.db.get(Case, "a").internal_notes)

    def test_all_duplicate_write_paths_and_primary_deletion_are_blocked(self):
        self.save()
        paths = [('patch', '/api/v1/cases/b', {"status": "Resuelto"}),
                 ('post', '/api/v1/cases/b/notes', {"note": "Should not save", "author_name": "Fixture"}),
                 ('post', '/api/v1/cases/b/dispatch', {"assigned_department": "Fixture", "assigned_to": "Fixture"}),
                 ('post', '/api/v1/cases/b/resolve', {"resolution_note": "Should not save fixture resolution", "resolved_by": "Fixture"}),
                 ('post', '/api/v1/cases/b/public-response', {"public_response": "Should not save"}),
                 ('post', '/api/v1/cases/b/priority-action', {})]
        for method, url, body in paths:
            response = getattr(self.client, method)(url, json=body, headers=self.headers)
            self.assertEqual(response.status_code, 409, (url, response.text))
        self.assertEqual(self.client.delete('/api/v1/cases/b').status_code, 409)
        self.assertEqual(self.client.delete('/api/v1/cases/a').status_code, 409)
        response = self.client.post('/api/v1/triage/consolidate', headers=self.auth('operator'), json={
            "comments": [{"post_id": "post-1", "comment_id": "comment-1"}], "target_case_id": "b"})
        self.assertEqual(response.status_code, 409)

    def test_cannot_choose_case_without_followup_over_case_with_followup(self):
        response = self.save(self.payload(primary_case_id="b", duplicate_case_id="a"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.db.query(CaseConsolidation).count(), 0)

    def test_stale_case_or_capture_revision_is_rejected(self):
        for kind in ("notes", "capture"):
            payload = self.payload()
            if kind == "notes":
                self.db.get(Case, "a").internal_notes += "\nNew work"
            else:
                self.db.get(MetaPost, "post-1").message = "New post context"
            self.db.commit()
            response = self.save(payload)
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.db.query(CaseConsolidation).count(), 0)

    def test_missing_or_mismatched_capture_and_multiple_comments_block_save(self):
        self.db.get(MetaPost, "post-1").raw_comments_json = '[]'
        self.db.commit()
        self.assertTrue(self.compare().json()["blockers"])
        self.assertEqual(self.save().status_code, 409)

    def test_extra_comment_or_third_case_requires_additional_review(self):
        self.db.add(CaseComment(post_id="post-1", comment_id="comment-2", case_id="b", comment_json={"message": "Additional request"}, linked_by="operator"))
        self.db.commit()
        self.assertTrue(self.compare().json()["blockers"])
        self.assertEqual(self.save().status_code, 409)
        self.db.query(CaseComment).filter_by(comment_id="comment-2").delete()
        self.db.add(Case(id="third", title="Another case", author="Fixture author", content="Isolated citizen request", source="Facebook",
                         category="Fixture", priority="Media", sentiment="Fixture", location="Fixture", date_time="2026-11-24T12:00:00Z",
                         internal_notes="[Post ID]: post-1\n[Comment ID]: comment-1"))
        self.db.commit()
        self.assertTrue(self.compare().json()["blockers"])
        self.assertEqual(self.save().status_code, 409)

    def test_old_undo_retry_cannot_undo_a_new_decision(self):
        first = self.save().json()["id"]
        self.undo(first)
        second = self.save().json()["id"]
        self.undo(first)
        self.assertIsNone(self.db.get(CaseConsolidation, second).undone_at)
        self.assertEqual(self.client.get('/api/v1/cases/b').json()["duplicate_of"], "a")

    def test_third_claimant_or_existing_pair_is_not_silently_absorbed(self):
        saved = self.save().json()
        self.assertTrue(self.compare().json()["blockers"])
        self.assertEqual(self.save().status_code, 409)
        self.undo(saved["id"])
        self.db.get(Case, "b").assigned_to = "Second operator"
        self.db.commit()
        self.assertEqual(self.save().status_code, 409)

    def test_auth_roles_and_explicit_confirmation_are_required(self):
        payload = self.payload()
        for headers in ({}, {"Authorization": "Bearer demo-token-admin"}):
            self.assertEqual(self.client.post('/api/v1/case-consolidations', headers=headers, json=payload).status_code, 401)
        self.assertEqual(self.save(payload, self.auth('operator')).status_code, 403)
        self.assertEqual(self.save({**payload, "confirmed_same_request": False}).status_code, 422)
        self.assertEqual(self.save({**payload, "reason": "          "}).status_code, 422)
        self.assertEqual(self.save(payload, self.auth('secretary')).status_code, 200)

    def test_distinct_exact_ids_and_idempotency_key_cannot_be_reused_for_other_decision(self):
        self.assertEqual(self.compare("a", "a").status_code, 422)
        self.assertEqual(self.compare("a", "missing").status_code, 404)
        payload = self.payload()
        self.save(payload)
        self.assertEqual(self.save({**payload, "reason": "Different decision must not reuse key"}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
