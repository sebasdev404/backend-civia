"""Analytics invariants in isolated SQLite; never seed the application's database."""
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
import app.models
from app.models.case import Case
from app.models.case_consolidation import CaseConsolidation
from app.models.meta_post import MetaPost
from app.models.conversation import CommentAnalysis, PostContext
from app.services import analytics
from app.services.conversation import context_for, fingerprint, captured_comments
from app.api.v1.analytics import router


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def case(self, key, **changes):
        row = Case(id=key, title='Isolated record', author='Fixture', content='Fixture text', date_time='2026-11-24',
            source='Facebook', category='Sin clasificar', priority='Media', sentiment='Sin evaluar',
            location='Sin verificar', status='Pendiente')
        for key, value in changes.items(): setattr(row, key, value)
        self.db.add(row)
        return row

    def post(self):
        post = MetaPost(id='p', title='Fixture publication', message='Fixture caption', source='Facebook',
            media_type='image', published_at='2026-11-24', total_comments=10,
            raw_comments_json=json.dumps([{'id':'c','content':'Fixture comment'}]))
        self.db.add(post); self.db.commit()
        return post

    def test_empty_database_is_zero_and_unmeasured_is_null(self):
        result = self.client.get('/api/v1/analytics/overview').json()
        self.assertEqual(result['cases']['total'], 0)
        self.assertEqual(result['capture']['captured_comments'], 0)
        self.assertEqual(result['capture']['reported_comments'], 0)
        self.assertEqual(result['cases']['emotions'], {})
        self.assertIsNone(result['response_time']['average_hours'])
        self.assertIsNone(result['data_updated_at'])

    def test_case_total_is_not_limited_to_a_page(self):
        for n in range(603): self.case(str(n))
        self.db.commit()
        result = analytics.case_counts(self.db)
        self.assertEqual(result['total'], 603)
        self.assertEqual(result['pending'], 603)

    def test_closed_high_priority_cases_are_not_open_critical(self):
        self.case('pending', priority='Alta')
        self.case('resolved', status='Resuelto', priority='Alta')
        self.case('general', status='No requiere gestión', priority='Crítica')
        self.case('progress', status='En Gestión', priority='Crítica')
        self.db.commit()
        result = analytics.case_counts(self.db)
        self.assertEqual((result['total'], result['open'], result['critical_open'], result['no_request']), (4, 2, 2, 1))
        self.assertEqual(sum(result['categories'].values()), result['total'])

    def test_only_active_duplicates_are_excluded_and_originals_retained(self):
        self.case('a'); self.case('b'); self.case('c'); self.db.commit()
        self.db.add(CaseConsolidation(id='op', primary_case_id='a', duplicate_case_id='b', reason='Isolated test',
            created_by='fixture', created_at=datetime.now(timezone.utc), evidence_json={}))
        self.db.commit()
        result = analytics.case_counts(self.db)
        self.assertEqual((result['stored'], result['total'], result['duplicates_excluded']), (3, 2, 1))
        self.db.get(CaseConsolidation, 'op').undone_at = datetime.now(timezone.utc); self.db.commit()
        self.assertEqual(analytics.case_counts(self.db)['total'], 3)

    def test_capture_deduplicates_per_post_but_keeps_replies_and_other_networks(self):
        raw = json.dumps([{'id':'same','message':'Comentario repetido'}, {'id':'same','message':'Comentario repetido'},
                          {'id':'reply','parent_id':'same','message':''}, {'message':'No individual ID'}])
        posts = [SimpleNamespace(source='Facebook', total_comments=8, raw_comments_json=raw),
                 SimpleNamespace(source='Instagram', total_comments=2, raw_comments_json=json.dumps([{'id':'same','message':'Otro comentario'}]))]
        result = analytics.captured_metrics(posts)
        self.assertEqual((result['posts'], result['captured_comments'], result['reported_comments']), (2, 3, 10))
        self.assertEqual(next(r for r in result['channels'] if r['source']=='Facebook')['captured_comments'], 2)
        self.assertNotIn('repetido', {r['term']:r['count'] for r in result['top_terms'] if r['count']>1})

    def test_missing_and_broken_capture_are_not_a_known_empty_capture(self):
        posts = [SimpleNamespace(source=None, total_comments=None, raw_comments_json=value) for value in (None,'broken','[]','{}')]
        result = analytics.captured_metrics(posts)
        self.assertEqual((result['posts_without_capture'], result['unreadable_captures']), (1, 2))
        self.assertEqual(result['reported_unknown_posts'], 4)
        self.assertEqual(result['captured_comments'], 0)

    def test_unknown_emotion_is_not_mapped_to_peace(self):
        self.case('a', sentiment='Sin evaluar'); self.case('b', sentiment='Enojo o ira: Frustración'); self.db.commit()
        emotions = analytics.case_counts(self.db)['emotions']
        self.assertEqual(emotions, {'Enojo o ira: Frustración': 1, 'Sin evaluar': 1})
        self.assertNotIn('Paz o tranquilidad', emotions)

    def test_contextual_count_requires_current_fingerprint_and_review_is_separate(self):
        post = self.post()
        result = {'stance':'support','emotion':'Enojo o ira','target':'Johan','topic':'General','narrative':'agreement',
            'explanation':'Isolated contextual review','confidence':0.9,'needs_review':False}
        self.db.add(CommentAnalysis(post_id='p',comment_id='c',fingerprint=fingerprint(context_for(post),captured_comments(post)[0],None),result_json=json.dumps(result)))
        self.db.commit()
        self.assertEqual(analytics.contextual_counts(self.db,[post])['stances'], {'support':1})
        post.message='Changed caption'; self.db.commit()
        counts=analytics.contextual_counts(self.db,[post])
        self.assertEqual((counts['analyzed'],counts['pending'],counts['review']), (0,1,1))
        self.assertEqual(counts['stances'], {})

    def test_territory_counts_evidenced_comments_once_without_inventing_scores(self):
        items=[{'source_post_id':'p','source_comment_id':cid,'evidence_text':'Lugar'} for cid in ('c','c','d')]
        with patch.object(analytics,'audit_incidents',return_value=(items,{'stored':5,'excluded':2})):
            result=analytics.territorial_counts(self.db)
        self.assertEqual(result['captured_mentions'],2)
        self.assertEqual(result['locations'],[{'location':'Lugar','mentions':2}])
        self.assertNotIn('sentiment_score', result['locations'][0])

    def test_overview_is_read_only_and_does_not_request_ai(self):
        self.post()
        statements=[]
        def track(connection,cursor,statement,parameters,context,executemany): statements.append(statement)
        event.listen(self.engine,'before_cursor_execute',track)
        try:
            with patch('app.services.conversation.classify_batch',side_effect=AssertionError('Must not invoke AI')):
                response=self.client.get('/api/v1/analytics/overview')
            self.assertEqual(response.status_code,200)
        finally: event.remove(self.engine,'before_cursor_execute',track)
        self.assertFalse(any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','CREATE')) for s in statements))

    def test_legacy_routes_no_longer_publish_invented_time_or_alerts(self):
        self.assertIsNone(self.client.get('/api/v1/analytics/summary').json()['active_territorial_alerts'])
        kpis=self.client.get('/api/v1/analytics/kpis').json()
        self.assertIsNone(kpis['avg_reaction_time'])
        self.assertIsNone(kpis['tension_index'])
        self.assertEqual(self.client.get('/api/v1/analytics/top-barrios').json(), [])

    def test_context_changes_are_reflected_in_the_data_timestamp(self):
        post=self.post()
        self.db.add(PostContext(post_id=post.id,summary='Fixture context',transcript='',updated_at=datetime(2030,1,2,tzinfo=timezone.utc)))
        self.db.commit()
        self.assertTrue(analytics.overview(self.db)['data_updated_at'].startswith('2030-01-02'))


if __name__ == '__main__': unittest.main()
