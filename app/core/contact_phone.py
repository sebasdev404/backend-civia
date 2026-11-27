"""Colombian contact numbers: canonical E.164 storage, national uniqueness."""
import re


def normalize_phone(value):
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Teléfono inválido")
    if isinstance(value, (int, float)):
        if not float(value).is_integer():
            raise ValueError("El teléfono no puede contener decimales")
        value = str(int(value))
    raw = str(value).strip()
    if not re.fullmatch(r"\+?[0-9 ()\-]+", raw):
        raise ValueError("Ingresa un solo teléfono, sin letras, extensiones ni separadores entre números")
    digits = re.sub(r"[^0-9]", "", raw)
    if digits.startswith("0057") and len(digits) == 14:
        digits = digits[4:]
    elif digits.startswith("57") and len(digits) == 12:
        digits = digits[2:]
    elif raw.startswith("+"):
        raise ValueError("Usa el indicativo de Colombia +57 y el número nacional de 10 dígitos")
    if not re.fullmatch(r"(?:3[0-9]{9}|60[1245678][0-9]{7})", digits):
        raise ValueError("Usa 10 dígitos: celular empieza en 3; fijo incluye 60 y el indicativo regional (608 en Huila). No se completan números de 7 dígitos automáticamente")
    return "+57" + digits


def whatsapp_link(value):
    try:
        number = normalize_phone(value)
    except ValueError:
        return None
    return "https://wa.me/" + number[1:] if number and number.startswith("+573") else None
