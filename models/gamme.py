from sqlalchemy import Column, Integer, String, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Gamme(Base):
    __tablename__ = "gamme"

    id_gamme     = Column(Integer, primary_key=True, autoincrement=True)
    id_composant = Column(Integer, ForeignKey("composant.id_composant"), nullable=False)
    version      = Column(Integer, nullable=False, default=1)
    active       = Column(Boolean, nullable=False, default=True)

    composant  = relationship("Composant", back_populates="gammes")
    operations = relationship("Operation", back_populates="gamme",
                              order_by="Operation.ordre",
                              cascade="all, delete-orphan")


class Operation(Base):
    __tablename__ = "operation"

    id_operation    = Column(Integer, primary_key=True, autoincrement=True)
    id_gamme        = Column(Integer, ForeignKey("gamme.id_gamme"), nullable=False)
    id_machine      = Column(Integer, ForeignKey("machine.id_machine"), nullable=True)
    id_piece_externe = Column(Integer, ForeignKey("piece_externe.id_piece_externe"), nullable=True)
    id_service = Column(Integer, ForeignKey("service.id_service"), nullable=True)
    ordre           = Column(Integer, nullable=False)
    description     = Column(String(255), nullable=True)
    tps_preparation = Column(Integer, nullable=False, default=0)
    tps_execution   = Column(Integer, nullable=False, default=0)
    plan_url = Column(String(500), nullable=True)

    gamme                 = relationship("Gamme", back_populates="operations")
    machine               = relationship("Machine", back_populates="operations")
    operations_planifiees = relationship("OperationPlanifiee", back_populates="operation")
    matieres_consommees   = relationship("OperationMatiere", back_populates="operation",
                                         cascade="all, delete-orphan")
    piece_externe = relationship("PieceExterne", foreign_keys=[id_piece_externe])
    service = relationship("Service", foreign_keys=[id_service])


class OperationMatiere(Base):
    __tablename__ = "operationmatiere"

    id_operation = Column(Integer, ForeignKey("operation.id_operation"), primary_key=True)
    id_matiere   = Column(Integer, ForeignKey("matierepremiere.id_matiere"), primary_key=True)
    quantite     = Column(Numeric(10, 3), nullable=False)

    operation = relationship("Operation", back_populates="matieres_consommees")
    matiere   = relationship("MatierePremiere", back_populates="operations_matieres")