import time
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy import text,func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.authentication import get_current_user
from app.models.case import Case
from app.models.user import User
from app.models.operations import AuditEvent,WebhookEvent
from app.services.email_service import smtp_is_configured

router=APIRouter(prefix='/system',tags=['Diagnóstico y auditoría'])
_started=time.monotonic()


@router.get('/diagnostics')
def diagnostics(db:Session=Depends(get_db)):
    started=time.perf_counter()
    try:
        db.execute(text('SELECT 1'))
        cases=db.query(Case).count();users=db.query(User).count()
        postgres={'status':'Operativo','latency_ms':round((time.perf_counter()-started)*1000,2),'cases_count':cases,'users_count':users,'detail':'Consulta y conteos realizados en la base configurada.'}
    except Exception:
        db.rollback();postgres={'status':'No disponible','latency_ms':None,'cases_count':None,'users_count':None,'detail':'La consulta a la base no pudo completarse.'}
    configured=lambda value:'Configurada; sin verificación en línea' if value else 'No configurada'
    return {'timestamp':datetime.now(timezone.utc).isoformat(),
        'postgres':postgres,
        'backend':{'status':'Operativo','version':settings.VERSION,'uptime_seconds':round(time.monotonic()-_started),'detail':'Esta respuesta fue generada por la API. No se calcula un porcentaje de disponibilidad.'},
        'meta':{'status':configured(bool(settings.META_PAGE_ACCESS_TOKEN)),'page_id':settings.META_PAGE_ID,'detail':'Tener credenciales configuradas no acredita vigencia, permisos ni recepción del webhook.'},
        'ai':{'status':configured(bool(settings.OPENAI_API_KEY)),'model':'gpt-4o-mini','detail':'El análisis utiliza el modelo configurado cuando se solicita. No se ha medido conexión ni gasto en esta consulta.'},
        'smtp':{'status':'Configurado; envío pendiente de verificar' if smtp_is_configured() else 'No configurado','detail':'La recuperación requiere proveedor, remitente y credenciales SMTP privados.'}}


@router.get('/audit')
def audit(limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0),db:Session=Depends(get_db)):
    query=db.query(AuditEvent)
    return {'total':query.count(),'items':[{key:getattr(row,key) for key in ('id','actor_id','actor_name','action','target_id','details','created_at')} for row in query.order_by(AuditEvent.created_at.desc(),AuditEvent.id.desc()).offset(offset).limit(limit)]}


@router.get('/webhooks')
def webhooks(limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0),db:Session=Depends(get_db)):
    return {'counts':dict(db.query(WebhookEvent.status,func.count(WebhookEvent.id)).group_by(WebhookEvent.status).all()),'items':[{key:getattr(row,key) for key in ('id','status','attempts','error','received_at','processed_at')} for row in db.query(WebhookEvent).order_by(WebhookEvent.received_at.desc()).offset(offset).limit(limit)]}


@router.post('/webhooks/{event_id}/retry')
def retry_webhook(event_id:str,db:Session=Depends(get_db),actor=Depends(get_current_user)):
    from app.services.audit import record
    event=db.query(WebhookEvent).filter_by(id=event_id).with_for_update().first()
    if not event:raise HTTPException(404,'Evento no encontrado.')
    if event.status in ('processed','queued'):raise HTTPException(409,'El evento ya está procesado o pendiente.')
    event.status='queued';event.attempts=0;event.error=None
    record(db,actor,'webhook_retried',event.id)
    db.commit()
    return {'status':'queued'}
