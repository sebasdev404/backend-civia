"""Pruebas aisladas: no escriben datos reales ni consumen llamadas a IA."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import get_current_user
from app.api.v1.conversation import router
from app.core.database import Base, get_db
from app.models.meta_post import MetaPost
from app.models.conversation import PostContext, CommentAnalysis
from app.services import conversation as svc
from app.services.ai_classifier import AIClassifierService


def result(stance="support", **extra):
    return {"stance": stance, "emotion": "Enojo o ira", "target": "Problema de la ciudad",
            "topic": "Seguridad", "narrative": "agreement", "explanation": "Respalda la denuncia de robos.",
            "confidence": 0.94, "needs_review": False, **extra}


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.post = MetaPost(id="FB_1", title="Denuncia de inseguridad", message="Johan denuncia los robos de Neiva.",
                             source="Facebook", media_type="video", published_at="13 Nov 2026", month_key="2026-11",
                             created_time="2026-11-13", total_comments=20,
                             raw_comments_json=json.dumps([
                                 {"id": "c1", "content": "Sí, es verdad, las ratas de este pueblo solamente roban"},
                                 {"id": "c2", "content": "Johan solamente critica, no propone nada"},
                                 {"id": "c3", "content": "Exacto", "parent_id": "c1"}]))
        self.db.add(self.post)
        self.db.add(MetaPost(id="IG_1", title="Instagram", source="Instagram", published_at="hoy",
                            raw_comments_json='[{"id":"ig1","content":"Excelente"}]'))
        self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="tester")
        self.client = TestClient(app)
        self.ai = patch.object(svc.ai_classifier, "client", MagicMock()).start()

    def tearDown(self):
        patch.stopall()
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def context(self):
        return self.client.put("/conversation/posts/FB_1/context", json={"summary": "Johan denuncia los robos y pide medidas de seguridad."})

    def analyze(self, results=None):
        results = results or {"c1": result(), "c2": result("criticism", target="Johan", narrative="only_criticizes"),
                              "c3": result("neutral", emotion="Neutral", narrative="other")}
        with patch.object(svc, "classify_batch", return_value=results) as model:
            response = self.client.post("/conversation/analyze", params={"post_id": "FB_1"})
        return response, model

    def test_video_caption_does_not_substitute_for_video_content(self):
        response, model = self.analyze()
        self.assertEqual(response.json()["processed"], 0)
        model.assert_not_called()
        data = self.client.get("/conversation").json()
        self.assertEqual(data["summary"]["captured"], 3)
        self.assertEqual(data["summary"]["review"], 3)
        self.assertEqual(data["summary"]["stances"], {})

    def test_anger_in_support_is_not_criticism_and_parent_is_supplied(self):
        self.assertEqual(self.context().status_code, 200)
        response, model = self.analyze()
        self.assertEqual(response.json()["processed"], 3)
        self.assertIn("las ratas", model.call_args.args[1][2]["parent"])
        data = self.client.get("/conversation").json()
        self.assertEqual(data["summary"]["stances"], {"support": 1, "criticism": 1, "neutral": 1})
        self.assertEqual(data["summary"]["anger_in_support"], 1)
        self.assertEqual(data["summary"]["reported"], 20)
        self.assertTrue(any(t["narrative"] == "only_criticizes" for t in data["themes"]))

    def test_context_update_invalidates_existing_results(self):
        self.context(); self.analyze()
        self.client.put("/conversation/posts/FB_1/context", json={"transcript": "Ahora Johan habla de otro problema."})
        data = self.client.get("/conversation").json()
        self.assertEqual(data["summary"]["pending"], 3)
        self.assertEqual(data["summary"]["stances"], {})

    def test_comment_and_parent_edits_invalidate_affected_analysis(self):
        self.context(); self.analyze()
        comments = svc.captured_comments(self.post)
        comments[0]["content"] = "Ya no estoy de acuerdo"
        self.post.raw_comments_json = json.dumps(comments)
        self.db.commit()
        data = self.client.get("/conversation").json()
        self.assertEqual(data["summary"]["pending"], 2)
        self.assertEqual(data["summary"]["stances"], {"criticism": 1})

    def test_retry_is_idempotent_and_meta_refresh_preserves_analysis(self):
        self.context(); self.analyze()
        comments = svc.captured_comments(self.post)
        self.post.raw_comments_json = json.dumps(comments + [comments[0]])
        self.db.commit()
        response, model = self.analyze()
        model.assert_not_called()
        self.assertEqual(response.json()["processed"], 0)
        self.assertEqual(self.db.query(CommentAnalysis).count(), 3)
        self.assertEqual(self.client.get("/conversation").json()["summary"]["captured"], 3)

    def test_filtered_pagination_and_themes_are_not_limited_to_current_page(self):
        self.context(); self.analyze()
        data = self.client.get("/conversation", params={"limit": 1, "offset": 1}).json()
        self.assertEqual(len(data["items"]), 1)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["summary"]["captured"], 3)
        filtered = self.client.get("/conversation", params={"stance": "criticism", "narrative": "only_criticizes"}).json()
        self.assertEqual([i["id"] for i in filtered["items"]], ["c2"])
        self.assertEqual(self.client.get("/conversation", params={"month": "2026-10"}).json()["total"], 0)

    def test_no_ai_and_failed_model_do_not_invent_classifications(self):
        self.context()
        with patch.object(svc.ai_classifier, "client", None):
            self.assertEqual(self.client.post("/conversation/analyze").json()["processed"], 0)
        with patch.object(svc, "classify_batch", side_effect=RuntimeError("offline")):
            response = self.client.post("/conversation/analyze")
        self.assertEqual(response.json()["processed"], 0)
        self.assertEqual(self.db.query(CommentAnalysis).count(), 0)

    def test_bad_inputs_and_instagram_context_are_rejected(self):
        for payload in ({}, {"summary": "  "}, {"summary": "x" * 6001}, {"transcript": "x" * 24001}):
            self.assertEqual(self.client.put("/conversation/posts/FB_1/context", json=payload).status_code, 422)
        self.assertEqual(self.client.get("/conversation/posts/IG_1/context").status_code, 404)
        for params in ({"limit": 0}, {"offset": -1}, {"stance": "negative"}):
            self.assertEqual(self.client.get("/conversation", params=params).status_code, 422)

    def test_transcript_and_image_caption_provide_explicit_context(self):
        self.assertEqual(self.client.put("/conversation/posts/FB_1/context", json={"transcript": "Johan: denuncio los robos."}).json()["source"], "transcript")
        self.assertTrue(svc.context_for(self.post, self.db.get(PostContext, "FB_1"))["ready"])
        self.post.media_type = "image"
        self.assertEqual(svc.context_for(self.post)["source"], "post_text")

    def test_review_results_are_excluded_from_favorable_and_critical_totals(self):
        self.context()
        values = {"c1": result(needs_review=True), "c2": result("mixed"), "c3": result("unclear", needs_review=True)}
        self.analyze(values)
        data = self.client.get("/conversation").json()
        self.assertEqual(data["summary"]["stances"], {"mixed": 1})
        self.assertEqual(data["summary"]["anger_in_support"], 0)
        self.assertEqual(self.client.get("/conversation", params={"stance": "review"}).json()["total"], 2)

    def test_model_output_validation_and_low_confidence_abstention(self):
        client = MagicMock()
        create = client.with_options.return_value.chat.completions.create
        def output(items):
            create.return_value.choices = [SimpleNamespace(message=SimpleNamespace(content=json.dumps({"items": items})))]
        comments = [{"id": "c1", "content": "Excelente…", "parent": None}]
        output([{ "id": "c1", **result(confidence=0.4)}])
        self.assertTrue(svc.classify_batch({}, comments, client)["c1"]["needs_review"])
        for items in ([], [{"id": "wrong", **result()}], [{"id": "c1", **result(stance="invented")}], [{"id": "c1", **result(confidence=2)}]):
            output(items)
            with self.assertRaises((ValueError, TypeError)):
                svc.classify_batch({}, comments, client)

    def test_authentication_is_required(self):
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(app) as client:
            self.assertEqual(client.get("/conversation").status_code, 401)
            self.assertEqual(client.post("/conversation/analyze").status_code, 401)
            self.assertEqual(client.put("/conversation/posts/FB_1/context", json={"summary": "abc"}).status_code, 401)

    def test_existing_institutional_classifier_receives_publication_context(self):
        classifier = AIClassifierService()
        classifier.client = MagicMock()
        classifier.client.chat.completions.create.return_value.choices = [SimpleNamespace(message=SimpleNamespace(content='{"sentiment":"Enojo o ira: Rabia"}'))]
        analysis = classifier.classify_comment("Sí, tiene razón", post_context="Johan denuncia robos")
        self.assertEqual(analysis["sentiment"], "Enojo o ira: Rabia")
        prompt = classifier.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("Johan denuncia robos", prompt)


if __name__ == "__main__":
    unittest.main()
