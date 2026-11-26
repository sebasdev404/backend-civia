"""Encrypted PostgreSQL backup and verification in a disposable database only."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tarfile
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from app.core.config import settings

MAGIC=b'CIVIA-BACKUP-AESGCM-1\n'


def key():
    value=os.environ.get('BACKUP_ENCRYPTION_KEY') or settings.BACKUP_ENCRYPTION_KEY
    if not value:raise RuntimeError('Configura BACKUP_ENCRYPTION_KEY y conserva una copia privada fuera del servidor.')
    result=base64.urlsafe_b64decode(value.encode())
    if len(result)!=32:raise RuntimeError('BACKUP_ENCRYPTION_KEY debe codificar 32 bytes aleatorios en base64 URL-safe.')
    return result


def connection(database=None):
    url=make_url(settings.DATABASE_URL)
    values={'host':url.host or 'localhost','port':url.port or 5432,'user':url.username,'password':url.password,'dbname':database or url.database,'connect_timeout':10}
    values.update({k:v for k,v in url.query.items() if k in ('sslmode','sslrootcert','sslcert','sslkey','channel_binding')})
    return psycopg.connect(**values)


def pg_environment(database=None):
    url=make_url(settings.DATABASE_URL);env=dict(os.environ)
    env.update({'PGHOST':url.host or 'localhost','PGPORT':str(url.port or 5432),'PGUSER':url.username or '', 'PGPASSWORD':url.password or '','PGDATABASE':database or url.database,'PGCONNECT_TIMEOUT':'10'})
    if url.query.get('sslmode'):env['PGSSLMODE']=url.query['sslmode']
    return env


def executable(name):
    folder=os.environ.get('PG_BIN_DIR')
    candidate=Path(folder)/(name+('.exe' if os.name=='nt' else '')) if folder else None
    result=str(candidate) if candidate and candidate.is_file() else shutil.which(name)
    if not result:raise RuntimeError('Instala las herramientas PostgreSQL de la misma versión o posterior al servidor, o configura PG_BIN_DIR.')
    return result


def fingerprints(db):
    db.execute("SET LOCAL TIME ZONE 'UTC'")
    tables=[row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    result={}
    for table in tables:
        digest=hashlib.sha256();count=0
        statement=sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text COLLATE "C"').format(sql.Identifier('public',table))
        with db.cursor(name='fingerprint_'+uuid.uuid4().hex) as cursor:
            cursor.itersize=50
            cursor.execute(statement)
            for row in cursor:
                digest.update(row[0].encode());digest.update(b'\n');count+=1
        result[table]={'count':count,'sha256':digest.hexdigest()}
    return result


def file_hash(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    return digest.hexdigest()


def encrypt(source,target,secret):
    nonce=os.urandom(12);encryptor=Cipher(algorithms.AES(secret),modes.GCM(nonce)).encryptor();encryptor.authenticate_additional_data(MAGIC)
    with open(source,'rb') as reader,open(target,'xb') as writer:
        os.chmod(target,0o600);writer.write(MAGIC+nonce)
        while chunk:=reader.read(1024*1024):writer.write(encryptor.update(chunk))
        writer.write(encryptor.finalize());writer.write(encryptor.tag)


def decrypt(source,target,secret):
    with open(source,'rb') as reader:
        if reader.read(len(MAGIC))!=MAGIC:raise RuntimeError('Formato de copia no reconocido.')
        nonce=reader.read(12);reader.seek(-16,2);tag=reader.read(16);end=reader.tell()-16;reader.seek(len(MAGIC)+12)
        decryptor=Cipher(algorithms.AES(secret),modes.GCM(nonce,tag)).decryptor();decryptor.authenticate_additional_data(MAGIC)
        with open(target,'wb') as writer:
            os.chmod(target,0o600)
            while reader.tell()<end:
                writer.write(decryptor.update(reader.read(min(1024*1024,end-reader.tell()))))
            writer.write(decryptor.finalize())  # No restore runs before authentication succeeds.


def temporary(parent):
    handle=tempfile.NamedTemporaryFile(prefix='.civia-',suffix='.dump',dir=parent,delete=False);handle.close()
    result=Path(handle.name).resolve()
    if result.parent!=Path(parent).resolve():raise RuntimeError('La ruta temporal no corresponde al directorio de copias.')
    os.chmod(result,0o600)
    return result


def backup(target,media_root=None):
    secret=key();target=Path(target).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    manifest=Path(str(target)+'.manifest.json')
    if target.exists() or manifest.exists():raise RuntimeError('No se sobrescribe una copia existente.')
    raw=temporary(target.parent)
    try:
        with connection() as db:
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            snapshot=db.execute('SELECT pg_export_snapshot()').fetchone()[0]
            data=fingerprints(db)
            subprocess.run([executable('pg_dump'),'--no-password','--format=custom','--no-owner','--no-acl','--snapshot',snapshot,'--file',str(raw)],env=pg_environment(),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        encrypt(raw,target,secret)
        result={'format':1,'archive_sha256':file_hash(target),'tables':data}
        if media_root:
            media_root=Path(media_root).resolve();media_raw=temporary(target.parent);media_target=Path(str(target)+'.media.enc')
            try:
                with tarfile.open(media_raw,'w') as archive:
                    for item in media_root.rglob('*'):
                        if not item.is_file() or item.is_symlink():continue
                        try:item.resolve().relative_to(media_root)
                        except ValueError:continue
                        if item.name in ('default_cover.jpg','ig_cover_comuna6.jpg','ig_cover_malecon.jpg','ig_cover_ceibas.jpg','ig_cover_salud.jpg'):continue
                        archive.add(item,arcname=item.relative_to(media_root).as_posix(),recursive=False)
                with tarfile.open(media_raw,'r') as archive:
                    files={}
                    for member in archive:
                        digest=hashlib.sha256()
                        with archive.extractfile(member) as reader:
                            while chunk:=reader.read(1024*1024):digest.update(chunk)
                        files[member.name]=digest.hexdigest()
                encrypt(media_raw,media_target,secret)
                result['media']={'archive_sha256':file_hash(media_target),'files':files}
            finally:media_raw.unlink(missing_ok=True)
        manifest.write_text(json.dumps(result,indent=2),encoding='utf-8');os.chmod(manifest,0o600)
        print('Copia cifrada y manifiesto creados. No contienen credenciales de conexión en texto.')
    finally:raw.unlink(missing_ok=True)


def restore_test(archive):
    secret=key();archive=Path(archive).resolve();manifest=json.loads(Path(str(archive)+'.manifest.json').read_text(encoding='utf-8'))
    if file_hash(archive)!=manifest['archive_sha256']:raise RuntimeError('La copia no coincide con su manifiesto.')
    name='civia_restore_test_'+uuid.uuid4().hex
    if not name.startswith('civia_restore_test_') or name==make_url(settings.DATABASE_URL).database:raise RuntimeError('Destino de restauración inseguro.')
    raw=temporary(archive.parent);created=False
    admin=connection();admin.autocommit=True
    try:
        decrypt(archive,raw,secret)
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(name)));created=True
        subprocess.run([executable('pg_restore'),'--no-password','--exit-on-error','--no-owner','--no-acl','--dbname',name,str(raw)],env=pg_environment(name),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        with connection(name) as db:restored=fingerprints(db)
        if restored!=manifest['tables']:raise RuntimeError('La restauración no conserva las huellas de todas las tablas.')
        if manifest.get('media'):
            media=Path(str(archive)+'.media.enc')
            if file_hash(media)!=manifest['media']['archive_sha256']:raise RuntimeError('No coincide el archivo multimedia.')
            decrypt(media,raw,secret)
            with tarfile.open(raw,'r') as archive_reader:
                actual={}
                for member in archive_reader:
                    if not member.isfile() or Path(member.name).is_absolute() or '..' in Path(member.name).parts:raise RuntimeError('Ruta multimedia no válida.')
                    digest=hashlib.sha256()
                    with archive_reader.extractfile(member) as reader:
                        while chunk:=reader.read(1024*1024):digest.update(chunk)
                    actual[member.name]=digest.hexdigest()
                if actual!=manifest['media']['files']:raise RuntimeError('La restauración multimedia no conserva sus archivos.')
        print(json.dumps({'restore_verified':True,'tables':len(restored),'media_files_verified':len(manifest.get('media',{}).get('files',{})),'source_database_modified':False}))
    finally:
        raw.unlink(missing_ok=True)
        if created:
            if not name.startswith('civia_restore_test_'):raise RuntimeError('Destino inesperado; no eliminar.')
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


def restore_empty(archive, confirm_database, media_target=None, media_owner=None):
    """Operator-only import into an empty destination; never clean existing data."""
    database=make_url(settings.DATABASE_URL).database
    if not database or database in ('postgres','template0','template1') or confirm_database!=database:
        raise RuntimeError('Confirma exactamente el nombre de la base destino vacía.')
    archive=Path(archive).resolve();manifest=json.loads(Path(str(archive)+'.manifest.json').read_text(encoding='utf-8'))
    if file_hash(archive)!=manifest['archive_sha256']:raise RuntimeError('La copia no coincide con su manifiesto.')
    with connection() as db:
        if db.execute("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='public')").fetchone()[0]:
            raise RuntimeError('La base destino contiene tablas. No se sobrescribe ni elimina información.')
    target=Path(media_target).resolve() if media_target else None
    if media_owner and (os.name=='nt' or not target or any(value<0 for value in media_owner)):
        raise RuntimeError('El propietario multimedia requiere destino y UID/GID válidos en Linux.')
    if manifest.get('media') and target is None:raise RuntimeError('La copia incluye multimedia: indica su destino vacío con --media-target.')
    if target and target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise RuntimeError('El directorio multimedia debe estar vacío; no se sobrescriben archivos.')
    secret=key();raw=temporary(archive.parent);media_raw=temporary(archive.parent)
    try:
        # Authenticate every archive before importing any data.
        decrypt(archive,raw,secret)
        if manifest.get('media'):
            media=Path(str(archive)+'.media.enc')
            if file_hash(media)!=manifest['media']['archive_sha256']:raise RuntimeError('No coincide el archivo multimedia.')
            decrypt(media,media_raw,secret)
            actual={}
            with tarfile.open(media_raw,'r') as reader:
                for member in reader:
                    destination=(target/member.name).resolve()
                    if not member.isfile() or not destination.is_relative_to(target) or Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                        raise RuntimeError('Ruta multimedia no válida.')
                    with reader.extractfile(member) as file:actual[member.name]=hashlib.file_digest(file,'sha256').hexdigest()
            if actual!=manifest['media']['files']:raise RuntimeError('Los archivos multimedia no coinciden con el manifiesto.')
        subprocess.run([executable('pg_restore'),'--no-password','--single-transaction','--exit-on-error','--no-owner','--no-acl','--dbname',database,str(raw)],env=pg_environment(),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        with connection() as db:
            if fingerprints(db)!=manifest['tables']:raise RuntimeError('Las huellas restauradas requieren revisión. No inicies la aplicación.')
        if manifest.get('media'):
            target.mkdir(parents=True,exist_ok=True)
            with tarfile.open(media_raw,'r') as reader:
                for member in reader:
                    destination=(target/member.name).resolve()
                    if not destination.is_relative_to(target):raise RuntimeError('Destino multimedia inesperado.')
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with reader.extractfile(member) as source,open(destination,'xb') as output:shutil.copyfileobj(source,output)
            if media_owner:
                for destination in [target,*target.rglob('*')]:
                    if destination.is_symlink() or not destination.resolve().is_relative_to(target):raise RuntimeError('Destino multimedia inesperado.')
                    os.chown(destination,*media_owner)
        print(json.dumps({'import_verified':True,'tables':len(manifest['tables']),'media_files_restored':len(manifest.get('media',{}).get('files',{})),'destination_was_empty':True}))
    finally:
        raw.unlink(missing_ok=True);media_raw.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    task=sub.add_parser('backup');task.add_argument('--output',required=True)
    task.add_argument('--media-root')
    task=sub.add_parser('restore-test');task.add_argument('--archive',required=True)
    task=sub.add_parser('restore-empty');task.add_argument('--archive',required=True);task.add_argument('--confirm-database',required=True);task.add_argument('--media-target');task.add_argument('--media-owner',nargs=2,type=int,metavar=('UID','GID'))
    args=parser.parse_args()
    try:
        if args.command=='backup':backup(args.output,args.media_root)
        elif args.command=='restore-test':restore_test(args.archive)
        else:restore_empty(args.archive,args.confirm_database,args.media_target,args.media_owner)
        return 0
    except Exception as error:
        print(str(error) if isinstance(error,RuntimeError) else 'La operación no se completó. Revisa el acceso privado, herramientas PostgreSQL y clave de cifrado.')
        return 1


if __name__=='__main__':raise SystemExit(main())
