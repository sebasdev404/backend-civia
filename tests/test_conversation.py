"""Pruebas aisladas: no escriben datos reales ni consumen llamadas a IA."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import get_current_user
from app.api.v1.conversation import router
from app.core.database import Base, get_db
from app.models.meta_post import MetaPost
from app.models.conversation import PostContext, CommentAnalysis
from app.models.publication import MetaSyncJob
from app.services import conversation as svc
from app.services import meta_sync_jobs as jobs
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
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="tester", full_name='Fixture reviewer')
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
        self.assertEqual(response.json()["processed"], 3)
        self.assertFalse(model.call_args.args[0]['ready'])
        self.assertEqual(model.call_args.args[0]['transcript'], '')
        self.assertEqual(model.call_args.args[0]['source'], 'missing')
        data = self.client.get("/conversation").json()
        self.assertEqual(data["summary"]["captured"], 3)
        self.assertEqual(data["summary"]["review"], 0)
        self.assertEqual(data["summary"]["pending_with_context"], 0)
        self.assertEqual(data["summary"]["stances"], {'support': 1, 'criticism': 1, 'neutral': 1})

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

    def test_automatic_queue_processes_existing_comments_in_bounded_batches(self):
        comments = svc.captured_comments(self.post)
        comments.extend({"id": f"fixture-{index}", "content": "Comentario de prueba"} for index in range(20))
        self.post.raw_comments_json = json.dumps(comments)
        self.db.commit()

        def classify(context, batch, client):
            return {comment["id"]: result() for comment in batch}

        with patch.object(jobs.settings, "AUTO_ANALYZE_ENABLED", True), \
             patch.object(jobs, "SessionLocal", sessionmaker(bind=self.engine)), \
             patch.object(jobs._executor, "submit", side_effect=lambda run, *args: run(*args)), \
             patch.object(svc, "classify_batch", side_effect=classify) as provider:
            data = self.client.get("/conversation").json()
            self.assertTrue(data["automatic_analysis"])
            self.assertEqual(data["summary"]["pending_with_context"], 0)
            self.assertEqual(data["summary"]["pending_eligible"], 23)

            with patch.object(jobs.settings, "AUTO_ANALYZE_ENABLED", False):
                jobs.queue_pending_analysis(self.db)
                provider.assert_not_called()

            jobs.queue_pending_analysis(self.db)
            self.assertEqual(self.db.query(CommentAnalysis).count(), 20)
            self.assertEqual(provider.call_count, 4)
            self.assertEqual(self.client.get("/conversation").json()["analysis_status"], "success")

            jobs.queue_pending_analysis(self.db)
            self.assertEqual(self.db.query(CommentAnalysis).count(), 23)
            jobs.queue_pending_analysis(self.db)
            self.assertEqual(provider.call_count, 5)
            self.assertEqual(self.db.query(MetaSyncJob).count(), 2)

    def test_complete_analysis_processes_more_than_twenty_without_video_transcript(self):
        from datetime import datetime, timezone
        self.post.raw_comments_json = json.dumps([{'id': f'full-{index}', 'content': 'Excelente Johan, siga así.'} for index in range(37)])
        self.db.commit()
        def classify(context, comments, client):
            self.assertFalse(context['ready'])
            return {comment['id']: result() for comment in comments}
        with patch.object(svc, 'classify_batch', side_effect=classify) as provider:
            values = svc.analyze_all(self.db, review_before=datetime.now(timezone.utc))
        self.assertEqual(values['processed'], 37)
        self.assertEqual(values['total'], 37)
        self.assertEqual(provider.call_count, 4)
        self.assertEqual(self.db.query(CommentAnalysis).count(), 37)

    def test_complete_analysis_retries_review_without_recharging_clear_results(self):
        from datetime import datetime, timezone
        values = {'c1': result(), 'c2': result('unclear', needs_review=True), 'c3': result('neutral')}
        self.analyze(values)
        with patch.object(svc, 'classify_batch', return_value={'c2': result('criticism')}) as provider:
            outcome = svc.analyze_all(self.db, include_review=True, review_before=datetime.now(timezone.utc))
        self.assertEqual(outcome['processed'], 1)
        self.assertEqual([row['id'] for row in provider.call_args.args[1]], ['c2'])
        self.assertEqual(self.client.get('/conversation').json()['summary']['uncertain'], 0)

    def test_cancel_and_resume_do_not_repeat_uncertain_results_from_saved_batches(self):
        from datetime import datetime, timezone
        started = datetime.now(timezone.utc)
        self.post.raw_comments_json = json.dumps([{'id': f'resume-{index}', 'content': 'Eso.'} for index in range(25)])
        self.db.commit()
        def uncertain(context, comments, client):
            return {comment['id']: result('unclear', needs_review=True) for comment in comments}
        with patch.object(svc, 'classify_batch', side_effect=uncertain) as provider:
            first = svc.analyze_all(self.db, review_before=started, should_cancel=lambda: provider.call_count > 0)
            self.assertEqual(first['status'], 'cancelled')
            self.assertEqual(first['completed'], 12)
            second = svc.analyze_all(self.db, review_before=started, previous=first)
        self.assertEqual(second['completed'], 25)
        self.assertEqual(second['uncertain'], 25)
        self.assertEqual(provider.call_count, 3)
        self.assertEqual(self.db.query(CommentAnalysis).count(), 25)

    def test_complete_jobs_are_deduplicated_persisted_and_cancellable(self):
        with patch.object(jobs._executor, 'submit') as executor:
            first = self.client.post('/conversation/analysis-jobs', json={'month': '2026-11'})
            self.assertEqual(first.status_code, 202, first.text)
            duplicate = self.client.post('/conversation/analysis-jobs', json={'month': '2026-11'})
            self.assertEqual(duplicate.json()['id'], first.json()['id'])
            self.assertTrue(duplicate.json()['already_running'])
            executor.assert_called_once()
            identity = first.json()['id']
            self.assertEqual(self.client.get('/conversation/analysis-jobs/latest').json()['id'], identity)
            self.assertEqual(self.client.post(f'/conversation/analysis-jobs/{identity}/cancel').json()['status'], 'cancelling')
        with patch.object(jobs, 'SessionLocal', sessionmaker(bind=self.engine)), patch.object(svc, 'classify_batch') as provider:
            jobs._run(identity, jobs.OPINION_SCOPE)
            provider.assert_not_called()
        self.db.expire_all()
        self.assertEqual(self.db.get(MetaSyncJob, identity).status, 'cancelled')
        with patch.object(jobs._executor, 'submit'):
            self.assertEqual(self.client.post(f'/conversation/analysis-jobs/{identity}/resume').status_code, 202)

    def test_provider_failure_preserves_partial_progress_and_failed_comments(self):
        self.post.raw_comments_json = json.dumps([{'id': f'failure-{index}', 'content': 'Excelente Johan.'} for index in range(24)])
        self.db.commit()
        seen = 0
        def classify(context, comments, client):
            nonlocal seen
            seen += 1
            if seen > 1:
                raise ValueError('invalid output')
            return {comment['id']: result() for comment in comments}
        with patch.object(svc, 'classify_batch', side_effect=classify), patch.object(svc.time, 'sleep'):
            outcome = svc.analyze_all(self.db)
        self.assertEqual(outcome['status'], 'partial')
        self.assertEqual(outcome['completed'], 12)
        self.assertEqual(self.db.query(CommentAnalysis).count(), 12)

    def test_parallel_provider_calls_keep_writes_and_progress_consistent(self):
        import threading
        barrier = threading.Barrier(3)
        self.post.raw_comments_json = json.dumps([{'id': f'parallel-{index}', 'content': 'Excelente Johan.'} for index in range(36)])
        self.db.commit()
        def classify(context, comments, client):
            barrier.wait(timeout=5)
            return {comment['id']: result() for comment in comments}
        with patch.object(svc, 'classify_batch', side_effect=classify):
            outcome = svc.analyze_all(self.db, concurrency=3)
        self.assertEqual(outcome['status'], 'success')
        self.assertEqual(outcome['completed'], 36)
        self.assertEqual(self.db.query(CommentAnalysis).count(), 36)

    def test_background_job_saves_batch_cursor_and_selected_scope(self):
        with patch.object(jobs._executor, 'submit'):
            created = self.client.post('/conversation/analysis-jobs', json={'post_id': 'FB_1', 'month': '2026-11'}).json()
        def classify(context, comments, client):
            return {comment['id']: result() for comment in comments}
        with patch.object(jobs, 'SessionLocal', sessionmaker(bind=self.engine)), patch.object(svc, 'classify_batch', side_effect=classify):
            jobs._run(created['id'], jobs.OPINION_SCOPE)
        self.db.expire_all()
        job = self.client.get('/conversation/analysis-jobs/latest').json()
        self.assertEqual(job['status'], 'success')
        self.assertEqual(job['progress']['completed'], 3)
        self.assertEqual(job['progress']['total'], 3)
        self.assertEqual(job['progress']['filters']['post_id'], 'FB_1')
        self.assertEqual(self.db.query(CommentAnalysis).count(), 3)
        self.assertIsNone(self.db.get(MetaSyncJob, created['id']).active_key)

    def test_scoped_analysis_and_selector_exclude_instagram_and_other_months(self):
        options = self.client.get('/conversation/posts').json()
        self.assertEqual([row['id'] for row in options], ['FB_1'])
        self.assertEqual(self.client.get('/conversation/posts', params={'month': '2026-10'}).json(), [])
        with patch.object(svc, 'classify_batch') as provider:
            self.assertEqual(svc.analyze_all(self.db, month='2026-10')['total'], 0)
            provider.assert_not_called()
        self.assertEqual(self.client.post('/conversation/analysis-jobs', json={'post_id': 'IG_1'}).status_code, 404)
        self.assertEqual(self.client.post('/conversation/analysis-jobs', json={'month': '2026-99'}).status_code, 422)

    def test_automatic_queue_waits_after_provider_failure(self):
        self.context()
        with patch.object(jobs.settings, "AUTO_ANALYZE_ENABLED", True), \
             patch.object(jobs, "SessionLocal", sessionmaker(bind=self.engine)), \
             patch.object(jobs._executor, "submit", side_effect=lambda run, *args: run(*args)), \
             patch.object(svc, "classify_batch", side_effect=RuntimeError("offline")) as provider:
            jobs.queue_pending_analysis(self.db)
            self.db.expire_all()
            data = self.client.get("/conversation").json()
            self.assertEqual(data["analysis_status"], "failed")
            self.assertEqual(data["summary"]["pending_with_context"], 3)
            jobs.queue_pending_analysis(self.db)
            provider.assert_called_once()

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
        output([{ "id": "comment_0", **result(confidence=0.4)}])
        self.assertTrue(svc.classify_batch({}, comments, client)["c1"]["needs_review"])
        for items in ([], [{"id": "wrong", **result()}], [{"id": "comment_0", **result(stance="invented")}], [{"id": "comment_0", **result(confidence=2)}]):
            output(items)
            with self.assertRaises((ValueError, TypeError)):
                svc.classify_batch({}, comments, client)

    def test_provider_local_ids_round_trip_long_meta_ids_without_precision_loss(self):
        client = MagicMock()
        create = client.with_options.return_value.chat.completions.create
        create.return_value.choices = [SimpleNamespace(message=SimpleNamespace(content=json.dumps({'items': [
            {'id': 'comment_1', **result('criticism')}, {'id': 'comment_0', **result()}]})))]
        originals = ['0000123456789012345678901234567890', 'FB_12345678901234567890_98765432109876543210']
        results = svc.classify_batch({}, [{'id': identity, 'content': 'Texto de prueba.'} for identity in originals], client)
        self.assertEqual(results[originals[0]]['stance'], 'support')
        self.assertEqual(results[originals[1]]['stance'], 'criticism')
        sent = json.loads(create.call_args.kwargs['messages'][-1]['content'])
        self.assertEqual([row['id'] for row in sent['comments']], ['comment_0', 'comment_1'])

    def test_one_malformed_comment_does_not_prevent_other_comments_from_being_classified(self):
        def classify(context, comments, client):
            if any(comment['id'] == 'c2' for comment in comments):
                raise ValueError('Provider omitted this entry')
            return {comment['id']: result() for comment in comments}
        with patch.object(svc, 'classify_batch', side_effect=classify), patch.object(svc.time, 'sleep'):
            outcome = svc.analyze_all(self.db)
        self.assertEqual(outcome['status'], 'partial')
        self.assertEqual(outcome['completed'], 2)
        self.assertEqual(outcome['failed'], 1)
        self.assertEqual({row.comment_id for row in self.db.query(CommentAnalysis)}, {'c1', 'c3'})

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
