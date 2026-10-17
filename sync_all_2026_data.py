import urllib.request
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup environment & UTF-8
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.services.ai_classifier import ai_classifier

# Ensure all tables exist
Base.metadata.create_all(bind=engine)

def format_colombia_datetime(iso_str: str) -> str:
    if not iso_str:
        return "Fecha reciente"
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S%z")
        col_tz = timezone(timedelta(hours=-5))
        dt_col = dt.astimezone(col_tz)
        meses = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        return f"{dt_col.day} {meses[dt_col.month]} {dt_col.year}, {dt_col.strftime('%I:%M %p')}"
    except Exception:
        return iso_str[:16].replace("T", " ")

def get_month_key(iso_str: str) -> str:
    if not iso_str:
        return "2026-10"
    return iso_str[:7] # e.g. "2026-01"

def fetch_all_meta_posts() -> List[Dict[str, Any]]:
    page_token = settings.META_PAGE_ACCESS_TOKEN
    page_id = getattr(settings, 'META_PAGE_ID', None) or "275486829735525"
    since_ts = 1767225600 # 2026-01-01 00:00:00 UTC

    print("==================================================", flush=True)
    print("CIVIA - SINCRONIZACIÓN COMPLETA 2026 (META GRAPH API)", flush=True)
    print(f"Página Oficial: ID {page_id}", flush=True)
    print("Rango: Desde 01 de Enero de 2026 hasta la fecha", flush=True)
    print("==================================================", flush=True)

    fields = (
        "id,created_time,message,full_picture,attachments{media_type,type},"
        "permalink_url,comments.summary(true).limit(25){id,message,from,created_time}"
    )
    url = f"https://graph.facebook.com/v21.0/{page_id}/posts?fields={fields}&since={since_ts}&limit=25&access_token={page_token}"

    all_posts = []
    page_num = 1

    while url:
        print(f"Descargando lote #{page_num} de Meta Graph API...", flush=True)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"Error consultando página #{page_num}: {e}", flush=True)
            break

        batch = data.get("data", [])
        all_posts.extend(batch)
        print(f"  -> Recibidas {len(batch)} publicaciones (Total acumulado: {len(all_posts)})", flush=True)

        paging = data.get("paging", {})
        url = paging.get("next") if len(batch) > 0 else None
        page_num += 1

    print(f"\nTotal publicaciones recuperadas de 2026: {len(all_posts)}", flush=True)
    return all_posts

def is_meaningful_comment(text: str) -> bool:
    if not text:
        return False
    clean = text.strip()
    if len(clean) < 10:
        return False
    low = clean.lower()
    trivial = ["amen", "amén", "bendiciones", "saludos", "gracias", "excelente", "buen dia", "buenos dias", "exitos", "éxitos", "hola", "apoyo total", "felicidades"]
    if low in trivial:
        return False
    return True

