"""Retired demonstration entry point; no sample records or initial passwords."""
from fastapi import APIRouter, HTTPException
router = APIRouter(prefix="/seed", tags=["Inicializaci\u00f3n retirada"])

@router.post("")
def seed_database():
    raise HTTPException(410, "La carga de demostraci\u00f3n fue retirada. Usa migraciones y datos reales verificados.")
