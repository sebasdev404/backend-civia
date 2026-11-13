"""Conexión e ingesta de Instagram mediante la cuenta vinculada a una página."""

import time

from app.core.config import settings
from app.services.facebook_graph import GraphAPIError, graph_get, iter_connection


MEDIA_FIELDS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"
IG_COMMENT_FIELDS = "id,text,username,from,timestamp,hidden,parent_id"
REQUIRED_PERMISSIONS = ["instagram_basic", "instagram_manage_comments"]
_status_cache = None


def get_instagram_connection(force_refresh=False):
    global _status_cache
    token = settings.META_PAGE_ACCESS_TOKEN
    page_id = settings.META_PAGE_ID
    fingerprint = (token, page_id)
    if not force_refresh and _status_cache and _status_cache[0] == fingerprint and time.monotonic() - _status_cache[1] < 60:
        return dict(_status_cache[2])

    result = {
        "status": "not_configured", "account_id": None, "username": None,
        "detail": "Falta configurar el token o la página de Meta.",
        "required_permissions": REQUIRED_PERMISSIONS, "missing_permissions": [],
        "permissions_checked": False, "comments_available": False,
    }
    if token and page_id:
        scopes = None
        if settings.META_APP_ID and settings.META_APP_SECRET:
            try:
                debug = graph_get("debug_token", f"{settings.META_APP_ID}|{settings.META_APP_SECRET}", input_token=token).get("data", {})
                scopes = set(debug.get("scopes", []))
                result["missing_permissions"] = [permission for permission in REQUIRED_PERMISSIONS if permission not in scopes]
                result["permissions_checked"] = True
            except (GraphAPIError, RuntimeError, TimeoutError):
                pass
        try:
            page = graph_get(page_id, token, fields="instagram_business_account")
            account_id = (page.get("instagram_business_account") or {}).get("id")
            result["account_id"] = account_id
            if not account_id:
                if scopes is not None and "instagram_basic" not in scopes:
                    result.update(status="missing_permissions", detail="El token no autoriza la lectura de Instagram y Meta no devuelve la cuenta vinculada. Autoriza Instagram y verifica que su cuenta profesional esté conectada a esta página.")
                else:
                    result.update(status="not_connected", detail="Meta no devuelve una cuenta profesional de Instagram vinculada a esta página de Facebook.")
            elif scopes is not None and "instagram_basic" not in scopes:
                result.update(status="missing_permissions", detail="La cuenta está vinculada, pero el token no incluye instagram_basic para leer sus publicaciones.")
            else:
                account = graph_get(account_id, token, fields="id,username")
                graph_get(f"{account_id}/media", token, fields="id", limit=1)
                result.update(
                    status="ready", username=account.get("username"),
                    comments_available=scopes is None or "instagram_manage_comments" in scopes,
                    detail="Instagram disponible para sincronizar publicaciones.",
                )
                if not result["comments_available"]:
                    result["detail"] += " Falta instagram_manage_comments para leer comentarios."
        except GraphAPIError as exc:
            result.update(
                status="missing_permissions" if exc.code in (10, 190, 200) else "error",
                detail=f"Meta no permitió verificar Instagram (código {exc.code}). Revisa la vinculación y los permisos del token.",
            )
        except (RuntimeError, TimeoutError):
            result.update(status="error", detail="No fue posible conectar con Meta para verificar Instagram.")

    _status_cache = (fingerprint, time.monotonic(), dict(result))
    return result


def read_instagram_comments(media_id, token):
    rows = {}
    fields = f"{IG_COMMENT_FIELDS},replies.limit(10){{{IG_COMMENT_FIELDS}}}"
    for page in iter_connection(f"{media_id}/comments", token, fields=fields, limit=50):
        for comment in page.get("data", []):
            if not comment.get("id"):
                continue
            rows[comment["id"]] = comment
            replies = comment.get("replies")
            if replies is not None:
                for reply_page in iter_connection(f"{comment['id']}/replies", token, initial=replies, fields=IG_COMMENT_FIELDS, limit=50):
                    for reply in reply_page.get("data", []):
                        if reply.get("id"):
                            rows[reply["id"]] = {**reply, "parent_id": reply.get("parent_id") or comment["id"]}
    return list(rows.values())


def normalize_instagram_comment(comment):
    author = comment.get("from") or {}
    username = comment.get("username") or author.get("username")
    return {
        "id": comment["id"],
        "author": f"@{username.lstrip('@')}" if username else "Usuario de Instagram (🔒 Perfil Protegido por Meta)",
        "author_id": author.get("id"), "author_picture_url": None,
        "author_is_protected": not bool(username),
        "content": (comment.get("text") or "").strip(),
        "parent_id": comment.get("parent_id"), "is_hidden": comment.get("hidden"),
        "source": "Instagram",
    }
