"""Pruebas de lectura sobre PostgreSQL real, sin crear datos.

Ejecutar desde backend-civia:
    python -m unittest discover -s tests -p test_meta_read_integration.py -v
"""

import unittest
import json
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import desc, text, event
from PIL import Image

from app.api.v1.meta import router
from app.core.database import SessionLocal, get_db
from app.models.meta_post import MetaPost


class MetaReadIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.ordered = self.db.query(MetaPost).order_by(desc(MetaPost.created_time), desc(MetaPost.id))

    def tearDown(self):
        self.client.close()
        self.db.rollback()
        self.db.close()

    def page(self, **params):
        response = self.client.get("/api/v1/meta/posts", params={"paginated": "true", **params})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_offset_total_and_stable_order(self):
        total = self.ordered.count()
        first = self.page(limit=3)
        second = self.page(limit=3, offset=3)
        self.assertEqual(first["total"], total)
        self.assertEqual(second["total"], total)
        self.assertEqual([p["id"] for p in first["items"]], [p.id for p in self.ordered.limit(3)])
        self.assertEqual([p["id"] for p in second["items"]], [p.id for p in self.ordered.offset(3).limit(3)])
        self.assertTrue(set(p["id"] for p in first["items"]).isdisjoint(p["id"] for p in second["items"]))
        self.assertEqual(second["has_more"], 3 + len(second["items"]) < total)

    def test_exhausted_page_is_empty(self):
        result = self.page(limit=3, offset=self.ordered.count() + 1)
        self.assertEqual(result["items"], [])
        self.assertFalse(result["has_more"])
        self.assertEqual(result["total"], self.ordered.count())

    def test_oldest_month_search_and_network_use_database(self):
        oldest = self.ordered.filter(MetaPost.month_key.is_not(None), MetaPost.source.is_not(None)).all()
        if not oldest:
            self.skipTest("No hay publicaciones reales sincronizadas")
        post = oldest[-1]
        term = post.title[:20]
        query = self.ordered.filter(
            MetaPost.month_key == post.month_key,
            MetaPost.source.ilike(f"%{post.source}%"),
            MetaPost.title.ilike(f"%{term}%") | MetaPost.message.ilike(f"%{term}%"),
        )
        result = self.page(limit=1, month=post.month_key, search=term, network=post.source)
        self.assertEqual(result["total"], query.count())
        self.assertEqual([p["id"] for p in result["items"]], [p.id for p in query.limit(1)])

    def test_legacy_array_and_real_metrics(self):
        response = self.client.get("/api/v1/meta/posts", params={"limit": 3})
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        for item in response.json():
            post = self.db.get(MetaPost, item["id"])
            for metric in ("likes_count", "views_count", "shares_count"):
                self.assertEqual(item[metric], getattr(post, metric) or 0)

    def test_invalid_pagination_is_rejected(self):
        for params in ({"offset": -1}, {"limit": 0}, {"limit": 2001}):
            response = self.client.get("/api/v1/meta/posts", params=params)
            self.assertEqual(response.status_code, 422)

    def test_light_summary_does_not_fetch_comment_payloads(self):
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.db.bind, "before_cursor_execute", capture)
        try:
            result = self.page(limit=24, include_details="false")
        finally:
            event.remove(self.db.bind, "before_cursor_execute", capture)
        self.assertFalse(any("meta_posts.raw_comments_json AS meta_posts_raw_comments_json" in sql for sql in statements))
        self.assertFalse(any("cases.content AS" in sql for sql in statements))
        for item in result["items"]:
            self.assertNotIn("raw_comments", item)
            self.assertNotIn("cases", item)
            self.assertLessEqual(len(item["message"] or ""), 360)
        for item in result["items"][:3]:
            detail = self.client.get(f"/api/v1/meta/posts/{item['id']}")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(item["cases_count"], detail.json()["cases_count"])
            self.assertEqual(item["total_comments"], detail.json()["total_comments"])

    def test_detail_preserves_full_real_comments(self):
        post = self.ordered.first()
        if post is None:
            self.skipTest("No hay publicaciones sincronizadas")
        response = self.client.get(f"/api/v1/meta/posts/{post.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], post.message)
        self.assertEqual(response.json()["raw_comments"], json.loads(post.raw_comments_json or "[]"))
        self.assertEqual(self.client.get("/api/v1/meta/posts/post-inexistente").status_code, 404)

    def test_light_pages_preserve_network_and_order(self):
        expected = self.ordered.filter(MetaPost.source.ilike("%Instagram%"))
        first = self.page(limit=24, network="Instagram", include_details="false")
        second = self.page(limit=24, offset=24, network="Instagram", include_details="false")
        self.assertEqual(first["total"], expected.count())
        self.assertEqual([p["id"] for p in first["items"]], [p.id for p in expected.limit(24)])
        self.assertEqual([p["id"] for p in second["items"]], [p.id for p in expected.offset(24).limit(24)])

    def test_cases_only_filter_uses_all_history_before_pagination(self):
        result = self.page(limit=24, cases_only="true", include_details="false")
        self.assertTrue(all(post["cases_count"] > 0 for post in result["items"]))
        self.assertEqual(result["has_more"], len(result["items"]) < result["total"])
        if result["items"]:
            post = result["items"][-1]
            exact = self.page(limit=1, cases_only="true", search=post["title"][:20], month=post["month_key"], include_details="false")
            self.assertGreater(exact["total"], 0)

    def test_thumbnail_is_smaller_and_reused(self):
        source = None
        post = None
        for candidate in self.ordered.limit(50):
            file = Path("static/covers") / f"{candidate.id}.jpg"
            if file.is_file() and file.stat().st_size > 100000:
                source, post = file, candidate
                break
        if source is None:
            self.skipTest("No hay portadas reales disponibles para comprobar la miniatura")
        response = self.client.get(f"/api/v1/meta/post-thumbnail/{post.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        with Image.open(BytesIO(response.content)) as image:
            image.verify()
        self.assertLess(len(response.content), source.stat().st_size)
        cached = Path("static/thumbnails") / f"{post.id}.jpg"
        stamp = cached.stat().st_mtime_ns
        repeated = self.client.get(f"/api/v1/meta/post-thumbnail/{post.id}")
        self.assertEqual(repeated.content, response.content)
        self.assertEqual(cached.stat().st_mtime_ns, stamp)

    def test_instagram_reports_actual_connection_and_does_not_seed_posts(self):
        from sync_live_service import sync_instagram_publications
        response = self.client.get("/api/v1/meta/instagram/status")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn(result["status"], ("ready", "not_connected", "not_configured", "missing_permissions", "error"))
        self.assertIsInstance(result["missing_permissions"], list)
        if result["status"] == "ready":
            from app.core.config import settings
            from app.services.facebook_graph import graph_get
            self.assertTrue(result["account_id"])
            self.assertTrue(result["username"])
            media = graph_get(f"{result['account_id']}/media", settings.META_PAGE_ACCESS_TOKEN, fields="id,permalink", limit=1).get("data", [])
            if media:
                stored = self.db.get(MetaPost, f"IG_{media[0]['id']}")
                self.assertIsNotNone(stored, "La publicación real más reciente debe estar sincronizada")
                self.assertEqual(stored.source, "Instagram")
                self.assertEqual(stored.permalink_url, media[0].get("permalink"))
            return
        stats = {}
        # La transacción READ ONLY detecta cualquier intento de crear datos sin conexión.
        count = sync_instagram_publications(self.db, stats=stats)
        self.assertEqual(count, 0)
        self.assertEqual(stats["posts_updated"], 0)
        self.assertEqual(stats["new_comments_captured"], 0)

    def test_case_author_metadata_matches_exact_comment(self):
        checked = 0
        for post in self.page(limit=300)["items"]:
            comments = {comment.get("id"): comment for comment in post["raw_comments"]}
            for case in post["cases"]:
                comment = comments.get(case.get("comment_id"))
                if not comment or "author_is_protected" not in comment:
                    continue
                checked += 1
                self.assertEqual(case["author"], comment["author"])
                self.assertEqual(case["author_picture_url"], comment.get("author_picture_url"))
                self.assertEqual(case["author_is_protected"], comment["author_is_protected"])
                self.assertEqual(case["comment_permalink_url"], comment.get("permalink_url"))
        if not checked:
            self.skipTest("No hay casos con metadatos de autor sincronizados")


if __name__ == "__main__":
    unittest.main()
