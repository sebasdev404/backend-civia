import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.v1 import api_v1_router
from app.services.password_recovery import prepare_recovery
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token, decode_access_token
from app.models.auth_session import AuthSession
from app.models.user import User


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'Fixture-password-12345'
        cls.hashed = get_password_hash(cls.password)

    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        event.listen(self.engine,'connect',lambda con,rec: con.execute('PRAGMA foreign_keys=ON'))
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        for name,role in [('person','OPERADOR'),('other','ADMIN')]:
            self.db.add(User(id=name,email=name+'@fixture.invalid',full_name='Fixture '+name,role=role,hashed_password=self.hashed,is_active=True))
        self.db.commit()
        self.app=FastAPI();self.app.include_router(api_v1_router,prefix='/api/v1')
        self.app.dependency_overrides[get_db]=lambda:self.db
        self.client=TestClient(self.app)

    def tearDown(self):
        self.client.close();self.db.close();self.engine.dispose()

    def login(self,name='person',password=None):
        response=self.client.post('/api/v1/auth/login',json={'email':name+'@fixture.invalid','password':password or self.password})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['access_token']

    def headers(self,token): return {'Authorization':'Bearer '+token}
    def me(self,token):return self.client.get('/api/v1/auth/me',headers=self.headers(token))

    def test_login_registers_session_and_checks_it_on_every_request(self):
        token=self.login()
        self.assertEqual(self.me(token).status_code,200)
        record=self.db.get(AuthSession,decode_access_token(token)['jti'])
        self.assertEqual(record.user_id,'person');self.assertIsNone(record.revoked_at)
        self.assertEqual(len(record.credential_fingerprint),64)

    def test_signed_token_without_registered_session_is_rejected(self):
        for payload in [{'sub':'person'},{'sub':'person','jti':'00000000-0000-0000-0000-000000000000'}]:
            self.assertEqual(self.me(create_access_token(payload)).status_code,401)

    def test_logout_revokes_current_token_but_preserves_other_session(self):
        first,second=self.login(),self.login()
        self.assertEqual(self.client.post('/api/v1/auth/logout',headers=self.headers(first)).status_code,200)
        self.assertEqual(self.me(first).status_code,401)
        self.assertEqual(self.me(second).status_code,200)

    def test_logout_all_revokes_own_sessions_only(self):
        first,second,other=self.login(),self.login(),self.login('other')
        self.assertEqual(self.client.post('/api/v1/auth/logout-all',headers=self.headers(first)).status_code,200)
        self.assertEqual(self.me(first).status_code,401);self.assertEqual(self.me(second).status_code,401)
        self.assertEqual(self.me(other).status_code,200)

    def test_password_change_revokes_previous_access_and_opens_new_session(self):
        first,second=self.login(),self.login()
        response=self.client.post('/api/v1/auth/change-password',headers=self.headers(first),json={'current_password':self.password,'new_password':'New-fixture-password-54321'})
        self.assertEqual(response.status_code,200,response.text)
        new=response.json()['access_token']
        self.assertEqual(self.me(first).status_code,401);self.assertEqual(self.me(second).status_code,401)
        self.assertEqual(self.me(new).status_code,200)
        rejected=self.client.post('/api/v1/auth/login',json={'email':'person@fixture.invalid','password':self.password})
        self.assertEqual(rejected.status_code,401)
        self.login(password='New-fixture-password-54321')

    def test_wrong_current_password_does_not_change_password_or_revoke_access(self):
        token=self.login()
        response=self.client.post('/api/v1/auth/change-password',headers=self.headers(token),json={'current_password':'wrong','new_password':'New-fixture-password-54321'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.db.get(User,'person').hashed_password,self.hashed)
        self.assertEqual(self.me(token).status_code,200)

    def test_password_reset_revokes_all_old_sessions_and_consumes_code(self):
        first,second=self.login(),self.login()
        user=self.db.get(User,'person');prepare_recovery(self.db,user,'123456');self.db.commit()
        payload={'email':user.email,'otp_code':'123456','new_password':'Reset-fixture-password-9999'}
        with patch('app.services.email_service.send_password_changed_email', return_value=True):
            response=self.client.post('/api/v1/auth/reset-password',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.me(first).status_code,401);self.assertEqual(self.me(second).status_code,401)
        self.assertEqual(self.me(response.json()['access_token']).status_code,200)
        self.assertIsNone(self.db.get(User,'person').reset_otp)
        self.assertEqual(self.client.post('/api/v1/auth/reset-password',json=payload).status_code,400)

    def test_registry_expiry_and_password_fingerprint_are_authoritative(self):
        first=self.login();row=self.db.get(AuthSession,decode_access_token(first)['jti'])
        row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);self.db.commit()
        self.assertEqual(self.me(first).status_code,401)
        second=self.login();self.db.get(User,'person').hashed_password=get_password_hash('Externally-updated-password-123');self.db.commit()
        self.assertEqual(self.me(second).status_code,401)

    def test_session_cannot_be_reused_with_another_subject(self):
        token=self.login()
        forged=create_access_token({**decode_access_token(token),'sub':'other'})
        self.assertEqual(self.me(forged).status_code,401)

    def test_list_discloses_only_own_valid_sessions_without_credentials(self):
        first=self.login();self.login();self.login('other')
        response=self.client.get('/api/v1/auth/sessions',headers=self.headers(first))
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()),2)
        self.assertEqual(sum(row['is_current'] for row in response.json()),1)
        self.assertNotIn('access_token',response.text);self.assertNotIn('credential_fingerprint',response.text)


if __name__=='__main__':unittest.main()
