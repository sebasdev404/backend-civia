import urllib.request
import urllib.parse
import json
import os
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

def make_token_permanent(short_lived_token: str, target_page_id: str = "275486829735525"):
    app_id = settings.META_APP_ID
    app_secret = settings.META_APP_SECRET
    
    print("=" * 60)
    print("CONVERTIDOR A TOKEN PERMANENTE DE META (NEVER EXPIRE)")
    print("=" * 60)
    
    # Paso 1: Intercambiar token de 1 hora por token de 60 días
    exchange_url = (
        f"https://graph.facebook.com/v21.0/oauth/access_token?"
        f"grant_type=fb_exchange_token&"
        f"client_id={app_id}&"
        f"client_secret={app_secret}&"
        f"fb_exchange_token={short_lived_token}"
    )
    
    try:
        req = urllib.request.Request(exchange_url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            long_lived_token = data.get("access_token")
            print("✓ Paso 1: Token de 60 días obtenido exitosamente.")
    except Exception as e:
        print(f"✗ Error en Paso 1 (Verifica que el token no haya expirado ya): {e}")
        return None

    # Paso 2: Obtener el Page Access Token PERMANENTE de la página objetivo
    accounts_url = f"https://graph.facebook.com/v21.0/me/accounts?access_token={long_lived_token}"
    try:
        req = urllib.request.Request(accounts_url)
        with urllib.request.urlopen(req) as resp:
            accounts = json.loads(resp.read().decode()).get("data", [])
            
            permanent_page_token = None
            page_name = None
            for acc in accounts:
                if acc.get("id") == target_page_id or "Johan" in acc.get("name", ""):
                    permanent_page_token = acc.get("access_token")
                    page_name = acc.get("name")
                    target_page_id = acc.get("id")
                    break
            
            if not permanent_page_token and accounts:
                # Si no encuentra coincidencia exacta, toma la primera o lista las opciones
                permanent_page_token = accounts[0].get("access_token")
                page_name = accounts[0].get("name")
                target_page_id = accounts[0].get("id")

            if permanent_page_token:
                print(f"✓ Paso 2: Token PERMANENTE obtenido para la página '{page_name}' (ID: {target_page_id})!")
                
                # Paso 3: Guardar automáticamente en .env
                env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    new_lines = []
                    found_token = False
                    found_page = False
                    for line in lines:
                        if line.startswith("META_PAGE_ACCESS_TOKEN="):
                            new_lines.append(f"META_PAGE_ACCESS_TOKEN={permanent_page_token}\n")
                            found_token = True
                        elif line.startswith("META_PAGE_ID="):
                            new_lines.append(f"META_PAGE_ID={target_page_id}\n")
                            found_page = True
                        else:
                            new_lines.append(line)
                    
                    if not found_token:
                        new_lines.append(f"META_PAGE_ACCESS_TOKEN={permanent_page_token}\n")
                    if not found_page:
                        new_lines.append(f"META_PAGE_ID={target_page_id}\n")

                    with open(env_path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                    print("✓ Paso 3: .env actualizado automáticamente con el token permanente.")
                    print("¡Listo! Este token NUNCA caducará mientras no cambies la contraseña de Facebook.")
                    return permanent_page_token
            else:
                print("✗ No se encontraron páginas asociadas a este usuario.")
                return None
    except Exception as e:
        print(f"✗ Error en Paso 2: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tok = sys.argv[1]
        make_token_permanent(tok)
    else:
        print("Uso: python generate_permanent_token.py <SHORT_LIVED_TOKEN>")

