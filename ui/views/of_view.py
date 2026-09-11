from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QSpinBox, QSplitter,
    QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import OFAssemblage, OrdreFabrication, OperationPlanifiee, LigneCommande
from services.planning_service import planifier_of_assemblage, changer_machine
from services.pointage_service import pointer_debut_operation, pointer_fin_operation


class OFView(QWidget):
    def __init__(self):
        super().__init__()
        self._ofa_data = []
        self._sort_active = "Priority"
        self._sort_buttons = {}
        self._status_checks = {}
        self._build_ui()
        self._charger_ofs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ── Title + Schedule button ────────────────────────────────────
        header = QHBoxLayout()
        titre = QLabel("Production Orders")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_planifier = QPushButton("📅 Schedule")
        btn_planifier.setFixedHeight(36)
        btn_planifier.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_planifier.clicked.connect(self._planifier)
        header.addWidget(btn_planifier)
        layout.addLayout(header)

        # ── Sort + Filter toolbar ──────────────────────────────────────
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #f4f6f8;
                border: 1px solid #dde;
                border-radius: 6px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(16)

        # Sort label + buttons
        sort_lbl = QLabel("Sort:")
        sort_lbl.setFont(QFont("Arial", 10, QFont.Bold))
        sort_lbl.setStyleSheet("color: #2c3e50; background: transparent; border: none;")
        toolbar_layout.addWidget(sort_lbl)

        sort_btn_style = """
            QPushButton {{
                background-color: {bg}; color: {fg};
                border: 1px solid {border};
                border-radius: 4px; padding: 4px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover}; color: white; }}
        """
        self._sort_active = "Priority"
        self._sort_buttons = {}
        for label, bg, fg, border, hover in [
            ("Order",    "#fff", "#2c3e50", "#bdc3c7", "#3498db"),
            ("Priority", "#3498db", "white", "#2980b9", "#2980b9"),
            ("Due Date", "#fff", "#2c3e50", "#bdc3c7", "#3498db"),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCheckable(True)
            btn.setChecked(label == self._sort_active)
            btn.setStyleSheet(sort_btn_style.format(
                bg=bg, fg=fg, border=border, hover=hover
            ))
            btn.clicked.connect(lambda checked, l=label: self._on_sort(l))
            toolbar_layout.addWidget(btn)
            self._sort_buttons[label] = btn

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #bdc3c7; background: transparent; border: none; border-left: 1px solid #bdc3c7;")
        sep.setFixedWidth(1)
        toolbar_layout.addWidget(sep)

        # Filter label + checkboxes
        filter_lbl = QLabel("Status:")
        filter_lbl.setFont(QFont("Arial", 10, QFont.Bold))
        filter_lbl.setStyleSheet("color: #2c3e50; background: transparent; border: none;")
        toolbar_layout.addWidget(filter_lbl)

        self._status_checks = {}
        status_options = [
            ("To Schedule", "a_planifier", "#e67e22"),
            ("Planned",     "planifie",    "#3498db"),
            ("In Progress", "en_cours",    "#8e44ad"),
            ("Completed",   "termine",     "#27ae60"),
            ("Cancelled",   "annule",      "#95a5a6"),
        ]
        for label, key, color in status_options:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {color};
                    font-size: 11px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                    spacing: 4px;
                }}
                QCheckBox::indicator {{
                    width: 14px; height: 14px;
                    border: 2px solid {color};
                    border-radius: 3px;
                    background: white;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {color};
                }}
            """)
            cb.stateChanged.connect(self._on_filter_changed)
            toolbar_layout.addWidget(cb)
            self._status_checks[key] = cb

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Vertical)

        # ── Assembly POs ──────────────────────────────────────────────
        ofa_widget = QWidget()
        ofa_layout = QVBoxLayout(ofa_widget)
        ofa_layout.setContentsMargins(0, 0, 0, 0)

        ofa_header = QHBoxLayout()
        ofa_label = QLabel("Assembly Production Orders")
        ofa_label.setFont(QFont("Arial", 12, QFont.Bold))
        ofa_header.addWidget(ofa_label)
        ofa_header.addStretch()

        btn_priorite = QPushButton("↑ Priority")
        btn_priorite.setFixedHeight(30)
        btn_priorite.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white;
                border-radius: 4px; padding: 0 12px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        btn_priorite.clicked.connect(self._changer_priorite)
        ofa_header.addWidget(btn_priorite)
        ofa_layout.addLayout(ofa_header)

        self.ofa_table = QTableWidget()
        self.ofa_table.setColumnCount(7)
        self.ofa_table.setHorizontalHeaderLabels([
            "ID", "Assembly", "Order", "Quantity",
            "Priority", "Due Date", "Status"
        ])
        self.ofa_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ofa_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ofa_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ofa_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ofa_table.setAlternatingRowColors(True)
        self.ofa_table.setStyleSheet(self._table_style())
        self.ofa_table.selectionModel().selectionChanged.connect(
            self._afficher_ofs_composants
        )
        ofa_layout.addWidget(self.ofa_table)
        splitter.addWidget(ofa_widget)

        # ── Component POs ─────────────────────────────────────────────
        ofc_widget = QWidget()
        ofc_layout = QVBoxLayout(ofc_widget)
        ofc_layout.setContentsMargins(0, 0, 0, 0)

        ofc_header = QHBoxLayout()
        ofc_label = QLabel("Component Production Orders")
        ofc_label.setFont(QFont("Arial", 12, QFont.Bold))
        ofc_header.addWidget(ofc_label)
        ofc_header.addStretch()

        btn_ops = QPushButton("View Operations")
        btn_ops.setFixedHeight(30)
        btn_ops.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white;
                border-radius: 4px; padding: 0 12px;
            }
            QPushButton:hover { background-color: #7d3c98; }
        """)
        btn_ops.clicked.connect(self._voir_operations)
        ofc_header.addWidget(btn_ops)
        ofc_layout.addLayout(ofc_header)

        self.ofc_table = QTableWidget()
        self.ofc_table.setColumnCount(6)
        self.ofc_table.setHorizontalHeaderLabels([
            "Code OF", "ID", "Component", "Type", "Quantity",
            "Due Date", "Status"
        ])
        self.ofc_table.setColumnCount(7)
        self.ofc_table.setHorizontalHeaderLabels([
            "Code OF", "ID", "Component", "Type", "Quantity", "Due Date", "Status"
        ])
        self.ofc_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.ofc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ofc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ofc_table.setAlternatingRowColors(True)
        self.ofc_table.setStyleSheet(self._table_style())
        ofc_layout.addWidget(self.ofc_table)
        splitter.addWidget(ofc_widget)

        layout.addWidget(splitter)

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
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """

    def _statut_couleur(self, statut):
        return {
            "planifie":    "#3498db",
            "a_planifier": "#e67e22",
            "en_cours":    "#8e44ad",
            "termine":     "#27ae60",
            "rebute":      "#e74c3c",
            "annule":      "#95a5a6",
        }.get(statut, "#95a5a6")

    def _statut_label(self, statut):
        return {
            "planifie":    "Planned",
            "a_planifier": "To Schedule",
            "en_cours":    "In Progress",
            "termine":     "Completed",
            "rebute":      "Scrapped",
            "annule":      "Cancelled",
        }.get(statut, statut)

    def _priorite_couleur(self, priorite):
        couleurs = {
            1: "#e74c3c",   # rouge   — Urgent
            2: "#e67e22",   # orange  — High
            3: "#e67e22",   # orange  — Elevated
            4: "#f39c12",   # jaune   — Moderate
            5: "#27ae60",   # vert    — Normal
        }
        return couleurs.get(priorite, "#27ae60")

    def _priorite_label(self, priorite):
        labels = {
            1: "Urgent",
            2: "High",
            3: "Elevated",
            4: "Moderate",
            5: "Normal",
        }
        return f"{priorite} — {labels.get(priorite, 'Normal')}"

    def _statut_effectif_ofa(self, ofa, session):
        """Déduit le statut réel de l'OFAssemblage depuis les opérations (requête fraîche)."""
        # Récupère tous les OFs de cet assemblage
        ofs = session.query(OrdreFabrication).filter_by(
            id_of_assemblage=ofa.id_of_assemblage
        ).all()
        if not ofs:
            return ofa.statut
        # Récupère toutes les opérations de ces OFs
        ids_ofs = [of.id_of for of in ofs]
        ops = session.query(OperationPlanifiee).filter(
            OperationPlanifiee.id_of.in_(ids_ofs)
        ).all()
        if ops and any(o.statut == "en_cours" for o in ops):
            return "en_cours"
        if ops and all(o.statut in ("terminee", "rebutee") for o in ops):
            return "termine"
        # Fallback sur statut OF
        statuts_of = [of.statut for of in ofs]
        if any(s == "en_cours" for s in statuts_of):
            return "en_cours"
        if all(s in ("termine", "rebute", "annule") for s in statuts_of):
            return "termine"
        if any(s == "planifie" for s in statuts_of):
            return "planifie"
        return ofa.statut

    def _on_sort(self, label):
        self._sort_active = label
        for lbl, btn in self._sort_buttons.items():
            active = (lbl == label)
            btn.setChecked(active)
            btn.setStyleSheet("""
                QPushButton {{
                    background-color: {bg}; color: {fg};
                    border: 1px solid {border};
                    border-radius: 4px; padding: 4px 12px; font-size: 11px;
                }}
                QPushButton:hover {{ background-color: #2980b9; color: white; }}
            """.format(
                bg="#3498db" if active else "#fff",
                fg="white" if active else "#2c3e50",
                border="#2980b9" if active else "#bdc3c7",
            ))
        self._appliquer_tri_filtre()

    def _on_filter_changed(self):
        self._appliquer_tri_filtre()

    def _charger_ofs(self):
        """Load all OFAs into _ofa_data, then apply sort/filter."""
        session = SessionLocal()
        try:
            ofas = session.query(OFAssemblage).all()
            self._ofa_data = []
            for ofa in ofas:
                # Resolve order code via ligne_commande → commande
                ligne = session.get(LigneCommande, ofa.id_ligne) if ofa.id_ligne else None
                if ligne and ligne.commande:
                    order_code = ligne.commande.code_commande or f"#{ofa.id_ligne}"
                else:
                    order_code = f"#{ofa.id_ligne}" if ofa.id_ligne else "—"

                statut_effectif = self._statut_effectif_ofa(ofa, session)
                self._ofa_data.append({
                    "id_ofa":        ofa.id_of_assemblage,
                    "assembly":      ofa.assemblage.nom if ofa.assemblage else "—",
                    "order_code":    order_code,
                    "quantite":      ofa.quantite,
                    "priorite":      ofa.priorite or 5,
                    "date_fin":      ofa.date_fin_prevue,
                    "statut":        statut_effectif,
                })
        finally:
            session.close()
        self._appliquer_tri_filtre()

    def _appliquer_tri_filtre(self):
        """Filter by checked statuses, sort by active sort key, then populate table."""
        active_statuts = {k for k, cb in self._status_checks.items() if cb.isChecked()}

        data = [row for row in self._ofa_data if row["statut"] in active_statuts]

        sort_key = self._sort_active
        if sort_key == "Order":
            data.sort(key=lambda r: r["order_code"])
        elif sort_key == "Priority":
            data.sort(key=lambda r: r["priorite"])
        elif sort_key == "Due Date":
            data.sort(key=lambda r: (r["date_fin"] is None, r["date_fin"]))

        self.ofa_table.setRowCount(len(data))
        for row, d in enumerate(data):
            id_item = QTableWidgetItem(str(d["id_ofa"]))
            id_item.setData(Qt.UserRole, d["id_ofa"])
            self.ofa_table.setItem(row, 0, id_item)
            self.ofa_table.setItem(row, 1, QTableWidgetItem(d["assembly"]))
            self.ofa_table.setItem(row, 2, QTableWidgetItem(d["order_code"]))
            self.ofa_table.setItem(row, 3, QTableWidgetItem(str(d["quantite"])))

            priorite_item = QTableWidgetItem(self._priorite_label(d["priorite"]))
            priorite_item.setForeground(QColor(self._priorite_couleur(d["priorite"])))
            priorite_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.ofa_table.setItem(row, 4, priorite_item)

            self.ofa_table.setItem(row, 5, QTableWidgetItem(
                str(d["date_fin"])[:16] if d["date_fin"] else "—"))

            statut_item = QTableWidgetItem(self._statut_label(d["statut"]))
            statut_item.setForeground(QColor(self._statut_couleur(d["statut"])))
            statut_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.ofa_table.setItem(row, 6, statut_item)

    def _afficher_ofs_composants(self):
        row = self.ofa_table.currentRow()
        if row < 0:
            return
        id_ofa = int(self.ofa_table.item(row, 0).text())
        self.ofc_table.setRowCount(0)

        session = SessionLocal()
        try:
            ofs = session.query(OrdreFabrication).filter_by(
                id_of_assemblage=id_ofa
            ).order_by(OrdreFabrication.id_of).all()

            for row_of, of in enumerate(ofs):
                self.ofc_table.insertRow(row_of)
                self.ofc_table.setItem(row_of, 0, QTableWidgetItem(
                    of.code_of or "—"))
                self.ofc_table.setItem(row_of, 1, QTableWidgetItem(
                    str(of.id_of)))
                self.ofc_table.setItem(row_of, 2, QTableWidgetItem(
                    of.composant.nom if of.composant else "—"))
                self.ofc_table.setItem(row_of, 3, QTableWidgetItem(
                    of.type_of or "—"))
                self.ofc_table.setItem(row_of, 4, QTableWidgetItem(
                    str(of.quantite)))
                self.ofc_table.setItem(row_of, 5, QTableWidgetItem(
                    str(of.date_fin_prevue)[:16] if of.date_fin_prevue else "—"))

                # Déduit le statut réel depuis les opérations (requête fraîche)
                ops = session.query(OperationPlanifiee).filter_by(
                    id_of=of.id_of
                ).all()
                if ops and any(o.statut == "en_cours" for o in ops):
                    statut_of = "en_cours"
                elif ops and all(o.statut in ("terminee", "rebutee") for o in ops):
                    statut_of = "termine"
                else:
                    statut_of = of.statut
                statut_item = QTableWidgetItem(self._statut_label(statut_of))
                statut_item.setForeground(QColor(self._statut_couleur(statut_of)))
                statut_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.ofc_table.setItem(row_of, 6, statut_item)
        finally:
            session.close()

    def _planifier(self):
        row = self.ofa_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning",
                                "Please select an Assembly Production Order.")
            return
        id_ofa = int(self.ofa_table.item(row, 0).text())
        session = SessionLocal()
        try:
            from models import OrdreFabrication
            nb_a_planifier = session.query(OrdreFabrication).filter_by(
                id_of_assemblage=id_ofa,
                statut="a_planifier"
            ).count()

            if nb_a_planifier == 0:
                QMessageBox.information(
                    self, "Information",
                    "All Production Orders for this assembly are already scheduled.\n"
                    "Use the Planning view to modify dates if needed."
                )
                return

            from datetime import datetime
            resultat = planifier_of_assemblage(
                session=session,
                id_of_assemblage=id_ofa,
                date_debut_souhaitee=datetime.now()
            )
            session.commit()
            QMessageBox.information(
                self, "Scheduling complete",
                f"{resultat['nb_ofs']} Production Order(s) scheduled\n"
                f"Due date : {str(resultat['date_fin_prevue'])[:16]}"
            )
            self._charger_ofs()
            self._afficher_ofs_composants()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _changer_priorite(self):
        row = self.ofa_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning",
                                "Please select an Assembly Production Order.")
            return
        id_ofa = int(self.ofa_table.item(row, 0).text())
        dialog = ChangerPrioriteDialog(id_ofa, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_ofs()
            self._afficher_ofs_composants()

    def _voir_operations(self):
        row = self.ofc_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning",
                                "Please select a Component Production Order.")
            return
        id_of = int(self.ofc_table.item(row, 1).text())
        dialog = OperationsDialog(id_of, self)
        dialog.exec()
        self._afficher_ofs_composants()


