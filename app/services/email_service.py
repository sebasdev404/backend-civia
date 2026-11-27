import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formataddr
import logging
import secrets
import ssl
from pathlib import Path
from app.core.config import settings
from app.services.email_templates import BRAND_NAME, LOGO_CID, render_otp_email, render_password_changed_email, render_welcome_email

logger = logging.getLogger("civia.email")

def generate_otp_code() -> str:
    """Genera un código OTP numérico de 6 dígitos criptográficamente seguro."""
    return f"{secrets.randbelow(900000) + 100000}"

def get_otp_html_template(user_name: str, otp_code: str) -> str:
    """Recovery email matching the platform's current logo, motto and colors."""
    return render_otp_email(user_name, otp_code)


def smtp_is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD
                and settings.SMTP_FROM_EMAIL and settings.SMTP_PORT > 0
                and settings.SMTP_TLS != settings.SMTP_SSL)


def _send_security_email(to_email, subject, text_content, html_content):
    if not smtp_is_configured():
        logger.warning('Recuperacion no disponible: SMTP sin configurar o transporte inseguro.')
        return False
    try:
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = formataddr((BRAND_NAME, settings.SMTP_FROM_EMAIL))
        msg['To'] = to_email
        alternatives = MIMEMultipart('alternative')
        alternatives.attach(MIMEText(text_content, 'plain', 'utf-8'))
        alternatives.attach(MIMEText(html_content, 'html', 'utf-8'))
        msg.attach(alternatives)
        logo_path = Path(__file__).resolve().parents[1] / 'assets' / 'email' / 'logo.png'
        logo = MIMEImage(logo_path.read_bytes(), _subtype='png')
        logo.add_header('Content-ID', f'<{LOGO_CID}>')
        logo.add_header('Content-Disposition', 'inline', filename='logo.png')
        msg.attach(logo)
        context = ssl.create_default_context()
        connection = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10, context=context) if settings.SMTP_SSL else smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        with connection as server:
            server.ehlo()
            if settings.SMTP_TLS:
                server.starttls(context=context)
                server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            if server.send_message(msg):
                logger.error('El servidor de correo rechazo la entrega.')
                return False
        logger.info('Correo de seguridad aceptado por el servidor SMTP.')
        return True
    except Exception:
        logger.error('No se pudo entregar el correo de seguridad.')
        return False


def send_welcome_email(to_email: str, user_name: str, password: str, role: str, login_url: str) -> bool:
    roles = {'ADMIN': 'Administrador', 'ALCALDE': 'Alcalde', 'SECRETARIO': 'Secretaría', 'OPERADOR': 'Operador'}
    text = (f'{BRAND_NAME}\n\nHola {user_name}, el administrador creó tu cuenta.\n\n'
            f'Correo de acceso: {to_email}\nContraseña inicial: {password}\nRol: {roles.get(role, role)}\n\n'
            f'Ingresar a la plataforma: {login_url}\n\n'
            'Después de ingresar, cambia la contraseña desde Mi cuenta y seguridad. '
            'Usa al menos 10 caracteres, mayúscula, minúscula, número y carácter especial.\n'
            'Conserva estas credenciales de forma privada. Si no reconoces esta cuenta, contacta al administrador.')
    return _send_security_email(to_email, f'Tus credenciales de acceso | {BRAND_NAME}', text,
                                render_welcome_email(user_name, to_email, password, role, login_url))


def send_otp_email(to_email: str, user_name: str, otp_code: str) -> bool:
    """Send the recovery code privately; never include it in headers or logs."""
    text_content = (
        f'{BRAND_NAME}\n\nHola {user_name},\n\n'
        f'Tu código para restablecer la contraseña es: {otp_code}\n\n'
        'Es válido durante 15 minutos y para un solo uso.\n'
        'Si no solicitaste este cambio, ignora el mensaje. No compartas el código.\n\n'
        'Seguridad de tu cuenta'
    )
    return _send_security_email(to_email, f'Recuperación de contraseña | {BRAND_NAME}', text_content, get_otp_html_template(user_name, otp_code))


def send_password_changed_email(to_email: str, user_name: str) -> bool:
    text = (
        f'{BRAND_NAME}\n\nHola {user_name},\n\n'
        'Cambio confirmado: tu nueva contraseña ya está activa.\n\n'
        'Tu próximo acceso: utiliza la nueva contraseña al iniciar sesión.\n'
        'Sesiones anteriores: los accesos abiertos antes del cambio quedaron invalidados.\n\n'
        'Si no realizaste este cambio, contacta al administrador de la plataforma inmediatamente.'
    )
    return _send_security_email(to_email, f'Tu contraseña se actualizó | {BRAND_NAME}', text, render_password_changed_email(user_name))
