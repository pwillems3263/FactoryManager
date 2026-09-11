"""
backend/main.py
---------------
Point d'entrée FastAPI — FactoryManager Web.

Démarrage :
    cd backend
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Documentation API interactive :
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth as auth_router
# Les autres routers seront ajoutés ici au fur et à mesure des vagues :
# from routers import composants, matieres, machines, of, planning, pointage ...

app = FastAPI(
    title="FactoryManager API",
    description="API REST pour la gestion de production — FactoryManager",
    version="2.0.0",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
# Autoriser le frontend React (dev: port 5173, prod: même domaine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # React dev alternatif
        # En production : ajouter l'URL du serveur, ex: "https://factory.monentreprise.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
# app.include_router(composants_router.router)   # Vague 1 — à venir
# app.include_router(matieres_router.router)     # Vague 1 — à venir
# app.include_router(machines_router.router)     # Vague 2 — à venir
# app.include_router(of_router.router)           # Vague 3 — à venir
# app.include_router(pointage_router.router)     # Vague 4 — à venir
# app.include_router(planning_router.router)     # Vague 5 — à venir


# ─── Health check ────────────────────────────────────────────────────────────
@app.get("/", tags=["Statut"])
def health_check():
    """Vérifie que l'API est en ligne."""
    return {"status": "ok", "app": "FactoryManager API", "version": "2.0.0"}
