from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base


class TypeMachine(Base):
    """Référentiel des types de machines, géré depuis l'interface."""
    __tablename__ = "typemachine"

    id_type = Column(Integer, primary_key=True, autoincrement=True)
    nom     = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)

    machines = relationship("Machine", back_populates="type_machine")


class Machine(Base):
    __tablename__ = "machine"

    id_machine      = Column(Integer, primary_key=True, autoincrement=True)
    nom             = Column(String(255), nullable=False)
    type            = Column(String(100), nullable=True)   # conservé pour compatibilité legacy
    id_type_machine = Column(Integer, ForeignKey("typemachine.id_type"), nullable=True)
    capacite_h_jour = Column(Numeric(5, 2), nullable=True)
    statut          = Column(String(50), nullable=False, default="disponible")
    # statut : disponible / maintenance / hors_service
    tarif_horaire = Column(Numeric(10, 2), nullable=True)  # €/heure
    cout_operateur = Column(Numeric(10, 2), nullable=True)  # €/heure opérateur
    charge_operateur = Column(Numeric(5, 2), nullable=True)  # % charge ex: 100 = full time
    travaille_samedi = Column(Boolean, nullable=False, default=False, server_default='0')
    travaille_dimanche = Column(Boolean, nullable=False, default=False, server_default='0')
    multi_taches = Column(Boolean, nullable=False, default=False, server_default='0')
    # multi_taches : si True, plusieurs opérations peuvent s'exécuter en même temps sur cette machine
    # Le planning respecte la contrainte de précédence (OP N attend la fin de OP N-1)
    # mais n'attend pas que la machine soit libre avant de démarrer

    operations            = relationship("Operation", back_populates="machine")
    operations_planifiees = relationship("OperationPlanifiee", back_populates="machine")
    arrets = relationship("ArretMachine", back_populates="machine",
                          cascade="all, delete-orphan")
    shift_configs = relationship("MachineShiftConfig", back_populates="machine",
                                 cascade="all, delete-orphan")
    type_machine  = relationship("TypeMachine", back_populates="machines")


class MatierePremiere(Base):
    __tablename__ = "matierepremiere"

    id_matiere   = Column(Integer, primary_key=True, autoincrement=True)
    nom          = Column(String(255), nullable=False)
    unite        = Column(String(50), nullable=False)
    stock_actuel = Column(Numeric(10, 3), nullable=False, default=0)
    poids_volumique = Column(Numeric(10, 6), nullable=True)  # kg/cm³
    prix_au_kg = Column(Numeric(10, 4), nullable=True)  # €/kg

    operations_matieres = relationship("OperationMatiere", back_populates="matiere")
    composants = relationship("Composant", back_populates="matiere_brut",
                              foreign_keys="Composant.id_matiere_brut")

class ArretMachine(Base):
    __tablename__ = "arretmachine"

    id_arret     = Column(Integer, primary_key=True, autoincrement=True)
    id_machine   = Column(Integer, ForeignKey("machine.id_machine"), nullable=False)
    type_arret   = Column(String(50), nullable=False)
    # type_arret : panne / maintenance_preventive / maintenance_corrective / nettoyage
    date_debut   = Column(DateTime, nullable=False)
    date_fin     = Column(DateTime, nullable=True)   # NULL si arrêt en cours
    description  = Column(String(255), nullable=True)

    machine = relationship("Machine", back_populates="arrets")