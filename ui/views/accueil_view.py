from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGridLayout, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import (
    Commande, OrdreFabrication, OFAssemblage, Rebut, Machine, ArretMachine
)
from datetime import datetime


class AccueilView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_donnees()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        titre = QLabel("Dashboard")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(titre)

        # KPIs
        self.kpi_layout = QGridLayout()
        self.kpi_layout.setSpacing(15)

        self.kpi_commandes = self._kpi_widget("Orders in production", "0", "#3498db")
        self.kpi_ofs_planif  = self._kpi_widget("Orders to schedule",       "0", "#e67e22")
        self.kpi_ofs_cours   = self._kpi_widget("Orders in progress",       "0", "#8e44ad")
        self.kpi_rebuts      = self._kpi_widget("Scrap this month",      "0", "#e74c3c")
        self.kpi_machines_ok = self._kpi_widget("Machines available",    "0", "#27ae60")
        self.kpi_machines_ko = self._kpi_widget("Non-operational Machines",  "0", "#e74c3c")

        self.kpi_layout.addWidget(self.kpi_commandes,   0, 0)
        self.kpi_layout.addWidget(self.kpi_ofs_planif,  0, 1)
        self.kpi_layout.addWidget(self.kpi_ofs_cours,   0, 2)
        self.kpi_layout.addWidget(self.kpi_rebuts,      0, 3)
        self.kpi_layout.addWidget(self.kpi_machines_ok, 0, 4)
        self.kpi_layout.addWidget(self.kpi_machines_ko, 0, 5)
        layout.addLayout(self.kpi_layout)

        # Two columns
        cols = QHBoxLayout()
        cols.setSpacing(15)

        # Urgent POs
        left = QVBoxLayout()
        left_titre = QLabel("🔴 Urgent Production Orders (priority 1-2)")
        left_titre.setFont(QFont("Arial", 13, QFont.Bold))
        left.addWidget(left_titre)

        self.table_urgents = QTableWidget()
        self.table_urgents.setColumnCount(4)
        self.table_urgents.setHorizontalHeaderLabels([
            "Assembly", "Qty", "Priority", "Status"
        ])
        self.table_urgents.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.table_urgents.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_urgents.setAlternatingRowColors(True)
        self.table_urgents.setStyleSheet(self._table_style())
        left.addWidget(self.table_urgents)

        left_widget = QWidget()
        left_widget.setLayout(left)
        cols.addWidget(left_widget)

        # Machines in stoppage
        right = QVBoxLayout()
        right_titre = QLabel("⚠ Machine Events")
        right_titre.setFont(QFont("Arial", 13, QFont.Bold))
        right.addWidget(right_titre)

        self.table_arrets = QTableWidget()
        self.table_arrets.setColumnCount(4)
        self.table_arrets.setHorizontalHeaderLabels([
            "Machine", "Event Type", "Since", "Duration (h)"
        ])
        self.table_arrets.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.table_arrets.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_arrets.setAlternatingRowColors(True)
        self.table_arrets.setStyleSheet(self._table_style())
        right.addWidget(self.table_arrets)

        right_widget = QWidget()
        right_widget.setLayout(right)
        cols.addWidget(right_widget)

        layout.addLayout(cols)

        # Late POs
        retard_titre = QLabel("⏰ Late Production Orders (due date exceeded)")
        retard_titre.setFont(QFont("Arial", 13, QFont.Bold))
        layout.addWidget(retard_titre)

        self.table_retards = QTableWidget()
        self.table_retards.setColumnCount(5)
        self.table_retards.setHorizontalHeaderLabels([
            "Code OF", "Component", "Quantity", "Due Date", "Status"
        ])
        self.table_retards.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.table_retards.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_retards.setAlternatingRowColors(True)
        self.table_retards.setStyleSheet(self._table_style())
        layout.addWidget(self.table_retards)

    def _kpi_widget(self, titre, valeur, couleur):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {couleur};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        frame.setMinimumHeight(90)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(15, 10, 15, 10)

        lbl_val = QLabel(valeur)
        lbl_val.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_val.setStyleSheet("color: white;")
        lbl_val.setAlignment(Qt.AlignCenter)

        lbl_titre = QLabel(titre)
        lbl_titre.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 12px;")
        lbl_titre.setAlignment(Qt.AlignCenter)
        lbl_titre.setWordWrap(True)

        frame_layout.addWidget(lbl_val)
        frame_layout.addWidget(lbl_titre)
        frame._lbl_val = lbl_val
        return frame

    def _update_kpi(self, frame, valeur):
        frame._lbl_val.setText(str(valeur))

    def _table_style(self):
        return """
            QTableWidget {
                border: 1px solid #dde;
                border-radius: 4px;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """

    def _charger_donnees(self):
        session = SessionLocal()
        try:
            now = datetime.now()
            from models import OperationPlanifiee, LigneCommande

            # KPI "Orders in production" — Commandes ayant au moins un OFAssemblage actif
            nb_commandes = session.query(Commande).filter(
                session.query(OFAssemblage).join(
                    LigneCommande,
                    OFAssemblage.id_ligne == LigneCommande.id_ligne
                ).filter(
                    LigneCommande.id_commande == Commande.id_commande,
                    OFAssemblage.statut.in_(["planifie", "en_cours"])
                ).exists()
            ).count()
            self._update_kpi(self.kpi_commandes, nb_commandes)

            # KPI "Orders to schedule" — OFAssemblages ayant au moins un OF a_planifier
            nb_a_planifier = session.query(OFAssemblage).filter(
                session.query(OrdreFabrication).filter(
                    OrdreFabrication.id_of_assemblage == OFAssemblage.id_of_assemblage,
                    OrdreFabrication.statut == "a_planifier"
                ).exists()
            ).count()
            self._update_kpi(self.kpi_ofs_planif, nb_a_planifier)

            # KPI "Orders in progress" — OFAssemblages ayant au moins une op en_cours
            nb_en_cours = session.query(OFAssemblage).filter(
                session.query(OperationPlanifiee).join(
                    OrdreFabrication,
                    OperationPlanifiee.id_of == OrdreFabrication.id_of
                ).filter(
                    OrdreFabrication.id_of_assemblage == OFAssemblage.id_of_assemblage,
                    OperationPlanifiee.statut == "en_cours"
                ).exists()
            ).count()
            self._update_kpi(self.kpi_ofs_cours, nb_en_cours)

            # KPI scrap this month
            debut_mois = now.replace(day=1, hour=0, minute=0, second=0)
            nb_rebuts = session.query(Rebut).filter(
                Rebut.date_constat >= debut_mois
            ).count()
            self._update_kpi(self.kpi_rebuts, nb_rebuts)

            # KPI machines
            nb_dispo = session.query(Machine).filter(
                Machine.statut == "available"
            ).count()
            nb_arret = session.query(Machine).filter(
                Machine.statut != "available"
            ).count()
            self._update_kpi(self.kpi_machines_ok, nb_dispo)
            self._update_kpi(self.kpi_machines_ko, nb_arret)

            # Urgent Assembly Orders — une ligne par OFAssemblage
            ofa_urgents = session.query(OFAssemblage).filter(
                OFAssemblage.priorite <= 2,
                OFAssemblage.statut.in_(["planifie", "en_cours"])
            ).order_by(OFAssemblage.priorite).all()

            statut_map = {
                "a_planifier": "To Schedule",
                "planifie":    "Planned",
                "en_cours":    "In Progress",
                "termine":     "Completed",
                "annule":      "Cancelled",
            }

            self.table_urgents.setRowCount(len(ofa_urgents))
            for row, ofa in enumerate(ofa_urgents):
                assembly_nom = ofa.assemblage.nom if ofa.assemblage else "—"
                self.table_urgents.setItem(row, 0, QTableWidgetItem(assembly_nom))
                self.table_urgents.setItem(row, 1, QTableWidgetItem(str(ofa.quantite)))
                prio_item = QTableWidgetItem(str(ofa.priorite))
                prio_item.setForeground(QColor("#e74c3c"))
                prio_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table_urgents.setItem(row, 2, prio_item)
                # Statut déduit depuis les opérations (source de vérité)
                ids_ofs = [of.id_of for of in ofa.ordres_fabrication]
                ops = session.query(OperationPlanifiee).filter(
                    OperationPlanifiee.id_of.in_(ids_ofs)
                ).all() if ids_ofs else []
                if ops and any(o.statut == "en_cours" for o in ops):
                    statut_effectif = "en_cours"
                elif ops and all(o.statut in ("terminee", "rebutee") for o in ops):
                    statut_effectif = "termine"
                else:
                    statut_effectif = ofa.statut
                statut_txt = statut_map.get(statut_effectif, statut_effectif)
                statut_item = QTableWidgetItem(statut_txt)
                couleur_statut = {
                    "en_cours": "#8e44ad", "termine": "#27ae60",
                    "planifie": "#3498db", "a_planifier": "#e67e22",
                }.get(statut_effectif, "#3498db")
                statut_item.setForeground(QColor(couleur_statut))
                statut_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table_urgents.setItem(row, 3, statut_item)

            # Machines in stoppage
            arrets = session.query(ArretMachine).filter(
                ArretMachine.date_fin.is_(None)
            ).all()

            self.table_arrets.setRowCount(len(arrets))
            for row, a in enumerate(arrets):
                self.table_arrets.setItem(row, 0, QTableWidgetItem(
                    a.machine.nom if a.machine else "—"))
                self.table_arrets.setItem(row, 1, QTableWidgetItem(a.type_arret))
                self.table_arrets.setItem(row, 2, QTableWidgetItem(
                    str(a.date_debut)[:16] if a.date_debut else "—"))
                duree = (now - a.date_debut).total_seconds() / 3600
                duree_item = QTableWidgetItem(f"{duree:.1f}")
                duree_item.setForeground(QColor("#e74c3c"))
                self.table_arrets.setItem(row, 3, duree_item)

            # Late POs
            ofs_retard = session.query(OrdreFabrication).filter(
                OrdreFabrication.date_fin_prevue < now,
                OrdreFabrication.statut.in_(["planifie", "en_cours"])
            ).order_by(OrdreFabrication.date_fin_prevue).all()

            self.table_retards.setRowCount(len(ofs_retard))
            for row, of in enumerate(ofs_retard):
                self.table_retards.setItem(row, 0, QTableWidgetItem(
                    of.code_of or "—"))
                self.table_retards.setItem(row, 1, QTableWidgetItem(
                    of.composant.nom if of.composant else "—"))
                self.table_retards.setItem(row, 2, QTableWidgetItem(
                    str(of.quantite)))
                date_item = QTableWidgetItem(
                    str(of.date_fin_prevue)[:16] if of.date_fin_prevue else "—"
                )
                date_item.setForeground(QColor("#e74c3c"))
                self.table_retards.setItem(row, 3, date_item)
                statut_txt = statut_map.get(of.statut, of.statut)
                self.table_retards.setItem(row, 4, QTableWidgetItem(statut_txt))

        finally:
            session.close()