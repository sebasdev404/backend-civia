"""Durable verified inbox. Captures exact source IDs; never creates cases or calls AI."""
import hashlib
import json
from sqlalchemy import or_, and_
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models.operations import WebhookEvent
from app.models.meta_post import MetaPost


def enqueue(db,payload):
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    event_id=hashlib.sha256(canonical.encode()).hexdigest()
    insert=sqlite_insert if db.get_bind().dialect.name=='sqlite' else pg_insert
    db.execute(insert(WebhookEvent).values(id=event_id,payload=payload,status='queued',attempts=0,received_at=datetime.now(timezone.utc)).on_conflict_do_nothing(index_elements=['id']))
    db.commit()
    return event_id


def capture(db,payload):
    if payload.get('object') not in ('page','instagram'):return True
    complete=True
    for entry in payload.get('entry',[]):
        for change in entry.get('changes',[]):
            value=change.get('value') or {}
            # Direct messages/mentions/likes aren't requests and aren't comments.
            if change.get('field') not in ('feed','comments') or value.get('item','comment')!='comment':continue
            pid=value.get('post_id') or (value.get('media') or {}).get('id')
            cid=value.get('comment_id') or value.get('id')
            message=value.get('message') or value.get('text')
            if not pid or not cid:continue
            pid,cid=str(pid),str(cid)
            if payload['object']=='instagram':pid=f'IG_{pid}'
            post=db.query(MetaPost).filter_by(id=pid).with_for_update().first()
            if not post:complete=False;continue
            try:comments=json.loads(post.raw_comments_json or '[]')
            except (TypeError,ValueError):complete=False;continue
            if not isinstance(comments,list):complete=False;continue
            known=next((row for row in comments if str(row.get('id'))==cid),None)
            if value.get('verb') in ('remove','delete'):
                # Keep captured text as evidence; explicitly mark source removal.
                if known:known['source_removed']=True
            elif message:
                author=value.get('from') or {}
                update={'id':cid,'content':str(message),'author':author.get('name') or author.get('username') or 'Autor no disponible','author_id':author.get('id'),'time':None,'source':'webhook'}
                timestamp=value.get('created_time')
                if timestamp:
                    try:update['time']=datetime.fromtimestamp(float(timestamp),timezone.utc).isoformat()
                    except (TypeError,ValueError,OverflowError):update['time']=str(timestamp)
                if known:
                    # Don't replace an already captured name with a fallback.
                    update={k:v for k,v in update.items() if v is not None and not(k=='author' and v=='Autor no disponible')}
                    known.update(update)
                else:comments.append(update)
            post.raw_comments_json=json.dumps(comments,ensure_ascii=False)
    return complete


def process_pending(db,limit=25):
    ready=or_(WebhookEvent.status=='queued',and_(WebhookEvent.status=='waiting_source',WebhookEvent.last_attempt_at<datetime.now(timezone.utc)-timedelta(minutes=1)))
    rows=db.query(WebhookEvent).filter(ready,WebhookEvent.attempts<20).order_by(WebhookEvent.received_at).with_for_update(skip_locked=True).limit(limit).all()
    for event in rows:
        event.last_attempt_at=datetime.now(timezone.utc)
        try:
            with db.begin_nested():
                complete=capture(db,event.payload)
            event.attempts+=1
            event.status='processed' if complete else 'waiting_source'
            event.processed_at=datetime.now(timezone.utc) if complete else None
            event.error=None if complete else 'Falta la publicación de origen en la captura. Se conserva el evento para revisión.'
        except Exception:
            event.attempts+=1;event.status='failed';event.error='No se pudo procesar el evento; el contenido permanece en la bandeja interna.'
    db.commit()
    # Raw inbox data is retained for 30 days after successful processing only.
    db.query(WebhookEvent).filter(WebhookEvent.status=='processed',WebhookEvent.processed_at<datetime.now(timezone.utc)-timedelta(days=30)).delete(synchronize_session=False)
    db.commit()
    return len(rows)
