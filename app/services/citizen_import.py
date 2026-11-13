"""Import real contacts without inferring social identities or classifications."""
import csv
import hashlib
import io
import re
import unicodedata
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.citizen import Citizen

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000


def normalized_header(value):
    value = unicodedata.normalize("NFKD", str(value or "")).lower()
    return re.sub(r"[^a-z0-9]", "", value)


def phone_key(value):
    return re.sub(r"\D", "", str(value or ""))


def normalize_phone(value):
    if value is None or str(value).strip() == "":
        return None
    raw = str(int(value)) if isinstance(value, (int, float)) and float(value).is_integer() else str(value).strip()
    if re.search(r"[a-zA-Z]", raw):
        raise ValueError("El teléfono contiene letras")
    digits = phone_key(raw)
    if raw.startswith("00"):
        digits = digits[2:]
    elif not raw.startswith("+") and len(digits) == 10 and digits.startswith("3"):
        digits = "57" + digits
    if not 7 <= len(digits) <= 15:
        raise ValueError("El teléfono debe contener entre 7 y 15 dígitos")
    return "+" + digits


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


ALIASES = {
    "name": ["Nombre", "name", "Nombre completo"],
    "phone": ["Teléfono (solo dígitos)", "Teléfono", "phone", "Celular"],
    "whatsapp_username": ["Usuario WhatsApp"],
    "profile_name": ["Nombre de perfil WhatsApp"],
    "agenda_name": ["Nombre en agenda"],
    "neighborhood": ["Barrio", "neighborhood"],
    "zone": ["Comuna mencionada", "Comuna", "zone"],
    "notes": ["Notas", "notes"],
}


