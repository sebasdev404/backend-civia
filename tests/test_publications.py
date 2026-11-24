"""Pruebas aisladas sin datos reales, sin peticiones a Meta ni llamadas a IA."""
import json
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.v1.auth import get_current_user
from app.api.v1.publications import router
from app.api.v1.meta import router as meta_router
from app.core.database import Base, get_db
from app.models.meta_post import MetaPost
from app.models.publication import PublicationSource, ObservedPost, PublicationSnapshot, MetaSyncJob
from app.services import publications, meta_sync_jobs
from app.services.automation_signals import comment_signals
from app.services.facebook_graph import GraphAPIError


class PublicationsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        publications.ensure_sources(self.db)
        self.db.add(MetaPost(id="own", title="Publicación de Johan", message="Contenido original", source="Facebook", published_at="hoy",
                             created_time="2026-11-13", total_comments=12, likes_count=0,
                             raw_comments_json=json.dumps([
                                 {"id": "a", "author": "Nombre entregado", "author_id": "user1", "author_is_protected": False, "content": "Comentario original", "likes_count": 0},
                                 {"id": "b", "author": "Perfil protegido", "content": "Johan solo critica"},
                                 {"id": "c", "content": "Estoy de acuerdo", "parent_id": "a"} ])))
        self.db.add(ObservedPost(id="external", source_id="jorge-gechem", title="Otra fuente", created_time="2026-11-12", raw_comments_json="[]"))
        self.db.commit()
        app = FastAPI(); app.include_router(router); app.include_router(meta_router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="test")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def test_sources_are_idempotent_and_external_posts_do_not_enter_johan(self):
        publications.ensure_sources(self.db)
        self.assertEqual(self.db.query(PublicationSource).count(), 2)
        own = self.client.get("/publications", params={"source_id": "johan"}).json()
        external = self.client.get("/publications", params={"source_id": "jorge-gechem"}).json()
        self.assertEqual([p["id"] for p in own["items"]], ["own"])
        self.assertEqual([p["id"] for p in external["items"]], ["external"])
        self.assertEqual(self.client.get("/publications/johan/external").status_code, 404)

    def test_missing_metrics_are_null_and_confirmed_zero_stays_zero(self):
        item = self.client.get("/publications").json()["items"][0]
        self.assertIsNone(item["likes_count"])
        self.db.add(PublicationSnapshot(post_id="own", likes_count=0, reactions_count=8, status="available")); self.db.commit()
        item = self.client.get("/publications").json()["items"][0]
        self.assertEqual(item["likes_count"], 0)
        self.assertEqual(item["reactions_count"], 8)
        self.assertIsNone(item["shares_count"])

    def test_comments_are_paginated_with_exact_returned_names_and_parent(self):
        first = self.client.get("/publications/johan/own", params={"limit": 1}).json()
        last = self.client.get("/publications/johan/own", params={"limit": 1, "offset": 2}).json()
        self.assertEqual(first["comments"][0]["author"], "Nombre entregado")
        self.assertEqual(first["comments"][0]["likes_count"], 0)
        self.assertEqual(last["comments"][0]["parent_content"], "Comentario original")
        self.assertEqual(first["captured_comments"], 3)
        self.assertEqual(first["comments_total"], 3)
        self.assertFalse(last["comments_has_more"])
        self.assertEqual(self.client.get("/publications/johan/own", params={"search": "solo critica"}).json()["comments_total"], 1)

    def test_names_and_negative_opinions_are_not_bot_evidence(self):
        data = self.client.get("/publications/johan/own").json()
        self.assertTrue(all(r["automation"]["status"] == "insufficient_data" for r in data["comments"]))
        self.assertEqual(self.client.get("/publications/johan/own", params={"signals_only": "true"}).json()["comments_total"], 0)
        rows = [{"id": str(i), "author": "Mismo nombre", "content": "Mensaje diferente " + str(i)} for i in range(20)]
        self.assertTrue(all(not r["signals"] for r in comment_signals(rows).values()))

    def test_repeated_text_is_only_a_review_signal(self):
        rows = [{"id": str(i), "content": "Este texto es idéntico en varios comentarios"} for i in range(3)]
        signals = comment_signals(rows)
        self.assertTrue(all(value["status"] == "review" for value in signals.values()))
        self.assertTrue(all("no confirman" in value["explanation"] for value in signals.values()))

    def test_profile_permission_rejection_is_visible_and_keeps_previous_capture(self):
        with patch.object(publications, "graph_get", side_effect=GraphAPIError({"code": 10})):
            result = publications.sync_external(self.db, "jorge-gechem", lambda **kw: None)
        source = self.db.get(PublicationSource, "jorge-gechem")
        self.assertEqual(source.status, "missing_permissions")
        self.assertIn("10", source.detail)
        self.assertEqual(result["posts_updated"], 0)
        self.assertIsNotNone(self.db.get(ObservedPost, "external"))

    def test_wrong_identity_is_not_imported(self):
        with patch.object(publications, "graph_get", return_value={"id": "wrong", "name": "Otra persona"}) as remote:
            publications.sync_external(self.db, "jorge-gechem", lambda **kw: None)
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(self.db.get(PublicationSource, "jorge-gechem").status, "identity_mismatch")

    def test_empty_reaction_identities_do_not_erase_reaction_counts(self):
        def counts(node, token, **params):
            return {"summary": {"total_count": 12 if params.get("type") == "LIKE" else 20}} if node.endswith('/reactions') else {"shares": {"count": 3}}
        with patch.object(publications, "graph_get", side_effect=counts), patch.object(publications, "iter_connection", return_value=iter([{"data": []}])):
            publications.capture_metrics(self.db, "own", "test-token", identities=True)
        data = self.client.get("/publications/johan/own").json()
        self.assertEqual(data["reactions_count"], 20)
        self.assertEqual(data["likes_count"], 12)
        self.assertEqual(data["reaction_people"], [])

    def test_confirmed_zero_views_are_preserved_in_capture(self):
        from app.services.meta_posts import post_metric_values
        def metrics(node, token, **params):
            if node.endswith('/insights'):
                return {'data': [{'name': 'post_media_view', 'values': [{'value': 0}]}]}
            if node.endswith('/reactions'):
                return {'summary': {'total_count': 40}}
            return {'shares': {'count': 1}}
        with patch.object(publications, 'graph_get', side_effect=metrics):
            publications.capture_metrics(self.db, 'own', 'test')
        result = post_metric_values(self.db.get(MetaPost, 'own'), self.db.get(PublicationSnapshot, 'own'))
        self.assertEqual(result['views_count'], 0)
        self.assertEqual(result['views_status'], 'available')

    def test_empty_insights_are_unavailable_and_keep_last_view_capture(self):
        from app.services.meta_posts import post_metric_values
        self.db.add(PublicationSnapshot(post_id='own', reactions_json=json.dumps({'views': {'count': 27}})))
        self.db.commit()
        def metrics(node, token, **params):
            return {'data': []} if node.endswith('/insights') else {'summary': {'total_count': 40}}
        with patch.object(publications, 'graph_get', side_effect=metrics):
            publications.capture_metrics(self.db, 'own', 'test')
        result = post_metric_values(self.db.get(MetaPost, 'own'), self.db.get(PublicationSnapshot, 'own'))
        self.assertEqual(result['views_count'], 27)
        self.assertEqual(result['views_status'], 'unavailable')

    def test_metrics_permission_failure_preserves_previous_counts(self):
        self.db.add(PublicationSnapshot(post_id="own", likes_count=9, status="available")); self.db.commit()
        with patch.object(publications, "graph_get", side_effect=GraphAPIError({"code": 200})), patch.object(publications, "iter_connection", side_effect=GraphAPIError({"code": 200})):
            publications.capture_metrics(self.db, "own", "test-token", identities=True)
        data = self.client.get("/publications/johan/own").json()
        self.assertEqual(data["likes_count"], 9)
        self.assertEqual(data["reaction_people_status"], "unavailable")

    def test_sync_acknowledges_immediately_and_deduplicates(self):
        with patch.object(meta_sync_jobs._executor, "submit") as worker:
            first = self.client.post("/meta/sync-live")
            second = self.client.post("/meta/sync-live")
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 202)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertTrue(second.json()["already_running"])
        worker.assert_called_once()
        self.assertEqual(self.client.get("/meta/sync-jobs/" + first.json()["id"]).json()["status"], "queued")

    def test_source_and_post_sync_are_separate_scopes(self):
        with patch.object(meta_sync_jobs._executor, "submit"):
            source = self.client.post("/publications/sources/jorge-gechem/sync").json()
            post = self.client.post("/publications/johan/own/refresh").json()
        self.assertEqual(source["scope"], "source:jorge-gechem")
        self.assertEqual(post["scope"], "post:johan:own")
        self.assertNotEqual(source["id"], post["id"])

    def test_restart_recovers_interrupted_jobs(self):
        with patch.object(meta_sync_jobs._executor, "submit"):
            job = meta_sync_jobs.start_job(self.db)
        meta_sync_jobs.recover_jobs(self.db)
        row = self.db.get(MetaSyncJob, job["id"])
        self.assertEqual(row.status, "interrupted")
        self.assertIsNone(row.active_key)

    def test_fast_capture_does_not_call_ai_or_wait_for_cover_downloads(self):
        with patch('sync_live_service.sync_facebook_live_posts') as facebook, patch('sync_live_service.sync_instagram_publications') as instagram:
            result = meta_sync_jobs._connected_sync(self.db, lambda **value: None)
        self.assertFalse(facebook.call_args.kwargs["classify_cases"])
        self.assertFalse(facebook.call_args.kwargs["analyze_comments"])
        self.assertFalse(facebook.call_args.kwargs["cache_covers"])
        self.assertFalse(instagram.call_args.kwargs["cache_covers"])
        self.assertEqual(facebook.call_args.kwargs["max_posts"], 12)
        self.assertTrue(result["analysis_deferred"])

    def test_invalid_requests_and_authentication(self):
        self.assertEqual(self.client.get('/publications',params={"limit": 0}).status_code,422)
        self.assertEqual(self.client.get('/publications',params={"source_id":"unknown"}).status_code,404)
        self.assertEqual(self.client.post('/publications/johan/unknown/refresh').status_code,404)
        app = FastAPI(); app.include_router(router); app.include_router(meta_router)
        app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(app) as client:
            self.assertEqual(client.get('/publications').status_code,401)
            self.assertEqual(client.post('/meta/sync-live').status_code,401)

    def test_csv_exports_only_captured_comments_and_escapes_spreadsheet_formulas(self):
        rows = publications.parse_rows(self.db.get(MetaPost, "own").raw_comments_json)
        rows[0]["author"] = "=FAKEFORMULA()"
        self.db.get(MetaPost, "own").raw_comments_json = json.dumps(rows)
        self.db.commit()
        response = self.client.get('/publications/johan/own/comments.csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=FAKEFORMULA()", response.text)
        self.assertIn("Comentario original", response.text)
        self.assertNotIn("Otra fuente", response.text)

    def test_bot_endpoint_does_not_assign_probability_from_criticism_or_missing_metadata(self):
        from app.services.ai_classifier import AIClassifierService
        classifier = AIClassifierService.__new__(AIClassifierService)
        response = classifier.detect_bot("Corruptos, no hacen nada, se roban la plata", {})
        self.assertIsNone(response["is_bot"])
        self.assertIsNone(response["bot_probability"])
        self.assertFalse(response["probability_available"])
        self.assertEqual(response["status"], "insufficient_data")

    def test_console_encoding_does_not_rollback_created_case(self):
        from app.models.case import Case
        from sync_live_service import sync_facebook_live_posts
        def legacy_console(*values, **kwargs):
            ' '.join(str(value) for value in values).encode('cp1252')
        remote = {"id": "safe-post", "message": "Reporte", "created_time": "2026-11-13T10:00:00+0000"}
        comments = [{"id": "safe-comment", "message": "Necesitamos reparar esta calle", "from": {"id": "u", "name": "Nombre \U0001f512"}}]
        with patch('sync_live_service.iter_connection', return_value=iter([{"data": [remote]}])), \
             patch('sync_live_service.read_post_comments', return_value=(comments, 1)), \
             patch('sync_live_service.download_and_cache_cover', return_value=None), \
             patch('sync_live_service.ai_classifier.classify_comment', return_value={"category": "General"}), \
             patch('sync_live_service.settings.META_PAGE_ACCESS_TOKEN', 'test_token_for_local_unit_tests'), \
             patch('builtins.print', side_effect=legacy_console):
            sync_facebook_live_posts(self.db, max_posts=1, analyze_comments=False)
        self.assertEqual(self.db.query(Case).count(), 1)
        self.assertIsNotNone(self.db.get(MetaPost, 'safe-post'))


if __name__ == '__main__':
    unittest.main()
