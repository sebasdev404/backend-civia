"""Disposable news data and mocked providers; never consult real media or send mail."""
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.api.v1.auth import get_current_user
from app.api.v1.publications import router
from app.models.publication import PublicationSource, ObservedPost, NewsSource, NewsAnalysis
from app.services import news_monitor as news, publications
from app.services.facebook_graph import GraphAPIError


def classification(**changes):
    return {'priority':'Alta','territory':'Neiva','topic':'Servicios públicos','summary':'El medio informa un corte de agua.',
            'reason':'Afecta servicios esenciales de barrios de Neiva.','place':'Neiva','confidence':0.95,'needs_review':False,**changes}


class NewsMonitorTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.db=Session(self.engine)
        publications.ensure_sources(self.db)
        self.actor=SimpleNamespace(id='qa-admin',full_name='Fixture admin',role='ADMIN')
        self.source=news.register_source(self.db,'Medio de PRUEBA','https://web.facebook.com/qaNoticias?locale=es_LA',self.actor)
        self.post=ObservedPost(id='qa-news-1',source_id=self.source,title='Corte de agua en Neiva',message='Corte de agua en varios barrios de Neiva.',created_time=datetime.now(timezone.utc).isoformat(),permalink_url='https://www.facebook.com/qaNoticias/posts/1',raw_comments_json='[]')
        self.db.add(self.post)
        self.db.add(ObservedPost(id='qa-other',source_id='jorge-gechem',title='No es noticia registrada',created_time='2026-01-01',raw_comments_json='[]'))
        self.db.commit()
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[get_current_user]=lambda:self.actor
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close();self.db.close();self.engine.dispose()

    def test_page_urls_are_canonical_and_reject_nonpages_and_lookalike_domains(self):
        self.assertEqual(news.page_address('https://web.facebook.com/OPANoticias?locale=es_LA')[0],'https://www.facebook.com/opanoticias')
        for url in ('https://facebook.com.evil.test/medio','https://evil.test/medio','https://facebook.com/groups/123',
                    'https://facebook.com/reel/123','https://facebook.com/user/posts/123','https://user:pass@facebook.com/medio','http://localhost/page'):
            with self.subTest(url=url),self.assertRaises(HTTPException):news.page_address(url)

    def test_registration_deduplicates_normalized_links_and_preserves_social_sources(self):
        with self.assertRaises(HTTPException) as error:
            news.register_source(self.db,'Duplicada','https://www.facebook.com/QANOTICIAS?x=1',self.actor)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(self.db.query(NewsSource).count(),1)
        self.assertEqual({source['id'] for source in publications.sources(self.db)},{'johan','jorge-gechem'})

    def test_feed_separates_news_from_other_sources_and_does_not_invent_analysis(self):
        feed=self.client.get('/publications/news').json()
        self.assertEqual(feed['summary']['captured'],1)
        self.assertEqual(feed['summary']['pending'],1)
        self.assertEqual(feed['items'][0]['id'],'qa-news-1')
        self.assertIsNone(feed['items'][0]['analysis'])

    def test_priority_territory_and_topic_filters_and_stale_content(self):
        self.db.add(NewsAnalysis(post_id=self.post.id,fingerprint=news.fingerprint(self.post),result_json=json.dumps(classification())))
        self.db.commit()
        self.assertEqual(self.client.get('/publications/news?priority=Alta&territory=Neiva').json()['total'],1)
        self.assertEqual(self.client.get('/publications/news?topic=Salud').json()['total'],0)
        self.post.message='El medio corrigió el contenido.';self.db.commit()
        feed=self.client.get('/publications/news').json()
        self.assertEqual(feed['summary']['pending'],1)
        self.assertIsNone(feed['items'][0]['analysis'])

    def test_only_admin_and_secretary_manage_sources_and_pausing_preserves_news(self):
        self.actor.role='OPERADOR'
        self.assertEqual(self.client.post('/publications/news/sources',json={'name':'Otra','url':'https://facebook.com/qaOtra'}).status_code,403)
        self.assertEqual(self.client.patch('/publications/news/sources/'+self.source,json={'enabled':False}).status_code,403)
        self.actor.role='SECRETARIO'
        self.assertEqual(self.client.patch('/publications/news/sources/'+self.source,json={'enabled':False}).status_code,200)
        self.assertEqual(news.feed(self.db)['total'],1)
        with patch.object(publications,'sync_external') as provider:
            self.assertEqual(news.run_monitor(self.db,lambda **value:None)['posts_updated'],0)
            provider.assert_not_called()

    def test_permission_failure_is_visible_and_never_adds_fake_publications(self):
        self.db.delete(self.post);self.db.commit()
        with patch.object(publications,'graph_get',side_effect=GraphAPIError({'code':10})):
            result=news.run_monitor(self.db,lambda **value:None)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['processed'],0)
        self.assertEqual(news.list_sources(self.db)[0]['status'],'missing_permissions')
        self.assertEqual(news.feed(self.db)['total'],0)

    def test_news_capture_avoids_comments_and_reactions_requests(self):
        def graph(path,token,**values):
            return {'id':'qa-page','name':'Medio QA'} if path=='qaNoticias' else {'data':[{'id':'qa-captured','message':'Noticia de prueba en Neiva.','created_time':'2026-11-26T14:00:00+00:00'}]}
        with patch.object(publications,'graph_get',side_effect=graph),patch.object(publications,'read_post_comments') as comments,patch.object(publications,'capture_metrics') as metrics:
            result=publications.sync_external(self.db,self.source,lambda **value:None,capture_discussion=False)
        self.assertEqual(result['posts_updated'],1)
        comments.assert_not_called();metrics.assert_not_called()

    def test_model_outputs_keep_ids_and_uncertainty_and_require_all_items(self):
        client=MagicMock()
        create=client.with_options.return_value.chat.completions.create
        create.return_value.choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'items':[{'id':'news_0',**classification(confidence=0.3)}]})))]
        result=news.classify_batch([self.post],client)
        self.assertTrue(result[self.post.id]['needs_review'])
        self.assertEqual(create.call_args.kwargs['model'],'gpt-4o-mini')
        create.return_value.choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":[]}'))]
        with self.assertRaises(ValueError):news.classify_batch([self.post],client)

    def test_worker_classifies_stores_and_does_not_repeat_fresh_results(self):
        with patch.object(publications,'sync_external',return_value={'status':'success','posts_updated':0}),patch.object(news.ai_classifier,'client',MagicMock()),patch.object(news,'classify_batch',return_value={self.post.id:classification()}) as provider:
            result=news.run_monitor(self.db,lambda **value:None)
            self.assertEqual(result['processed'],1)
            self.assertEqual(news.run_monitor(self.db,lambda **value:None)['processed'],0)
            provider.assert_called_once()
        self.assertEqual(news.feed(self.db)['summary']['high'],1)

    def test_provider_failure_keeps_captured_news_pending(self):
        with patch.object(publications,'sync_external',return_value={'status':'success','posts_updated':0}),patch.object(news.ai_classifier,'client',MagicMock()),patch.object(news,'classify_batch',side_effect=RuntimeError('offline')):
            self.assertEqual(news.run_monitor(self.db,lambda **value:None)['status'],'partial')
        self.assertEqual(self.db.query(NewsAnalysis).count(),0)
        self.assertEqual(news.feed(self.db)['summary']['pending'],1)

    def test_default_order_prioritizes_regional_importance_and_recent_order_is_available(self):
        second=ObservedPost(id='qa-news-newer',source_id=self.source,title='Deporte fuera de la región',message='Noticia de Madrid.',created_time='2099-01-01',raw_comments_json='[]')
        self.db.add(second);self.db.flush()
        for post,value in [(self.post,classification()),(second,classification(priority='Fuera de foco',territory='Fuera de la región'))]:
            self.db.add(NewsAnalysis(post_id=post.id,fingerprint=news.fingerprint(post),result_json=json.dumps(value)))
        self.db.commit()
        self.assertEqual(news.feed(self.db)['items'][0]['id'],self.post.id)
        self.assertEqual(news.feed(self.db,order='recent')['items'][0]['id'],second.id)
