import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.models.incident import Incident
from app.services.map_evidence import audit_incidents, location_evidence
from app.services.case_workflow import revision
from app.api.v1.cases import dispatch_case, resolve_case
from app.schemas.case import CaseDispatch, CaseResolve


class WorkflowTests(unittest.TestCase):
    def test_no_close_without_assignment(self):
        item = SimpleNamespace(status='Pendiente', assigned_department=None, assigned_to=None)
        with patch('app.api.v1.cases.writable_case', return_value=item):
            with self.assertRaises(HTTPException) as error:
                resolve_case('test', CaseResolve(resolution_note='Solución con soporte de visita', resolved_by='Operador'), MagicMock())
        self.assertEqual(error.exception.status_code, 409)

    def test_closed_cases_cannot_be_dispatched(self):
        with patch('app.api.v1.cases.writable_case', return_value=SimpleNamespace(status='Resuelto')):
            with self.assertRaises(HTTPException):
                dispatch_case('test', CaseDispatch(assigned_department='Equipo', assigned_to='Ana'), MagicMock())

    def test_dispatch_requires_named_owner(self):
        with patch('app.api.v1.cases.writable_case', return_value=SimpleNamespace(status='Pendiente')):
            with self.assertRaises(HTTPException):
                dispatch_case('test', CaseDispatch(assigned_department='Equipo'), MagicMock())

    def test_dispatch_always_records_audit_note(self):
        item = SimpleNamespace(id='isolated-case', status='Pendiente', internal_notes=None)
        db = MagicMock()
        with patch('app.api.v1.cases.writable_case', return_value=item):
            dispatch_case('test', CaseDispatch(assigned_department='Equipo', assigned_to='Ana', note='Verificar la solicitud en sitio.', confirmed_review=True, expected_revision=revision(item)), db, SimpleNamespace(full_name='Responsable real', id='test-user'))
        self.assertIn('Ana', item.internal_notes)
        self.assertEqual(item.status, 'En Gestión')
        db.commit.assert_called_once()


class MapEvidenceTests(unittest.TestCase):
    def test_place_in_derived_metadata_is_not_evidence(self):
        self.assertIsNone(location_evidence("Mención explícita en texto: 'chapinero'", 'Buenísimo'))
        self.assertIsNone(location_evidence("Mención explícita en texto: 'centro'", 'descentralizado'))

    def test_accents_are_normalized(self):
        self.assertEqual(location_evidence("Mención explícita en texto: 'cándido'", 'En Candido hay una fuga'), 'cándido')

    def test_only_traceable_mentions_are_displayed_without_random_offsets(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(MetaPost(id='p', title='Origen', published_at='hoy', raw_comments_json=json.dumps([
                {'id': 'good', 'content': 'En Chapinero hay una fuga'}, {'id': 'bad', 'content': 'Buenísimo'}])))
            for key in ('good', 'bad', 'missing'):
                db.add(Case(id=key, title='Caso', content='Metadatos no son evidencia', author='Ciudadano', source='Facebook', category='Agua', priority='Media', sentiment='Neutro', location='Chapinero', date_time='hoy', internal_notes=f'[Post ID]: p\n[Comment ID]: {key}'))
                db.add(Incident(id=key, lat=2.999, lng=-75.999, title='Caso', description="Mención explícita en texto: 'chapinero'", category='Agua', priority='Media', sentiment='Neutro', source='Facebook', neighborhood='Chapinero', zone='comuna-3', date_time='hoy'))
            db.commit()
            items, audit = audit_incidents(db, db.query(Incident).all())
            self.assertEqual([i['id'] for i in items], ['good'])
            self.assertEqual(items[0]['lat'], 2.9320)
            self.assertEqual(items[0]['verification_status'], 'territorial_mention')
            self.assertEqual(audit['excluded'], 2)
            self.assertEqual(db.query(Incident).count(), 3)
        engine.dispose()
