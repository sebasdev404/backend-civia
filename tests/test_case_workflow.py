from tests.auth_helpers import prime_sessions, fixture_token
"""Full HTTP workflow on isolated SQLite, with real auth and no external calls."""
import json
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.v1 import api_v1_router
from app.core.database import Base, get_db
from app.models.case import Case
from app.models.case_workflow import CaseWorkflowEvent
from app.models.case_comment import CaseComment
from app.models.citizen import Citizen
from app.models.user import User
from app.models.meta_post import MetaPost
from app.services.case_workflow import snapshot


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        event.listen(self.engine, 'connect', lambda con, rec: con.execute('PRAGMA foreign_keys=ON'))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        for role in ('ADMIN', 'SECRETARIO', 'OPERADOR', 'ALCALDE'):
            self.db.add(User(id=role, email=role.lower()+'@fixture.invalid', full_name='Fixture '+role, role=role, hashed_password='unused', is_active=True))
        self.db.add(Case(id='work', source='Facebook', author='Autor de prueba', title='Solicitud de prueba', content='Revisar una fuga en el sitio indicado.', category='Servicios', priority='Media', sentiment='Sin analizar', status='Pendiente', location='Sin verificar', date_time='2026-11-25', internal_notes='[Post ID]: origin\n[Comment ID]: comment', requires_followup=True))
        self.db.add(MetaPost(id='origin', title='Publicación de prueba', source='Facebook', permalink_url='https://example.invalid/fixture', published_at='2026-11-25', raw_comments_json=json.dumps([{'id':'comment','author':'Autor de prueba','content':'Revisar una fuga en el sitio indicado.'}])))
        self.db.add(Citizen(id='citizen', name='Autor de prueba', handle='@fixture', channel='Facebook'))
        self.db.add(Citizen(id='other', name='Otra persona', handle='@other', channel='Facebook'))
        self.db.commit()
        prime_sessions(self.db)
        self.app = FastAPI()
        self.app.include_router(api_v1_router, prefix='/api/v1')
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close(); self.db.close(); self.engine.dispose()

    def headers(self, role='ADMIN'):
        return {'Authorization': 'Bearer ' + fixture_token(self.db, role)}

    def read(self, case_id='work'):
        response = self.client.get('/api/v1/cases/'+case_id, headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def action(self, suffix, data=None, role='ADMIN', *, version=None):
        payload = {'expected_revision':version or self.read()['workflow_revision'], **(data or {})}
        return self.client.post('/api/v1/cases/work/'+suffix, headers=self.headers(role), json=payload)

    def assign(self, **updates):
        return self.action('dispatch', {'assigned_department':'Equipo de prueba','assigned_to':'Responsable de prueba','note':'Verificar la fuga y documentar el resultado.', 'confirmed_review':True, **updates}, role='SECRETARIO')

    def close(self, **updates):
        return self.action('resolve', {'resolution_note':'Verificación de la reparación en esta fixture aislada.', 'evidence_reference':'Acta de prueba AISLADA-001','confirmed_resolution':True, **updates},role='SECRETARIO')

    def stable_state(self):
        return (snapshot(self.db.get(Case,'work')), self.db.get(Case,'work').internal_notes, self.db.query(CaseWorkflowEvent).count())

    def test_complete_assignment_followup_draft_close_and_reload(self):
        original=self.read()
        self.assertEqual(self.assign().status_code,200)
        self.assertEqual(self.action('notes',{'note':'Se realizó la inspección de prueba.'},role='OPERADOR').status_code,200)
        self.assertEqual(self.action('public-response',{'public_response':'Borrador de prueba sin envío.'},role='OPERADOR').status_code,200)
        self.assertEqual(self.close().status_code,200)
        result=self.read()
        self.assertEqual(result['status'],'Resuelto')
        self.assertFalse(result['requires_followup'])
        self.assertEqual(result['resolved_by'],'Fixture SECRETARIO')
        self.assertEqual(result['content'],original['content'])
        self.assertEqual(result['author'],original['author'])
        self.assertIn('[Comment ID]: comment',result['internal_notes'])
        self.assertCountEqual([row['event_type'] for row in result['workflow_events']],['assigned','note_added','response_drafted','resolved'])
        self.assertEqual([row['event_type'] for row in result['workflow_events']],['resolved','response_drafted','note_added','assigned'])
        resolved=next(row for row in result['workflow_events'] if row['event_type']=='resolved')
        self.assertEqual(resolved['evidence_reference'],'Acta de prueba AISLADA-001')
        self.assertEqual(resolved['actor_id'],'SECRETARIO')
        self.assertEqual(resolved['before_state']['status'],'En Gestión')
        self.assertEqual(resolved['after_state']['status'],'Resuelto')
        self.assertIsNone(result['institutional_radicado'])

    def test_general_patch_cannot_bypass_state_or_replace_source(self):
        for payload in [{'status':'Resuelto'},{'status':None},{'assigned_to':'Fake'},{'assigned_department':'Fake'},
                        {'internal_notes':'[Post ID]: forged'},{'resolution_note':'Fake solution'},{'resolved_by':'Fake'},
                        {'public_response':'Fake'},{'requires_followup':False},{'comments_count':9000},
                        {'institutional_radicado':'CIV-2026-001'},{'priority_action':True}]:
            before=self.stable_state()
            response=self.client.patch('/api/v1/cases/work',headers=self.headers(),json={**payload,'expected_revision':self.read()['workflow_revision']})
            self.assertEqual(response.status_code,422,(payload,response.text))
            self.assertEqual(self.stable_state(),before)

    def test_assignment_requires_review_person_department_and_instruction(self):
        for updates in [{'confirmed_review':False},{'assigned_to':' '},{'assigned_department':' '},{'note':' '},{'note':'short'}, {'assigned_to':'x'*101}]:
            before=self.stable_state()
            self.assertEqual(self.assign(**updates).status_code,422,updates)
            self.assertEqual(self.stable_state(),before)

    def test_cannot_close_without_assignment_even_with_a_long_note(self):
        before=self.stable_state()
        self.assertEqual(self.close().status_code,409)
        self.assertEqual(self.stable_state(),before)

    def test_pending_case_with_legacy_owner_is_not_an_active_assignment(self):
        row=self.db.get(Case,'work');row.assigned_to='Legacy';row.assigned_department='Legacy';self.db.commit()
        self.assertEqual(self.close().status_code,409)

    def test_close_requires_support_confirmation_and_substantive_result(self):
        self.assertEqual(self.assign().status_code,200)
        for updates in [{'evidence_reference':None},{'evidence_reference':' '},{'confirmed_resolution':False},{'resolution_note':' '},{'resolution_note':'short'}]:
            before=self.stable_state()
            self.assertEqual(self.close(**updates).status_code,422,updates)
            self.assertEqual(self.stable_state(),before)

    def test_closed_case_rejects_ordinary_attention_actions(self):
        self.assign();self.close();before=self.stable_state()
        for suffix,payload in [('dispatch',{'assigned_department':'Other','assigned_to':'Other','note':'New instruction','confirmed_review':True}),
                               ('resolve',{'resolution_note':'Another attempted closure.'}),('notes',{'note':'After closure'}),
                               ('public-response',{'public_response':'After closure'}),('priority-action',{'priority_action':True}),
                               ('no-request',{'reason':'Attempted discard after closure.','confirmed_review':True})]:
            self.assertEqual(self.action(suffix,payload).status_code,409,suffix)
            self.assertEqual(self.stable_state(),before)

    def test_no_request_is_a_reasoned_decision_and_never_counts_as_resolution(self):
        result=self.action('no-request',{'reason':'El mensaje es una conversación general sin solicitud concreta.','confirmed_review':True})
        self.assertEqual(result.status_code,200,result.text)
        row=self.read()
        self.assertEqual(row['status'],'No requiere gestión')
        self.assertFalse(row['requires_followup'])
        self.assertIsNone(row['resolution_note']);self.assertIsNone(row['resolved_by'])
        self.assertEqual(row['workflow_events'][0]['event_type'],'no_request')
        self.assertIn('[Post ID]: origin',row['internal_notes'])
        metrics=self.client.get('/api/v1/analytics/overview',headers=self.headers()).json()['cases']
        self.assertEqual(metrics['no_request'],1)
        self.assertEqual(metrics['resolved'],0)
        self.assertEqual(metrics['open'],0)

    def test_no_request_cannot_discard_an_assigned_case(self):
        self.assign();before=self.stable_state()
        result=self.action('no-request',{'reason':'Reason long enough for an attempted discard.','confirmed_review':True})
        self.assertEqual(result.status_code,409)
        self.assertEqual(self.stable_state(),before)

    def test_no_request_requires_reason_and_review(self):
        for data in [{'reason':'short','confirmed_review':True},{'reason':'Reason is long enough but not reviewed.','confirmed_review':False}]:
            self.assertEqual(self.action('no-request',data).status_code,422)
        self.assertEqual(self.db.query(CaseWorkflowEvent).count(),0)

    def test_stale_version_prevents_lost_updates_and_duplicate_notes(self):
        version=self.read()['workflow_revision']
        self.assertEqual(self.action('notes',{'note':'First committed note.'},version=version).status_code,200)
        before=self.stable_state()
        self.assertEqual(self.action('notes',{'note':'Repeated or stale note.'},version=version).status_code,409)
        self.assertEqual(self.stable_state(),before)

    def test_actions_without_reviewed_version_are_rejected(self):
        response=self.client.post('/api/v1/cases/work/notes',headers=self.headers(),json={'note':'Must not save without a revision.'})
        self.assertEqual(response.status_code,422)
        self.assertEqual(self.db.query(CaseWorkflowEvent).count(),0)

    def test_origin_markers_in_a_note_do_not_change_the_reference(self):
        response=self.action('notes',{'note':'[Post ID]: forged\n[Comment ID]: forged'})
        self.assertEqual(response.status_code,200)
        case=self.read()
        self.assertEqual(case['post_data']['id'],'origin')
        self.assertNotIn('[Post ID]: forged',case['internal_notes'])
        self.assertIn('[Post ID]: forged',case['workflow_events'][0]['note'])

    def test_priority_action_sets_explicit_value_and_audits_real_actor(self):
        self.assertEqual(self.action('priority-action',{'priority_action':True},role='ALCALDE').status_code,200)
        count=self.db.query(CaseWorkflowEvent).count()
        self.assertEqual(self.action('priority-action',{'priority_action':True},role='ALCALDE').status_code,200)
        self.assertEqual(self.db.query(CaseWorkflowEvent).count(),count)
        self.assertEqual(self.read()['workflow_events'][0]['actor_id'],'ALCALDE')

    def test_blank_notes_and_drafts_cannot_clear_existing_information(self):
        self.action('public-response',{'public_response':'A saved draft.'})
        before=self.stable_state()
        self.assertEqual(self.action('public-response',{'public_response':' '}).status_code,422)
        self.assertEqual(self.action('notes',{'note':' '}).status_code,422)
        self.assertEqual(self.stable_state(),before)

    def test_citizen_reply_uses_same_draft_rules_without_advancing_state(self):
        response=self.client.post('/api/v1/citizens/citizen/reply',headers=self.headers('OPERADOR'),json={
            'case_id':'work','reply_text':'Borrador guardado sin envío.','expected_revision':self.read()['workflow_revision']})
        self.assertEqual(response.status_code,200,response.text)
        row=self.read()
        self.assertEqual(row['status'],'Pendiente')
        self.assertEqual(row['public_response'],'Borrador guardado sin envío.')
        self.assertEqual(row['workflow_events'][0]['actor_id'],'OPERADOR')

    def test_citizen_reply_cannot_close_or_advance_case(self):
        for status in ('Resuelto','En Gestión','No requiere gestión'):
            before=self.stable_state()
            response=self.client.post('/api/v1/citizens/citizen/reply',headers=self.headers(),json={
                'case_id':'work','reply_text':'Attempted bypass.','status':status,'expected_revision':self.read()['workflow_revision']})
            self.assertEqual(response.status_code,422)
            self.assertEqual(self.stable_state(),before)

    def test_citizen_reply_rejects_stale_version_unrelated_contact_and_closed_case(self):
        version=self.read()['workflow_revision'];self.assign()
        data={'case_id':'work','reply_text':'Draft','expected_revision':version}
        self.assertEqual(self.client.post('/api/v1/citizens/citizen/reply',headers=self.headers(),json=data).status_code,409)
        data['expected_revision']=self.read()['workflow_revision']
        self.assertEqual(self.client.post('/api/v1/citizens/other/reply',headers=self.headers(),json=data).status_code,409)
        self.close();data['expected_revision']=self.read()['workflow_revision']
        self.assertEqual(self.client.post('/api/v1/citizens/citizen/reply',headers=self.headers(),json=data).status_code,409)

    def test_citizen_history_never_uses_arbitrary_post_or_calls_ai(self):
        self.db.get(Case,'work').internal_notes='No source reference';self.db.commit()
        with patch('app.api.v1.citizens.ai_classifier.generate_smart_response') as ai:
            result=self.client.get('/api/v1/citizens/citizen/comments',headers=self.headers()).json()
            ai.assert_not_called()
        self.assertEqual(len(result['comments']),1)
        self.assertIsNone(result['comments'][0]['post']['id'])
        self.assertIsNone(result['comments'][0]['post']['permalink_url'])
        self.assertIsNone(result['comments'][0]['ai_suggestion'])
        self.assertEqual(result['relationship_status'],'name_match_unverified')

    def test_new_case_cannot_start_closed_or_with_fabricated_workflow(self):
        base={'source':'Manual','author':'Fixture','priority':'Media','title':'Test request','content':'Manual fixture request.', 'category':'General','sentiment':'Sin analizar','location':'Sin verificar'}
        for update in [{'status':'Resuelto'},{'status':'En Gestión'},{'assigned_to':'Fake owner'},{'internal_notes':'[Post ID]: forged'},
                       {'institutional_radicado':'Fake radicado'},{'priority_action':True},{'comments_count':100}]:
            response=self.client.post('/api/v1/cases',headers=self.headers('OPERADOR'),json={**base,**update})
            self.assertEqual(response.status_code,422,(update,response.text))
        self.assertEqual(self.db.query(Case).count(),1)
        response=self.client.post('/api/v1/cases',headers=self.headers('OPERADOR'),json=base)
        self.assertEqual(response.status_code,201,response.text)
        row=self.read(response.json()['id'])
        self.assertEqual(row['status'],'Pendiente')
        self.assertIsNone(row['institutional_radicado']);self.assertIsNone(row['zone'])
        self.assertEqual(row['workflow_events'][0]['actor_id'],'OPERADOR')

    def test_case_with_workflow_history_cannot_be_deleted(self):
        self.action('notes',{'note':'An audited note.'})
        self.assertEqual(self.client.delete('/api/v1/cases/work',headers=self.headers()).status_code,409)
        self.assertEqual(self.db.query(CaseWorkflowEvent).count(),1)

    def test_classification_uses_reviewed_version_and_preserves_workflow(self):
        before=snapshot(self.db.get(Case,'work'))
        response=self.client.patch('/api/v1/cases/work',headers=self.headers('SECRETARIO'),json={'priority':'Alta','category':'Infraestructura','expected_revision':self.read()['workflow_revision']})
        self.assertEqual(response.status_code,200,response.text)
        after=snapshot(self.db.get(Case,'work'))
        self.assertEqual(after['status'],before['status'])
        self.assertEqual(after['assigned_to'],before['assigned_to'])
        self.assertEqual(after['priority'],'Alta')
        self.assertEqual(self.read()['workflow_events'][0]['event_type'],'classified')

    def test_capture_review_creation_assignment_followup_and_closure_preserve_source(self):
        raw=json.dumps([{'id':'fresh-comment','author':'Autor de prueba','content':'Otra solicitud de prueba aislada.','time':'2026-11-25T10:00:00Z'}])
        self.db.add(MetaPost(id='fresh-post',title='Nueva fixture',source='Facebook',published_at='2026-11-25',raw_comments_json=raw));self.db.commit()
        payload={'comments':[{'post_id':'fresh-post','comment_id':'fresh-comment'}]}
        created=self.client.post('/api/v1/triage/consolidate',headers=self.headers('OPERADOR'),json=payload)
        self.assertEqual(created.status_code,200,created.text)
        key=created.json()['case_id']
        self.assertTrue(created.json()['created'])
        repeated=self.client.post('/api/v1/triage/consolidate',headers=self.headers('OPERADOR'),json=payload)
        self.assertEqual(repeated.status_code,200)
        self.assertEqual(repeated.json()['case_id'],key)
        def act(suffix,data,role='SECRETARIO'):
            return self.client.post('/api/v1/cases/'+key+'/'+suffix,headers=self.headers(role),json={**data,'expected_revision':self.read(key)['workflow_revision']})
        self.assertEqual(act('dispatch',{'assigned_department':'Equipo','assigned_to':'Ana','note':'Verificar el reporte en sitio.','confirmed_review':True}).status_code,200)
        self.assertEqual(act('notes',{'note':'Visita documentada en la fixture.'},'OPERADOR').status_code,200)
        self.assertEqual(act('resolve',{'resolution_note':'Resultado registrado en la prueba aislada.','evidence_reference':'Acta de prueba 002','confirmed_resolution':True}).status_code,200)
        result=self.read(key)
        self.assertEqual(result['content'],'Otra solicitud de prueba aislada.')
        self.assertEqual(result['linked_comments'][0]['comment_id'],'fresh-comment')
        self.assertEqual(result['linked_comments'][0]['comment']['content'],'Otra solicitud de prueba aislada.')
        self.assertEqual(result['workflow_events'][-1]['event_type'],'created_from_comments')
        self.assertEqual(result['workflow_events'][-1]['actor_id'],'OPERADOR')
        self.assertEqual(result['status'],'Resuelto')
        self.assertEqual(self.db.get(MetaPost,'fresh-post').raw_comments_json,raw)
        self.assertEqual(self.db.query(CaseComment).count(),1)

    def test_unknown_state_cannot_receive_more_comments(self):
        self.db.get(Case,'work').status='Estado histórico sin revisar';self.db.commit()
        response=self.client.post('/api/v1/triage/consolidate',headers=self.headers('OPERADOR'),json={'comments':[{'post_id':'origin','comment_id':'comment'}],'target_case_id':'work'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.db.query(CaseComment).count(),0)

    def test_commit_failure_rolls_back_case_and_audit_event_together(self):
        before=self.stable_state()
        with patch.object(self.db,'commit',side_effect=RuntimeError('Isolated commit failure')):
            with self.assertRaises(RuntimeError):
                self.action('notes',{'note':'Must not persist without its event.'})
        self.db.expire_all()
        self.assertEqual(self.stable_state(),before)

    def test_generic_protected_author_is_not_a_citizen_identity_link(self):
        protected='Usuario de Facebook (Perfil Protegido por Meta)'
        self.db.get(Citizen,'citizen').name=protected;self.db.get(Case,'work').author=protected;self.db.commit()
        response=self.client.get('/api/v1/citizens/citizen/comments',headers=self.headers())
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['comments'],[])
        write=self.client.post('/api/v1/citizens/citizen/reply',headers=self.headers(),json={'case_id':'work','reply_text':'Do not link protected identity.','expected_revision':self.read()['workflow_revision']})
        self.assertEqual(write.status_code,409)

    def test_case_identifiers_are_not_guessed_from_shared_numeric_suffixes(self):
        from app.services.case_workflow import revision
        row=Case(id='CIV-2026-0042', source='Manual', author='Fixture', title='Exact ID', content='Fixture request.', category='General', priority='Media', sentiment='Sin analizar', status='Pendiente', location='Sin verificar', date_time='2026-11-25')
        self.db.add(row);self.db.commit()
        self.assertEqual(self.client.get('/api/v1/cases/CASO-042',headers=self.headers()).status_code,404)
        response=self.client.post('/api/v1/cases/CASO-042/notes',headers=self.headers(),json={'note':'Must not target another ID.','expected_revision':revision(row)})
        self.assertEqual(response.status_code,404)
        self.assertIsNone(self.db.get(Case,'CIV-2026-0042').internal_notes)

    def test_ambiguous_external_reference_is_not_resolved_to_an_arbitrary_case(self):
        self.db.get(Case,'work').institutional_radicado='EXTERNAL-FIXTURE'
        self.db.add(Case(id='other-case', source='Manual',author='Fixture',title='Fixture',content='Other fixture',category='General',priority='Media',sentiment='Sin analizar',status='Pendiente',location='Sin verificar',date_time='2026-11-25',institutional_radicado='EXTERNAL-FIXTURE'))
        self.db.commit()
        response=self.client.get('/api/v1/cases/EXTERNAL-FIXTURE',headers=self.headers())
        self.assertEqual(response.status_code,409)

    def reopen(self, **updates):
        return self.action('reopen', {'reason':'La situación persiste y requiere revisar la decisión anterior.', 'confirmed_reopening':True, **updates}, role='SECRETARIO')

    def test_reopen_preserves_previous_closure_and_clears_current_cycle(self):
        self.assign()
        self.action('public-response', {'public_response':'Borrador del ciclo anterior.'})
        self.close()
        old = self.read()
        result = self.reopen()
        self.assertEqual(result.status_code,200,result.text)
        row = self.read()
        self.assertEqual(row['status'],'Pendiente');self.assertTrue(row['requires_followup'])
        for key in ('assigned_department','assigned_to','resolution_note','resolved_by','public_response'):
            self.assertIsNone(row[key],key)
        for key in ('id','title','content','author','source','category','priority','comments_count','linked_comments','post_data'):
            self.assertEqual(row[key],old[key],key)
        previous = {event['id']:event for event in row['workflow_events'] if event['event_type']!='reopened'}
        self.assertEqual(previous,{event['id']:event for event in old['workflow_events']})
        event = next(event for event in row['workflow_events'] if event['event_type']=='reopened')
        self.assertEqual(event['actor_id'],'SECRETARIO')
        self.assertEqual(event['before_state']['resolution_note'],old['resolution_note'])
        self.assertEqual(event['before_state']['public_response'],'Borrador del ciclo anterior.')
        self.assertEqual(event['after_state']['status'],'Pendiente')
        self.assertEqual(event['before_state']['resolved_by'],'Fixture SECRETARIO')
        self.assertIn(old['internal_notes'],row['internal_notes'])

    def test_reopen_no_request_preserves_decision_and_reactivates_review(self):
        reason = 'El texto disponible no contiene una solicitud de atención.'
        self.action('no-request',{'reason':reason,'confirmed_review':True})
        self.assertEqual(self.reopen().status_code,200)
        row = self.read()
        self.assertEqual(row['status'],'Pendiente')
        self.assertEqual(next(e for e in row['workflow_events'] if e['event_type']=='no_request')['note'],reason)
        self.assertEqual(next(e for e in row['workflow_events'] if e['event_type']=='reopened')['before_state']['status'],'No requiere gestión')
        metrics=self.client.get('/api/v1/analytics/overview',headers=self.headers()).json()['cases']
        self.assertEqual(metrics['open'],1);self.assertEqual(metrics['resolved'],0);self.assertEqual(metrics['no_request'],0)

    def test_reopen_rejects_open_and_unknown_states_without_changes(self):
        for state in ('Pendiente','En Gestión','Unknown legacy state'):
            self.db.get(Case,'work').status=state;self.db.commit();before=self.stable_state()
            self.assertEqual(self.reopen().status_code,409)
            self.assertEqual(self.stable_state(),before)

    def test_reopen_requires_reason_confirmation_revision_and_no_forged_actor(self):
        self.assign();self.close()
        for updates in ({'reason':'short'}, {'reason':' '*25}, {'reason':'x'*10001}, {'confirmed_reopening':False}, {'confirmed_reopening':'true'}, {'resolved_by':'Forged identity'}):
            before=self.stable_state()
            self.assertEqual(self.reopen(**updates).status_code,422,updates)
            self.assertEqual(self.stable_state(),before)
        response=self.client.post('/api/v1/cases/work/reopen',headers=self.headers(),json={'reason':'A valid reason but no reviewed version.','confirmed_reopening':True})
        self.assertEqual(response.status_code,422)

    def test_reopen_roles_and_authentication(self):
        self.assign();self.close();before=self.stable_state()
        payload={'reason':'New evidence justifies reviewing this closed case.','confirmed_reopening':True}
        for role in ('OPERADOR','ALCALDE'):
            self.assertEqual(self.action('reopen',payload,role=role).status_code,403)
            self.assertEqual(self.stable_state(),before)
        self.assertEqual(self.client.post('/api/v1/cases/work/reopen',json=payload).status_code,401)
        for role in ('ADMIN','SECRETARIO'):
            self.assertEqual(self.action('reopen',payload,role=role).status_code,200)
            self.assertEqual(next(e for e in self.read()['workflow_events'] if e['event_type']=='reopened')['actor_id'],role)
            self.assign();self.close()

    def test_reopen_rejects_stale_revision_and_duplicate_submission(self):
        self.assign();self.close();old_version=self.read()['workflow_revision']
        self.db.get(Case,'work').resolution_note='A corrected closure note added by another operation.';self.db.commit()
        before=self.stable_state()
        payload={'reason':'A valid reason with a stale view of the closure.','confirmed_reopening':True}
        self.assertEqual(self.action('reopen',payload,version=old_version).status_code,409)
        self.assertEqual(self.stable_state(),before)
        valid_version=self.read()['workflow_revision']
        self.assertEqual(self.action('reopen',payload,version=valid_version).status_code,200)
        after=self.stable_state()
        self.assertEqual(self.action('reopen',payload,version=valid_version).status_code,409)
        self.assertEqual(self.stable_state(),after)
        self.assertEqual(self.db.query(CaseWorkflowEvent).filter_by(event_type='reopened').count(),1)

    def test_reopen_cannot_modify_a_consolidated_duplicate(self):
        from app.models.case_consolidation import CaseConsolidation
        from datetime import datetime, timezone
        self.assign();self.close()
        self.db.add(Case(id='principal',source='Manual',author='Fixture',title='Primary fixture',content='Original',category='General',priority='Media',sentiment='Sin analizar',status='Pendiente',location='Sin verificar',date_time='2026-11-25'))
        self.db.flush()
        self.db.add(CaseConsolidation(id='fixture-operation',primary_case_id='principal',duplicate_case_id='work',reason='Fixture only',created_by='ADMIN',created_at=datetime.now(timezone.utc),evidence_json={}))
        self.db.commit();before=self.stable_state()
        self.assertEqual(self.reopen().status_code,409)
        self.assertEqual(self.stable_state(),before)

    def test_reopen_and_audit_roll_back_together_on_commit_failure(self):
        self.assign();self.close();before=self.stable_state()
        with patch.object(self.db,'commit',side_effect=RuntimeError('Isolated commit failure')):
            with self.assertRaises(RuntimeError):self.reopen()
        self.assertEqual(self.stable_state(),before)

    def test_reopened_case_requires_new_assignment_and_keeps_multiple_closures(self):
        self.assign();self.close();self.reopen()
        self.assertEqual(self.close().status_code,409)
        self.assign(assigned_to='New fixture owner')
        self.assertEqual(self.close(resolution_note='Second repair verified in this isolated fixture.',evidence_reference='Acta de prueba AISLADA-002').status_code,200)
        row=self.read();closures=[e for e in row['workflow_events'] if e['event_type']=='resolved']
        self.assertEqual(len(closures),2)
        self.assertEqual({e['evidence_reference'] for e in closures},{'Acta de prueba AISLADA-001','Acta de prueba AISLADA-002'})
        self.assertEqual(row['resolution_note'],'Second repair verified in this isolated fixture.')

    def test_reopen_legacy_closure_records_snapshot_without_inventing_old_events(self):
        case=self.db.get(Case,'work');case.status='Resuelto';case.resolution_note='Texto histórico de cierre conservado.';case.resolved_by='Nombre histórico no verificado';self.db.commit()
        self.assertEqual(self.reopen().status_code,200)
        row=self.read()
        self.assertEqual([e['event_type'] for e in row['workflow_events']],['reopened'])
        self.assertEqual(row['workflow_events'][0]['before_state']['resolution_note'],'Texto histórico de cierre conservado.')

    def test_map_and_metrics_read_current_case_state_after_closure(self):
        from app.models.incident import Incident
        raw='En Chapinero hay una fuga de prueba.'
        self.db.get(Case,'work').content=raw
        self.db.get(MetaPost,'origin').raw_comments_json=json.dumps([{'id':'comment','author':'Autor de prueba','content':raw}])
        self.db.add(Incident(id='work',lat=0,lng=0,title='Fixture',description="Mención explícita en texto: 'chapinero'",category='Servicios',priority='Media',sentiment='Sin analizar',source='Facebook',neighborhood='Chapinero',zone='Sin verificar',date_time='2026-11-25',status='Pendiente'))
        self.db.commit()
        self.assign();self.close()
        mapped=self.client.get('/api/v1/map/incidents',headers=self.headers()).json()
        self.assertEqual(mapped[0]['status'],'Resuelto')
        self.assertEqual(mapped[0]['verification_status'],'territorial_mention')
        self.assertEqual(mapped[0]['location_precision'],'area_reference')
        metrics=self.client.get('/api/v1/analytics/overview',headers=self.headers()).json()['cases']
        self.assertEqual(metrics['resolved'],1)
        self.assertEqual(metrics['open'],0)
        self.assertEqual(self.reopen().status_code,200)
        reopened_map=self.client.get('/api/v1/map/incidents',headers=self.headers()).json()
        self.assertEqual(reopened_map[0]['status'],'Pendiente')
        metrics=self.client.get('/api/v1/analytics/overview',headers=self.headers()).json()['cases']
        self.assertEqual(metrics['resolved'],0);self.assertEqual(metrics['open'],1)


if __name__=='__main__': unittest.main()
