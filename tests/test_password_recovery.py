"""Focused recovery checks. Disposable SQLite and mocked SMTP only."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from email import policy
from email.parser import BytesParser
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.v1 import api_v1_router
from app.core.database import Base, get_db
from app.core.auth_limits import _consume
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.password_recovery import PasswordRecovery, AuthRateLimit
from app.services.password_recovery import prepare_recovery
from app.services.email_service import send_otp_email, send_password_changed_email, smtp_is_configured
from app.services.email_templates import LOGO_CID


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashed = get_password_hash('Fixture-original-password-2026')

    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id='fixture', email='fixture@recovery.invalid', full_name='Fixture recovery', role='OPERADOR', hashed_password=self.hashed, is_active=True))
        self.db.commit()
        app = FastAPI(); app.include_router(api_v1_router, prefix='/api/v1')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.ready = patch('app.api.v1.auth.smtp_is_configured', return_value=True); self.ready.start()
        self.mail = patch('app.services.password_recovery.send_otp_email', return_value=True).start()
        self.notice = patch('app.services.email_service.send_password_changed_email', return_value=True).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def request_code(self, code='246810', email='fixture@recovery.invalid'):
        with patch('app.services.password_recovery.generate_otp_code', return_value=code):
            response = self.client.post('/api/v1/auth/forgot-password', json={'email': email})
        self.db.expire_all()
        return response

    def verify(self, code='246810', email='fixture@recovery.invalid'):
        return self.client.post('/api/v1/auth/verify-otp', json={'email': email, 'otp_code': code})

    def reset(self, code='246810'):
        return self.client.post('/api/v1/auth/reset-password', json={'email': 'fixture@recovery.invalid', 'otp_code': code, 'new_password': 'Fixture-new-password-2026'})

    def test_storage_and_response_do_not_disclose_code(self):
        response = self.request_code()
        self.assertEqual(response.status_code, 200)
        row = self.db.get(PasswordRecovery, 'fixture')
        self.assertEqual(len(row.code_digest), 64)
        self.assertNotIn('246810', row.code_digest)
        self.assertNotIn('246810', response.text)
        self.assertIsNone(self.db.get(User, 'fixture').reset_otp)
        self.assertNotIn('fixture@recovery.invalid', ''.join(row.key_hash for row in self.db.query(AuthRateLimit)))

    def test_request_response_is_uniform_for_active_missing_and_inactive_accounts(self):
        active = self.request_code()
        missing = self.request_code(email='missing@recovery.invalid')
        self.db.get(User, 'fixture').is_active = False; self.db.commit()
        inactive = self.request_code()
        self.assertEqual(active.json(), inactive.json())
        self.assertEqual(active.json()['message'], missing.json()['message'])
        self.assertEqual([active.status_code, missing.status_code, inactive.status_code], [200] * 3)
        self.assertEqual(self.mail.call_count, 1)

    def test_missing_smtp_is_reported_without_checking_account(self):
        with patch('app.api.v1.auth.smtp_is_configured', return_value=False):
            active = self.request_code(); missing = self.request_code(email='missing@recovery.invalid')
        self.assertEqual(active.status_code, 503)
        self.assertEqual(active.json(), missing.json())
        self.assertEqual(self.db.query(PasswordRecovery).count(), 0)
        self.mail.assert_not_called()

    def test_smtp_failure_preserves_previous_challenge_and_never_claims_delivery(self):
        self.request_code(); original = self.db.get(PasswordRecovery, 'fixture').code_digest
        self.mail.return_value = False
        response = self.request_code('135790')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['message'].startswith('Si el correo'))
        self.assertEqual(self.db.get(PasswordRecovery, 'fixture').code_digest, original)
        self.assertEqual(self.verify().status_code, 200)

    def test_resend_replaces_previous_code(self):
        self.request_code(); self.request_code('135790')
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(self.verify('135790').status_code, 200)

    def test_expiry_missing_and_wrong_code_have_same_error(self):
        missing = self.verify(email='missing@recovery.invalid')
        self.request_code(); wrong = self.verify('111111')
        self.db.get(PasswordRecovery, 'fixture').expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); self.db.commit()
        expired = self.verify()
        self.assertEqual(missing.json(), wrong.json()); self.assertEqual(wrong.json(), expired.json())
        self.assertEqual(expired.status_code, 400)

    def test_attempt_budget_is_shared_by_verify_and_reset(self):
        self.request_code()
        for _ in range(4): self.assertEqual(self.verify('111111').status_code, 400)
        self.assertEqual(self.reset('111111').status_code, 400)
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(self.db.get(PasswordRecovery, 'fixture').failed_attempts, 5)
        self.assertEqual(self.db.get(User, 'fixture').hashed_password, self.hashed)

    def test_success_consumes_code_and_sends_notice_without_password(self):
        self.request_code(); response = self.reset()
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(self.db.get(PasswordRecovery, 'fixture').used_at)
        self.assertEqual(self.reset().status_code, 400)
        self.notice.assert_called_once_with('fixture@recovery.invalid', 'Fixture recovery')

    def test_changed_password_invalidates_unused_code(self):
        self.request_code()
        self.db.get(User, 'fixture').hashed_password = get_password_hash('Other-fixture-password-2026'); self.db.commit()
        self.assertEqual(self.verify().status_code, 400)

    def test_legacy_plaintext_code_cannot_reset_password(self):
        user = self.db.get(User, 'fixture'); user.reset_otp = '246810'; user.reset_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10); self.db.commit()
        self.assertEqual(self.reset().status_code, 400)
        self.assertEqual(user.hashed_password, self.hashed)

    def test_input_rejects_non_numeric_code_and_oversized_password(self):
        self.assertEqual(self.verify('abcdef').status_code, 422)
        self.request_code()
        response = self.client.post('/api/v1/auth/reset-password', json={'email': 'fixture@recovery.invalid', 'otp_code': '246810', 'new_password': '\u00e9' * 40})
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.db.get(PasswordRecovery, 'fixture').used_at)

    def test_policy_rejection_preserves_code_and_allows_a_later_valid_reset(self):
        self.request_code()
        for password in ('lowercase-only-2026', 'NoSpecialCharacter2026', 'No-Numbers-Here', 'ALL-UPPERCASE-2026'):
            response = self.client.post('/api/v1/auth/reset-password', json={
                'email': 'fixture@recovery.invalid', 'otp_code': '246810', 'new_password': password})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(self.db.get(User, 'fixture').hashed_password, self.hashed)
            challenge = self.db.get(PasswordRecovery, 'fixture')
            self.assertIsNone(challenge.used_at)
            self.assertEqual(challenge.failed_attempts, 0)
        self.assertEqual(self.reset().status_code, 200)


class SharedLimitTests(unittest.TestCase):
    def test_multiple_connections_share_atomic_budget_and_expiry(self):
        with tempfile.TemporaryDirectory(prefix='civia-recovery-') as directory:
            engine = create_engine('sqlite:///' + directory.replace('\\', '/') + '/isolated.sqlite3', connect_args={'timeout': 15})
            Base.metadata.create_all(engine)
            def attempt(_):
                with Session(engine) as db:
                    try: _consume(db, 'fixture', 'private-identity', 3, 900); return True
                    except HTTPException as error:
                        self.assertEqual(error.status_code, 429); self.assertIn('Retry-After', error.headers); return False
            with ThreadPoolExecutor(max_workers=8) as workers:
                outcomes = list(workers.map(attempt, range(8)))
            self.assertEqual(sum(outcomes), 3)
            with Session(engine) as db:
                row = db.query(AuthRateLimit).one()
                self.assertNotIn('private-identity', row.key_hash)
                row.reset_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
            self.assertTrue(attempt(None))
            engine.dispose()


class MailTransportTests(unittest.TestCase):
    def test_tls_subject_and_html_do_not_expose_or_interpret_secrets(self):
        with patch.multiple(settings, SMTP_HOST='smtp.fixture.invalid', SMTP_USER='fixture', SMTP_PASSWORD='fixture-secret', SMTP_FROM_EMAIL='fixture@recovery.invalid', SMTP_PORT=587, SMTP_TLS=True, SMTP_SSL=False), patch('app.services.email_service.smtplib.SMTP') as transport:
            server = transport.return_value.__enter__.return_value
            server.send_message.return_value = {}
            self.assertTrue(smtp_is_configured())
            with self.assertLogs('civia.email', level='INFO') as logs:
                self.assertTrue(send_otp_email('recipient@recovery.invalid', '<img src=x>', '246810'))
            server.starttls.assert_called_once()
            message = server.send_message.call_args.args[0]
            self.assertNotIn('246810', str(message['Subject']))
            delivered = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
            html = delivered.get_body(preferencelist=('html',)).get_content()
            self.assertIn('&lt;img src=x&gt;', html)
            self.assertEqual(delivered.get_content_type(), 'multipart/related')
            self.assertIn(f'cid:{LOGO_CID}', html)
            logo = next(part for part in delivered.walk() if part.get('Content-ID') == f'<{LOGO_CID}>')
            self.assertEqual(logo.get_content_type(), 'image/png')
            self.assertEqual(logo.get_content_disposition(), 'inline')
            self.assertTrue(logo.get_payload(decode=True).startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertIn('Ordenemos a Neiva', delivered['From'])
            self.assertIn('#151515', html)
            self.assertIn('#f3cc52', html)
            self.assertNotIn('CIVIA', html)
            self.assertNotIn('CIVIA', delivered['Subject'])
            self.assertNotIn('CIVIA', delivered.get_body(preferencelist=('plain',)).get_content())
            self.assertNotIn('http://', html); self.assertNotIn('https://', html)
            self.assertNotIn('246810', str(logs.output)); self.assertNotIn('recipient@recovery.invalid', str(logs.output))

    def test_password_change_notice_uses_the_same_brand_and_embedded_logo(self):
        with patch.multiple(settings, SMTP_HOST='smtp.fixture.invalid', SMTP_USER='fixture', SMTP_PASSWORD='fixture-secret', SMTP_FROM_EMAIL='fixture@recovery.invalid', SMTP_PORT=587, SMTP_TLS=True, SMTP_SSL=False), patch('app.services.email_service.smtplib.SMTP') as transport:
            server = transport.return_value.__enter__.return_value
            server.send_message.return_value = {}
            self.assertTrue(send_password_changed_email('recipient@recovery.invalid', '<script>unsafe</script>'))
            message = BytesParser(policy=policy.default).parsebytes(server.send_message.call_args.args[0].as_bytes())
            html = message.get_body(preferencelist=('html',)).get_content()
            self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;', html)
            self.assertNotIn('<script>', html)
            self.assertIn('Ordenemos a Neiva', message['Subject'])
            self.assertIn(f'cid:{LOGO_CID}', html)
            self.assertNotIn('CIVIA', html)


if __name__ == '__main__': unittest.main()
