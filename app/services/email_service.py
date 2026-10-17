import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import secrets
from typing import Optional
from app.core.config import settings

logger = logging.getLogger("civia.email")

def generate_otp_code() -> str:
    """Genera un código OTP numérico de 6 dígitos criptográficamente seguro."""
    return f"{secrets.randbelow(900000) + 100000}"

def get_otp_html_template(user_name: str, otp_code: str) -> str:
    """Retorna una plantilla HTML profesional con la identidad corporativa de CIVIA."""
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
                Alcaldía y Despacho de Gobierno • Sistema Integral CIVIA 2026<br>
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

def send_otp_email(to_email: str, user_name: str, otp_code: str) -> bool:
    """
    Envía el correo con el código OTP.
    Si hay servidor SMTP configurado lo envía vía SMTP.
    En cualquier caso, registra el OTP claramente en la consola del servidor para desarrollo y auditoría.
    """
    # 1. Log visual enriquecido en consola para desarrollo
    print("\n" + "="*60)
    print("[CIVIA SEGURIDAD] CODIGO OTP DE RECUPERACION GENERADO")
    print(f"Destinatario: {to_email} ({user_name})")
    print(f"CODIGO OTP:   >>> {otp_code} <<<")
    print("Vigencia:     15 minutos")
    print("="*60 + "\n")

    # 2. Si no hay host SMTP configurado, completamos de forma exitosa en modo desarrollo
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info(f"SMTP no configurado en .env. Codigo OTP {otp_code} registrado para {to_email}.")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Codigo de Recuperacion OTP: {otp_code} - CIVIA"
        msg["From"] = f"CIVIA Seguridad <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        # Texto plano alternativo
        text_content = (
            f"Hola {user_name},\n\n"
            f"Tu código OTP para restablecer tu contraseña en CIVIA es:\n\n"
            f"    {otp_code}\n\n"
            f"Este código es válido por 15 minutos.\n"
            f"Si no solicitaste este cambio, puedes ignorar este mensaje.\n\n"
            f"Equipo de Seguridad CIVIA"
        )
        html_content = get_otp_html_template(user_name, otp_code)

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        if settings.SMTP_TLS:
            server.starttls()
        if settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        
        server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Correo OTP enviado exitosamente vía SMTP a {to_email}")
        return True
    except Exception as e:
        logger.error(f"Error enviando correo OTP vía SMTP a {to_email}: {e}")
        # Retornamos True para que el usuario pueda usar el código visualizado en consola
        return True
