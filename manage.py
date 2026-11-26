"""Explicit schema, operator provisioning and release checks; never prints secrets."""
import argparse
import getpass
import hashlib
import json
import os
import re
from pathlib import Path
from sqlalchemy import text
from app.core.database import engine,Base,SessionLocal
import app.models
from app.models.user import User
from app.core.config import settings
from app.core.schema import verify_schema

ROOT=Path(__file__).resolve().parent


def migration_checksum(file):
    # Git may check out the same SQL with CRLF on Windows and LF on Linux.
    return hashlib.sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def migrate(check=False):
    if engine.dialect.name!='postgresql':raise RuntimeError('La migración de producción requiere PostgreSQL.')
    files=sorted((ROOT/'migrations').glob('*.sql'))
    with engine.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(1128879682)'))
        if check:
            verify_schema(connection)
            applied=dict(connection.execute(text('SELECT name,sha256 FROM civia_schema_migrations')).all())
        else:
            connection.execute(text('CREATE TABLE IF NOT EXISTS civia_schema_migrations (name TEXT PRIMARY KEY,sha256 VARCHAR(64) NOT NULL,applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())'))
            applied=dict(connection.execute(text('SELECT name,sha256 FROM civia_schema_migrations')).all())
            Base.metadata.create_all(connection)
        for file in files:
            digest=migration_checksum(file)
            if file.name in applied:
                if applied[file.name]!=digest:raise RuntimeError('Una migración aplicada cambió: '+file.name)
                continue
            if check:raise RuntimeError('Hay migraciones pendientes: '+file.name)
            sql=re.sub(r'^\s*(?:BEGIN|COMMIT);\s*$','',file.read_text(encoding='utf-8'),flags=re.MULTILINE|re.IGNORECASE)
            # Migration files are trusted source, not parameterized statements.
            # Passing SQLAlchemy's empty parameter tuple would reinterpret '%' in
            # LIKE patterns as psycopg placeholders.
            with connection.connection.cursor() as cursor:
                cursor.execute(sql)
            connection.execute(text('INSERT INTO civia_schema_migrations(name,sha256) VALUES (:name,:digest)'),{'name':file.name,'digest':digest})
        verify_schema(connection)
    print('Esquema y migraciones verificados.' if check else 'Migraciones aplicadas en una transacción.')


def bootstrap(email,name):
    from app.core.security import get_password_hash
    from app.services.audit import record
    password=os.environ.get('CIVIA_ADMIN_PASSWORD') or getpass.getpass('Contraseña inicial privada (mínimo 14 caracteres): ')
    if len(password)<14 or len(password.encode())>72:raise RuntimeError('La contraseña debe tener al menos 14 caracteres y como máximo 72 bytes.')
    if not email or '@' not in email or not name.strip():raise RuntimeError('Indica correo y titular reales.')
    with SessionLocal() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(1128879683)'))
        if db.query(User).filter_by(role='ADMIN',is_active=True).first():raise RuntimeError('Ya existe administración activa. Usa la gestión autenticada de cuentas.')
        account=User(email=email.strip().lower(),full_name=name.strip(),hashed_password=get_password_hash(password),role='ADMIN',is_active=True)
        db.add(account);db.flush();record(db,None,'admin_bootstrapped',account.id);db.commit()
    print('Cuenta administradora creada. La contraseña no se muestra ni se guarda en documentación.')


def preflight():
    from app.services.email_service import smtp_is_configured
    checks={'production_mode':settings.ENVIRONMENT=='production','smtp_configured':smtp_is_configured(),
        'proxy_secret_configured':bool(settings.BFF_PROXY_SECRET and len(settings.BFF_PROXY_SECRET)>=32),
        'meta_configured':bool(settings.META_PAGE_ACCESS_TOKEN and settings.META_PAGE_ID and settings.META_APP_SECRET and settings.META_VERIFY_TOKEN!='civia_meta_webhook_neiva_2026'),
        'openai_configured':bool(settings.OPENAI_API_KEY),'schema':False,'administrator':False}
    try:
        migrate(check=True);checks['schema']=True
        with SessionLocal() as db:checks['administrator']=db.query(User).filter_by(role='ADMIN',is_active=True).first() is not None
    except Exception:pass
    print(json.dumps({'checks':checks,'ready_for_external_validation':all(checks.values()),'note':'Configuración no equivale a probar SMTP, permisos de Meta, DNS/TLS o aceptación funcional.'},ensure_ascii=False))
    return 0 if all(checks.values()) else 1


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    migration=sub.add_parser('migrate');migration.add_argument('--check',action='store_true')
    sub.add_parser('preflight')
    owner=sub.add_parser('bootstrap-admin');owner.add_argument('--email',required=True);owner.add_argument('--name',required=True)
    args=parser.parse_args()
    try:
        if args.command=='migrate':migrate(args.check)
        elif args.command=='bootstrap-admin':bootstrap(args.email,args.name)
        else:return preflight()
        return 0
    except Exception as error:
        # DB/provider exception messages can contain connection strings or values.
        if isinstance(error,RuntimeError):print(str(error))
        else:print('La operación no se completó. Revisa conexión, permisos y esquema del entorno privado.')
        return 1


if __name__=='__main__':raise SystemExit(main())
