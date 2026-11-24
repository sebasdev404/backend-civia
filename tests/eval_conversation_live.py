"""Evaluación opcional contra IA real con ejemplos sintéticos; no guarda datos.

Ejecutar: python tests/eval_conversation_live.py
Consume una llamada al proveedor configurado. No forma parte de unittest discover.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.conversation import ai_classifier, classify_batch


def main():
    if ai_classifier.client is None:
        raise SystemExit("No hay cliente de IA configurado")
    context = {
        "title": "Denuncia de robos en Neiva", "caption": "",
        "summary": "Johan denuncia la inseguridad en Neiva y exige medidas contra los robos; cuestiona a los responsables.",
        "transcript": "", "source": "summary", "ready": True, "is_video": True,
    }
    examples = [
        ("angry_support", "Sí, es verdad, las ratas de este pueblo solamente roban", "support"),
        ("direct_criticism", "Johan solamente critica y nunca propone nada", "criticism"),
        ("local_report", "En mi barrio también se roban las motos", "neutral"),
        ("sarcasm", "Excelente Johan, otro video para criticar y ninguna solución, como siempre", "criticism"),
    ]
    comments = [{"id": key, "content": content, "parent": None} for key, content, _ in examples]
    values = classify_batch(context, comments, ai_classifier.client)
    print(json.dumps(values, ensure_ascii=True, indent=2))
    for key, _, expected in examples:
        assert values[key]["stance"] == expected, f"{key}: expected {expected}, got {values[key]['stance']}"
        assert not values[key]["needs_review"], f"{key}: unexpectedly marked for review"
    assert values["angry_support"]["emotion"] == "Enojo o ira"
    print("All contextual examples passed")


if __name__ == "__main__":
    main()
