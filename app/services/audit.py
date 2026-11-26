from app.models.operations import AuditEvent


def record(db, actor, action, target=None, **details):
    # Deliberately exclude payloads, contact information and credentials.
    forbidden=('password','token','secret','email','phone','content','payload','code')
    safe={key:value for key,value in details.items() if not any(word in key.lower() for word in forbidden)}
    db.add(AuditEvent(actor_id=actor.id if actor else 'system',actor_name=actor.full_name if actor else 'Sistema',action=action,target_id=target,details=safe))
