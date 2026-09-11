from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QComboBox,
    QSplitter, QDoubleSpinBox, QTextEdit,
    QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import Commande, LigneCommande, Assemblage
from services.of_service import (
    generer_of_depuis_ligne, generer_code_commande, generer_code_ligne
)


class CommandesView(QWidget):
    def __init__(self):
        super().__init__()
        self._cmd_data = []
        self._sort_active = "Order Date"
        self._sort_buttons = {}
        self._status_checks = {}
        self._build_ui()
        self._charger_commandes()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ── Title + New Order button ───────────────────────────────────
        header = QHBoxLayout()
        titre = QLabel("Orders")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Order")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_nouveau.clicked.connect(self._nouvelle_commande)
        header.addWidget(btn_nouveau)
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

        self._sort_buttons = {}
        for label in ["Order Date", "Delivery Date", "Customer", "Code"]:
            active = (label == self._sort_active)
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCheckable(True)
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
            btn.clicked.connect(lambda checked, l=label: self._on_sort(l))
            toolbar_layout.addWidget(btn)
            self._sort_buttons[label] = btn

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("border: none; border-left: 1px solid #bdc3c7;")
        sep.setFixedWidth(1)
        toolbar_layout.addWidget(sep)

        # Filter label + checkboxes
        filter_lbl = QLabel("Status:")
        filter_lbl.setFont(QFont("Arial", 10, QFont.Bold))
        filter_lbl.setStyleSheet("color: #2c3e50; background: transparent; border: none;")
        toolbar_layout.addWidget(filter_lbl)

        self._status_checks = {}
        status_options = [
            ("Draft",         "planifiee",     "#f39c12"),
            ("In Production", "in_production", "#3498db"),
            ("Finished",      "finished",      "#27ae60"),
            ("On Hold",       "on_hold",       "#e67e22"),
            ("Cancelled",     "cancelled",     "#e74c3c"),
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

        # Orders table
        cmd_widget = QWidget()
        cmd_layout = QVBoxLayout(cmd_widget)
        cmd_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Code", "Ext. Ref.", "Customer",
            "Order Date", "Delivery Date", "Status", "Lines"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self._table_style())
        self.table.selectionModel().selectionChanged.connect(
            self._afficher_lignes
        )
        cmd_layout.addWidget(self.table)
        splitter.addWidget(cmd_widget)

        # Order lines table
        ligne_widget = QWidget()
        ligne_layout = QVBoxLayout(ligne_widget)
        ligne_layout.setContentsMargins(0, 10, 0, 0)

        ligne_header = QHBoxLayout()
        self.ligne_titre = QLabel("Order Lines")
        self.ligne_titre.setFont(QFont("Arial", 12, QFont.Bold))
        ligne_header.addWidget(self.ligne_titre)
        ligne_header.addStretch()

        btn_ajouter_ligne = QPushButton("+ Add Line")
        btn_ajouter_ligne.setFixedHeight(30)
        btn_ajouter_ligne.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_ajouter_ligne.clicked.connect(self._ajouter_ligne)
        ligne_header.addWidget(btn_ajouter_ligne)
        ligne_layout.addLayout(ligne_header)

        self.ligne_table = QTableWidget()
        self.ligne_table.setColumnCount(5)
        self.ligne_table.setHorizontalHeaderLabels([
            "Line Code", "Assembly", "Quantity", "Status", "Actions"
        ])
        self.ligne_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.ligne_table.setColumnWidth(0, 120)
        self.ligne_table.setColumnWidth(2, 80)
        self.ligne_table.setColumnWidth(3, 110)
        self.ligne_table.setColumnWidth(4, 220)
        self.ligne_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ligne_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ligne_table.setAlternatingRowColors(True)
        self.ligne_table.setStyleSheet(self._table_style())
        self.ligne_table.verticalHeader().setDefaultSectionSize(40)
        ligne_layout.addWidget(self.ligne_table)

        splitter.addWidget(ligne_widget)
        splitter.setSizes([300, 200])
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

    # ── Sort / Filter helpers ──────────────────────────────────────────

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

    # Status label/color maps (order-level)
    _STATUT_LABELS = {
        "planifiee":     "Draft",
        "in_production": "In Production",
        "finished":      "Finished",
        "on_hold":       "On Hold",
        "cancelled":     "Cancelled",
    }
    _STATUT_COLORS = {
        "planifiee":     "#f39c12",
        "in_production": "#3498db",
        "finished":      "#27ae60",
        "on_hold":       "#e67e22",
        "cancelled":     "#e74c3c",
    }

    def _charger_commandes(self):
        """Load all orders into _cmd_data, then apply sort/filter."""
        from sqlalchemy.orm import selectinload
        session = SessionLocal()
        try:
            commandes = session.query(Commande).options(
                selectinload(Commande.lignes)
            ).all()
            self._cmd_data = []
            for cmd in commandes:
                self._cmd_data.append({
                    "id_commande":   cmd.id_commande,
                    "code":          cmd.code_commande or "—",
                    "ext_ref":       cmd.numero_externe or "—",
                    "client":        cmd.client or "—",
                    "date_commande": cmd.date_commande,
                    "date_livraison":cmd.date_livraison,
                    "statut":        cmd.statut or "planifiee",
                    "nb_lignes":     len(cmd.lignes),
                })
        finally:
            session.close()
        self._appliquer_tri_filtre()

    def _appliquer_tri_filtre(self):
        """Filter by checked statuses, sort, then populate table."""
        active_statuts = {k for k, cb in self._status_checks.items() if cb.isChecked()}
        data = [r for r in self._cmd_data if r["statut"] in active_statuts]

        key = self._sort_active
        if key == "Order Date":
            data.sort(key=lambda r: (r["date_commande"] is None, r["date_commande"]), reverse=True)
        elif key == "Delivery Date":
            data.sort(key=lambda r: (r["date_livraison"] is None, r["date_livraison"]))
        elif key == "Customer":
            data.sort(key=lambda r: r["client"].lower())
        elif key == "Code":
            data.sort(key=lambda r: r["code"])

        self.table.setRowCount(len(data))
        for row, d in enumerate(data):
            id_item = QTableWidgetItem(d["code"])
            id_item.setData(Qt.UserRole, d["id_commande"])
            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, QTableWidgetItem(d["ext_ref"]))
            self.table.setItem(row, 2, QTableWidgetItem(d["client"]))
            self.table.setItem(row, 3, QTableWidgetItem(
                str(d["date_commande"]) if d["date_commande"] else "—"))
            self.table.setItem(row, 4, QTableWidgetItem(
                str(d["date_livraison"]) if d["date_livraison"] else "—"))

            statut_txt = self._STATUT_LABELS.get(d["statut"], d["statut"])
            couleur = self._STATUT_COLORS.get(d["statut"], "#95a5a6")
            statut_item = QTableWidgetItem(statut_txt)
            statut_item.setForeground(QColor(couleur))
            statut_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.table.setItem(row, 5, statut_item)
            self.table.setItem(row, 6, QTableWidgetItem(str(d["nb_lignes"])))

    def _get_id_commande_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _afficher_lignes(self):
        id_commande = self._get_id_commande_selectionne()
        if not id_commande:
            return

        row = self.table.currentRow()
        code_commande = self.table.item(row, 0).text()
        self.ligne_titre.setText(f"Order Lines — {code_commande}")
        self.ligne_table.setRowCount(0)

        from sqlalchemy.orm import selectinload, joinedload
        session = SessionLocal()
        try:
            commande = session.get(
                Commande, id_commande,
                options=[
                    selectinload(Commande.lignes).joinedload(LigneCommande.assemblage),
                    selectinload(Commande.lignes).selectinload(LigneCommande.of_assemblages),
                ]
            )
            if not commande:
                return

            for row_l, ligne in enumerate(commande.lignes):
                self.ligne_table.insertRow(row_l)

                self.ligne_table.setItem(row_l, 0, QTableWidgetItem(
                    ligne.code_ligne or "—"))
                self.ligne_table.setItem(row_l, 1, QTableWidgetItem(
                    ligne.assemblage.nom if ligne.assemblage else "—"))
                self.ligne_table.setItem(row_l, 2, QTableWidgetItem(
                    str(ligne.quantite)))

                statut_map = {
                    "on_hold":   ("On Hold",       "#e67e22"),
                    "released":  ("In Production", "#3498db"),
                    "completed": ("Completed",     "#27ae60"),
                    "cancelled": ("Cancelled",     "#e74c3c"),
                }
                statut_txt, statut_color = statut_map.get(
                    ligne.statut, (ligne.statut, "#95a5a6")
                )
                statut_item = QTableWidgetItem(statut_txt)
                statut_item.setForeground(QColor(statut_color))
                statut_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.ligne_table.setItem(row_l, 3, statut_item)

                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(4, 2, 4, 2)
                actions_layout.setSpacing(4)

                if ligne.statut == "on_hold":
                    btn_release = QPushButton("Release")
                    btn_release.setFixedHeight(28)
                    btn_release.setStyleSheet("""
                        QPushButton {
                            background-color: #27ae60; color: white;
                            border-radius: 4px; padding: 0 8px; font-size: 11px;
                        }
                        QPushButton:hover { background-color: #219a52; }
                    """)
                    btn_release.clicked.connect(
                        lambda checked, lid=ligne.id_ligne: self._release_ligne(lid)
                    )
                    actions_layout.addWidget(btn_release)

                    btn_cancel = QPushButton("Cancel")
                    btn_cancel.setFixedHeight(28)
                    btn_cancel.setStyleSheet("""
                        QPushButton {
                            background-color: #e74c3c; color: white;
                            border-radius: 4px; padding: 0 8px; font-size: 11px;
                        }
                        QPushButton:hover { background-color: #c0392b; }
                    """)
                    btn_cancel.clicked.connect(
                        lambda checked, lid=ligne.id_ligne: self._cancel_ligne(lid)
                    )
                    actions_layout.addWidget(btn_cancel)

                elif ligne.statut == "released":
                    nb_ofs = len(ligne.of_assemblages)
                    lbl = QLabel(f"In Production — {nb_ofs} order(s)")
                    lbl.setStyleSheet("color: #3498db; font-size: 11px;")
                    actions_layout.addWidget(lbl)

                    btn_cost = QPushButton("💰 Cost")
                    btn_cost.setFixedHeight(28)
                    btn_cost.setStyleSheet("""
                        QPushButton {
                            background-color: #8e44ad; color: white;
                            border-radius: 4px; padding: 0 8px; font-size: 11px;
                        }
                        QPushButton:hover { background-color: #7d3c98; }
                    """)
                    btn_cost.clicked.connect(
                        lambda checked, lid=ligne.id_ligne: self._voir_cout_revient(lid)
                    )
                    actions_layout.addWidget(btn_cost)

                    btn_cancel = QPushButton("Cancel")
                    btn_cancel.setFixedHeight(28)
                    btn_cancel.setStyleSheet("""
                        QPushButton {
                            background-color: #e74c3c; color: white;
                            border-radius: 4px; padding: 0 8px; font-size: 11px;
                        }
                        QPushButton:hover { background-color: #c0392b; }
                    """)
                    btn_cancel.clicked.connect(
                        lambda checked, lid=ligne.id_ligne: self._cancel_ligne(lid)
                    )
                    actions_layout.addWidget(btn_cancel)

                elif ligne.statut == "cancelled":
                    reason = ligne.cancel_reason or "—"
                    lbl = QLabel(f"Reason: {reason}")
                    lbl.setStyleSheet("color: #e74c3c; font-size: 11px;")
                    lbl.setToolTip(reason)
                    actions_layout.addWidget(lbl)

                elif ligne.statut == "completed":
                    btn_cost = QPushButton("💰 Cost")
                    btn_cost.setFixedHeight(28)
                    btn_cost.setStyleSheet("""
                        QPushButton {
                            background-color: #8e44ad; color: white;
                            border-radius: 4px; padding: 0 8px; font-size: 11px;
                        }
                        QPushButton:hover { background-color: #7d3c98; }
                    """)
                    btn_cost.clicked.connect(
                        lambda checked, lid=ligne.id_ligne: self._voir_cout_revient(lid)
                    )
                    actions_layout.addWidget(btn_cost)

                actions_layout.addStretch()
                self.ligne_table.setCellWidget(row_l, 4, actions_widget)

        finally:
            session.close()

    def _nouvelle_commande(self):
        dialog = NouvelleCommandeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_commandes()

    def _ajouter_ligne(self):
        id_commande = self._get_id_commande_selectionne()
        if not id_commande:
            QMessageBox.warning(self, "Warning", "Please select an order.")
            return

        row = self.table.currentRow()
        code_commande = self.table.item(row, 0).text()

        dialog = AjouterLigneDialog(id_commande, code_commande, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_commandes()
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).data(Qt.UserRole) == id_commande:
                    self.table.selectRow(r)
                    break
            self._afficher_lignes()

    def _release_ligne(self, id_ligne):
        reply = QMessageBox.question(
            self, "Release Line",
            "Generate Production Orders for this line?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        session = SessionLocal()
        try:
            ligne = session.get(LigneCommande, id_ligne)
            if not ligne:
                return
            id_commande = ligne.id_commande

            # 1. Génère les OFs composants
            of_assemblage = generer_of_depuis_ligne(session, id_ligne)

            # 2. Planifie automatiquement tous les OFs au plus tôt
            from services.planning_service import planifier_of_assemblage
            planifier_of_assemblage(
                session=session,
                id_of_assemblage=of_assemblage.id_of_assemblage
            )

            # 3. Sauvegarde le snapshot du prix de revient
            from services.cout_service import recalculer_assemblage
            ligne = session.get(LigneCommande, id_ligne)
            if ligne and ligne.assemblage:
                prix = recalculer_assemblage(session, ligne.id_assemblage)
                ligne.prix_revient_snapshot = prix
            ligne.statut = "released"
            session.commit()
            QMessageBox.information(
                self, "Success",
                "Production Orders generated and scheduled."
            )
            self._charger_commandes()
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).data(Qt.UserRole) == id_commande:
                    self.table.selectRow(r)
                    break
            self._afficher_lignes()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _voir_cout_revient(self, id_ligne):
        dialog = CoutRevientLigneDialog(id_ligne, self)
        dialog.exec()

    def _cancel_ligne(self, id_ligne):
        dialog = CancelLigneDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        reason = dialog.get_reason()

        session = SessionLocal()
        try:
            from models import OrdreFabrication, OperationPlanifiee, OFAssemblage

            ligne = session.get(LigneCommande, id_ligne)
            if not ligne:
                return

            # Vérifie les opérations en cours
            for ofa in ligne.of_assemblages:
                for of in ofa.ordres_fabrication:
                    ops_en_cours = session.query(OperationPlanifiee).filter_by(
                        id_of=of.id_of,
                        statut="en_cours"
                    ).first()
                    if ops_en_cours:
                        QMessageBox.warning(
                            self, "Warning",
                            f"Cannot cancel line {ligne.code_ligne}.\n"
                            f"Operation in progress on Production Order "
                            f"{of.code_of}.\n"
                            f"Please finish or stop the operation first."
                        )
                        return

            code_ligne  = ligne.code_ligne
            id_commande = ligne.id_commande

            # Annule les OFs et OFAssemblages
            for ofa in ligne.of_assemblages:
                for of in ofa.ordres_fabrication:
                    if of.statut not in ("termine", "rebute"):
                        of.statut = "annule"
                    for op in of.operations_planifiees:
                        if op.statut == "planifiee":
                            op.statut = "annulee"
                ofa.statut = "annule"

            ligne.statut        = "cancelled"
            ligne.cancel_reason = reason
            session.commit()

            QMessageBox.information(
                self, "Success",
                f"Line {code_ligne} cancelled.\n"
                f"All associated Production Orders have been cancelled."
            )
            self._charger_commandes()
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).data(Qt.UserRole) == id_commande:
                    self.table.selectRow(r)
                    break
            self._afficher_lignes()

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class CancelLigneDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cancel Order Line")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        lbl = QLabel("Please provide a reason for cancellation :")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText("Enter cancellation reason...")
        self.reason_input.setFixedHeight(100)
        layout.addWidget(self.reason_input)

        btns = QHBoxLayout()
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(self.reject)
        btn_confirm = QPushButton("Confirm Cancellation")
        btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_confirm.clicked.connect(self._valider)
        btns.addWidget(btn_back)
        btns.addWidget(btn_confirm)
        layout.addLayout(btns)

    def _valider(self):
        reason = self.reason_input.toPlainText().strip()
        if not reason:
            QMessageBox.warning(self, "Warning",
                                "Cancellation reason is required.")
            return
        self.accept()

    def get_reason(self):
        return self.reason_input.toPlainText().strip()


