from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base


class MachineShiftConfig(Base):
    """
    Stores which shifts are active for a given machine.
    shift_index : 0 = 6h–14h, 1 = 14h–22h, 2 = 22h–6h
    active      : True = machine works this shift (default True for all)
    """
    __tablename__ = "machineshiftconfig"

    id_config   = Column(Integer, primary_key=True, autoincrement=True)
    id_machine  = Column(Integer, ForeignKey("machine.id_machine"), nullable=False)
    shift_index = Column(Integer, nullable=False)   # 0, 1 or 2
    active      = Column(Boolean, nullable=False, default=True)

    machine = relationship("Machine", back_populates="shift_configs")


class OFAssemblage(Base):
    __tablename__ = "ofassemblage"

    id_of_assemblage = Column(Integer, primary_key=True, autoincrement=True)
    id_ligne         = Column(Integer, ForeignKey("lignecommande.id_ligne"), nullable=False)
    id_assemblage    = Column(Integer, ForeignKey("assemblage.id_assemblage"), nullable=False)
    quantite         = Column(Numeric(10, 3), nullable=False)
    date_lancement   = Column(DateTime, nullable=True)
    date_fin_prevue  = Column(DateTime, nullable=True)
    priorite         = Column(Integer, nullable=False, default=5, server_default='5')
    # priorite : 1 = urgent, 2 = high, 3-4 = elevated, 5 = normal (default)
    statut           = Column(String(50), nullable=False, default="planifie")
    # statut : planifie / en_cours / termine / annule

    ligne_commande     = relationship("LigneCommande", back_populates="of_assemblages")
    assemblage         = relationship("Assemblage", back_populates="of_assemblages")
    ordres_fabrication = relationship("OrdreFabrication", back_populates="of_assemblage",
                                      cascade="all, delete-orphan")


class OrdreFabrication(Base):
    __tablename__ = "ordrefabrication"

    id_of            = Column(Integer, primary_key=True, autoincrement=True)
    id_of_assemblage = Column(Integer, ForeignKey("ofassemblage.id_of_assemblage"),
                              nullable=False)
    id_composant     = Column(Integer, ForeignKey("composant.id_composant"), nullable=False)
    id_of_parent     = Column(Integer, ForeignKey("ordrefabrication.id_of"), nullable=True)
    type_of          = Column(String(50), nullable=False, default="normal")
    # type_of : normal / retouche / complement
    code_of               = Column(String(14), nullable=True)  # ex: "2604-001-01-01"
    quantite              = Column(Numeric(10, 3), nullable=False)
    date_lancement        = Column(DateTime, nullable=True)
    date_fin_prevue       = Column(DateTime, nullable=True)
    date_fin_reelle       = Column(DateTime, nullable=True)
    prix_revient_snapshot = Column(Numeric(12, 2), nullable=True)
    # Prix de revient du composant au moment de la génération de l'OF
    statut           = Column(String(50), nullable=False, default="a_planifier")
    # statut : a_planifier / planifie / en_cours / termine / rebute

    of_assemblage         = relationship("OFAssemblage", back_populates="ordres_fabrication")
    composant             = relationship("Composant", back_populates="ordres_fabrication")
    of_parent             = relationship("OrdreFabrication", remote_side="OrdreFabrication.id_of",
                                         back_populates="retouches")
    retouches             = relationship("OrdreFabrication", back_populates="of_parent")
    operations_planifiees = relationship("OperationPlanifiee", back_populates="of",
                                         cascade="all, delete-orphan")
    rebuts                = relationship("Rebut", back_populates="of",
                                         cascade="all, delete-orphan")
    livraisons            = relationship("LivraisonPartielle", back_populates="of",
                                         cascade="all, delete-orphan")

    @property
    def priorite(self):
        """Convenience proxy — returns the parent assembly's priority."""
        return self.of_assemblage.priorite if self.of_assemblage else 5