def classify_single_batch(comments_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clasifica un subconjunto de comentarios con GPT-4o-mini.
    """
    if not ai_classifier.client:
        return []

    prompt = f"""Eres CIVIA AI, motor de inteligencia ciudadana de la Alcaldía de Neiva, Huila.
Analiza la siguiente lista de comentarios ciudadanos de Facebook y extrae para CADA UNO:
- id: el mismo id que se envía
- category: Infraestructura | Servicios Públicos | Movilidad | Alumbrado Público | Seguridad | Salud | Medio Ambiente | General
- neighborhood: Barrio de Neiva identificado o 'Neiva (General)'
- commune: Comuna de Neiva (ej. 'Comuna 1' ... 'Comuna 10') o 'No especificada'
- detected_problem: Problema o necesidad específica detectada en máximo 10 palabras
- sentiment: Crítico | Preocupado | Indignación | Neutral | Positivo
- priority_suggestion: Alta | Media | Baja | Crítica
- assigned_department_suggestion: Dependencia competente de Neiva (ej. Las Ceibas E.S.P., Secretaría de Infraestructura y Vías, Secretaría de Movilidad y Tránsito, Alumbrado Público Neiva - ESIP, Secretaría de Gobierno y Convivencia)

Lista de comentarios a analizar:
{json.dumps([{"id": c["id"], "text": c["text"]} for c in comments_batch], ensure_ascii=False)}

Devuelve ÚNICAMENTE un JSON con el formato:
{{"results": [
  {{"id": "...", "category": "...", "neighborhood": "...", "commune": "...", "detected_problem": "...", "sentiment": "...", "priority_suggestion": "...", "assigned_department_suggestion": "..."}}
]}}
"""
    try:
        res = ai_classifier.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres CIVIA AI. Responde exclusivamente JSON estructurado."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=900
        )
        data = json.loads(res.choices[0].message.content)
        return data.get("results", [])
    except Exception as e:
        print(f"Error clasificando lote con OpenAI: {e}", flush=True)
        fallback = []
        for c in comments_batch:
            text = c["text"].lower()
            cat = "General"
            dept = "Despacho Municipal"
            if any(k in text for k in ["agua", "tubo", "fuga", "ceibas", "factura"]):
                cat = "Servicios Públicos"
                dept = "Las Ceibas - Empresas Públicas de Neiva E.S.P."
            elif any(k in text for k in ["via", "vía", "calle", "hueco", "pavimento", "bacheo"]):
                cat = "Infraestructura"
                dept = "Secretaría de Infraestructura y Vías"
            elif any(k in text for k in ["semaforo", "semáforo", "transito", "tránsito", "moto", "carro"]):
                cat = "Movilidad"
                dept = "Secretaría de Movilidad y Tránsito"
            elif any(k in text for k in ["luz", "luminaria", "poste", "oscuro", "esip"]):
                cat = "Alumbrado Público"
                dept = "Alumbrado Público Neiva - ESIP"
            elif any(k in text for k in ["robo", "seguridad", "policia", "atraco"]):
                cat = "Seguridad"
                dept = "Secretaría de Gobierno y Convivencia"

            fallback.append({
                "id": c["id"],
                "category": cat,
                "neighborhood": "Neiva (General)",
                "commune": "No especificada",
                "detected_problem": c["text"][:50],
                "sentiment": "Crítico",
                "priority_suggestion": "Media",
                "assigned_department_suggestion": dept
            })
        return fallback

def run_sync():
    posts_data = fetch_all_meta_posts()
    if not posts_data:
        print("No se encontraron publicaciones para sincronizar.", flush=True)
        return

    db = SessionLocal()

    try:
        print("\nPreparando base de datos PostgreSQL...", flush=True)
        db.query(Case).filter(Case.id.like("CIV-%")).delete(synchronize_session=False)
        db.query(MetaPost).delete(synchronize_session=False)
        db.commit()
        print("Tablas 'cases' y 'meta_posts' preparadas.", flush=True)

        comments_to_classify = []
        processed_posts = []

        for p in posts_data:
            post_id = p.get("id")
            raw_msg = p.get("message") or "Publicación oficial de Johan Steed"
            clean_title = raw_msg.replace("\n", " ").strip()[:90]
            pic = p.get("full_picture")
            permalink = p.get("permalink_url") or f"https://facebook.com/{post_id}"
            iso_time = p.get("created_time")
            published_at = format_colombia_datetime(iso_time)
            month_key = get_month_key(iso_time)

            att = p.get("attachments", {}).get("data", [])
            mtype = "none"
            if pic:
                mtype = "image"
                if att and (att[0].get("media_type") == "video" or att[0].get("type") in ["video", "video_inline", "video_autoplay"]):
                    mtype = "video"

            comms_raw = p.get("comments", {}).get("data", [])
            c_sum = p.get("comments", {}).get("summary", {})
            fb_total = c_sum.get("total_count", len(comms_raw))
            total_comments = max(fb_total, len(comms_raw))

            all_raw_formatted = []
            for c in comms_raw:
                txt = c.get("message", "").strip()
                if txt:
                    all_raw_formatted.append({
                        "id": c.get("id"),
                        "author": c.get("from", {}).get("name", "Ciudadano"),
                        "message": txt,
                        "time": format_colombia_datetime(c.get("created_time")),
                        "is_meaningful": is_meaningful_comment(txt)
                    })

            # Extraer hasta 6 comentarios significativos por publicación para convertirlos en Casos
            selected_comments = []
            for c in comms_raw:
                c_text = c.get("message", "").strip()
                if is_meaningful_comment(c_text):
                    selected_comments.append(c)
                    if len(selected_comments) >= 6:
                        break

            # Si hay comentarios pero ninguno superó el filtro largo, tomar el primero
            if not selected_comments and comms_raw:
                first_text = comms_raw[0].get("message", "").strip()
                if len(first_text) >= 3:
                    selected_comments.append(comms_raw[0])

            post_record = {
                "id": post_id,
                "title": clean_title,
                "message": raw_msg,
                "cover_image": pic,
                "media_type": mtype,
                "permalink_url": permalink,
                "created_time": iso_time,
                "published_at": published_at,
                "month_key": month_key,
                "total_comments": total_comments,
                "cases_count": 0,
                "selected_comments": selected_comments,
                "raw_comments_json": json.dumps(all_raw_formatted, ensure_ascii=False)
            }
            processed_posts.append(post_record)

            for sc in selected_comments:
                comments_to_classify.append({
                    "id": sc.get("id"),
                    "text": sc.get("message", "").strip(),
                    "author": sc.get("from", {}).get("name", "Ciudadano"),
                    "time": sc.get("created_time"),
                    "post_id": post_id,
                    "post_title": clean_title,
                    "post_pic": pic,
                    "post_link": permalink,
                    "media_type": mtype
                })

        print(f"\nPublicaciones procesadas: {len(processed_posts)}", flush=True)
        print(f"Comentarios ciudadanos listos para clasificar: {len(comments_to_classify)}", flush=True)

        # Clasificación concurrente con ThreadPoolExecutor
        classified_map = {}
        batch_size = 8
        batches = [comments_to_classify[i:i + batch_size] for i in range(0, len(comments_to_classify), batch_size)]
        
        print(f"Iniciando clasificación IA concurrente ({len(batches)} lotes)...", flush=True)

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_batch = {executor.submit(classify_single_batch, b): b for b in batches}
            done_count = 0
            for future in as_completed(future_to_batch):
                done_count += 1
                try:
                    results = future.result()
                    for r in results:
                        classified_map[r["id"]] = r
                except Exception as exc:
                    print(f"Excepción en lote: {exc}", flush=True)
                if done_count % 5 == 0 or done_count == len(batches):
                    print(f"  Progreso IA: {done_count}/{len(batches)} lotes completados ({len(classified_map)} comentarios)", flush=True)

        print(f"\n¡Clasificación IA completada con éxito! Comentarios clasificados: {len(classified_map)}", flush=True)

        # Guardar Casos en DB
        case_counter = 1
        post_cases_count = {}

        for item in comments_to_classify:
            c_id = item["id"]
            ai_data = classified_map.get(c_id, {
                "category": "General",
                "neighborhood": "Neiva (General)",
                "commune": "No especificada",
                "detected_problem": item["text"][:50],
                "sentiment": "Crítico",
                "priority_suggestion": "Media",
                "assigned_department_suggestion": "Despacho Municipal"
            })

            case_str_id = f"CIV-2026-{str(case_counter).zfill(4)}"
            case_counter += 1

            post_id = item["post_id"]
            post_cases_count[post_id] = post_cases_count.get(post_id, 0) + 1

            exact_date_time = format_colombia_datetime(item["time"])

            new_case = Case(
                id=case_str_id,
                title=f"{ai_data.get('category')}: {ai_data.get('detected_problem', item['text'][:50])}",
                content=item["text"],
                category=ai_data.get("category", "General"),
                sentiment=ai_data.get("sentiment", "Crítico"),
                priority=ai_data.get("priority_suggestion", "Media"),
                status="Pendiente",
                location=f"{ai_data.get('neighborhood', 'Neiva')} ({ai_data.get('commune', 'Comuna General')})",
                zone=ai_data.get("commune", "Comuna General"),
                date_time=exact_date_time,
                source="Facebook Oficial - Johan Steed",
                author=item["author"],
                media_type=item["media_type"],
                image_url=item["post_pic"],
                impact_if_solved=f"Atención ciudadana al reporte en {ai_data.get('neighborhood', 'Neiva')}.",
                impact_if_ignored="Riesgo de escalamiento y afectación a la percepción comunitaria en redes.",
                assigned_department=ai_data.get("assigned_department_suggestion", "Despacho Municipal"),
                internal_notes=f"[Post ID]: {post_id}\n[Publicación de Origen]: {item['post_title']}\n[Enlace en Facebook]: {item['post_link']}",
                requires_followup=True,
                comments_count=1,
            )
            db.add(new_case)

        db.commit()
        print(f"Casos guardados en DB: {case_counter - 1}", flush=True)

        # Guardar en meta_posts
        print("Guardando publicaciones en tabla 'meta_posts'...", flush=True)
        for p in processed_posts:
            p_id = p["id"]
            cnt = post_cases_count.get(p_id, 0)
            meta_record = MetaPost(
                id=p_id,
                title=p["title"],
                message=p["message"],
                cover_image=p["cover_image"],
                media_type=p["media_type"],
                permalink_url=p["permalink_url"],
                created_time=p["created_time"],
                published_at=p["published_at"],
                month_key=p["month_key"],
                total_comments=p["total_comments"],
                cases_count=cnt,
                raw_comments_json=p["raw_comments_json"]
            )
            db.add(meta_record)

        db.commit()
        print(f"Publicaciones guardadas en DB: {len(processed_posts)}", flush=True)

        # Resumen por mes
        print("\n==================================================", flush=True)
        print("RESUMEN DE SINCRONIZACIÓN POR MES (2026):", flush=True)
        print("==================================================", flush=True)
        months_stat = {}
        for p in processed_posts:
            m = p["month_key"]
            if m not in months_stat:
                months_stat[m] = {"posts": 0, "cases": 0}
            months_stat[m]["posts"] += 1
            months_stat[m]["cases"] += post_cases_count.get(p["id"], 0)

        for m in sorted(months_stat.keys()):
            s = months_stat[m]
            print(f"  Mes {m}: {s['posts']} publicaciones | {s['cases']} casos clasificados", flush=True)

        total_posts_saved = db.query(MetaPost).count()
        total_cases_saved = db.query(Case).count()
        print("--------------------------------------------------", flush=True)
        print(f"TOTAL: {total_posts_saved} publicaciones | {total_cases_saved} casos en PostgreSQL", flush=True)
        print("==================================================", flush=True)

    except Exception as e:
        db.rollback()
        print(f"Error durante la sincronización: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_sync()

