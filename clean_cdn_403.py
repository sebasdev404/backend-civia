import os
import sys

sys.path.append(os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.case import Case
from app.models.meta_post import MetaPost

def clean_all_cdn_403():
    db = SessionLocal()
    default_url = "http://localhost:8000/static/covers/default_cover.jpg"
    covers_dir = os.path.join(os.path.dirname(__file__), "static", "covers")

    print("Iniciando saneamiento de URLs de CDN de Meta para evitar errores 403...")

    # 1. Sanear MetaPosts
    posts = db.query(MetaPost).all()
    cleaned_posts = 0
    for p in posts:
        cov = p.cover_image or ""
        if "scontent" in cov or "fbcdn.net" in cov or not cov.startswith("http"):
            safe_id = str(p.id).replace(":", "_").replace("/", "_")
            local_file = os.path.join(covers_dir, f"{safe_id}.jpg")
            if os.path.exists(local_file) and os.path.getsize(local_file) > 1000:
                p.cover_image = f"http://localhost:8000/static/covers/{safe_id}.jpg"
            else:
                p.cover_image = default_url
            cleaned_posts += 1

    # 2. Sanear Casos Ciudadanos
    cases = db.query(Case).all()
    cleaned_cases = 0
    for c in cases:
        img = c.image_url or ""
        if "scontent" in img or "fbcdn.net" in img:
            # Buscar si tiene Post ID asociado en internal_notes
            resolved = default_url
            if c.internal_notes and "[Post ID]:" in c.internal_notes:
                for line in c.internal_notes.split("\n"):
                    if line.startswith("[Post ID]:"):
                        pid = line.replace("[Post ID]:", "").strip()
                        safe_pid = pid.replace(":", "_").replace("/", "_")
                        local_file = os.path.join(covers_dir, f"{safe_pid}.jpg")
                        if os.path.exists(local_file) and os.path.getsize(local_file) > 1000:
                            resolved = f"http://localhost:8000/static/covers/{safe_pid}.jpg"
                        break
            c.image_url = resolved
            cleaned_cases += 1

    db.commit()
    db.close()
    print(f"Saneamiento exitoso:\n- {cleaned_posts} publicaciones actualizadas.\n- {cleaned_cases} casos ciudadanos actualizados con URLs locales permanentes (0 errores 403).")

if __name__ == "__main__":
    clean_all_cdn_403()
