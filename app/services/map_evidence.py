"""Read-only audit: distinguish captured territorial mentions from confirmed reports."""
import json
import re
import unicodedata
from collections import Counter
from app.models.case import Case
from app.models.meta_post import MetaPost


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text or '').casefold() if not unicodedata.combining(c))


def location_evidence(description, original_text):
    match = re.search(r"Mención explícita en texto: '([^']+)'", description or '')
    if not match:
        return None
    keyword = normalized(match.group(1))
    return match.group(1) if re.search(r'(?<!\w)' + re.escape(keyword) + r'(?!\w)', normalized(original_text)) else None


def audit_incidents(db, incidents):
    # Catalog coordinates represent an area, never a citizen's exact GPS position.
    from sync_strict_map import BARRIOS_CATALOG, COMUNA_DATA
    cases = {c.id: c for c in db.query(Case).filter(Case.id.in_([i.id for i in incidents])).all()}
    references = {}
    for key, case in cases.items():
        post = re.search(r'\[Post ID\]:\s*([^\s]+)', case.internal_notes or '')
        comment = re.search(r'\[Comment ID\]:\s*([^\s]+)', case.internal_notes or '')
        if post and comment:
            references[key] = (post[1], comment[1])
    posts = {p.id: p for p in db.query(MetaPost).filter(MetaPost.id.in_([r[0] for r in references.values()])).all()}
    comments = {}
    for key, post in posts.items():
        try:
            comments[key] = {str(c.get('id')): c for c in json.loads(post.raw_comments_json or '[]') if isinstance(c, dict)}
        except (ValueError, TypeError):
            comments[key] = {}
    items, reasons = [], Counter()
    for incident in incidents:
        reference = references.get(incident.id)
        captured = comments.get(reference[0], {}).get(reference[1]) if reference else None
        if not captured:
            reasons['Sin comentario original trazable'] += 1
            continue
        keyword = location_evidence(incident.description, captured.get('content') or captured.get('message'))
        if not keyword:
            reasons['Lugar no mencionado en el comentario original'] += 1
            continue
        catalog = next((v for k, v in BARRIOS_CATALOG.items() if normalized(k) == normalized(keyword)), None)
        comuna = COMUNA_DATA.get(normalized(keyword))
        if catalog:
            lat, lng = catalog[2:4]
        elif comuna:
            lat, lng = comuna['lat'], comuna['lng']
        else:
            reasons['Sin referencia territorial en el catálogo'] += 1
            continue
        item = {c.name: getattr(incident, c.name) for c in incident.__table__.columns}
        item.update(lat=lat, lng=lng, status=cases[incident.id].status, location_precision='area_reference', evidence_text=keyword,
                    source_post_id=reference[0], source_comment_id=reference[1],
                    verification_status='territorial_mention', source_url=captured.get('permalink_url') or posts[reference[0]].permalink_url,
                    description=(captured.get('content') or captured.get('message') or '') + '\n\nUbicación aproximada por mención textual. No confirma un incidente ni una dirección exacta.')
        items.append(item)
    return items, {'stored': len(incidents), 'with_source_and_location': len(items), 'excluded': sum(reasons.values()),
                   'excluded_reasons': dict(reasons), 'exact_coordinates_verified': 0}
