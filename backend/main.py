from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth as auth_router
from routers import dashboard as dashboard_router
from routers import composants as composants_router
from routers import matieres as matieres_router
from routers import pieces_externes as pieces_router
from routers import services as services_router
from routers import machines as machines_router
from routers import assemblages as assemblages_router
from routers import commandes as commandes_router
from routers import of as of_router
from routers import production_track as prod_router
from routers import time_tracking as tt_router
from routers import users as users_router
from routers import planning as planning_router
from routers import settings as settings_router
from routers import db_admin as db_admin_router

app = FastAPI(title="FactoryManager API", version="2.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(composants_router.router)
app.include_router(matieres_router.router)
app.include_router(pieces_router.router)
app.include_router(services_router.router)
app.include_router(machines_router.router)
app.include_router(assemblages_router.router)
app.include_router(commandes_router.router)
app.include_router(of_router.router)
app.include_router(prod_router.router)
app.include_router(tt_router.router)
app.include_router(users_router.router)
app.include_router(planning_router.router)
app.include_router(settings_router.router)
app.include_router(db_admin_router.router)

@app.get("/", tags=["Status"])
def health_check():
    return {"status": "ok", "app": "FactoryManager API", "version": "2.0.0"}
