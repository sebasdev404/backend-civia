import urllib.request
import json
import os
import sys

# Ensure backend-civia is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.case import Case
from app.services.ai_classifier import ai_classifier

page_token = settings.META_PAGE_ACCESS_TOKEN
pid = "190282074165302" # Noticias El Mandato

print(f"Connecting to Meta Graph API for Page {pid}...")
url = f"https://graph.facebook.com/v21.0/{pid}/posts?fields=id,message,created_time,comments.limit(100){{id,message,from,created_time}}&limit=50&access_token={page_token}"

req = urllib.request.Request(url)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())

posts = data.get("data", [])
print(f"Total posts retrieved from Facebook: {len(posts)}\n")

comments_to_process = []
for p in posts:
    post_time = p.get("created_time", "")[:10]
    post_msg = p.get("message", "(Sin texto)").replace("\n", " ")[:60]
    comments = p.get("comments", {}).get("data", [])
    
    if comments:
        print(f"Post [{post_time}]: {post_msg} -> {len(comments)} comentarios")
        for c in comments:
            c_text = c.get("message", "").strip()
            c_author = c.get("from", {}).get("name", "Ciudadano")
            c_id = c.get("id")
            c_time = c.get("created_time")
            if len(c_text) >= 5:
                comments_to_process.append({
                    "id": c_id,
                    "text": c_text,
                    "author": c_author,
                    "post_title": post_msg,
                    "created_time": c_time
                })

print(f"\nTotal real citizen comments found: {len(comments_to_process)}\n")
for idx, c in enumerate(comments_to_process[:8], 1):
    print(f"  {idx}. [{c['author']}]: \"{c['text']}\"")

