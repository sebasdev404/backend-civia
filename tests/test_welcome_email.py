"""New-account mail is transactional, encrypted, branded and never sent in tests."""
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.v1 import api_v1_router
from app.core.config import settings, Settings
from app.core.database import Base, get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.operations import MailOutbox
from app.services.auth_sessions import issue_session
from app.services.mail_queue import process_outbox, cipher
from app.services.email_service import send_welcome_email
from app.services.email_templates import render_welcome_email, LOGO_CID


class WelcomeEmailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_hash = get_password_hash('Fixture-admin-2026!')

    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        admin = User(id='admin', email='admin@fixture.invalid', full_name='ISOLATED ADMIN', role='ADMIN', hashed_password=self.admin_hash, is_active=True)
        self.db.add(admin); self.db.flush()
        self.headers = {'Authorization': 'Bearer ' + issue_session(self.db, admin)}
        self.db.commit()
        app = FastAPI(); app.include_router(api_v1_router, prefix='/api/v1')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.background = patch('app.api.v1.auth.process_outbox')
        self.background.start(); self.addCleanup(self.background.stop)
        self.sender = patch('app.services.email_service.send_welcome_email', return_value=True)
        self.mail = self.sender.start(); self.addCleanup(self.sender.stop)
        self.url = patch.object(settings, 'PUBLIC_APP_URL', 'https://portal.fixture.invalid')
        self.url.start(); self.addCleanup(self.url.stop)
        self.payload = {'email': 'new-user@fixture.invalid', 'full_name': 'ISOLATED USER', 'role': 'SECRETARIO'}

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def register(self, **changes):
        return self.client.post('/api/v1/auth/register', json={**self.payload, **changes}, headers=self.headers)

    def test_default_credentials_queued_encrypted_and_sent_once(self):
        response = self.register(); self.assertEqual(response.status_code, 201, response.text)
        data = response.json(); self.assertNotIn('password', data); self.assertNotIn('hashed_password', data)
        self.assertEqual(data['welcome_email_status'], 'queued')
        row = self.db.query(MailOutbox).one()
        payload = json.loads(cipher().decrypt(row.ciphertext.encode()))
        self.assertEqual(payload['password'], '1234'); self.assertEqual(payload['login_url'], 'https://portal.fixture.invalid/login')
        self.assertNotIn(self.payload['email'], row.ciphertext)
        self.assertTrue(verify_password('1234', self.db.get(User, data['id']).hashed_password))
        process_outbox(self.engine); process_outbox(self.engine)
        self.mail.assert_called_once_with(self.payload['email'], self.payload['full_name'], '1234', 'SECRETARIO', 'https://portal.fixture.invalid/login')
        self.db.expire_all(); row = self.db.get(MailOutbox, row.id)
        self.assertEqual(row.status, 'delivered'); self.assertEqual(row.ciphertext, '')
        users = self.client.get('/api/v1/auth/users', headers=self.headers).json()
        listed = next(user for user in users if user['id'] == data['id'])
        self.assertEqual(listed['welcome_email_status'], 'delivered')
        self.assertIn('servidor de correo', listed['welcome_email_detail'])

    def test_custom_initial_password_and_recipient(self):
        password = 'Custom-Initial-2026!'
        response = self.register(password=password, email=' Custom@Fixture.Invalid ')
        self.assertEqual(response.status_code, 201)
        self.assertNotIn(password, response.text)
        process_outbox(self.engine)
        self.assertEqual(self.mail.call_args.args[0], 'custom@fixture.invalid')
        self.assertEqual(self.mail.call_args.args[2], password)

    def test_failed_delivery_retries_without_creating_another_account(self):
        self.register(); self.mail.return_value = False
        process_outbox(self.engine)
        self.db.expire_all(); row = self.db.query(MailOutbox).one()
        self.assertEqual(row.status, 'retry'); self.assertEqual(row.attempts, 1)
        self.assertEqual(self.db.query(User).count(), 2)
        self.assertNotIn(self.payload['email'], row.error)
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1); self.db.commit()
        self.mail.return_value = True; process_outbox(self.engine)
        self.db.expire_all(); self.assertEqual(self.db.get(MailOutbox, row.id).status, 'delivered')
        self.assertEqual(self.register().status_code, 400)
        self.assertEqual(self.db.query(MailOutbox).count(), 1)

    def test_changed_password_cancels_old_credentials(self):
        user_id = self.register().json()['id']
        self.db.get(User, user_id).hashed_password = self.admin_hash; self.db.commit()
        process_outbox(self.engine); self.mail.assert_not_called()
        self.db.expire_all(); row = self.db.query(MailOutbox).one()
        self.assertEqual(row.status, 'superseded'); self.assertEqual(row.ciphertext, '')

    def test_deleted_account_or_expired_invitation_is_not_sent(self):
        user_id = self.register().json()['id']
        self.db.delete(self.db.get(User, user_id)); self.db.commit()
        process_outbox(self.engine); self.mail.assert_not_called()
        self.db.expire_all(); self.assertEqual(self.db.query(MailOutbox).one().status, 'skipped')
        self.db.query(MailOutbox).delete(); self.db.commit()
        self.register(); row = self.db.query(MailOutbox).one()
        row.created_at = datetime.now(timezone.utc) - timedelta(hours=25); self.db.commit()
        process_outbox(self.engine); self.mail.assert_not_called()
        self.db.expire_all(); self.assertEqual(self.db.get(MailOutbox, row.id).status, 'expired')

    def test_invalid_email_creates_neither_account_nor_mail(self):
        for email in ('not-an-email', 'person@example.invalid\r\nBcc: other@invalid.test'):
            self.assertEqual(self.register(email=email).status_code, 422)
        self.assertEqual(self.db.query(User).count(), 1)
        self.assertEqual(self.db.query(MailOutbox).count(), 0)

    def test_template_escapes_credentials_and_uses_existing_identity(self):
        html = render_welcome_email('<script>USER</script>', 'person@fixture.invalid', 'Private<&Initial-2026!', 'SECRETARIO', 'https://portal.fixture.invalid/login')
        self.assertIn('cid:' + LOGO_CID, html); self.assertIn('Ordenemos a Neiva', html)
        self.assertIn('#22804d', html); self.assertIn('#f3cc52', html)
        self.assertIn('Secretaría', html); self.assertIn('Ingresar a la plataforma', html)
        self.assertNotIn('<script>USER</script>', html); self.assertIn('Private&lt;&amp;Initial-2026!', html)
        self.assertNotIn('Private<&Initial-2026!', html)

    def test_smtp_message_has_plain_and_html_no_password_in_headers_or_logs(self):
        password = 'Private-SMTP-Fixture-2026!'
        with patch.multiple(settings, SMTP_HOST='smtp.fixture.invalid', SMTP_USER='fixture', SMTP_PASSWORD='not-real', SMTP_FROM_EMAIL='sender@fixture.invalid', SMTP_PORT=587, SMTP_TLS=True, SMTP_SSL=False), patch('app.services.email_service.smtplib.SMTP') as transport:
            server = transport.return_value.__enter__.return_value; server.send_message.return_value = {}
            with self.assertLogs('civia.email', level='INFO') as logs:
                self.assertTrue(send_welcome_email('recipient@fixture.invalid', 'ISOLATED USER', password, 'OPERADOR', 'https://portal.fixture.invalid/login'))
            message = server.send_message.call_args.args[0]
            self.assertNotIn(password, str(message.items())); self.assertNotIn(password, str(logs.output))
            self.assertNotIn('recipient@fixture.invalid', str(logs.output))
            self.assertEqual({part.get_content_type() for part in message.walk()}, {'multipart/related', 'multipart/alternative', 'text/plain', 'text/html', 'image/png'})
            server.starttls.assert_called_once()

    def test_public_app_url_rejects_unsafe_redirects(self):
        for url in ('javascript:alert(1)', 'https://user:pass@example.invalid', 'https://example.invalid?token=secret', 'http://example.invalid'):
            with self.assertRaises(ValueError): Settings(_env_file=None, ENVIRONMENT='development', PUBLIC_APP_URL=url)