def parse_contact_file(content: bytes, filename: str):
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("El archivo está vacío o supera el límite de 10 MB")
    suffix = Path(filename).suffix.lower()
    sheet_name = "CSV"
    workbook = None
    try:
        if suffix == ".xlsx":
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(f.file_size for f in archive.infolist()) > 50 * 1024 * 1024:
                    raise ValueError("El Excel descomprimido supera el límite de 50 MB")
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
            sheet = workbook["Contactos"] if "Contactos" in workbook.sheetnames else workbook.worksheets[0]
            sheet_name = sheet.title
            if sheet.max_row and sheet.max_row > MAX_ROWS + 1:
                raise ValueError("Máximo 10.000 contactos por archivo")
            if sheet.max_column and sheet.max_column > 100:
                raise ValueError("Máximo 100 columnas por archivo")
            iterator = sheet.iter_rows(values_only=True)
        elif suffix == ".csv":
            try:
                decoded = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                decoded = content.decode("cp1252")
            try:
                dialect = csv.Sniffer().sniff(decoded[:8192], delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            iterator = iter(csv.reader(io.StringIO(decoded), dialect))
        else:
            raise ValueError("Selecciona un archivo .xlsx o .csv")
        headers = [str(v).strip() if v is not None else "" for v in next(iterator, [])]
        while headers and not headers[-1]:
            headers.pop()
        if not headers or len(headers) > 100 or any(not h for h in headers):
            raise ValueError("La primera fila debe contener encabezados para todas las columnas")
        normalized = [normalized_header(h) for h in headers]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Hay encabezados repetidos; usa un nombre distinto para cada columna")
        mapping = {}
        for field, aliases in ALIASES.items():
            mapping[field] = [normalized.index(normalized_header(a)) for a in aliases if normalized_header(a) in normalized]
        if not any(mapping[k] for k in ("name", "agenda_name", "profile_name")):
            raise ValueError("Falta la columna Nombre")
        if not mapping["phone"] and not mapping["whatsapp_username"]:
            raise ValueError("Falta Teléfono o Usuario WhatsApp para identificar contactos sin duplicarlos")

        def cell(values, field):
            for index in mapping[field]:
                v = values[index] if index < len(values) else None
                if v is not None and str(v).strip():
                    return str(v).strip()
            return None

        records, issues = [], []
        total_rows = 0
        for row_number, values in enumerate(iterator, start=2):
            if not any(v is not None and str(v).strip() for v in values):
                continue
            total_rows += 1
            if total_rows > MAX_ROWS:
                raise ValueError("Máximo 10.000 contactos por archivo")
            try:
                name = cell(values, "name") or cell(values, "agenda_name") or cell(values, "profile_name")
                phone = normalize_phone(cell(values, "phone"))
                username = cell(values, "whatsapp_username")
                if not name or len(name) > 100:
                    raise ValueError("Nombre obligatorio, máximo 100 caracteres")
                if not phone and not username:
                    raise ValueError("Se necesita teléfono o usuario WhatsApp; el nombre no es un identificador único")
                if username and len(username) > 70:
                    raise ValueError("Usuario WhatsApp demasiado largo")
                zone = cell(values, "zone")
                if zone and zone.isdigit():
                    zone = "Comuna " + zone
                neighborhood = cell(values, "neighborhood")
                if (zone and len(zone) > 100) or (neighborhood and len(neighborhood) > 150):
                    raise ValueError("La comuna o el barrio supera el tamaño permitido")
                records.append({
                    "name": name, "phone": phone, "whatsapp_username": username,
                    "zone": zone, "neighborhood": neighborhood, "notes": cell(values, "notes"),
                    "channel": "WhatsApp" if any("whatsapp" in h for h in normalized) else "Base de Datos",
                    "row_number": row_number,
                    "fields": {h: json_value(values[i] if i < len(values) else None) for i, h in enumerate(headers)},
                })
            except ValueError as exc:
                issues.append({"row": row_number, "reason": str(exc)})
        if total_rows == 0:
            raise ValueError("El archivo no contiene contactos")
        return {
            "file_name": Path(filename).name, "file_sha256": hashlib.sha256(content).hexdigest(),
            "sheet_name": sheet_name, "total_rows": total_rows, "records": records, "issues": issues,
            "column_mapping": {k: [headers[i] for i in indexes] for k, indexes in mapping.items() if indexes},
            "columns": headers,
        }
    except (zipfile.BadZipFile, KeyError, TypeError, csv.Error) as exc:
        raise ValueError("No se pudo leer el archivo; revisa que sea un Excel o CSV válido") from exc
    finally:
        if workbook is not None:
            workbook.close()


def import_contacts(db: Session, parsed: dict, *, preview=False):
    """Exact identifiers only. One transaction; repeat imports do not create duplicates."""
    existing = db.query(Citizen).all()
    by_phone, by_username = {}, {}
    for citizen in existing:
        if citizen.phone:
            try:
                key = phone_key(normalize_phone(citizen.phone))
            except ValueError:
                key = phone_key(citizen.phone)
            by_phone.setdefault(key, []).append(citizen)
        username = (citizen.source_data or {}).get("whatsapp_username")
        if username:
            by_username.setdefault(username.casefold(), []).append(citizen)
    counts = dict(total_processed=parsed["total_rows"], new_citizens_added=0, existing_updated=0,
                  unchanged=0, duplicates=0, rejected=len(parsed["issues"]), with_phone=0, without_phone=0)
    issues = list(parsed["issues"])
    seen_phone, seen_username = set(), set()
    sample = []
    for row in parsed["records"]:
        phone = phone_key(row["phone"])
        username = (row["whatsapp_username"] or "").casefold()
        if (phone and phone in seen_phone) or (username and username in seen_username):
            counts["duplicates"] += 1
            issues.append({"row": row["row_number"], "reason": "Identificador repetido en el archivo; se conserva la primera fila"})
            continue
        if phone:
            seen_phone.add(phone)
        if username:
            seen_username.add(username)
        matches = {c.id: c for c in by_phone.get(phone, []) + by_username.get(username, [])}
        if len(matches) > 1:
            counts["rejected"] += 1
            issues.append({"row": row["row_number"], "reason": "Los identificadores coinciden con varios ciudadanos; requiere revisión"})
            continue
        counts["with_phone" if phone else "without_phone"] += 1
        source = {k: parsed[k] for k in ("file_name", "file_sha256", "sheet_name")}
        source.update({k: row[k] for k in ("row_number", "whatsapp_username", "fields")})
        citizen = next(iter(matches.values()), None)
        action = "new_citizens_added"
        if citizen:
            action = "unchanged" if citizen.source_data == source else "existing_updated"
        counts[action] += 1
        if len(sample) < 5:
            sample.append({k: row[k] for k in ("name", "phone", "whatsapp_username", "zone", "neighborhood")})
        if preview or action == "unchanged":
            continue
        if citizen is None:
            handle = "contact:phone:" + phone if phone else "contact:whatsapp:" + username
            citizen = Citizen(
                id="CIUD-" + uuid.uuid4().hex[:20].upper(), handle=handle,
                name=row["name"], phone=row["phone"], channel=row["channel"],
                zone=row["zone"], neighborhood=row["neighborhood"], notes=row["notes"],
                user_type="Sin clasificar", total_reports=0, followers_count=0, following_count=0,
                credibility_score=0, bot_probability=0, sentiment_tendency="Sin evaluar",
                origen_dato="BASE_SUBIDA", source_data=source,
            )
            # Assign unknown location explicitly (the legacy ORM has a Neiva default).
            citizen.zone = row["zone"] or "No especificada"
            db.add(citizen)
        else:
            # Keep verified social identities, existing cases and classifications intact.
            if citizen.channel in ("WhatsApp", "Base de Datos"):
                citizen.name = row["name"]
                for field in ("zone", "neighborhood", "notes"):
                    if row[field] is not None:
                        setattr(citizen, field, row[field])
            for field in ("phone", "zone", "neighborhood", "notes"):
                if not getattr(citizen, field) and row[field]:
                    setattr(citizen, field, row[field])
            citizen.source_data = source
    if not preview:
        db.commit()
    return {
        "success": True, "preview": preview, "summary": counts,
        "sheet_name": parsed["sheet_name"], "file_name": parsed["file_name"],
        "columns": parsed["columns"], "column_mapping": parsed["column_mapping"],
        "sample": sample, "issues": issues[:100],
        "message": "Vista previa lista" if preview else "Importación guardada en Ciudadanos",
    }
