"""Synthetic fixtures are isolated in SQLite; production cases are never modified."""
import json
import unittest
from types import SimpleNamespace as Record

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_provenance import CaseProvenanceReview
from app.models.meta_post import MetaPost
from app.services.case_conflict_review import compare_conflicts, run_conflict_review
from app.services.provenance_recovery import BATCH, run_recovery


def fixture():
    values = dict(content="Isolated fixture", author="Fixture author", date_time="2026-11-24T12:00:00Z",
                  internal_notes="[Post ID]: post-1", status="Pendiente")
    first = Record(id="case-a", **values)
    second = Record(id="case-b", **{**values, "internal_notes": values["internal_notes"] + "\n[Comment ID]: comment-1"})
    raw = dict(id="comment-1", message=values["content"], author=values["author"], published_at=values["date_time"])
    post = Record(id="post-1", raw_comments_json=json.dumps([raw]))
    review = Record(case_id="case-a", evidence_json={"post_id": "post-1", "comment_id": "comment-1"})
    return first, second, post, review


class ConflictComparisonTests(unittest.TestCase):
    def compare(self, change=None):
        a, b, post, review = fixture()
        if change:
            change(a, b, post, review)
        return compare_conflicts([a, b], [post], [], [review])[0]

    def test_same_source_is_not_permission_to_merge(self):
        result = self.compare()
        self.assertEqual(result["classification"], "same_source_same_case_data")
        self.assertEqual(result["related_case_ids"], ["case-b"])
        self.assertEqual(result["action"], "manual_review_no_merge")

    def test_classification_and_emotion_differences_are_recorded(self):
        result = self.compare(lambda a, b, p, r: setattr(b, "sentiment", "Different classification"))
        self.assertEqual(result["classification"], "same_source_metadata_differs")
        self.assertIn("sentiment", result["differences"]["case-b"])

    def test_attention_in_either_case_is_highlighted(self):
        for name, value in (("status", "En Gestión"), ("assigned_to", "Fixture operator"),
                            ("public_response", "Internal draft"), ("resolution_note", "Fixture solution"),
                            ("institutional_radicado", "Fixture reference")):
            for target in (0, 1):
                def change(a, b, p, r):
                    setattr((a, b)[target], name, value)
                result = self.compare(change)
                self.assertEqual(result["classification"], "same_source_attention_recorded")
                self.assertEqual(result["attention_case_ids"], ["case-a" if target == 0 else "case-b"])

    def test_author_text_time_post_or_capture_mismatch_is_not_verified(self):
        for field, value in (("author", "Another author"), ("content", "Another text"),
                             ("date_time", "Another date"), ("internal_notes", "[Post ID]: other-post\n[Comment ID]: comment-1")):
            result = self.compare(lambda a, b, p, r: setattr(b, field, value))
            self.assertEqual(result["classification"], "insufficient_evidence")
        result = self.compare(lambda a, b, p, r: setattr(p, "raw_comments_json", "invalid json"))
        self.assertEqual(result["classification"], "insufficient_evidence")

    def test_missing_owner_is_not_verified(self):
        a, b, post, review = fixture()
        self.assertEqual(compare_conflicts([a], [post], [], [review])[0]["classification"], "insufficient_evidence")

    def test_structured_claim_and_multiple_owners(self):
        a, b, post, review = fixture()
        b.internal_notes = a.internal_notes
        link = Record(post_id="post-1", comment_id="comment-1", case_id=b.id)
        self.assertEqual(compare_conflicts([a, b], [post], [link], [review])[0]["related_case_ids"], [b.id])
        third = Record(**{**vars(b), "id": "case-c"})
        links = [link, Record(post_id=link.post_id, comment_id=link.comment_id, case_id=third.id)]
        self.assertEqual(compare_conflicts([a, b, third], [post], links, [review])[0]["classification"], "same_source_multiple_cases")


class ConflictPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        a, b, post, review = fixture()
        for data in (a, b):
            self.db.add(Case(**vars(data), source="Facebook", title="Fixture title", category="Fixture category",
                             sentiment="Fixture sentiment", priority="Media", location="Fixture location"))
        self.db.add(MetaPost(id=post.id, raw_comments_json=post.raw_comments_json, title="Fixture post", published_at="Fixture date"))
        self.db.add(CaseProvenanceReview(case_id=a.id, batch=BATCH, status="needs_review",
                    reason="comment_linked_to_other_case", evidence_json={**review.evidence_json, "original_evidence": "preserve"}, reviewed_by="original-reviewer"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def snapshot(self):
        return [{column.name: getattr(case, column.name) for column in Case.__table__.columns}
                for case in self.db.query(Case).order_by(Case.id)]

    def test_preview_is_read_only_and_expected_count_guard_writes_nothing(self):
        run_conflict_review(self.db)
        with self.assertRaises(ValueError):
            run_conflict_review(self.db, apply=True, expected_count=2)
        self.assertNotIn("conflict_review", self.db.get(CaseProvenanceReview, "case-a").evidence_json)

    def test_save_is_idempotent_and_changes_no_cases_links_or_review_decision(self):
        before = self.snapshot()
        result = run_conflict_review(self.db, apply=True, expected_count=1)
        self.assertEqual(result["saved"], 1)
        self.db.expire_all()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.db.query(CaseComment).count(), 0)
        review = self.db.get(CaseProvenanceReview, "case-a")
        self.assertEqual((review.status, review.reason, review.reviewed_by),
                         ("needs_review", "comment_linked_to_other_case", "original-reviewer"))
        self.assertEqual(review.evidence_json["original_evidence"], "preserve")
        self.assertEqual(run_conflict_review(self.db, apply=True)["saved"], 0)
        self.db.get(Case, "case-b").assigned_to = "Fixture operator"
        self.db.commit()
        self.assertEqual(run_conflict_review(self.db, apply=True)["saved"], 1)
        self.assertEqual(review.evidence_json["conflict_review"]["classification"], "same_source_attention_recorded")

    def test_recovery_rerun_preserves_dated_comparison(self):
        run_conflict_review(self.db, apply=True)
        before = self.db.get(CaseProvenanceReview, "case-a").evidence_json["conflict_review"]
        run_recovery(self.db, apply=True)
        self.assertEqual(self.db.get(CaseProvenanceReview, "case-a").evidence_json["conflict_review"], before)


if __name__ == "__main__":
    unittest.main()
