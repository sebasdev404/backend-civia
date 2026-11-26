"""Read-only check of the configured page; credentials stay in private config."""
from app.core.config import settings
from app.services.facebook_graph import graph_get,GraphAPIError


def check():
    if not settings.META_PAGE_ACCESS_TOKEN or not settings.META_PAGE_ID:
        print('Configura Meta en el entorno privado.');return 1
    try:
        result=graph_get(f'{settings.META_PAGE_ID}/posts',settings.META_PAGE_ACCESS_TOKEN,fields='id',limit=1)
        print('Lectura autorizada; publicaciones recibidas en esta página:',len(result.get('data',[])))
        return 0
    except GraphAPIError as error:
        print(f'Meta rechazó la consulta: código {error.code}, subcódigo {error.subcode}.');return 1
    except Exception:
        print('No se pudo completar la consulta. Revisa conexión y configuración privadas.');return 1


if __name__=='__main__':raise SystemExit(check())
