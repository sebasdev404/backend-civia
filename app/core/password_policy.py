"""Shared policy for newly chosen passwords; existing logins remain compatible."""
import unicodedata

PASSWORD_POLICY_MESSAGE = (
    'La contraseña debe tener al menos 10 caracteres, una mayúscula, '
    'una minúscula, un número y un carácter especial.'
)


def validate_new_password(value: str) -> str:
    if len(value.encode('utf-8')) > 72:
        raise ValueError('La contraseña no puede superar 72 bytes.')
    categories = {unicodedata.category(character) for character in value}
    if (len(value) < 10 or not {'Lu', 'Ll', 'Nd'} <= categories
            or not any(category.startswith(('P', 'S')) for category in categories)):
        raise ValueError(PASSWORD_POLICY_MESSAGE)
    return value
