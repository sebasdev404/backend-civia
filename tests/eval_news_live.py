"""Optional GPT-4o mini evaluation with synthetic news; never persists articles."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.news_monitor import classify_batch,ai_classifier

if __name__=='__main__':
    now=datetime.now(timezone.utc).isoformat()
    articles=[
        SimpleNamespace(id='fixture-water',title='Corte de agua en Neiva',message='El acueducto informa un corte de agua por rotura de tubería que afecta hoy a doce barrios de Neiva durante las próximas ocho horas.',created_time=now),
        SimpleNamespace(id='fixture-sports',title='Resultado deportivo en Madrid',message='Un club de fútbol de Madrid ganó un torneo local de España. La noticia no menciona Colombia.',created_time=now),
        SimpleNamespace(id='fixture-unknown',title='Transmisión en vivo',message='',created_time=now),
    ]
    result=classify_batch(articles,ai_classifier.client)
    assert result['fixture-water']['priority']=='Alta' and result['fixture-water']['territory']=='Neiva'
    assert result['fixture-sports']['priority']=='Fuera de foco'
    assert result['fixture-unknown']['needs_review']
    print('GPT-4o mini: 3 synthetic regional-news relevance checks passed; no data saved.')
