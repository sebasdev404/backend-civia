import urllib.request
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Set up paths and UTF-8 encoding
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.case import Case
from app.services.ai_classifier import ai_classifier

def format_colombia_datetime(iso_str):
    if not iso_str:
        return "Fecha reciente"
    try:
        # Formato ISO de Meta: "2026-10-12T18:34:04+0000"
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S%z")
        # Colombia es UTC-5
        col_tz = timezone(timedelta(hours=-5))
        dt_col = dt.astimezone(col_tz)
        meses = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        hour_str = dt_col.strftime('%I:%M %p')
        return f"{dt_col.day} {meses[dt_col.month]} {dt_col.year}, {hour_str}"
    except Exception as e:
        return iso_str[:16].replace("T", " ")

def sync_facebook_posts_and_comments(max_posts=50, max_cases_to_create=10):
    page_token = settings.META_PAGE_ACCESS_TOKEN
    page_id = getattr(settings, 'META_PAGE_ID', None) or "275486829735525" # Johan Steed Oficial

    print("==================================================")
    print("CIVIA - SINCRONIZACIÓN DE POSTS, MEDIOS Y FECHAS (META)")
    print(f"Página Seleccionada: ID {page_id}")
    print("==================================================")

    url = (
        f"https://graph.facebook.com/v21.0/{page_id}/posts?"
        f"fields=id,message,created_time,full_picture,attachments{{media_type,type}},permalink_url,"
        f"comments.limit(100){{id,message,from,created_time}}&limit={max_posts}&access_token={page_token}"
    )

    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error consultando Meta Graph API: {e}")
        return

    posts = data.get("data", [])
    print(f"Publicaciones recuperadas de Meta: {len(posts)}")

    db = SessionLocal()

    # Limpiar casos CIV previos para reimportar con imágenes y fecha/hora exacta
    db.query(Case).filter(Case.id.like("CIV-%")).delete(synchronize_session=False)
    db.commit()
    print("Limpieza de casos previos completada. Generando casos con imágenes y fechas exactas...")

    created_count = 0
    base_case_num = 1

    try:
        for p in posts:
            if created_count >= max_cases_to_create:
                break

            post_raw_msg = p.get("message", "Publicación comunitaria en Noticias El Mandato")
            post_title = post_raw_msg.replace("\n", " ").strip()[:90]
            post_pic = p.get("full_picture")
            post_link = p.get("permalink_url", "")
            
            # Detectar si es video o imagen
            att = p.get("attachments", {}).get("data", [])
            media_type = "none"
            if post_pic:
                media_type = "image"
                if att and (att[0].get("media_type") == "video" or att[0].get("type") in ["video", "video_inline", "video_autoplay"]):
                    media_type = "video"

            comments = p.get("comments", {}).get("data", [])

            for c in comments:
                if created_count >= max_cases_to_create:
                    break

                comment_text = c.get("message", "").strip()
                author_name = c.get("from", {}).get("name", "Ciudadano")
                comment_iso_time = c.get("created_time")
                exact_date_time = format_colombia_datetime(comment_iso_time)

                # Filtrar comentarios irrelevantes o menores a 15 caracteres
                if len(comment_text) < 15:
                    continue

                print(f"\n[Procesando comentario de {author_name}]: \"{comment_text[:60]}...\"")
                print(f" -> Fecha y Hora exacta: {exact_date_time}")
                print(f" -> Post Origen: {post_title[:50]}... (Media: {media_type})")
                print(f" -> Foto/Video Post: {post_pic[:60] if post_pic else 'Sin imagen'}")

                # Clasificar con OpenAI (gpt-4o-mini con toponimia de Neiva)
                try:
                    ai_analysis = ai_classifier.classify_comment(comment_text)
                    print(f" -> Clasificación IA: {ai_analysis.get('category')} | Comuna: {ai_analysis.get('commune')} | Prioridad: {ai_analysis.get('priority_suggestion')}")

                    case_id = f"CIV-2026-{str(base_case_num).zfill(4)}"
                    base_case_num += 1

                    new_case = Case(
                        id=case_id,
                        title=f"{ai_analysis.get('category')}: {ai_analysis.get('detected_problem', comment_text[:50])}",
                        content=comment_text,
                        category=ai_analysis.get("category", "General"),
                        sentiment=ai_analysis.get("sentiment", "Crítico"),
                        priority=ai_analysis.get("priority_suggestion", "Media"),
                        status="Pendiente",
                        location=f"{ai_analysis.get('neighborhood', 'Neiva')} ({ai_analysis.get('commune', 'Comuna General')})",
                        zone=ai_analysis.get("commune", "Comuna General"),
                        date_time=exact_date_time,  # ¡FECHA Y HORA EXACTA FORMATEADA!
                        source="Facebook (Noticias El Mandato)",
                        author=author_name,
                        media_type=media_type,      # ¡VIDEO O IMAGEN!
                        image_url=post_pic,         # ¡URL DE LA FOTO/VIDEO DEL POST!
                        impact_if_solved=f"Atención al reclamo ciudadano en {ai_analysis.get('neighborhood', 'Neiva')}.",
                        impact_if_ignored="Riesgo de escalamiento y viralización de la queja en redes sociales.",
                        assigned_department=ai_analysis.get("assigned_department_suggestion", "Despacho Municipal"),
                        internal_notes=f"[Publicación de Origen]: {post_title}\n[Enlace en Facebook]: {post_link}",
                        requires_followup=ai_analysis.get("requires_followup", True),
                        comments_count=1,
                    )
                    db.add(new_case)
                    db.commit()
                    created_count += 1
                    print(f" -> GUARDADO EXITOSO COMO {case_id} CON FOTO Y HORA")
                except Exception as err:
                    print(f" -> Error procesando comentario: {err}")
                    db.rollback()

    finally:
        db.close()

    print("\n==================================================")
    print(f"SINCRONIZACIÓN EXITOSA: {created_count} casos guardados con previsualización multimedia y hora exacta")
    print("==================================================")

if __name__ == "__main__":
    sync_facebook_posts_and_comments(max_posts=50, max_cases_to_create=8)
