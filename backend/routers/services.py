"""
backend/routers/services.py
---------------------------
CRUD Services
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_permission, get_db
from models import Service, Composant

router = APIRouter(prefix="/services", tags=["Services"])


class ServiceBase(BaseModel):
    code_produit: Optional[str]   = None
    nom:          str
    description:  Optional[str]   = None
    type_service: str              = "internal"
    cout_horaire: Optional[float] = None
    cout_fixe:    Optional[float] = None
    multi_taches: bool             = False


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    code_produit: Optional[str]   = None
    nom:          Optional[str]   = None
    description:  Optional[str]   = None
    type_service: Optional[str]   = None
    cout_horaire: Optional[float] = None
    cout_fixe:    Optional[float] = None
    multi_taches: Optional[bool]  = None


class ServiceResponse(BaseModel):
    id_service:   int
    code_produit: Optional[str]
    nom:          str
    description:  Optional[str]
    type_service: str
    cout_horaire: Optional[float]
    cout_fixe:    Optional[float]
    multi_taches: bool
    nb_composants: int

    class Config:
        from_attributes = True


class ServiceListResponse(BaseModel):
    items: list[ServiceResponse]
    total: int
    page:  int
    pages: int


def _to_response(s: Service, db: Session) -> ServiceResponse:
    nb = db.query(Composant).filter(Composant.id_service == s.id_service).count()
    return ServiceResponse(
        id_service=s.id_service,
        code_produit=s.code_produit,
        nom=s.nom,
        description=s.description,
        type_service=s.type_service,
        cout_horaire=float(s.cout_horaire) if s.cout_horaire else None,
        cout_fixe=float(s.cout_fixe) if s.cout_fixe else None,
        multi_taches=s.multi_taches,
        nb_composants=nb,
    )


@router.get("", response_model=ServiceListResponse)
def list_services(
    search: Optional[str] = Query(None),
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(100, ge=1, le=500),
    db:     Session       = Depends(get_db),
    _user                 = Depends(require_permission("services")),
):
    q = db.query(Service)
    if search:
        like = f"%{search}%"
        q = q.filter(Service.nom.ilike(like) | Service.code_produit.ilike(like))
    q = q.order_by(Service.nom)
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    pages = max(1, (total + limit - 1) // limit)
    return ServiceListResponse(
        items=[_to_response(s, db) for s in items],
        total=total, page=page, pages=pages,
    )


@router.get("/{id_service}", response_model=ServiceResponse)
def get_service(id_service: int, db: Session = Depends(get_db),
                _user=Depends(require_permission("services"))):
    s = db.get(Service, id_service)
    if not s:
        raise HTTPException(404, "Service not found")
    return _to_response(s, db)


@router.post("", response_model=ServiceResponse, status_code=201)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db),
                   _user=Depends(require_permission("services"))):
    s = Service(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_response(s, db)


@router.put("/{id_service}", response_model=ServiceResponse)
def update_service(id_service: int, payload: ServiceUpdate,
                   db: Session = Depends(get_db),
                   _user=Depends(require_permission("services"))):
    s = db.get(Service, id_service)
    if not s:
        raise HTTPException(404, "Service not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return _to_response(s, db)


@router.delete("/{id_service}", status_code=204)
def delete_service(id_service: int, db: Session = Depends(get_db),
                   _user=Depends(require_permission("services"))):
    s = db.get(Service, id_service)
    if not s:
        raise HTTPException(404, "Service not found")
    nb = db.query(Composant).filter(Composant.id_service == id_service).count()
    if nb:
        raise HTTPException(409, f"Cannot delete: used by {nb} component(s)")
    db.delete(s)
    db.commit()