class OperationPlanifiee(Base):
    __tablename__ = "operationplanifiee"

    id_op_plan        = Column(Integer, primary_key=True, autoincrement=True)
    id_of             = Column(Integer, ForeignKey("ordrefabrication.id_of"), nullable=False)
    id_operation      = Column(Integer, ForeignKey("operation.id_operation"), nullable=False)
    id_machine        = Column(Integer, ForeignKey("machine.id_machine"), nullable=True)
    id_service        = Column(Integer, ForeignKey("service.id_service"), nullable=True)
    date_debut        = Column(DateTime, nullable=True)
    date_fin          = Column(DateTime, nullable=True)
    date_debut_reelle = Column(DateTime, nullable=True)
    date_fin_reelle   = Column(DateTime, nullable=True)
    tps_prep_reel     = Column(Integer, nullable=True)
    tps_exec_reel     = Column(Integer, nullable=True)
    duree_reelle_min  = Column(Integer, nullable=True)
    # duree_reelle_min = tps_prep_reel + tps_exec_reel, stocké indépendamment
    # des horaires machine pour rester valide après reconfiguration
    statut            = Column(String(50), nullable=False, default="planifiee")
    # statut : planifiee / en_cours / terminee / rebutee

    of        = relationship("OrdreFabrication", back_populates="operations_planifiees")
    operation = relationship("Operation", back_populates="operations_planifiees")
    machine   = relationship("Machine", back_populates="operations_planifiees")
    service   = relationship("Service", foreign_keys=[id_service])
    rebuts = relationship("Rebut", back_populates="operation_planifiee")
    pauses = relationship("PausePointage", back_populates="operation_planifiee",  # ← ajouter
                          cascade="all, delete-orphan",
                          order_by="PausePointage.debut_pause")

class PausePointage(Base):
    """
    Enregistre chaque plage de pause sur une opération en cours.
    - debut_pause  : horodatage de début de pause (obligatoire)
    - fin_pause    : horodatage de reprise (NULL = pause encore active)
    - duree_min    : durée calculée en minutes lors de la reprise
    - motif        : raison de la pause (repas / panne / attente_matiere / formation / autre)
    """
    __tablename__ = "pausepointage"

    id_pause = Column(Integer, primary_key=True, autoincrement=True)
    id_op_plan = Column(Integer, ForeignKey("operationplanifiee.id_op_plan"), nullable=False)
    debut_pause = Column(DateTime, nullable=False)
    fin_pause = Column(DateTime, nullable=True)  # NULL = en cours
    duree_min = Column(Integer, nullable=True)  # calculé à la reprise
    motif = Column(String(100), nullable=True)
    # motif : repas / panne / attente_matiere / formation / autre

    operation_planifiee = relationship("OperationPlanifiee", back_populates="pauses")

class Rebut(Base):
    __tablename__ = "rebut"

    id_rebut         = Column(Integer, primary_key=True, autoincrement=True)
    id_of            = Column(Integer, ForeignKey("ordrefabrication.id_of"), nullable=False)
    id_op_plan       = Column(Integer, ForeignKey("operationplanifiee.id_op_plan"), nullable=False)
    date_constat     = Column(DateTime, nullable=False)
    quantite_rebutee = Column(Numeric(10, 3), nullable=False)
    cause            = Column(String(255), nullable=True)
    decision         = Column(String(50), nullable=False)
    # decision : rebut_definitif / retouche

    of                  = relationship("OrdreFabrication", back_populates="rebuts")
    operation_planifiee = relationship("OperationPlanifiee", back_populates="rebuts")


class LivraisonPartielle(Base):
    __tablename__ = "livraisonpartielle"

    id_livraison   = Column(Integer, primary_key=True, autoincrement=True)
    id_of          = Column(Integer, ForeignKey("ordrefabrication.id_of"), nullable=False)
    date_livraison = Column(DateTime, nullable=False)
    quantite       = Column(Numeric(10, 3), nullable=False)
    commentaire    = Column(String(255), nullable=True)

    of = relationship("OrdreFabrication", back_populates="livraisons")