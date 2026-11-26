import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import secrets
import ssl
from html import escape
from typing import Optional
from app.core.config import settings

logger = logging.getLogger("civia.email")

def generate_otp_code() -> str:
    """Genera un código OTP numérico de 6 dígitos criptográficamente seguro."""
    return f"{secrets.randbelow(900000) + 100000}"

def get_otp_html_template(user_name: str, otp_code: str) -> str:
    """Retorna una plantilla HTML profesional con la identidad corporativa de CIVIA."""
    user_name = escape(user_name)
    otp_code = escape(otp_code)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Código de Recuperación - CIVIA</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0b1120; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background-color: #111827; border: 1px solid #1f2937; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);">
          <!-- Encabezado con Brand -->
          <tr>
            <td style="padding: 32px 32px 20px 32px; text-align: center; border-bottom: 1px solid #1f2937;">
              <div style="display: inline-block; width: 44px; height: 44px; background: linear-gradient(135deg, #2563eb, #1d4ed8); border-radius: 12px; line-height: 44px; font-size: 22px; font-weight: 800; color: #ffffff; margin-bottom: 12px;">C</div>
              <h1 style="margin: 0; font-size: 20px; font-weight: 800; letter-spacing: 0.05em; color: #ffffff;">CIVIA</h1>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em;">Inteligencia Ciudadana &amp; Gestión Estratégica</p>
            </td>
          </tr>
          
          <!-- Contenido Principal -->
          <tr>
            <td style="padding: 32px;">
              <h2 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 700; color: #f8fafc;">Recuperación de Contraseña</h2>
              <p style="margin: 0 0 20px 0; font-size: 14px; line-height: 1.6; color: #cbd5e1;">
                Hola <strong>{user_name}</strong>, hemos recibido una solicitud para restablecer la contraseña de acceso a tu cuenta institucional en CIVIA.
              </p>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                Utiliza el siguiente código de un solo uso (OTP) para verificar tu identidad y configurar tu nueva clave:
              </p>
              
              <!-- Caja del Código OTP -->
              <div style="text-align: center; margin: 28px 0; padding: 24px 20px; background-color: #0f172a; border: 2px dashed #3b82f6; border-radius: 12px;">
                <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #60a5fa; font-family: 'Courier New', Courier, monospace;">
                  {otp_code}
                </span>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #64748b;">
                  ⏱ Este código expira en <strong>15 minutos</strong>.
                </p>
              </div>
              
              <div style="background-color: #1e293b; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 6px; margin-top: 24px;">
                <p style="margin: 0; font-size: 12px; color: #fbbf24; line-height: 1.5;">
                  <strong>Aviso de Seguridad:</strong> Si tú no solicitaste este cambio, ignora este correo. Tu contraseña actual permanecerá segura y protegida.
                </p>
              </div>
            </td>
          </tr>
          
          <!-- Pie de Página -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0b1120; border-top: 1px solid #1f2937; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #64748b;">
                CIVIA • Seguridad de la cuenta<br>
                Este es un mensaje automático de seguridad, no respondas a este correo.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def smtp_is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD
                and settings.SMTP_FROM_EMAIL and settings.SMTP_PORT > 0
                and settings.SMTP_TLS != settings.SMTP_SSL)


def _send_security_email(to_email, subject, text_content, html_content):
    if not smtp_is_configured():
        logger.warning('Recuperacion no disponible: SMTP sin configurar o transporte inseguro.')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'CIVIA Seguridad <{settings.SMTP_FROM_EMAIL}>'
        msg['To'] = to_email
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
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


def send_otp_email(to_email: str, user_name: str, otp_code: str) -> bool:
    """
    Envía el correo con el código OTP.
    Si hay servidor SMTP configurado lo envía vía SMTP.
    Nunca publica el codigo en la respuesta HTTP ni en los registros del servidor.
    """
    text_content = (
            f"Hola {user_name},\n\n"
            f"Tu código OTP para restablecer tu contraseña en CIVIA es:\n\n"
            f"    {otp_code}\n\n"
            f"Este código es válido por 15 minutos.\n"
            f"Si no solicitaste este cambio, puedes ignorar este mensaje.\n\n"
            f"Equipo de Seguridad CIVIA"
    )
    return _send_security_email(to_email, 'Recuperación de contraseña - CIVIA', text_content, get_otp_html_template(user_name, otp_code))


def send_password_changed_email(to_email: str, user_name: str) -> bool:
    text = f'Hola {user_name}, tu contraseña de CIVIA se restableció y los accesos anteriores quedaron invalidados. Si no solicitaste el cambio, contacta al administrador inmediatamente.'
    return _send_security_email(to_email, 'Tu contraseña de CIVIA cambió', text, f'<p>{escape(text)}</p>')
