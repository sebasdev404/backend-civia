"""Diagnóstico de solo lectura: python diagnose_facebook_comments.py POST_ID.

No crea casos, no llama a OpenAI y no imprime tokens ni textos de ciudadanos.
"""

import argparse
import json

from app.core.config import settings
from app.services.facebook_graph import COMMENT_FIELDS, graph_get, iter_connection, video_nodes


def describe(rows):
    return [
        {
            "id": row.get("id"),
            "author": (row.get("from") or {}).get("name"),
            "parent_id": (row.get("parent") or {}).get("id"),
            "is_hidden": row.get("is_hidden"),
            "reply_count": row.get("comment_count"),
        }
        for row in rows
    ]


def diagnose(post_id):
    token = settings.META_PAGE_ACCESS_TOKEN
    if not token:
        raise RuntimeError("Falta META_PAGE_ACCESS_TOKEN")
    report = {"page": graph_get("me", token, fields="id,name")}
    if settings.META_APP_ID and settings.META_APP_SECRET:
        debug = graph_get(
            "debug_token", f"{settings.META_APP_ID}|{settings.META_APP_SECRET}", input_token=token,
        ).get("data", {})
        report["token"] = {key: debug.get(key) for key in (
            "is_valid", "type", "app_id", "expires_at", "data_access_expires_at", "scopes",
        )}
    post = graph_get(post_id, token, fields="id,permalink_url,attachments{media_type,type,target,subattachments}")
    report["post"] = post
    report["connections"] = []
    for node in dict.fromkeys([post_id, *video_nodes(post)]):
        for mode in ("toplevel", "stream"):
            params = dict(fields=COMMENT_FIELDS, filter=mode, limit=100, summary="true")
            if node != post_id:
                params["live_filter"] = "no_filter"
            pages = list(iter_connection(f"{node}/comments", token, **params))
            rows = [row for page in pages for row in page.get("data", [])]
            result = {
                "node": node, "filter": mode, "pages": len(pages),
                "summary": pages[0].get("summary"), "comments": describe(rows),
            }
            if mode == "toplevel":
                result["threads"] = []
                for row in rows:
                    replies = [reply for page in iter_connection(
                        f"{row['id']}/comments", token, fields=COMMENT_FIELDS, limit=100,
                    ) for reply in page.get("data", [])]
                    result["threads"].append({"parent_id": row["id"], "replies": describe(replies)})
            report["connections"].append(result)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("post_id")
    args = parser.parse_args()
    try:
        print(json.dumps(diagnose(args.post_id), ensure_ascii=True, indent=2))
    except Exception as exc:
        # Evitar tracebacks de urllib con URLs y credenciales del depurador.
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        raise SystemExit(1)