class ChangerPrioriteDialog(QDialog):
    """Dialogue de changement de priorité au niveau OFAssemblage."""

    def __init__(self, id_of_assemblage: int, parent=None):
        super().__init__(parent)
        self.id_of_assemblage = id_of_assemblage
        self.setWindowTitle("Change Assembly Priority")
        self.setMinimumWidth(320)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.priorite_spin = QSpinBox()
        self.priorite_spin.setMinimum(1)
        self.priorite_spin.setMaximum(5)
        self.priorite_spin.setValue(5)

        legende = QLabel(
            "1 = Urgent  |  2 = High  |  3 = Elevated  |  4 = Moderate  |  5 = Normal"
        )
        legende.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        legende.setWordWrap(True)

        session = SessionLocal()
        try:
            ofa = session.get(OFAssemblage, self.id_of_assemblage)
            if ofa:
                self.priorite_spin.setValue(ofa.priorite or 5)
                nom = ofa.assemblage.nom if ofa.assemblage else f"#{self.id_of_assemblage}"
                self.setWindowTitle(f"Priority — {nom}")
        finally:
            session.close()

        form.addRow("Priority :", self.priorite_spin)
        layout.addLayout(form)
        layout.addWidget(legende)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _valider(self):
        session = SessionLocal()
        try:
            ofa = session.get(OFAssemblage, self.id_of_assemblage)
            if ofa:
                ofa.priorite = self.priorite_spin.value()
                session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class OperationsDialog(QDialog):
    def __init__(self, id_of: int, parent=None):
        super().__init__(parent)
        self.id_of = id_of
        self.setWindowTitle(f"Operations — PO {id_of}")
        self.setMinimumSize(900, 400)
        self._build_ui()
        self._charger_operations()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Order", "Description", "Machine",
            "Planned Start", "Planned End", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dde;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 6px;
            }
        """)
        layout.addWidget(self.table)

        btns = QHBoxLayout()

        btn_debut = QPushButton("▶ Start")
        btn_debut.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #219a52; }
        """)
        btn_debut.clicked.connect(self._demarrer)

        btn_fin = QPushButton("⏹ Complete")
        btn_fin.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        btn_fin.clicked.connect(self._terminer)

        btn_machine = QPushButton("🔄 Change Machine")
        btn_machine.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #7d3c98; }
        """)
        btn_machine.clicked.connect(self._changer_machine)

        btns.addWidget(btn_debut)
        btns.addWidget(btn_fin)
        btns.addWidget(btn_machine)
        btns.addStretch()
        layout.addLayout(btns)

    def _charger_operations(self):
        session = SessionLocal()
        try:
            ops = session.query(OperationPlanifiee).filter_by(
                id_of=self.id_of
            ).order_by(OperationPlanifiee.date_debut).all()

            self.table.setRowCount(len(ops))
            couleurs = {
                "planifiee": "#3498db",
                "en_cours":  "#e67e22",
                "terminee":  "#27ae60",
                "rebutee":   "#e74c3c",
            }
            labels = {
                "planifiee": "Planned",
                "en_cours":  "In Progress",
                "terminee":  "Completed",
                "rebutee":   "Scrapped",
            }
            for row, op in enumerate(ops):
                self.table.setItem(row, 0, QTableWidgetItem(str(op.id_op_plan)))
                self.table.setItem(row, 1, QTableWidgetItem(
                    str(op.operation.ordre) if op.operation else "—"))
                self.table.setItem(row, 2, QTableWidgetItem(
                    op.operation.description if op.operation else "—"))
                self.table.setItem(row, 3, QTableWidgetItem(
                    op.machine.nom if op.machine else "—"))
                self.table.setItem(row, 4, QTableWidgetItem(
                    str(op.date_debut)[:16] if op.date_debut else "—"))
                self.table.setItem(row, 5, QTableWidgetItem(
                    str(op.date_fin)[:16] if op.date_fin else "—"))
                statut_item = QTableWidgetItem(labels.get(op.statut, op.statut))
                statut_item.setForeground(
                    QColor(couleurs.get(op.statut, "#95a5a6"))
                )
                statut_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 6, statut_item)
        finally:
            session.close()

    def _demarrer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select an operation.")
            return
        id_op_plan = int(self.table.item(row, 0).text())
        session = SessionLocal()
        try:
            pointer_debut_operation(session, id_op_plan)
            session.commit()
            self._charger_operations()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _terminer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select an operation.")
            return
        id_op_plan = int(self.table.item(row, 0).text())
        dialog = TerminerOperationDialog(id_op_plan, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_operations()

    def _changer_machine(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select an operation.")
            return
        id_op_plan = int(self.table.item(row, 0).text())
        dialog = ChangerMachineDialog(id_op_plan, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_operations()


class TerminerOperationDialog(QDialog):
    def __init__(self, id_op_plan: int, parent=None):
        super().__init__(parent)
        self.id_op_plan = id_op_plan
        self.setWindowTitle("Complete Operation")
        self.setMinimumWidth(300)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.prep_spin = QSpinBox()
        self.prep_spin.setMinimum(0)
        self.prep_spin.setMaximum(9999)
        self.prep_spin.setSuffix(" min")

        self.exec_spin = QSpinBox()
        self.exec_spin.setMinimum(0)
        self.exec_spin.setMaximum(9999)
        self.exec_spin.setSuffix(" min")

        form.addRow("Actual setup time :", self.prep_spin)
        form.addRow("Actual cycle time :", self.exec_spin)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _valider(self):
        session = SessionLocal()
        try:
            pointer_fin_operation(
                session=session,
                id_op_plan=self.id_op_plan,
                tps_prep_reel=self.prep_spin.value(),
                tps_exec_reel=self.exec_spin.value()
            )
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class ChangerMachineDialog(QDialog):
    def __init__(self, id_op_plan: int, parent=None):
        super().__init__(parent)
        self.id_op_plan = id_op_plan
        self.setWindowTitle("Change Machine")
        self.setMinimumWidth(300)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        lbl = QLabel("Select machine :")
        lbl.setFont(QFont("Arial", 10))
        layout.addWidget(lbl)

        self.machine_list = QListWidget()
        self.machine_list.setFixedHeight(120)
        self.machine_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QListWidget::item { padding: 4px 8px; }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        self._charger_machines()
        layout.addWidget(self.machine_list)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _charger_machines(self):
        from PySide6.QtWidgets import QListWidgetItem
        from models import Machine
        session = SessionLocal()
        try:
            machines = session.query(Machine).order_by(Machine.nom).all()
            for m in machines:
                item = QListWidgetItem(f"{m.nom} ({m.statut})")
                item.setData(Qt.UserRole, m.id_machine)
                self.machine_list.addItem(item)
        finally:
            session.close()

    def _valider(self):
        item = self.machine_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Please select a machine.")
            return
        session = SessionLocal()
        try:
            changer_machine(
                session=session,
                id_op_plan=self.id_op_plan,
                id_nouvelle_machine=item.data(Qt.UserRole)
            )
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()