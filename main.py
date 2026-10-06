from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_v1_router
from app.core.database import engine, Base

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CIVIA API", description="Plataforma de Inteligencia Ciudadana y Política", version="1.0.0")

# CORS para comunicación con Next.js (puerto 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a la API de CIVIA!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
