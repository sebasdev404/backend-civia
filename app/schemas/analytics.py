from pydantic import BaseModel
from typing import Dict, List, Any

class DashboardSummaryResponse(BaseModel):
    total_cases: int
    critical_cases: int
    in_progress_cases: int
    resolved_cases: int
    active_territorial_alerts: int
    primary_category: str
    categories_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    channel_distribution: Dict[str, int]

