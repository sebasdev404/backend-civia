"""Señales observables, sin afirmar identidad humana, bots ni afinidad política."""
import re
import unicodedata
from collections import Counter, defaultdict


def normalize_content(value):
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"\s+", " ", text).strip()


def comment_signals(comments):
    repeated = Counter(normalize_content(c.get("content")) for c in comments)
    authors = defaultdict(list)
    for comment in comments:
        # Un nombre visible puede coincidir entre personas: solo agrupar IDs entregados por Meta.
        if comment.get("author_id"):
            authors[comment["author_id"]].append(comment)
    results = {}
    for comment in comments:
        text = normalize_content(comment.get("content"))
        signals = []
        if len(text) >= 25 and repeated[text] >= 3:
            signals.append(f"Texto idéntico en {repeated[text]} comentarios de esta publicación.")
        own = authors.get(comment.get("author_id"), [])
        if len(own) >= 10:
            signals.append(f"El mismo ID publicó {len(own)} comentarios en esta captura; conviene revisar su contexto.")
        results[str(comment.get("id"))] = {
            "status": "review" if signals else "insufficient_data", "signals": signals,
            "label": "Señales para revisar" if signals else "Sin evidencia suficiente",
            "explanation": "Estas señales no confirman un bot. No se verificó la identidad ni la automatización de la cuenta.",
        }
    return results
