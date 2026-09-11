from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth as auth_router
from routers import dashboard as dashboard_router
from routers import composants as composants_router
from routers import matieres as matieres_router
from routers import pieces_externes as pieces_router

app = FastAPI(title="FactoryManager API", version="2.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(composants_router.router)
app.include_router(matieres_router.router)
app.include_router(pieces_router.router)

@app.get("/", tags=["Status"])
def health_check():
    return {"status": "ok", "app": "FactoryManager API", "version": "2.0.0"}
