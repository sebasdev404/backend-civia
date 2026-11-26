import hashlib
import hmac
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
import tests.test_case_workflow as workflow_fixtures
from app.core.config import settings
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.models.operations import AuditEvent,WebhookEvent,MailOutbox
from app.models.password_recovery import PasswordRecovery
from app.services.webhooks import process_pending
from app.services.mail_queue import enqueue,process_outbox,invalidate_recovery_mail,cipher


class ProductionOperations(unittest.TestCase):
    def setUp(self):
        self.fixture=workflow_fixtures.WorkflowTests();self.fixture.setUp()
        self.db=self.fixture.db;self.client=self.fixture.client

    def tearDown(self):self.fixture.tearDown()

    def registration(self,**changes):
        return self.fixture.action('registration',{'number':'EXT-FIXTURE-123','institution':'Entidad de prueba','issued_on':(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat(),'evidence_reference':'Archivo de prueba 001','reason':'Registro cotejado con el documento externo de prueba.','confirmed_review':True,**changes})

    def test_external_registration_is_audited_without_changing_case_state(self):
        before=self.fixture.read();self.assertEqual(self.registration().status_code,200)
        row=self.fixture.read();self.assertEqual(row['status'],before['status']);self.assertEqual(row['institutional_radicado'],'EXT-FIXTURE-123')
        self.assertTrue(row['registrations'][0]['is_current']);self.assertEqual(row['registrations'][0]['evidence_reference'],'Archivo de prueba 001')
        self.assertEqual(row['workflow_events'][0]['event_type'],'registration_recorded')
        self.assertEqual(self.registration().status_code,409)
        self.assertEqual(self.registration(number='work').status_code,422)
        self.assertEqual(self.registration(confirmed_review=False).status_code,422)
        self.assertEqual(self.registration(issued_on=(datetime.now(timezone.utc)+timedelta(days=2)).date().isoformat()).status_code,422)

    def test_external_reference_correction_and_cancellation_keep_old_support(self):
        self.registration();self.assertEqual(self.registration(number='EXT-FIXTURE-456').status_code,200)
        self.assertEqual(self.fixture.action('registration/cancel',{'reason':'El documento se registró en un expediente equivocado.','confirmed_review':True}).status_code,200)
        row=self.fixture.read();self.assertIsNone(row['institutional_radicado']);self.assertEqual(len(row['registrations']),2)
        self.assertFalse(any(item['is_current'] for item in row['registrations']))
        self.assertTrue(row['registrations'][0]['cancelled_at']);self.assertEqual(row['registrations'][1]['evidence_reference'],'Archivo de prueba 001')

    def test_external_reference_role_and_stale_revision(self):
        payload={'number':'EXT-123','institution':'Entidad','issued_on':'2020-01-01','evidence_reference':'Document 1','reason':'Reason sufficiently long for registration.','confirmed_review':True}
        for role in ('ALCALDE','OPERADOR'):
            self.assertEqual(self.fixture.action('registration',payload,role=role).status_code,403)
        old=self.fixture.read()['workflow_revision'];self.registration()
        self.assertEqual(self.fixture.action('registration',payload,version=old).status_code,409)

    def webhook(self,payload):
        body=json.dumps(payload).encode();signature='sha256='+hmac.new(b'fixture-webhook-key',body,hashlib.sha256).hexdigest()
        with patch.object(settings,'META_APP_SECRET','fixture-webhook-key'):
            return self.client.post('/api/v1/meta/webhook',content=body,headers={'x-hub-signature-256':signature})

    def test_webhook_is_deduplicated_durable_and_never_creates_cases(self):
        payload={'object':'page','entry':[{'changes':[{'field':'feed','value':{'item':'comment','post_id':'origin','comment_id':'from-webhook','message':'Texto recibido en la prueba','from':{'id':'author-id','name':'Autor QA'}}}]}]}
        with patch('app.services.ai_classifier.ai_classifier.classify_comment') as ai:
            self.assertEqual(self.webhook(payload).status_code,200);self.assertEqual(self.webhook(payload).status_code,200)
            self.assertEqual(self.db.query(WebhookEvent).count(),1)
            self.assertEqual(self.db.query(Case).count(),1)
            process_pending(self.db);ai.assert_not_called()
        self.assertEqual(self.db.query(WebhookEvent).one().status,'processed')
        comments=json.loads(self.db.get(MetaPost,'origin').raw_comments_json)
        self.assertEqual(sum(c.get('id')=='from-webhook' for c in comments),1)
        self.assertEqual(self.db.query(Case).count(),1)

    def test_webhook_missing_post_waits_then_retries_without_invented_origin(self):
        payload={'object':'instagram','entry':[{'changes':[{'field':'comments','value':{'id':'comment-ig','media':{'id':'exact-id'},'text':'Mensaje capturado'}}]}]}
        self.webhook(payload);process_pending(self.db)
        event=self.db.query(WebhookEvent).one();self.assertEqual(event.status,'waiting_source')
        self.assertEqual(self.db.query(MetaPost).count(),1)
        self.db.add(MetaPost(id='IG_exact-id',source='Instagram',title='Fixture exacta',published_at='2020-01-01',raw_comments_json='[]'))
        event.last_attempt_at=datetime.now(timezone.utc)-timedelta(minutes=2);self.db.commit();process_pending(self.db)
        self.assertEqual(event.status,'processed');self.assertEqual(self.db.query(Case).count(),1)

    def test_webhook_signature_and_size_are_checked_before_storage(self):
        with patch.object(settings,'META_APP_SECRET','fixture-webhook-key'):
            self.assertEqual(self.client.post('/api/v1/meta/webhook',content=b'{}',headers={'x-hub-signature-256':'invalid'}).status_code,403)
            self.assertEqual(self.client.post('/api/v1/meta/webhook',content=b'x'*(512*1024+1)).status_code,413)
        self.assertEqual(self.db.query(WebhookEvent).count(),0)

    def test_admin_update_revokes_access_and_audits_without_credentials(self):
        rows=self.client.get('/api/v1/auth/users',headers=self.fixture.headers()).json();target=next(u for u in rows if u['id']=='SECRETARIO')
        payload={'full_name':target['full_name'],'role':'OPERADOR','department':'Equipo QA','is_active':True,'reason':'Cambio de responsabilidades aprobado para esta fixture.','expected_revision':target['account_revision']}
        response=self.client.patch('/api/v1/auth/users/SECRETARIO',headers=self.fixture.headers(),json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=self.fixture.headers('SECRETARIO')).status_code,401)
        audit=self.client.get('/api/v1/system/audit',headers=self.fixture.headers()).json()
        self.assertEqual(audit['items'][0]['action'],'user_updated');self.assertNotIn('hashed_password',json.dumps(audit))
        self.assertEqual(self.client.patch('/api/v1/auth/users/SECRETARIO',headers=self.fixture.headers(),json=payload).status_code,409)

    def test_manual_budget_is_persisted_and_diagnostics_do_not_invent_measurements(self):
        with patch('urllib.request.urlopen') as network:
            result=self.client.get('/api/v1/ai/credits',headers=self.fixture.headers()).json();network.assert_not_called()
        self.assertIsNone(result['tokens_processed']);self.assertIsNone(result['remaining_usd'])
        saved=self.client.post('/api/v1/ai/sync-balance',headers=self.fixture.headers(),json={'initial_budget':0,'real_balance':0})
        self.assertEqual(saved.status_code,200)
        self.assertEqual(self.client.get('/api/v1/ai/credits',headers=self.fixture.headers()).json()['remaining_usd'],0)
        data=self.client.get('/api/v1/system/diagnostics',headers=self.fixture.headers()).json()
        self.assertEqual(data['postgres']['cases_count'],1);self.assertNotIn('99.98',json.dumps(data));self.assertNotIn('Entrenado',json.dumps(data))

    def test_mail_queue_is_encrypted_durable_and_invalidated_on_password_change(self):
        with patch('app.services.password_recovery.generate_otp_code',return_value='246810'):
            row=enqueue(self.db,'admin@fixture.invalid');self.db.commit()
        self.assertNotIn('246810',row.ciphertext);self.assertNotIn('admin@fixture.invalid',row.ciphertext)
        self.assertEqual(json.loads(cipher().decrypt(row.ciphertext.encode()))['code'],'246810')
        invalidate_recovery_mail(self.db,'admin@fixture.invalid');self.db.commit()
        self.assertEqual(row.status,'cancelled')

    def test_mail_retry_rolls_back_code_and_can_deliver_later(self):
        with patch('app.services.password_recovery.generate_otp_code',return_value='246810'):
            row=enqueue(self.db,'missing@fixture.invalid');self.db.commit()
        # This fixture has no matching address: no invented account or mail.
        process_outbox(self.fixture.engine);self.db.expire_all();self.assertEqual(row.status,'skipped')
        with patch('app.services.password_recovery.generate_otp_code',return_value='246810'):
            row=enqueue(self.db,'secretario@fixture.invalid');self.db.commit()
        with patch('app.services.password_recovery.send_otp_email',return_value=False):process_outbox(self.fixture.engine)
        self.db.expire_all();self.assertEqual(row.status,'retry');self.assertIsNone(self.db.get(PasswordRecovery,'SECRETARIO'))
        row.next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1);self.db.commit()
        with patch('app.services.password_recovery.send_otp_email',return_value=True):process_outbox(self.fixture.engine)
        self.db.expire_all();self.assertEqual(row.status,'delivered');self.assertIsNotNone(self.db.get(PasswordRecovery,'SECRETARIO'))

    def test_backup_encryption_authenticates_before_restoration(self):
        from ops.backup import encrypt,decrypt
        from cryptography.exceptions import InvalidTag
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plain=root/'source';plain.write_bytes(b'Private fixture only'*1000)
            encrypt(plain,root/'encrypted',b'x'*32);decrypt(root/'encrypted',root/'restored',b'x'*32)
            self.assertEqual(plain.read_bytes(),(root/'restored').read_bytes())
            with self.assertRaises(InvalidTag):decrypt(root/'encrypted',root/'invalid',b'y'*32)

    def test_client_limits_accept_only_fresh_method_and_route_bound_signatures(self):
        from starlette.requests import Request
        from app.core.auth_limits import client_identity
        identity='a'*64;timestamp=str(int(datetime.now(timezone.utc).timestamp()))
        def request(signature,stamp=timestamp,method='POST'):
            headers={'x-civia-client':identity,'x-civia-client-time':stamp,'x-civia-client-signature':signature,'x-forwarded-for':'198.51.100.1'}
            return Request({'type':'http','method':method,'path':'/api/v1/auth/login','headers':[(k.encode(),v.encode()) for k,v in headers.items()],'client':('127.0.0.1',5000)})
        secret='fixture-only-proxy-secret-for-production-qa'
        signature=hmac.new(secret.encode(),f'POST\n/auth/login\n{timestamp}\n{identity}'.encode(),hashlib.sha256).hexdigest()
        with patch.object(settings,'BFF_PROXY_SECRET',secret):
            self.assertEqual(client_identity(request(signature),'/auth/login'),'proxy:'+identity)
            self.assertEqual(client_identity(request(signature),'/auth/reset-password'),'127.0.0.1')
            self.assertEqual(client_identity(request(signature,method='GET'),'/auth/login'),'127.0.0.1')
            self.assertEqual(client_identity(request(signature,stamp='1'),'/auth/login'),'127.0.0.1')
            self.assertEqual(client_identity(request('b'*64),'/auth/login'),'127.0.0.1')

    def test_no_ai_does_not_fabricate_generated_facts_or_embeddings(self):
        from app.services.ai_classifier import ai_classifier
        with patch.object(ai_classifier,'client',None):
            with self.assertRaises(RuntimeError):ai_classifier.generate_smart_response('Solicitud de fixture','Sin clasificar')
            with self.assertRaises(RuntimeError):ai_classifier.get_embedding('Solicitud de fixture')

    def test_similarity_requires_explicit_bounded_candidates_and_never_scans_every_case(self):
        from app.services.ai_classifier import ai_classifier
        headers=self.fixture.headers()
        with patch.object(ai_classifier,'get_embedding',return_value=[1.0,0.0]) as embeddings:
            self.assertEqual(self.client.post('/api/v1/ai/match-cases',headers=headers,json={'text':'Fixture only'}).status_code,422)
            self.assertEqual(self.client.post('/api/v1/ai/match-cases',headers=headers,json={'text':'Fixture only','candidate_ids':['x']*21}).status_code,422)
            result=self.client.post('/api/v1/ai/match-cases',headers=headers,json={'text':'Fixture only','candidate_ids':['not-a-case']})
            self.assertEqual(result.status_code,200);self.assertEqual(result.json(),[]);embeddings.assert_not_called()

    def test_migration_checksums_survive_git_line_endings_but_detect_changed_sql(self):
        from manage import migration_checksum
        with tempfile.TemporaryDirectory() as folder:
            migration=Path(folder)/'fixture.sql';migration.write_bytes(b'BEGIN;\nSELECT 1;\nCOMMIT;\n')
            digest=migration_checksum(migration)
            migration.write_bytes(b'BEGIN;\r\nSELECT 1;\r\nCOMMIT;\r\n');self.assertEqual(migration_checksum(migration),digest)
            migration.write_bytes(b'BEGIN;\nSELECT 2;\nCOMMIT;\n');self.assertNotEqual(migration_checksum(migration),digest)


if __name__=='__main__':unittest.main()
