"""Lectura de Graph API sin exponer tokens en URLs ni mensajes de error."""

import json
import urllib.error
import urllib.parse
import urllib.request


GRAPH_ROOT = "https://graph.facebook.com/v21.0/"
COMMENT_FIELDS = (
    "id,message,from{id,name,picture.width(80).height(80){url,is_silhouette}},"
    "created_time,parent,is_hidden,comment_count,permalink_url"
)
PROTECTED_FACEBOOK_AUTHOR = "Usuario de Facebook (🔒 Perfil Protegido por Meta)"


def facebook_author_fields(comment):
    """Conserva solo identidad y foto que Meta efectivamente devuelve."""
    author = comment.get("from") or {}
    picture = ((author.get("picture") or {}).get("data") or {})
    picture_url = picture.get("url")
    if picture.get("is_silhouette") or not isinstance(picture_url, str) or not picture_url.startswith("https://"):
        picture_url = None
    elif "access_token" in urllib.parse.parse_qs(urllib.parse.urlsplit(picture_url).query):
        # Nunca enviar credenciales de Graph API al navegador mediante una foto.
        picture_url = None
    return {
        "author": author.get("name") or PROTECTED_FACEBOOK_AUTHOR,
        "author_id": author.get("id"),
        "author_picture_url": picture_url,
        "author_is_protected": not bool(author.get("name")),
        "permalink_url": comment.get("permalink_url"),
    }


class GraphAPIError(RuntimeError):
    def __init__(self, error):
        self.code = error.get("code")
        self.subcode = error.get("error_subcode")
        # Las excepciones HTTP originales incluyen URLs con credenciales.
        super().__init__(f"Meta Graph API: código {self.code}, subcódigo {self.subcode}")


def graph_get(node, token, **params):
    url = GRAPH_ROOT + node + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error = json.load(exc).get("error", {})
        except (ValueError, AttributeError):
            error = {"code": exc.code}
        # Meta puede rechazar páginas densas por el volumen de campos expandidos.
        limit = int(params.get("limit", 1))
        if error.get("code") == 1 and "reduce the amount of data" in error.get("message", "").lower() and limit > 1:
            return graph_get(node, token, **{**params, "limit": max(1, limit // 2)})
        raise GraphAPIError(error) from None
    except urllib.error.URLError:
        raise RuntimeError("No fue posible conectar con Meta Graph API") from None
    if "error" in result:
        raise GraphAPIError(result["error"])
    return result


def iter_connection(node, token, *, initial=None, max_pages=None, **params):
    """Sigue paging.next mediante su cursor, incluso si una página llega corta."""
    page = initial if initial is not None else graph_get(node, token, **params)
    seen = set()
    count = 0
    while True:
        yield page
        count += 1
        next_url = (page.get("paging") or {}).get("next")
        if not next_url:
            return
        if max_pages is not None and count >= max_pages:
            raise RuntimeError(f"Se alcanzó el límite de {max_pages} páginas de Meta")
        # No reenviar URLs ni tokens que vengan dentro de paging.next.
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(next_url).query)
        after = query.get("after", [None])[0]
        if not after or after in seen:
            raise RuntimeError("Meta devolvió un cursor de paginación ausente o repetido")
        seen.add(after)
        next_params = {**params, "after": after}
        # Conservar el tamaño aceptado por Meta si hubo reducción de la página.
        if query.get("limit", [""])[0].isdigit():
            next_params["limit"] = max(1, min(int(query["limit"][0]), int(params.get("limit", 100))))
        params = next_params
        page = graph_get(node, token, **params)


def video_nodes(post):
    nodes = []

    def visit(attachments):
        for attachment in attachments.get("data", []):
            if attachment.get("media_type") == "video" or attachment.get("type", "").startswith("video"):
                node = (attachment.get("target") or {}).get("id")
                if node and node not in nodes:
                    nodes.append(node)
            visit(attachment.get("subattachments") or {})

    visit(post.get("attachments") or {})
    return nodes


def read_comments(node, token, initial=None):
    rows = {}
    total = 0
    for page in iter_connection(
        f"{node}/comments", token, initial=initial,
        fields=COMMENT_FIELDS, filter="stream", summary="true", limit=100,
    ):
        total = max(total, (page.get("summary") or {}).get("total_count", 0))
        for comment in page.get("data", []):
            if comment.get("id"):
                rows[comment["id"]] = comment
    return list(rows.values()), max(total, len(rows))


def read_post_comments(post, token):
    comments, total = read_comments(post["id"], token, initial=post.get("comments"))
    rows = {comment["id"]: comment for comment in comments}
    for node in video_nodes(post):
        if node == post["id"]:
            continue
        video_comments, video_total = read_comments(node, token)
        total = max(total, video_total)
        for comment in video_comments:
            rows[comment["id"]] = comment
    return list(rows.values()), max(total, len(rows))
