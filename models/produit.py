from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base


class Assemblage(Base):
    __tablename__ = "assemblage"

    id_assemblage = Column(Integer, primary_key=True, autoincrement=True)
    nom           = Column(String(255), nullable=False)
    reference     = Column(String(100), nullable=True)
    description   = Column(String, nullable=True)
    prix_revient  = Column(Numeric(12, 2), nullable=True)
    plan_url      = Column(String(500), nullable=True)

    # Relations
    lignes_commande = relationship("LigneCommande", back_populates="assemblage")
    nomenclatures = relationship("Nomenclature",
                                 primaryjoin="and_(Assemblage.id_assemblage==Nomenclature.id_parent, "
                                             "Nomenclature.type_parent=='assemblage')",
                                 foreign_keys="Nomenclature.id_parent",
                                 viewonly=True)
    of_assemblages = relationship("OFAssemblage", back_populates="assemblage")


class Composant(Base):
    __tablename__ = "composant"

    id_composant  = Column(Integer, primary_key=True, autoincrement=True)
    reference     = Column(String(100), nullable=True)
    nom           = Column(String(255), nullable=False)
    type          = Column(String(50), nullable=True)
    description   = Column(String, nullable=True)
    plan_url      = Column(String(500), nullable=True)
    prix_revient = Column(Numeric(12, 2), nullable=True)

    # Matière brute
    id_matiere_brut  = Column(Integer, ForeignKey("matierepremiere.id_matiere"), nullable=True)
    forme_brut       = Column(String(20), nullable=True)
    # forme_brut : 'axe' | 'tube' | 'plaque'

    # Dimensions axe
    brut_diametre    = Column(Numeric(10, 3), nullable=True)  # mm

    # Dimensions tube
    brut_diam_ext    = Column(Numeric(10, 3), nullable=True)  # mm
    brut_diam_int    = Column(Numeric(10, 3), nullable=True)  # mm

    # Commun axe + tube
    brut_longueur    = Column(Numeric(10, 3), nullable=True)  # mm

    # Dimensions plaque
    brut_largeur     = Column(Numeric(10, 3), nullable=True)  # mm
    brut_hauteur     = Column(Numeric(10, 3), nullable=True)  # mm
    brut_epaisseur   = Column(Numeric(10, 3), nullable=True)  # mm

    # Liens service et pièce externe
    id_service       = Column(Integer, ForeignKey("service.id_service"), nullable=True)
    id_piece_externe = Column(Integer, ForeignKey("piece_externe.id_piece_externe"), nullable=True)

    # Relations
    matiere_brut         = relationship("MatierePremiere", foreign_keys=[id_matiere_brut])
    service              = relationship("Service", foreign_keys=[id_service])
    piece_externe        = relationship("PieceExterne", foreign_keys=[id_piece_externe])
    gammes               = relationship("Gamme", back_populates="composant")
    ordres_fabrication   = relationship("OrdreFabrication", back_populates="composant")


class Nomenclature(Base):
    __tablename__ = "nomenclature"

    id_nomenclature  = Column(Integer, primary_key=True, autoincrement=True)
    id_parent        = Column(Integer, nullable=False)
    type_parent      = Column(String(20), nullable=False)
    # type_parent : 'assemblage' | 'composant'
    quantite         = Column(Numeric(10, 3), nullable=False)

    # Liens optionnels — un seul doit être renseigné
    id_composant     = Column(Integer, ForeignKey("composant.id_composant"), nullable=True)
    id_service       = Column(Integer, ForeignKey("service.id_service"), nullable=True)
    id_piece_externe = Column(Integer, ForeignKey("piece_externe.id_piece_externe"), nullable=True)

    # Relations
    composant     = relationship("Composant", foreign_keys=[id_composant])
    service       = relationship("Service", foreign_keys=[id_service])
    piece_externe = relationship("PieceExterne", foreign_keys=[id_piece_externe])


class Service(Base):
    __tablename__ = "service"

    id_service   = Column(Integer, primary_key=True, autoincrement=True)
    code_produit = Column(String(100), nullable=True)
    nom          = Column(String(255), nullable=False)
    description  = Column(String(500), nullable=True)
    type_service = Column(String(20), nullable=False)
    # type_service : 'internal' / 'external'
    cout_horaire = Column(Numeric(10, 2), nullable=True)   # €/h
    cout_fixe    = Column(Numeric(10, 2), nullable=True)   # € fixe
    multi_taches = Column(Boolean, nullable=False, default=False, server_default='0')
    # multi_taches : si True, plusieurs opérations peuvent s'exécuter en même temps sur ce service


class PieceExterne(Base):
    __tablename__ = "piece_externe"

    id_piece_externe = Column(Integer, primary_key=True, autoincrement=True)
    code_produit     = Column(String(100), nullable=True)
    nom              = Column(String(255), nullable=False)
    description      = Column(String(500), nullable=True)
    fournisseur      = Column(String(255), nullable=True)
    prix_unitaire    = Column(Numeric(12, 2), nullable=True)   # €/unit