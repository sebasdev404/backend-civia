"""Read-only counts of stored evidence. No seed values, scoring or external calls."""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from sqlalchemy import func, select, union_all
from app.models.case import Case
from app.models.case_consolidation import CaseConsolidation
from app.models.case_correction import CaseCorrection
from app.models.case_provenance import CaseProvenanceReview
from app.models.incident import Incident
from app.models.meta_post import MetaPost
from app.models.conversation import CommentAnalysis, PostContext
from app.services.case_reads import filtered_cases, has_active_consolidation
from app.services.conversation import build_rows
from app.services.map_evidence import audit_incidents


def channel(source):
    name = (source or '').strip()
    if 'facebook' in name.casefold():
        return 'Facebook'
    if 'instagram' in name.casefold():
        return 'Instagram'
    return name or 'Sin fuente registrada'


def grouped(query, column):
    return {str(key or 'Sin clasificar'): count for key, count in query.with_entities(column, func.count(Case.id)).group_by(column)}


def case_counts(db):
    query = filtered_cases(db)
    statuses = grouped(query, Case.status)
    sources = Counter()
    for name, count in grouped(query, Case.source).items():
        sources[channel(name)] += count
    opened = query.filter(Case.status.in_(['Pendiente', 'Nuevo', 'En Gestión']))
    return {
        'stored': db.query(Case).count(), 'total': sum(statuses.values()),
        'duplicates_excluded': db.query(CaseConsolidation).filter(CaseConsolidation.undone_at.is_(None)).count(),
        'open': opened.count(), 'pending': statuses.get('Pendiente', 0) + statuses.get('Nuevo', 0),
        'in_progress': statuses.get('En Gestión', 0), 'resolved': statuses.get('Resuelto', 0),
        'no_request': statuses.get('No requiere gestión', 0),
        'critical_open': opened.filter(Case.priority.in_(['Alta', 'Crítica'])).count(),
        'priority_open': opened.filter(Case.priority_action.is_(True)).count(),
        'source_needs_review': query.filter(~has_active_consolidation(), Case.id.in_(
            db.query(CaseProvenanceReview.case_id).filter_by(status='needs_review'))).count(),
        'statuses': statuses, 'priorities': grouped(query, Case.priority),
        'categories': grouped(query, Case.category), 'emotions': grouped(query, Case.sentiment),
        'channels': dict(sources), 'departments': grouped(query, Case.assigned_department),
    }


def captured_metrics(posts):
    sources, terms = {}, Counter()
    missing, unreadable = 0, 0
    stop = set('estos estas todos todas donde sobre entre hasta desde porque mucho muchos tienen hacer hacen puede pueden cuando estan tiene haber habia señor alcalde johan steed neiva para pero como que del las los una unos unas esto esta este con por mas muy solo eso sin hay'.split())
    for post in posts:
        name = channel(post.source)
        row = sources.setdefault(name, {'source': name, 'posts': 0, 'captured_comments': 0,
            'reported_comments': 0, 'reported_unknown_posts': 0})
        row['posts'] += 1
        if post.total_comments is None or post.total_comments < 0:
            row['reported_unknown_posts'] += 1
        else:
            row['reported_comments'] += post.total_comments
        if post.raw_comments_json is None or not post.raw_comments_json.strip():
            missing += 1
            continue
        try:
            raw = json.loads(post.raw_comments_json)
            if not isinstance(raw, list):
                raise ValueError('Capture is not a list')
        except (ValueError, TypeError):
            unreadable += 1
            continue
        unique = {str(c['id']): c for c in raw if isinstance(c, dict) and c.get('id')}
        row['captured_comments'] += len(unique)
        for comment in unique.values():
            content = comment.get('content') or comment.get('message')
            if isinstance(content, str):
                terms.update(w for w in re.findall(r'\b[a-záéíóúñ]{5,}\b', content.casefold()) if w not in stop)
    channels = sorted(sources.values(), key=lambda r: (-r['captured_comments'], r['source']))
    return {
        'posts': len(posts), 'captured_comments': sum(r['captured_comments'] for r in channels),
        'reported_comments': sum(r['reported_comments'] for r in channels),
        'reported_unknown_posts': sum(r['reported_unknown_posts'] for r in channels),
        'posts_without_capture': missing, 'unreadable_captures': unreadable, 'channels': channels,
        'top_terms': [{'term': term, 'count': count} for term, count in sorted(terms.items(), key=lambda p: (-p[1], p[0]))[:12]],
    }


def contextual_counts(db, posts):
    facebook = [p for p in posts if channel(p.source) == 'Facebook']
    rows, _ = build_rows(db, facebook)
    usable = [r for r in rows if r['status'] == 'analyzed' and not r['needs_review']]
    return {'source': 'Facebook', 'captured_text_comments': len(rows),
        'analyzed': sum(r['status'] == 'analyzed' for r in rows),
        'pending': sum(r['status'] == 'pending' for r in rows),
        'review': sum(r['needs_review'] for r in rows),
        'usable': len(usable), 'stances': dict(Counter(r['stance'] for r in usable))}


def territorial_counts(db):
    items, audit = audit_incidents(db, db.query(Incident).all())
    unique, locations = set(), Counter()
    for item in items:
        key = (item['source_post_id'], item['source_comment_id'], item['evidence_text'].casefold())
        if key not in unique:
            unique.add(key)
            locations[item['evidence_text']] += 1
    return {'stored': audit['stored'], 'traceable_rows': len(items), 'captured_mentions': len(unique),
        'excluded_rows': audit['excluded'], 'exact_coordinates_verified': 0,
        'locations': [{'location': location, 'mentions': count} for location, count in sorted(locations.items(), key=lambda p: (-p[1], p[0]))[:10]]}


def iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


def overview(db):
    # This aggregate read never refreshes Meta, creates cases or invokes AI.
    posts = db.query(MetaPost).all()
    # A consolidation or context edit can change the summary without updating a case.
    timestamps = (Case.updated_at, MetaPost.updated_at, CommentAnalysis.updated_at, PostContext.updated_at,
        CaseProvenanceReview.checked_at, CaseConsolidation.created_at, CaseConsolidation.undone_at,
        CaseCorrection.created_at, CaseCorrection.undone_at, Incident.created_at)
    latest = union_all(*[select(func.max(column).label('changed_at')) for column in timestamps]).subquery()
    last_change = db.execute(select(func.max(latest.c.changed_at))).scalar()
    return {'generated_at': datetime.now(timezone.utc).isoformat(),
        'data_updated_at': iso(last_change),
        'scope': 'Histórico guardado en CIVIA; no equivale a solicitudes confirmadas ni a una consulta en vivo de Meta.',
        'cases': case_counts(db), 'capture': captured_metrics(posts), 'contextual': contextual_counts(db, posts),
        'territorial': territorial_counts(db),
        'response_time': {'average_hours': None, 'reason': 'No hay eventos de atención estructurados suficientes para calcular este tiempo.'}}
