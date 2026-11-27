"""Email-safe layouts matching the login identity; no remote assets or fonts."""
from html import escape
from app.core.branding import APP_NAME

BRAND_NAME = APP_NAME
LOGO_CID = 'brand-logo@ordenemos'


def _layout(title: str, content: str, preheader: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{escape(title)} | {BRAND_NAME}</title>
  <style>
    @media only screen and (max-width: 480px) {{
      .email-outer {{ padding: 16px 10px !important; }}
      .email-pad {{ padding: 26px 20px !important; }}
      .email-motto {{ font-size: 25px !important; }}
      .email-title {{ font-size: 23px !important; }}
      .email-code {{ font-size: 34px !important; letter-spacing: 5px !important; }}
    }}
  </style>
</head>
<body bgcolor="#0b0b0b" style="margin:0;padding:0;background-color:#0b0b0b;color:#f4f4f4;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;mso-hide:all;">{escape(preheader)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#0b0b0b" style="background-color:#0b0b0b;">
    <tr><td align="center" class="email-outer" style="padding:32px 16px;">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" bgcolor="#151515" style="width:100%;max-width:600px;background-color:#151515;border:1px solid #353535;border-radius:22px;overflow:hidden;">
        <tr><td style="padding:0 24px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
            <td width="33.33%" height="3" bgcolor="#ef626c" style="height:3px;line-height:3px;font-size:0;">&nbsp;</td>
            <td width="33.33%" height="3" bgcolor="#58c783" style="height:3px;line-height:3px;font-size:0;">&nbsp;</td>
            <td width="33.33%" height="3" bgcolor="#f3cc52" style="height:3px;line-height:3px;font-size:0;">&nbsp;</td>
          </tr></table>
        </td></tr>
        <tr><td align="center" class="email-pad" style="padding:34px 36px 30px;border-bottom:1px solid #353535;">
          <img src="cid:{LOGO_CID}" width="112" alt="{BRAND_NAME}" style="display:block;width:112px;max-width:100%;height:auto;margin:0 auto 20px;border:0;">
          <p class="email-motto" style="margin:0;color:#dddddd;font-family:Georgia,'Times New Roman',serif;font-size:29px;font-weight:bold;font-style:italic;line-height:1.3;">&ldquo;{BRAND_NAME}&rdquo;</p>
        </td></tr>
        <tr><td class="email-pad" style="padding:32px 36px;">
          <h1 class="email-title" style="margin:0 0 20px;font-size:25px;line-height:1.3;font-weight:700;color:#f4f4f4;">{escape(title)}</h1>
          {content}
        </td></tr>
        <tr><td align="center" bgcolor="#101010" style="padding:21px 24px;background-color:#101010;border-top:1px solid #353535;">
          <p style="margin:0;font-size:12px;line-height:1.7;color:#aaaaaa;">Seguridad de tu cuenta<br>Mensaje autom&aacute;tico. No respondas a este correo.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''


def render_otp_email(user_name: str, otp_code: str) -> str:
    name, code = escape(user_name), escape(otp_code)
    content = f'''
      <p style="margin:0 0 16px;color:#c6c6c6;font-size:16px;line-height:1.7;">Hola <strong style="color:#f4f4f4;">{name}</strong>, recibimos una solicitud para restablecer la contrase&ntilde;a de tu cuenta.</p>
      <p style="margin:0 0 25px;color:#c6c6c6;font-size:15px;line-height:1.7;">Introduce este c&oacute;digo en la pantalla de recuperaci&oacute;n para elegir una nueva contrase&ntilde;a.</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#13251b" style="background-color:#13251b;border:1px solid #22804d;border-radius:14px;">
        <tr><td align="center" style="padding:23px 12px 24px;">
          <p style="margin:0 0 13px;font-size:11px;line-height:1.5;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase;color:#58c783;">C&oacute;digo de recuperaci&oacute;n</p>
          <p class="email-code" dir="ltr" style="margin:0;color:#f3cc52;font-family:'Courier New',Courier,monospace;font-size:42px;font-weight:bold;letter-spacing:7px;line-height:1.3;">{code}</p>
          <p style="margin:14px 0 0;color:#c6c6c6;font-size:12px;line-height:1.6;">V&aacute;lido durante <strong style="color:#f4f4f4;">15 minutos</strong> y para un solo uso.</p>
        </td></tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
        <tr><td bgcolor="#212121" style="padding:14px 16px;background-color:#212121;border-left:3px solid #f3cc52;border-radius:6px;">
          <p style="margin:0;color:#c6c6c6;font-size:12px;line-height:1.7;"><strong style="color:#f3cc52;">&iquest;No solicitaste el cambio?</strong><br>Ignora este mensaje. Recibir el c&oacute;digo no cambia tu contrase&ntilde;a. No compartas este c&oacute;digo con otras personas.</p>
        </td></tr>
      </table>'''
    return _layout('Recupera tu contraseña', content, 'Tu código de recuperación es válido durante 15 minutos.')


def render_password_changed_email(user_name: str) -> str:
    content = f'''
      <p style="margin:0 0 24px;color:#c6c6c6;font-size:16px;line-height:1.7;">Hola <strong style="color:#f4f4f4;">{escape(user_name)}</strong>, te confirmamos que se complet&oacute; el cambio de contrase&ntilde;a de tu cuenta.</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#13251b" style="background-color:#13251b;border:1px solid #22804d;border-radius:14px;">
        <tr><td align="center" style="padding:24px 18px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto 16px;"><tr><td width="48" height="48" align="center" valign="middle" bgcolor="#22804d" style="width:48px;height:48px;background-color:#22804d;border-radius:50%;color:#ffffff;font-size:27px;line-height:48px;" aria-hidden="true">&#10003;</td></tr></table>
          <p style="margin:0 0 9px;color:#58c783;font-size:11px;line-height:1.5;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase;">Cambio confirmado</p>
          <p style="margin:0;color:#f4f4f4;font-size:19px;font-weight:bold;line-height:1.5;">Tu nueva contrase&ntilde;a ya est&aacute; activa.</p>
        </td></tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:24px;">
        <tr><td style="padding:0 0 18px;border-bottom:1px solid #353535;">
          <p style="margin:0 0 5px;color:#f4f4f4;font-size:14px;font-weight:bold;line-height:1.6;">Tu pr&oacute;ximo acceso</p>
          <p style="margin:0;color:#c6c6c6;font-size:14px;line-height:1.7;">Utiliza la nueva contrase&ntilde;a cuando vuelvas a iniciar sesi&oacute;n.</p>
        </td></tr>
        <tr><td style="padding:18px 0 0;">
          <p style="margin:0 0 5px;color:#f4f4f4;font-size:14px;font-weight:bold;line-height:1.6;">Sesiones anteriores cerradas</p>
          <p style="margin:0;color:#c6c6c6;font-size:14px;line-height:1.7;">Los accesos abiertos antes del cambio quedaron invalidados.</p>
        </td></tr>
      </table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:25px;">
        <tr><td bgcolor="#212121" style="padding:15px 17px;background-color:#212121;border-left:3px solid #f3cc52;border-radius:6px;">
          <p style="margin:0 0 5px;color:#f3cc52;font-size:13px;line-height:1.6;font-weight:bold;">&iquest;No realizaste este cambio?</p>
          <p style="margin:0;color:#c6c6c6;font-size:13px;line-height:1.7;">Contacta al administrador de la plataforma inmediatamente para revisar el acceso a tu cuenta.</p>
        </td></tr>
      </table>'''
    return _layout('Tu contraseña se actualizó', content, 'Cambio confirmado. Tu nueva contraseña está activa y las sesiones anteriores se cerraron.')
