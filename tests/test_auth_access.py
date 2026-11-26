from tests.auth_helpers import prime_sessions, fixture_token
import hashlib
import hmac
import io
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from unittest.mock import patch
import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.v1 import api_v1_router
from app.api.access import PUBLIC
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.models.case import Case
from app.services.email_service import send_otp_email


class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'Only-an-isolated-fixture-123'
        cls.password_hash = get_password_hash(cls.password)

    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        for role in ('ADMIN', 'ALCALDE', 'SECRETARIO', 'OPERADOR'):
            self.db.add(User(id=role, email=f'{role.lower()}@example.test', full_name=f'Fixture {role}', role=role, hashed_password=self.password_hash))
        self.db.add(Case(id='CASE-TEST', title='Solicitud aislada', content='Texto original', source='Facebook', author='Autor', category='General', sentiment='Sin analizar', priority='Media', status='Pendiente', location='Sin verificar', date_time='2026-11-24'))
        self.db.commit()
        prime_sessions(self.db)
        self.app = FastAPI()
        self.app.include_router(api_v1_router, prefix='/api/v1')
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def headers(self, account_role='ADMIN', **claims):
        return {'Authorization': 'Bearer ' + fixture_token(self.db, account_role, **claims)}

    def test_all_nonpublic_routes_require_auth_before_processing(self):
        checked = 0
        for route_path, operations in self.app.openapi()['paths'].items():
            if not route_path.startswith('/api/v1'): continue
            path = route_path.removeprefix('/api/v1')
            for operation in operations:
                method = operation.upper()
                if (method, path) in PUBLIC: continue
                concrete = route_path
                for name in ('case_id', 'user_id', 'operation_id', 'post_id', 'source_id', 'job_id', 'citizen_id'):
                    concrete = concrete.replace('{' + name + '}', 'isolated')
                with self.subTest(method=method, path=path):
                    response = self.client.request(method, concrete, json={})
                    self.assertEqual(response.status_code, 401, response.text)
                checked += 1
        self.assertGreater(checked, 50)

    def test_demo_malformed_expired_and_unsigned_tokens_are_rejected(self):
        tokens = ['demo-token-admin', 'demo-token-alcalde', 'malformed', create_access_token({'sub': 'ADMIN'}, timedelta(seconds=-1)), jwt.encode({'sub': 'ADMIN'}, settings.SECRET_KEY, algorithm='HS256')]
        for token in tokens:
            with self.subTest(kind=token.split('.')[0][:18]):
                self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 401)

    def test_login_requires_password_and_returns_only_active_profile(self):
        wrong = self.client.post('/api/v1/auth/login', json={'email': 'admin@example.test', 'password': 'wrong'})
        self.assertEqual(wrong.status_code, 401)
        good = self.client.post('/api/v1/auth/login', json={'email': ' ADMIN@example.test ', 'password': self.password})
        self.assertEqual(good.status_code, 200)
        self.assertNotIn('hashed_password', good.text)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + good.json()['access_token']}).status_code, 200)
        self.db.get(User, 'ADMIN').is_active = False
        self.db.commit()
        self.assertEqual(self.client.get('/api/v1/auth/me', headers=self.headers()).status_code, 401)

    def test_database_role_overrides_forged_or_outdated_role_claim(self):
        response = self.client.get('/api/v1/auth/users', headers=self.headers('OPERADOR', role='ADMIN'))
        self.assertEqual(response.status_code, 403)

    def test_only_admin_can_manage_users_and_self_delete_is_refused(self):
        for role in ('ALCALDE', 'SECRETARIO', 'OPERADOR'):
            for method, path in [('GET', '/auth/users'), ('POST', '/auth/register'), ('DELETE', '/auth/users/ADMIN')]:
                self.assertEqual(self.client.request(method, '/api/v1' + path, headers=self.headers(role), json={}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/auth/users', headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.delete('/api/v1/auth/users/ADMIN', headers=self.headers()).status_code, 409)
        self.assertEqual(self.db.query(User).count(), 4)

    def test_role_permissions_protect_case_mutations_without_changes(self):
        calls = [
            ('OPERADOR', 'POST', '/dispatch', {'assigned_department': 'Equipo', 'assigned_to': 'Ana'}),
            ('ALCALDE', 'PATCH', '', {'status': 'No requiere gesti\u00f3n'}),
            ('OPERADOR', 'POST', '/resolve', {'resolution_note': 'Una nota completa de cierre.', 'resolved_by': 'Falso'}),
            ('SECRETARIO', 'POST', '/priority-action', {}),
            ('SECRETARIO', 'PATCH', '', {'priority_action': True}),
            ('OPERADOR', 'DELETE', '', {}),
        ]
        for role, method, suffix, payload in calls:
            with self.subTest(role=role, action=suffix):
                self.assertEqual(self.client.request(method, '/api/v1/cases/CASE-TEST' + suffix, headers=self.headers(role), json=payload).status_code, 403)
        self.assertEqual(self.db.get(Case, 'CASE-TEST').status, 'Pendiente')
        self.assertIsNone(self.db.get(Case, 'CASE-TEST').assigned_to)

    def revision(self, case_id='CASE-TEST'):
        return self.client.get('/api/v1/cases/' + case_id, headers=self.headers()).json()['workflow_revision']

    def test_notes_and_resolution_record_authenticated_actor(self):
        response = self.client.post('/api/v1/cases/CASE-TEST/notes', headers=self.headers('OPERADOR'), json={'note': 'Nota de seguimiento', 'author_name': 'Identidad falsificada', 'expected_revision': self.revision()})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Fixture OPERADOR', response.json()['internal_notes'])
        self.assertNotIn('Identidad falsificada', response.json()['internal_notes'])
        dispatch = self.client.post('/api/v1/cases/CASE-TEST/dispatch', headers=self.headers('SECRETARIO'), json={'assigned_department': 'Equipo', 'assigned_to': 'Ana', 'note': 'Verificar el reporte en sitio.', 'confirmed_review': True, 'expected_revision': self.revision()})
        self.assertEqual(dispatch.status_code, 200)
        closed = self.client.post('/api/v1/cases/CASE-TEST/resolve', headers=self.headers('SECRETARIO'), json={'resolution_note': 'Solucion documentada solo en SQLite.', 'resolved_by': 'Identidad falsificada', 'evidence_reference': 'Acta aislada de prueba', 'confirmed_resolution': True, 'expected_revision': self.revision()})
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()['resolved_by'], 'Fixture SECRETARIO')

    def test_seed_and_simulator_are_disabled_even_for_admin(self):
        for path in ('/seed', '/meta/simulate-comment'):
            self.assertEqual(self.client.post('/api/v1' + path, headers=self.headers(), json={}).status_code, 410)
        self.assertEqual(self.db.query(Case).count(), 1)

    def test_read_only_role_cannot_create_case_by_opening_an_incident(self):
        from app.models.incident import Incident
        self.db.add(Incident(id='only-an-incident', lat=2.9, lng=-75.2, title='Fixture', description='Sin expediente', category='General', priority='Media', sentiment='Sin analizar', source='Facebook', neighborhood='Sin verificar', zone='sin-verificar', date_time='2026-11-25'))
        self.db.commit()
        response = self.client.get('/api/v1/cases/only-an-incident', headers=self.headers('ALCALDE'))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query(Case).count(), 1)
        self.assertIsNotNone(self.db.get(Incident, 'only-an-incident'))

    def test_sensitive_admin_information_is_not_available_to_other_roles(self):
        for path in ('/system/diagnostics', '/ai/credits'):
            self.assertEqual(self.client.get('/api/v1' + path, headers=self.headers('OPERADOR')).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/ai/sync-balance', headers=self.headers('SECRETARIO'), json={}).status_code, 403)

    def test_unsigned_webhook_never_calls_ai_or_writes(self):
        with patch.object(settings, 'META_APP_SECRET', 'fixture-secret'), patch('app.api.v1.meta.ai_classifier.classify_comment') as ai:
            self.assertEqual(self.client.post('/api/v1/meta/webhook', json={'object': 'page', 'entry': []}).status_code, 403)
            body = b'{"object":"not-a-page"}'
            signature = 'sha256=' + hmac.new(b'fixture-secret', body, hashlib.sha256).hexdigest()
            self.assertEqual(self.client.post('/api/v1/meta/webhook', content=body, headers={'x-hub-signature-256': signature}).status_code, 200)
            ai.assert_not_called()
        self.assertEqual(self.db.query(Case).count(), 1)

    def test_recovery_never_returns_or_logs_the_code(self):
        with patch('app.api.v1.auth.smtp_is_configured', return_value=True), patch('app.services.password_recovery.generate_otp_code', return_value='246810'), patch('app.services.password_recovery.send_otp_email', return_value=True):
            result = self.client.post('/api/v1/auth/forgot-password', json={'email': 'admin@example.test'})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('dev_otp', result.json())
        code = '246810'
        self.assertIsNone(self.db.get(User, 'ADMIN').reset_otp)
        self.assertNotIn(code, result.text)
        output = io.StringIO()
        with patch.object(settings, 'SMTP_HOST', None), redirect_stdout(output):
            self.assertFalse(send_otp_email('fixture@example.test', 'Fixture', code))
        self.assertNotIn(code, output.getvalue())

    def test_recovery_delivery_failure_does_not_claim_success_or_leave_code(self):
        with patch('app.api.v1.auth.smtp_is_configured', return_value=False):
            result = self.client.post('/api/v1/auth/forgot-password', json={'email': 'admin@example.test'})
        self.assertEqual(result.status_code, 503)
        self.assertIsNone(self.db.get(User, 'ADMIN').reset_otp)

    def test_inactive_account_cannot_reset_password(self):
        from datetime import datetime
        user = self.db.get(User, 'ADMIN')
        user.is_active, user.reset_otp, user.reset_otp_expires_at = False, '123456', datetime.utcnow() + timedelta(minutes=15)
        self.db.commit()
        response = self.client.post('/api/v1/auth/reset-password', json={'email': user.email, 'otp_code': '123456', 'new_password': 'Another-test-password'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(user.hashed_password, self.password_hash)

    def test_otp_attempts_have_a_shared_limit(self):
        for _ in range(10):
            self.client.post('/api/v1/auth/verify-otp', json={'email': 'missing@example.test', 'otp_code': '111111'})
        response = self.client.post('/api/v1/auth/verify-otp', json={'email': 'missing@example.test', 'otp_code': '111111'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('retry-after', response.headers)

    def test_production_refuses_example_keys_and_insecure_origins(self):
        from app.core.config import Settings
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, ENVIRONMENT='production', SECRET_KEY='SUPER_SECRET_KEY_REEMPLAZAR_EN_PRODUCCION', BACKEND_CORS_ORIGINS=['https://civia.example.test'])
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, ENVIRONMENT='production', SECRET_KEY='fixture-only-random-value-12345678901234567890', BACKEND_CORS_ORIGINS=['http://localhost:3000'])

    def test_user_creation_rejects_invalid_role_and_oversized_bcrypt_password(self):
        base = {'email': 'new@example.test', 'full_name': 'New fixture', 'password': 'Fixture-password-123'}
        invalid_role = self.client.post('/api/v1/auth/register', headers=self.headers(), json={**base, 'role': 'SUPERADMIN'})
        invalid_length = self.client.post('/api/v1/auth/register', headers=self.headers(), json={**base, 'password': '\u00e9' * 40})
        self.assertEqual(invalid_role.status_code, 422)
        self.assertEqual(invalid_length.status_code, 422)
        self.assertEqual(self.db.query(User).count(), 4)


if __name__ == '__main__': unittest.main()
