"""Test dispatch corrections use isolated fixtures, never production comments."""
import unittest
import uuid
from tests import test_case_consolidation as fixtures
from app.api.v1.case_corrections import router
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.case_correction import CaseCorrection
from app.models.case_provenance import CaseProvenanceReview


class CorrectionTests(unittest.TestCase):
    auth = fixtures.ConsolidationTests.auth
    snapshot = fixtures.ConsolidationTests.snapshot
    tearDown = fixtures.ConsolidationTests.tearDown

    def setUp(self):
        fixtures.ConsolidationTests.setUp(self)
        self.client.app.include_router(router, prefix='/api/v1')
        self.db.get(Case, 'a').internal_notes += '\n[Fixture date] [Despacho a Fixture department]: Despacho de prueba'
        self.db.commit()

    def preview(self):
        return self.client.get('/api/v1/case-corrections/case/a', headers=self.headers)

    def payload(self, **changes):
        return {**dict(request_id=str(uuid.uuid4()), case_id='a', revision=self.preview().json()['revision'],
                       reason='Human review of the explicitly recorded test dispatch', disposition='needs_review', confirmed_review=True), **changes}

    def save(self, payload=None, headers=None):
        return self.client.post('/api/v1/case-corrections', headers=headers or self.headers, json=payload or self.payload())

    def undo(self, key):
        return self.client.post(f'/api/v1/case-corrections/{key}/undo', headers=self.headers, json={'reason': 'Revert the isolated correction test'})

    def test_preview_requires_explicit_latest_test_assignment_and_exact_source(self):
        result=self.preview().json()
        self.assertEqual(result['blockers'], [])
        self.assertIn('Despacho de prueba', result['test_note'])
        self.assertEqual(result['source']['comment']['message'], 'Isolated citizen request')
        self.db.get(Case, 'a').internal_notes += '\n[Later date] [Asignación CIVIA a Another owner]: Real work'
        self.db.commit()
        self.assertTrue(self.preview().json()['blockers'])
        self.assertEqual(self.save().status_code, 409)

    def test_correction_clears_test_assignment_without_inventing_classification(self):
        before=self.snapshot(CaseComment), self.snapshot(CaseProvenanceReview)
        payload=self.payload()
        response=self.save(payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.save(payload).status_code, 200)
        self.assertEqual(self.db.query(CaseCorrection).count(), 1)
        row=self.db.get(Case, 'a')
        self.assertEqual(row.status, 'Pendiente')
        self.assertTrue(row.requires_followup)
        self.assertIsNone(row.assigned_to)
        self.assertIsNone(row.assigned_department)
        self.assertIn('Despacho de prueba', row.internal_notes)
        self.assertIn('Corrección CIVIA por admin', row.internal_notes)
        self.assertEqual(before, (self.snapshot(CaseComment), self.snapshot(CaseProvenanceReview)))
        self.assertEqual(self.client.delete('/api/v1/cases/a').status_code, 409)

    def test_human_opinion_decision_does_not_mark_case_resolved(self):
        self.assertEqual(self.save(self.payload(disposition='general_opinion')).status_code, 200)
        row=self.db.get(Case, 'a')
        self.assertEqual(row.status, 'No requiere gestión')
        self.assertFalse(row.requires_followup)
        self.assertIsNone(row.resolution_note)
        self.assertIsNone(row.resolved_by)

    def test_undo_restores_only_changed_fields_and_keeps_audit_notes(self):
        before=self.db.get(Case, 'a')
        status, owner, department, followup = before.status, before.assigned_to, before.assigned_department, before.requires_followup
        key=self.save().json()['id']
        self.assertEqual(self.undo(key).status_code, 200)
        self.assertEqual(self.undo(key).status_code, 200)
        row=self.db.get(Case, 'a')
        self.assertEqual((row.status,row.assigned_to,row.assigned_department,row.requires_followup), (status,owner,department,followup))
        self.assertIn('Corrección CIVIA',row.internal_notes)
        self.assertIn('Reversión de corrección',row.internal_notes)

    def test_later_work_blocks_undo_without_overwriting_it(self):
        key=self.save().json()['id']
        self.client.post('/api/v1/cases/a/notes', headers=self.headers,json={'note':'Subsequent real work','author_name':'Fixture', 'expected_revision':self.client.get('/api/v1/cases/a',headers=self.headers).json()['workflow_revision']})
        self.assertEqual(self.undo(key).status_code, 409)
        self.assertIn('Subsequent real work',self.db.get(Case,'a').internal_notes)
        self.assertIsNone(self.db.get(Case,'a').assigned_to)

    def test_stale_preview_cannot_clear_new_work(self):
        payload=self.payload()
        self.db.get(Case,'a').internal_notes+='\nNew note'
        self.db.commit()
        self.assertEqual(self.save(payload).status_code, 409)
        self.assertEqual(self.db.query(CaseCorrection).count(),0)

    def test_rejects_real_work_and_missing_capture(self):
        row=self.db.get(Case,'a'); row.public_response='A real response draft'; self.db.commit()
        self.assertEqual(self.save().status_code,409)
        row.public_response=None; row.author='Different author'; self.db.commit()
        self.assertEqual(self.save().status_code,409)

    def test_auth_confirmation_and_meaningful_reason_are_required(self):
        payload=self.payload()
        self.assertEqual(self.client.post('/api/v1/case-corrections',json=payload).status_code,401)
        self.assertEqual(self.save(payload,self.auth('operator')).status_code,403)
        self.assertEqual(self.save({**payload,'confirmed_review':False}).status_code,422)
        self.assertEqual(self.save({**payload,'reason':'          '}).status_code,422)

    def test_idempotency_key_cannot_be_reused_for_other_decision(self):
        payload=self.payload()
        self.save(payload)
        self.assertEqual(self.save({**payload,'disposition':'general_opinion'}).status_code,409)

    def test_active_consolidation_blocks_correction_and_later_correction_undo(self):
        def consolidate():
            pair={'primary_case_id':'a','duplicate_case_id':'b'}
            value=self.client.post('/api/v1/case-consolidations/compare',headers=self.headers,json=pair).json()
            response=self.client.post('/api/v1/case-consolidations',headers=self.headers,json={**pair,
                'request_id':str(uuid.uuid4()),'revision':value['revision'],'reason':'Isolated pair review for integration test','confirmed_same_request':True})
            self.assertEqual(response.status_code,200,response.text)
            return response.json()['id']
        pair_id=consolidate()
        self.assertEqual(self.save().status_code,409)
        self.client.post(f'/api/v1/case-consolidations/{pair_id}/undo',headers=self.headers,json={'reason':'Undo isolated pair to test correction'})
        correction_id=self.save().json()['id']
        consolidate()
        self.assertEqual(self.undo(correction_id).status_code,409)


if __name__ == '__main__': unittest.main()
