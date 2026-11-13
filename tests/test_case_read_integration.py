"""Read-only tests against real synchronized cases, without creating sample data."""
import re
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import desc, event, text

from app.api.v1.cases import router
from app.api.v1.meta import router as meta_router
from app.core.database import SessionLocal, get_db
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.services.post_images import real_image_url


class CaseReadIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.include_router(meta_router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.rollback()
        self.db.close()

    def page(self, **params):
        response = self.client.get("/api/v1/cases", params={"paginated": True, "limit": 24, **params})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_stable_pagination_and_real_total(self):
        first = self.page()
        second = self.page(skip=24)
        ordered = self.db.query(Case).order_by(desc(Case.created_at), desc(Case.id))
        self.assertEqual(first["total"], ordered.count())
        self.assertEqual([c["id"] for c in first["items"]], [c.id for c in ordered.limit(24)])
        self.assertEqual([c["id"] for c in second["items"]], [c.id for c in ordered.offset(24).limit(24)])
        self.assertTrue(set(c["id"] for c in first["items"]).isdisjoint(c["id"] for c in second["items"]))
        self.assertFalse(self.page(skip=first["total"])["has_more"])

    def test_summaries_are_bounded_and_do_not_load_heavy_fields(self):
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.db.bind, "before_cursor_execute", capture)
        try:
            result = self.page()
        finally:
            event.remove(self.db.bind, "before_cursor_execute", capture)
        self.assertLessEqual(len(statements), 2)
        self.assertFalse(any("meta_posts.raw_comments_json AS" in sql for sql in statements))
        self.assertFalse(any("cases.internal_notes AS" in sql for sql in statements))
        for item in result["items"]:
            self.assertNotIn("internal_notes", item)
            self.assertLessEqual(len(item["content"]), 600)
        self.assertLessEqual(len(self.page(limit=1000)["items"]), 100)

    def test_database_search_filters_beyond_first_page(self):
        case = self.db.query(Case).order_by(Case.created_at, Case.id).first()
        if not case:
            self.skipTest("No hay casos sincronizados")
        result = self.page(search=case.id, priority=case.priority, category=case.category,
                           source=case.source, status=case.status)
        self.assertIn(case.id, [c["id"] for c in result["items"]])
        if case.assigned_department:
            self.assertIn(case.id, [c["id"] for c in self.page(search=case.id, department=case.assigned_department)["items"]])
        priority_only = self.page(priority_only=True)
        self.assertTrue(all(c["priority_action"] for c in priority_only["items"]))
        self.assertEqual(priority_only["total"], self.db.query(Case).filter(Case.priority_action.is_(True)).count())

    def test_generic_covers_never_return_as_source_images(self):
        for offset in range(0, self.db.query(Case).count(), 100):
            for item in self.page(skip=offset, limit=100)["items"]:
                self.assertEqual(item["image_url"], real_image_url(item["image_url"]))
                self.assertNotIn("default_cover", item["image_url"] or "")
                if item["thumbnail_url"]:
                    self.assertIn("/" + item["post_id"] + "?", item["thumbnail_url"])
                self.assertEqual(item["media_available"], bool(item["image_url"]))

    def test_known_orphans_do_not_borrow_another_publication(self):
        for case_id in ("CIV-2026-2666", "CIV-2026-2667", "CIV-2026-2662"):
            case = self.db.get(Case, case_id)
            if not case:
                continue
            match = re.search(r"\[Post ID\]:\s*([^\s\n]+)", case.internal_notes or "")
            pid = match.group(1) if match else None
            detail = self.client.get("/api/v1/cases/" + case_id).json()
            if detail["post_data"]:
                self.assertEqual(detail["post_data"]["id"], pid)
            elif pid:
                self.assertIsNone(self.db.get(MetaPost, pid))
            self.assertNotIn("default_cover", detail["image_url"] or "")
            if case_id in ("CIV-2026-2666", "CIV-2026-2667"):
                self.assertIsNone(detail["image_url"])

    def test_missing_case_and_image_return_404(self):
        self.assertEqual(self.client.get("/api/v1/cases/no-existing-case").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/meta/post-image/no-existing-post").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/meta/post-image/default_cover").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/meta/post-thumbnail/default_cover").status_code, 404)

    def test_legacy_list_remains_available(self):
        response = self.client.get("/api/v1/cases?limit=15")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        self.assertLessEqual(len(response.json()), 15)

    def test_invalid_page_is_rejected(self):
        for query in ("limit=0", "skip=-1", "limit=1001"):
            self.assertEqual(self.client.get("/api/v1/cases?paginated=true&" + query).status_code, 422)


if __name__ == "__main__":
    unittest.main()
