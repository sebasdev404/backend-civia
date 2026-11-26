from sqlalchemy import inspect
from app.core.database import Base


def verify_schema(connection):
    inspector=inspect(connection)
    missing=[]
    for name,table in Base.metadata.tables.items():
        if not inspector.has_table(name):missing.append(name);continue
        columns={item['name'] for item in inspector.get_columns(name)}
        missing.extend(name+'.'+column.name for column in table.columns if column.name not in columns)
    if missing:raise RuntimeError('El esquema necesita migraciones antes de iniciar la API: '+', '.join(missing))
