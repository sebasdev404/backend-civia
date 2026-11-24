"""Isolated fixtures only; no network calls or writes to the project's database."""
import json
import unittest
from types import SimpleNamespace as Record
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_provenance import CaseProvenanceReview
from app.models.meta_post import MetaPost
from app.services.provenance_recovery import plan_recovery, run_recovery, reference


def case(key="case-a", **changes):
    values = dict(id=key, content="Texto completo de prueba", author="Autor de prueba", date_time="2026-11-24T12:00:00Z", internal_notes="[Post ID]: post-a")
    values.update(changes)
    return Record(**values)


def post(rows=None):
    if rows is None:
        rows = [dict(id="comment-1", message="Texto completo de prueba", author="Autor de prueba", published_at="2026-11-24T12:00:00Z")]
    return Record(id="post-a", raw_comments_json=json.dumps(rows))


class RecoveryPlanningTests(unittest.TestCase):
    def test_requires_exact_post_text_author_and_time(self):
        original = case()
        self.assertEqual(plan_recovery([original], [post()], [])[0]["status"], "recovered_local")
        self.assertNotIn("[Comment ID]", original.internal_notes)
        for changes, reason in [({"content": original.content + " "}, "text_not_in_capture"),
                                ({"author": "Otro autor"}, "author_mismatch_or_missing"),
                                ({"date_time": "otra fecha"}, "timestamp_mismatch_or_missing"),
                                ({"date_time": ""}, "timestamp_mismatch_or_missing")]:
            item = plan_recovery([case(**changes)], [post()], [])[0]
            self.assertEqual(item["status"], "needs_review")
            self.assertEqual(item["reason"], reason)

    def test_identical_text_in_different_post_is_not_a_match(self):
        item = plan_recovery([case(internal_notes="[Post ID]: other-post")], [post()], [])[0]
        self.assertEqual(item["reason"], "source_missing")

    def test_two_comment_ids_with_same_evidence_are_ambiguous(self):
        row = json.loads(post().raw_comments_json)[0]
        item = plan_recovery([case()], [post([row, {**row, "id": "comment-2"}])], [])[0]
        self.assertEqual(item["reason"], "ambiguous_exact_match")

    def test_conflicting_versions_of_one_comment_reject_capture(self):
        row = json.loads(post().raw_comments_json)[0]
        item = plan_recovery([case()], [post([row, {**row, "message": "Changed"}])], [])[0]
        self.assertEqual(item["reason"], "invalid_or_conflicting_capture")

    def test_existing_legacy_claim_prevents_reassignment(self):
        other = case("case-b", internal_notes="[Post ID]: post-a\n[Comment ID]: comment-1")
        item = plan_recovery([case(), other], [post()], [])[0]
        self.assertEqual(item["reason"], "comment_linked_to_other_case")

    def test_structured_claim_prevents_reassignment(self):
        link = Record(post_id="post-a", comment_id="comment-1", case_id="case-b")
        self.assertEqual(plan_recovery([case()], [post()], [link])[0]["reason"], "comment_linked_to_other_case")

    def test_two_legacy_cases_cannot_take_same_comment(self):
        result = plan_recovery([case(), case("case-b")], [post()], [])
        self.assertTrue(all(item["reason"] == "multiple_cases_for_same_comment" for item in result))

    def test_reviewed_cohort_does_not_expand_to_new_cases(self):
        result = plan_recovery([case(), case("case-b")], [post()], [], ["case-a"])
        self.assertEqual([item["case_id"] for item in result], ["case-a"])


class RecoveryPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        event.listen(self.engine, "connect", lambda connection, record: connection.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        data = case()
        self.db.add(MetaPost(id="post-a", title="Test source", published_at="Test date", raw_comments_json=post().raw_comments_json))
        self.db.add(Case(id=data.id, content=data.content, author=data.author, date_time=data.date_time, internal_notes=data.internal_notes,
                         title="Existing title", category="Existing category", priority="Alta", sentiment="Existing sentiment", source="Facebook", location="Existing location", comments_count=1))
        self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def test_preview_does_not_write(self):
        result = run_recovery(self.db)
        self.assertEqual(result["counts"]["recovered_local"], 1)
        self.assertEqual(self.db.query(CaseComment).count(), 0)
        self.assertEqual(self.db.query(CaseProvenanceReview).count(), 0)

    def test_apply_persists_evidence_without_changing_business_fields(self):
        before = self.db.get(Case, "case-a")
        values = {c.name: getattr(before, c.name) for c in Case.__table__.columns if c.name not in ("internal_notes", "updated_at")}
        result = run_recovery(self.db, apply=True, expected_recoverable=1)
        self.assertEqual(result["links_added"], 1)
        self.db.close()
        self.db = Session(self.engine)
        updated = self.db.get(Case, "case-a")
        self.assertEqual(reference(updated.internal_notes, "Comment ID"), "comment-1")
        self.assertEqual(values, {field: getattr(updated, field) for field in values})
        self.assertEqual(self.db.get(CaseProvenanceReview, "case-a").status, "recovered_local")
        notes = updated.internal_notes
        second = run_recovery(self.db, apply=True, expected_recoverable=1)
        self.assertEqual(second["links_added"], 0)
        self.assertEqual(updated.internal_notes, notes)
        self.assertEqual(self.db.query(CaseComment).count(), 1)

    def test_changed_preview_rolls_back_without_writing(self):
        with self.assertRaises(ValueError):
            run_recovery(self.db, apply=True, expected_recoverable=2)
        self.assertEqual(self.db.query(CaseComment).count(), 0)
        self.assertEqual(self.db.query(CaseProvenanceReview).count(), 0)

    def test_unrecoverable_is_persistently_flagged_without_modifying_case(self):
        self.db.get(Case, "case-a").author = "Different recorded author"
        self.db.commit()
        result = run_recovery(self.db, apply=True)
        self.assertEqual(result["links_added"], 0)
        self.assertEqual(self.db.get(CaseProvenanceReview, "case-a").reason, "author_mismatch_or_missing")
        self.assertIsNone(reference(self.db.get(Case, "case-a").internal_notes, "Comment ID"))


if __name__ == "__main__": unittest.main()