# ---------------------------------------------------------------------------
# Dialog : Prix de revient par ligne de commande
# ---------------------------------------------------------------------------

class CoutRevientLigneDialog(QDialog):
    """
    Fenêtre affichant par composant (OF) :
      - Prix de revient initial (snapshot au moment du Release)
      - Prix de revient réel :
          * Si OF terminé  → calculé depuis les tps pointés réels
          * Si OF en cours / planifié → calculé depuis les tps planifiés (planning)
    """

    def __init__(self, id_ligne: int, parent=None):
        super().__init__(parent)
        self.id_ligne = id_ligne
        self.setWindowTitle("Production Cost Analysis")
        self.setMinimumWidth(900)
        self.setMinimumHeight(520)
        self._build_ui()
        self._charger_donnees()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Titre ligne
        self.lbl_titre = QLabel("Cost Analysis")
        self.lbl_titre.setFont(QFont("Arial", 15, QFont.Bold))
        layout.addWidget(self.lbl_titre)

        # Résumé en-tête : snapshot vs réel total
        self.lbl_snapshot = QLabel()
        self.lbl_snapshot.setStyleSheet(
            "font-size: 13px; color: #2c3e50; padding: 6px 0;"
        )
        layout.addWidget(self.lbl_snapshot)

        # Tableau détail par OF / composant
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "OF Code", "Component", "Qty",
            "Status",
            "Initial Cost\n(snapshot)",
            "Real Cost\n(actual/planned)",
            "Variance\n(€)",
            "Source",
        ])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dde;
                border-radius: 4px;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 6px;
                font-size: 11px;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        layout.addWidget(self.table)

        # Légende
        legende = QLabel(
            "🟢 Actual timed data  |  🔵 Planned schedule data  |  "
            "🔴 Variance > 10%"
        )
        legende.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        layout.addWidget(legende)

        # Bouton fermer
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(34)
        btn_close.setFixedWidth(100)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                border-radius: 4px; padding: 0 14px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        btn_close.clicked.connect(self.accept)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(btn_close)
        layout.addLayout(h)

    # ---------------------------------------------------------- Data logic --

    def _charger_donnees(self):
        from database import SessionLocal
        from models import LigneCommande, OrdreFabrication, OperationPlanifiee

        session = SessionLocal()
        try:
            ligne = session.get(LigneCommande, self.id_ligne)
            if not ligne:
                return

            self.lbl_titre.setText(
                f"Cost Analysis — Line {ligne.code_ligne or self.id_ligne}  "
                f"({ligne.assemblage.nom if ligne.assemblage else '—'})"
            )

            # ---- Snapshot total (prix de revient initial de la ligne) ----
            snapshot_ligne = float(ligne.prix_revient_snapshot or 0)

            rows = []
            cout_reel_total = 0.0

            for ofa in ligne.of_assemblages:
                for of in ofa.ordres_fabrication:
                    snap_of = float(of.prix_revient_snapshot or 0)
                    cout_reel, source = self._calculer_cout_reel_of(session, of)
                    cout_reel_total += cout_reel
                    rows.append({
                        "code_of":  of.code_of or str(of.id_of),
                        "composant": of.composant.nom if of.composant else "—",
                        "quantite":  float(of.quantite),
                        "statut":    of.statut,
                        "snapshot":  snap_of,
                        "reel":      cout_reel,
                        "source":    source,
                    })

            # ---- Résumé en-tête ----
            ecart_total = cout_reel_total - snapshot_ligne
            ecart_pct   = (ecart_total / snapshot_ligne * 100) if snapshot_ligne else 0
            couleur_ecart = "#27ae60" if ecart_total <= 0 else (
                "#e74c3c" if abs(ecart_pct) > 10 else "#e67e22"
            )
            self.lbl_snapshot.setText(
                f"<b>Initial cost (snapshot) :</b> {self._fmt(snapshot_ligne)}   "
                f"<b>Real / estimated cost :</b> {self._fmt(cout_reel_total)}   "
                f"<b>Variance :</b> <span style='color:{couleur_ecart}'>"
                f"{'+' if ecart_total >= 0 else ''}{self._fmt(ecart_total)} "
                f"({'+' if ecart_pct >= 0 else ''}{ecart_pct:.1f}%)</span>"
            )

            # ---- Remplir le tableau ----
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                ecart = row["reel"] - row["snapshot"]
                ecart_pct_of = (
                    ecart / row["snapshot"] * 100 if row["snapshot"] else 0
                )

                self.table.setItem(r, 0, QTableWidgetItem(row["code_of"]))
                self.table.setItem(r, 1, QTableWidgetItem(row["composant"]))
                self.table.setItem(r, 2, self._right(f"{row['quantite']:.3g}"))
                statut_item = self._statut_item(row["statut"])
                self.table.setItem(r, 3, statut_item)
                self.table.setItem(r, 4, self._right(self._fmt(row["snapshot"])))
                self.table.setItem(r, 5, self._right(self._fmt(row["reel"])))

                ecart_item = self._right(
                    f"{'+' if ecart >= 0 else ''}{self._fmt(ecart)}"
                )
                if abs(ecart_pct_of) > 10:
                    ecart_item.setForeground(QColor("#e74c3c"))
                elif ecart > 0:
                    ecart_item.setForeground(QColor("#e67e22"))
                else:
                    ecart_item.setForeground(QColor("#27ae60"))
                self.table.setItem(r, 6, ecart_item)

                src_item = QTableWidgetItem(row["source"])
                src_item.setForeground(QColor(
                    "#27ae60" if row["source"] == "Actual" else "#3498db"
                ))
                self.table.setItem(r, 7, src_item)

        finally:
            session.close()

    # ---- Calcul du coût réel d'un OF ----
    def _calculer_cout_reel_of(self, session, of) -> tuple[float, str]:
        """
        Retourne (coût_réel, source) pour un OF.
        source = "Actual"  → toutes les ops terminées, on utilise les tps réels
        source = "Planned" → ops en cours/planifiées, on utilise les tps du planning
        """
        from models import OperationPlanifiee

        ops_plan = session.query(OperationPlanifiee).filter_by(
            id_of=of.id_of
        ).all()

        if not ops_plan:
            # Pas d'ops planifiées : on se rabat sur le snapshot
            return float(of.prix_revient_snapshot or 0), "Planned"

        # Inclut aussi le coût matière (inchangé quel que soit le statut)
        cout_mat = 0.0
        if of.composant:
            from services.cout_service import calculer_cout_matiere
            cout_mat = calculer_cout_matiere(of.composant)

        cout_ops = 0.0
        all_terminee = all(op.statut == "terminee" for op in ops_plan)
        source = "Actual" if all_terminee else "Planned"

        for op_plan in ops_plan:
            machine = op_plan.machine
            service = op_plan.service if hasattr(op_plan, "service") else None

            if op_plan.statut == "terminee" and (
                op_plan.tps_prep_reel is not None
                and op_plan.tps_exec_reel is not None
            ):
                # Temps réels pointés (en minutes)
                duree_h = (
                    float(op_plan.tps_prep_reel) + float(op_plan.tps_exec_reel)
                ) / 60.0
            else:
                # Temps planifiés (dates)
                if op_plan.date_debut and op_plan.date_fin:
                    duree_h = (
                        op_plan.date_fin - op_plan.date_debut
                    ).total_seconds() / 3600.0
                else:
                    # Fallback sur les temps théoriques de la gamme
                    op = op_plan.operation
                    if op:
                        duree_h = (
                            float(op.tps_preparation or 0)
                            + float(op.tps_execution or 0) * float(of.quantite)
                        ) / 60.0
                    else:
                        duree_h = 0.0

            # Tarification
            if machine:
                if machine.tarif_horaire:
                    cout_ops += duree_h * float(machine.tarif_horaire)
                if machine.cout_operateur and machine.charge_operateur:
                    charge = float(machine.charge_operateur) / 100.0
                    cout_ops += duree_h * float(machine.cout_operateur) * charge
            elif service:
                if service.cout_horaire:
                    cout_ops += duree_h * float(service.cout_horaire)
                elif service.cout_fixe:
                    cout_ops += float(service.cout_fixe) * float(of.quantite)
            else:
                # Pièce externe : récupérée depuis l'opération de gamme
                op = op_plan.operation
                if op and op.piece_externe and op.piece_externe.prix_unitaire:
                    cout_ops += float(op.piece_externe.prix_unitaire) * float(of.quantite)

        return round(cout_mat + cout_ops, 2), source

    # ---- Helpers ----
    @staticmethod
    def _fmt(val: float) -> str:
        return f"{val:,.2f} €".replace(",", "\u202f")

    @staticmethod
    def _right(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return item

    @staticmethod
    def _statut_item(statut: str) -> QTableWidgetItem:
        labels = {
            "a_planifier": ("To Schedule", "#e67e22"),
            "planifie":    ("Planned",     "#3498db"),
            "en_cours":    ("In Progress", "#9b59b6"),
            "termine":     ("Completed",   "#27ae60"),
            "rebute":      ("Scrapped",    "#e74c3c"),
            "annule":      ("Cancelled",   "#95a5a6"),
        }
        txt, color = labels.get(statut, (statut, "#95a5a6"))
        item = QTableWidgetItem(txt)
        item.setForeground(QColor(color))
        item.setFont(QFont("Arial", 10, QFont.Bold))
        return item


class NouvelleCommandeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Order")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("Customer name")

        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("DD/MM/YYYY")
        from PySide6.QtCore import QDate
        self.date_input.setText(QDate.currentDate().toString("dd/MM/yyyy"))

        self.num_externe_input = QLineEdit()
        self.num_externe_input.setPlaceholderText("Customer reference (optional)")

        self.date_livraison_input = QLineEdit()
        self.date_livraison_input.setPlaceholderText("DD/MM/YYYY")
        self.date_livraison_input.setText(
            QDate.currentDate().addDays(30).toString("dd/MM/yyyy")
        )

        form.addRow("Customer :", self.client_input)
        form.addRow("Date :", self.date_input)
        form.addRow("External Ref. :", self.num_externe_input)
        form.addRow("Delivery Date :", self.date_livraison_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _valider(self):
        client = self.client_input.text().strip()
        if not client:
            QMessageBox.warning(self, "Warning", "Customer is required.")
            return

        from datetime import datetime
        try:
            date_cmd = datetime.strptime(
                self.date_input.text(), "%d/%m/%Y"
            ).date()
        except ValueError:
            QMessageBox.warning(self, "Warning",
                                "Invalid date format. Use DD/MM/YYYY.")
            return

        try:
            date_livraison = datetime.strptime(
                self.date_livraison_input.text(), "%d/%m/%Y"
            ).date()
        except ValueError:
            QMessageBox.warning(self, "Warning",
                                "Invalid delivery date. Use DD/MM/YYYY.")
            return

        session = SessionLocal()
        try:
            code = generer_code_commande(session, date_cmd)
            commande = Commande(
                client=client,
                date_commande=date_cmd,
                numero_externe=self.num_externe_input.text().strip() or None,
                date_livraison=date_livraison,
                statut="planifiee",
                code_commande=code
            )
            session.add(commande)
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class AjouterLigneDialog(QDialog):
    def __init__(self, id_commande: int, code_commande: str, parent=None):
        super().__init__(parent)
        self.id_commande   = id_commande
        self.code_commande = code_commande
        self.setWindowTitle(f"Add Order Line — {code_commande}")
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.assemblage_combo = QComboBox()
        self._charger_assemblages()

        self.quantite_spin = QDoubleSpinBox()
        self.quantite_spin.setMinimum(0.001)
        self.quantite_spin.setMaximum(99999)
        self.quantite_spin.setValue(1.0)
        self.quantite_spin.setDecimals(3)

        form.addRow("Assembly :", self.assemblage_combo)
        form.addRow("Quantity :", self.quantite_spin)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _charger_assemblages(self):
        session = SessionLocal()
        try:
            assemblages = session.query(Assemblage).order_by(
                Assemblage.nom
            ).all()
            for a in assemblages:
                self.assemblage_combo.addItem(
                    f"{a.nom} ({a.reference or '—'})", a.id_assemblage
                )
        finally:
            session.close()

    def _valider(self):
        session = SessionLocal()
        try:
            nb_lignes = session.query(LigneCommande).filter_by(
                id_commande=self.id_commande
            ).count()

            code_ligne = generer_code_ligne(
                self.code_commande, nb_lignes + 1
            )

            ligne = LigneCommande(
                id_commande=self.id_commande,
                id_assemblage=self.assemblage_combo.currentData(),
                quantite=self.quantite_spin.value(),
                code_ligne=code_ligne
            )
            session.add(ligne)
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()