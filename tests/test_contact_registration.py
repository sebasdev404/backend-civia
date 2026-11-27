"""Isolated contact registration, provenance, national phone validation and uniqueness."""
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.contact_phone import normalize_phone, whatsapp_link
from app.models.citizen import Citizen
from app.models.user import User
from app.services.auth_sessions import issue_session
from app.services.citizen_import import parse_contact_file, import_contacts
from app.api.v1.citizens import router


class ContactRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        app = FastAPI(); app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.headers = {}
        for role in ('ADMIN', 'ALCALDE', 'SECRETARIO', 'OPERADOR'):
            user = User(id=role, email=role+'@fixture.invalid', full_name='ISOLATED FIXTURE', role=role, hashed_password='unused', is_active=True)
            self.db.add(user); self.db.flush()
            self.headers[role] = {'Authorization': 'Bearer '+issue_session(self.db, user)}
        self.db.commit()
        self.payload = {'name': 'ISOLATED CONTACT', 'phone': '3101234567', 'contact_origin': 'Censo', 'origin_observation': 'ISOLATED census', 'notes': 'Original note'}

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def create(self, payload=None, role='ADMIN'):
        return self.client.post('/api/v1/citizens', json=payload or self.payload, headers=self.headers[role])

    def test_phone_formats_same_key_and_invalid_lengths(self):
        for value in ('3101234567', '+57 310-123-4567', '573101234567', '0057 3101234567', 3101234567):
            self.assertEqual(normalize_phone(value), '+573101234567')
        self.assertEqual(normalize_phone('(608) 871-2345'), '+576088712345')
        for value in ('8712345', '03101234567', '+1 3101234567', '+3101234567', '3101234567/3201234567', '3101234567 ext 1', '6031234567', '1111111111', '3e9', '310123456.7', 3101234567.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError): normalize_phone(value)
        self.assertIsNone(whatsapp_link('6088712345'))
        self.assertEqual(whatsapp_link('3101234567'), 'https://wa.me/573101234567')

    def test_manual_creation_normalizes_and_rejects_duplicate(self):
        response = self.create(); self.assertEqual(response.status_code, 201, response.text)
        data = response.json(); self.assertEqual(data['phone'], '+573101234567')
        self.assertEqual(data['contact_origin'], 'Censo'); self.assertEqual(data['origin_observation'], 'ISOLATED census')
        self.assertEqual(data['user_type'], 'Sin clasificar'); self.assertEqual(data['total_reports'], 0)
        self.assertEqual(self.create({**self.payload, 'phone': '+57 310 123 4567'}).status_code, 409)
        self.assertEqual(self.db.query(Citizen).count(), 1)

    def test_roles_and_required_fields(self):
        for role in ('SECRETARIO', 'OPERADOR'): self.assertEqual(self.create(role=role).status_code, 403)
        self.assertEqual(self.create(role='ALCALDE').status_code, 201)
        for field, value in (('phone', ''), ('phone', '1234567'), ('name', ' '), ('contact_origin', 'invented'), ('origin_observation', 'x'*2001)):
            self.assertEqual(self.create({**self.payload, field: value}).status_code, 422)

    def test_database_blocks_inserts_even_without_api(self):
        self.create()
        with self.assertRaises(IntegrityError):
            self.db.execute(text("INSERT INTO citizens(id,name,handle,phone) VALUES ('other','FIXTURE','other','+573101234567')"))
            self.db.commit()
        self.db.rollback()
        self.db.add(Citizen(id='social', name='EXISTING SOCIAL', handle='social', phone=None))
        self.db.commit()

    def test_import_preview_then_commit_and_preserve_history(self):
        self.create()
        content = b'Nombre,Telefono,Notas\nCHANGED NAME,573101234567,Changed note\nNEW FIXED,6088712345,Fixed\nDUPLICATE,+57 608 8712345,Duplicate\nNO PHONE,,Missing\n'
        parsed = parse_contact_file(content, 'contacts.csv')
        provenance = {'contact_origin': 'Evento', 'origin_observation': 'ISOLATED event'}
        preview = import_contacts(self.db, parsed, preview=True, provenance=provenance)
        self.assertEqual(self.db.query(Citizen).count(), 1)
        self.assertEqual(preview['summary']['duplicates'], 1); self.assertEqual(preview['summary']['rejected'], 1)
        result = import_contacts(self.db, parsed, provenance=provenance)
        self.assertEqual(result['summary']['new_citizens_added'], 1)
        self.assertEqual(result['summary']['existing_updated'], 1)
        existing = self.db.query(Citizen).filter(Citizen.phone == '+573101234567').one()
        self.assertEqual(existing.name, 'ISOLATED CONTACT'); self.assertEqual(existing.notes, 'Original note')
        self.assertEqual(existing.source_data['history'][0]['contact_origin'], 'Censo')
        self.assertEqual(existing.contact_origin, 'Evento')
        repeat = import_contacts(self.db, parsed, provenance=provenance)
        self.assertEqual(repeat['summary']['unchanged'], 2)
        self.assertEqual(len(existing.source_data['history']), 1)

    def test_multipart_and_legacy_upload_require_origin_and_permissions(self):
        file = {'file': ('contacts.csv', b'Nombre,phone\nFIXTURE,3101234567\n')}
        self.assertEqual(self.client.post('/api/v1/citizens/import/preview', files=file, headers=self.headers['ADMIN']).status_code, 422)
        for role in ('SECRETARIO', 'OPERADOR'):
            self.assertEqual(self.client.post('/api/v1/citizens/import', files=file, data={'contact_origin':'Censo'}, headers=self.headers[role]).status_code, 403)
            self.assertEqual(self.client.post('/api/v1/citizens/upload', json={'citizens':[self.payload], 'contact_origin':'Censo'}, headers=self.headers[role]).status_code, 403)
        response = self.client.post('/api/v1/citizens/import', files=file, data={'contact_origin':'Familiar', 'origin_observation':'Family registration'}, headers=self.headers['ADMIN'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.query(Citizen).one().contact_origin, 'Familiar')
