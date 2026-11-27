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
    missing = {**context, 'summary': '', 'caption': 'Johan comparte una publicación.', 'source': 'missing', 'ready': False}
    explicit = [
        ('explicit_support', 'Excelente trabajo Johan, siga así, lo apoyo.', 'support'),
        ('explicit_criticism', 'Johan es un mentiroso y nunca cumple nada.', 'criticism'),
        ('only_criticism', 'Solo critica y critica, nunca propone nada Johan.', 'criticism'),
        ('unrelated', 'Salmo 23: El Señor es mi pastor; nada me faltará.', 'neutral'),
        ('tag', 'Pedro Ramírez', 'neutral'),
        ('third_party', 'El alcalde Germán Casagua no cumple con la ciudad.', 'neutral'),
        ('mixed', 'Tiene razón Johan con esta denuncia, pero usted nunca propone soluciones.', 'mixed'),
        ('request_third_party', 'Señor Johan, por favor denuncie a ese alcalde corrupto y pida que devuelvan la plata.', 'support'),
        ('compare_third_parties', 'No me cae bien Casagua pero ese señor ha hecho más que Gorky, que ese sí se robó todo.', 'neutral'),
        ('campaign_reproach', 'Haga campaña con sus propuestas Johan, no denigrando de los demás.', 'criticism'),
    ]
    values = classify_batch(missing, [{'id': key, 'content': text, 'parent': None} for key, text, _ in explicit], ai_classifier.client)
    for key, _, expected in explicit:
        assert values[key]['stance'] == expected, f'{key}: expected {expected}, got {values[key]["stance"]}'
        assert not values[key]['needs_review'], f'{key}: unexpectedly blocked by missing transcript'
    print("All contextual examples passed")


if __name__ == "__main__":
    main()
