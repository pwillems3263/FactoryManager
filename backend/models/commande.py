from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Commande(Base):
    __tablename__ = "commande"

    id_commande   = Column(Integer, primary_key=True, autoincrement=True)
    date_commande = Column(Date, nullable=False)
    client        = Column(String(255), nullable=False)
    numero_externe = Column(String(100), nullable=True)
    code_commande = Column(String(8), nullable=True)  # ex: "2604-001"
    date_livraison = Column(Date, nullable=True)  # estimated delivery date — frozen once Part. Confirmed / Confirmed
    date_livraison_reelle = Column(Date, nullable=True)  # actual delivery date — recorded when the order is Finished, kept separate so the two can be compared later
    statut        = Column(String(50), nullable=False, default="estimation")

    lignes = relationship("LigneCommande", back_populates="commande",
                          cascade="all, delete-orphan")


class LigneCommande(Base):
    __tablename__ = "lignecommande"

    id_ligne      = Column(Integer, primary_key=True, autoincrement=True)
    id_commande   = Column(Integer, ForeignKey("commande.id_commande"), nullable=False)
    id_assemblage = Column(Integer, ForeignKey("assemblage.id_assemblage"), nullable=False)
    quantite      = Column(Numeric(10, 3), nullable=False)
    code_ligne = Column(String(11), nullable=True)  # ex: "2604-001-01"
    statut = Column(String(20), nullable=False, default="on_hold")
    # statut : on_hold / released / completed / cancelled
    cancel_reason = Column(String(500), nullable=True)
    prix_revient_snapshot = Column(Numeric(12, 2), nullable=True)
    # Prix de revient de l'assemblage au moment du Release

    commande       = relationship("Commande", back_populates="lignes")
    assemblage     = relationship("Assemblage", back_populates="lignes_commande")
    of_assemblages = relationship("OFAssemblage", back_populates="ligne_commande",
                                  cascade="all, delete-orphan")