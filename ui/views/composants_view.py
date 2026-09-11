from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QSplitter, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import Composant, Gamme, Operation, Machine, MatierePremiere
from services.cout_service import (
    calculer_prix_revient, format_prix,
    recalculer_et_sauvegarder_composant,
    _recalculer_assemblages_du_composant
)


def list_style():
    return """
        QListWidget {
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }
        QListWidget::item { padding: 4px 8px; }
        QListWidget::item:selected {
            background-color: #3498db;
            color: white;
        }
    """


class ComposantsView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_composants()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("Components")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Component")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet(self._btn_style("#3498db", "#2980b9"))
        btn_nouveau.clicked.connect(self._nouveau_composant)
        header.addWidget(btn_nouveau)

        btn_modifier = QPushButton("✏ Edit")
        btn_modifier.setFixedHeight(36)
        btn_modifier.setStyleSheet(self._btn_style("#8e44ad", "#7d3c98"))
        btn_modifier.clicked.connect(self._modifier_composant)
        header.addWidget(btn_modifier)

        btn_cout = QPushButton("💰 Calculate Cost")
        btn_cout.setFixedHeight(36)
        btn_cout.setStyleSheet(self._btn_style("#27ae60", "#219a52"))
        btn_cout.clicked.connect(self._calculer_cout)
        header.addWidget(btn_cout)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Vertical)

        # Components table
        comp_widget = QWidget()
        comp_layout = QVBoxLayout(comp_widget)
        comp_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Product Code", "Name", "Type",
            "Material", "Cost Price", "Plan URL"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self._table_style())
        self.table.selectionModel().selectionChanged.connect(self._afficher_gamme)
        comp_layout.addWidget(self.table)
        splitter.addWidget(comp_widget)

        # Routing table
        gamme_widget = QWidget()
        gamme_layout = QVBoxLayout(gamme_widget)
        gamme_layout.setContentsMargins(0, 10, 0, 0)

        gamme_header = QHBoxLayout()
        self.gamme_titre = QLabel("Manufacturing Routing")
        self.gamme_titre.setFont(QFont("Arial", 12, QFont.Bold))
        gamme_header.addWidget(self.gamme_titre)
        gamme_header.addStretch()

        for label, color, hover, slot in [
            ("+ Add Operation", "#27ae60", "#219a52", lambda: self._ajouter_operation()),
            ("✏ Edit",          "#8e44ad", "#7d3c98", lambda: self._modifier_operation()),
            ("✕ Delete",        "#e74c3c", "#c0392b", lambda: self._supprimer_operation()),
            ("↑ Move Up",       "#2c3e50", "#34495e", lambda: self._monter_operation()),
            ("↓ Move Down",     "#2c3e50", "#34495e", lambda: self._descendre_operation()),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setStyleSheet(self._btn_style(color, hover))
            btn.clicked.connect(slot)
            gamme_header.addWidget(btn)

        gamme_layout.addLayout(gamme_header)

        self.ops_table = QTableWidget()
        self.ops_table.setColumnCount(6)
        self.ops_table.setHorizontalHeaderLabels([
            "Order", "Description", "Machine / Service",
            "Prep (min)", "Exec (min/unit)", "Plan URL"
        ])
        self.ops_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ops_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ops_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ops_table.setAlternatingRowColors(True)
        self.ops_table.setStyleSheet(self._table_style())
        gamme_layout.addWidget(self.ops_table)
        splitter.addWidget(gamme_widget)
        splitter.setSizes([350, 300])
        layout.addWidget(splitter)

    def _btn_style(self, color, hover):
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                border-radius: 4px; padding: 0 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """

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

    def _get_id_composant_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _get_id_operation_selectionne(self):
        row = self.ops_table.currentRow()
        if row < 0:
            return None
        item = self.ops_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _charger_composants(self):
        session = SessionLocal()
        try:
            composants = session.query(Composant).order_by(Composant.nom).all()
            self.table.setRowCount(len(composants))
            for row, c in enumerate(composants):
                id_item = QTableWidgetItem(str(c.id_composant))
                id_item.setData(Qt.UserRole, c.id_composant)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, QTableWidgetItem(c.reference or "—"))
                self.table.setItem(row, 2, QTableWidgetItem(c.nom))

                type_labels = {
                    "usine":          "Machined",
                    "machined":       "Machined",
                    "brut":           "Raw",
                    "raw":            "Raw",
                    "sous_assemblage":"Sub-assembly",
                    "sub_assembly":   "Sub-assembly",
                }
                type_txt = type_labels.get(c.type or "", c.type or "—")
                self.table.setItem(row, 3, QTableWidgetItem(type_txt))

                matiere_nom = c.matiere_brut.nom if c.matiere_brut else "—"
                self.table.setItem(row, 4, QTableWidgetItem(matiere_nom))
                self.table.setItem(row, 5, QTableWidgetItem(
                    format_prix(c.prix_revient) if c.prix_revient else "—"
                ))
                self.table.setItem(row, 6, QTableWidgetItem(c.plan_url or "—"))
        finally:
            session.close()

    def _afficher_gamme(self):
        id_composant = self._get_id_composant_selectionne()
        if not id_composant:
            return

        row = self.table.currentRow()
        nom = self.table.item(row, 2).text()
        self.ops_table.setRowCount(0)

        session = SessionLocal()
        try:
            gamme = session.query(Gamme).filter_by(
                id_composant=id_composant, active=True
            ).first()

            if not gamme:
                self.gamme_titre.setText(
                    f"Manufacturing Routing — {nom} (No active routing)")
                return

            self.gamme_titre.setText(
                f"Manufacturing Routing — {nom} (v{gamme.version})")

            ops = sorted(gamme.operations, key=lambda o: o.ordre)
            for row_op, op in enumerate(ops):
                self.ops_table.insertRow(row_op)
                ordre_item = QTableWidgetItem(str(op.ordre))
                ordre_item.setData(Qt.UserRole, op.id_operation)
                self.ops_table.setItem(row_op, 0, ordre_item)
                self.ops_table.setItem(row_op, 1, QTableWidgetItem(
                    op.description or "—"))

                if op.machine:
                    ressource = op.machine.nom
                elif hasattr(op, 'piece_externe') and op.piece_externe:
                    ressource = f"[EXT] {op.piece_externe.nom}"
                elif hasattr(op, 'service') and op.service:
                    ressource = f"[SRV] {op.service.nom}"
                else:
                    ressource = "—"
                self.ops_table.setItem(row_op, 2, QTableWidgetItem(ressource))

                self.ops_table.setItem(row_op, 3, QTableWidgetItem(
                    str(op.tps_preparation)))
                self.ops_table.setItem(row_op, 4, QTableWidgetItem(
                    str(op.tps_execution)))
                self.ops_table.setItem(row_op, 5, QTableWidgetItem(
                    op.plan_url or "—"))
        finally:
            session.close()

    def _nouveau_composant(self):
        dialog = ComposantDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_composants()

    def _modifier_composant(self):
        id_composant = self._get_id_composant_selectionne()
        if not id_composant:
            QMessageBox.warning(self, "Warning", "Please select a component.")
            return
        dialog = ComposantDialog(self, id_composant=id_composant)
        if dialog.exec() == QDialog.Accepted:
            self._charger_composants()
            self._afficher_gamme()

    def _calculer_cout(self):
        id_composant = self._get_id_composant_selectionne()
        if not id_composant:
            QMessageBox.warning(self, "Warning", "Please select a component.")
            return

        session = SessionLocal()
        try:
            recalculer_et_sauvegarder_composant(session, id_composant)
            _recalculer_assemblages_du_composant(session, id_composant)
            session.commit()

            result = calculer_prix_revient(session, id_composant, quantite=1.0)
            QMessageBox.information(
                self, "Cost Calculation",
                f"Component : {result['composant']}\n\n"
                f"Material cost  : {format_prix(result['matiere'])}\n"
                f"Operation cost : {format_prix(result['operations'])}\n"
                f"─────────────────────────\n"
                f"Total cost     : {format_prix(result['total'])}\n\n"
                f"(for 1 unit)"
            )
            row = self.table.currentRow()
            if row >= 0:
                self.table.setItem(row, 5, QTableWidgetItem(
                    format_prix(result['total'])
                ))
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _ajouter_operation(self):
        id_composant = self._get_id_composant_selectionne()
        if not id_composant:
            QMessageBox.warning(self, "Warning", "Please select a component.")
            return
        dialog = OperationDialog(id_composant, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_composants()  # ← prix mis à jour dans la table
            self._afficher_gamme()

    def _modifier_operation(self):
        id_operation = self._get_id_operation_selectionne()
        if not id_operation:
            QMessageBox.warning(self, "Warning", "Please select an operation.")
            return
        dialog = OperationDialog(None, self, id_operation=id_operation)
        if dialog.exec() == QDialog.Accepted:
            self._charger_composants()  # ← prix mis à jour dans la table
            self._afficher_gamme()

    def _supprimer_operation(self):
        id_operation = self._get_id_operation_selectionne()
        if not id_operation:
            QMessageBox.warning(self, "Warning", "Please select an operation.")
            return
        reply = QMessageBox.question(
            self, "Delete Operation",
            "Delete this operation from the routing?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        session = SessionLocal()
        try:
            op = session.get(Operation, id_operation)
            if op:
                id_composant_op = op.gamme.id_composant
                session.delete(op)
                session.commit()
                recalculer_et_sauvegarder_composant(session, id_composant_op)
                _recalculer_assemblages_du_composant(session, id_composant_op)
                session.commit()
                self._charger_composants()  # rafraîchit le prix dans le tableau
                self._afficher_gamme()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _monter_operation(self):
        self._deplacer_operation(-1)

    def _descendre_operation(self):
        self._deplacer_operation(1)

    def _deplacer_operation(self, direction: int):
        id_operation = self._get_id_operation_selectionne()
        if not id_operation:
            QMessageBox.warning(self, "Warning", "Please select an operation.")
            return
        id_composant = self._get_id_composant_selectionne()
        session = SessionLocal()
        try:
            gamme = session.query(Gamme).filter_by(
                id_composant=id_composant, active=True
            ).first()
            if not gamme:
                return
            ops = sorted(gamme.operations, key=lambda o: o.ordre)
            idx = next(
                (i for i, o in enumerate(ops)
                 if o.id_operation == id_operation), None
            )
            if idx is None:
                return
            idx_cible = idx + direction
            if idx_cible < 0 or idx_cible >= len(ops):
                return
            op_courante = session.get(Operation, id_operation)
            op_cible    = ops[idx_cible]
            ordre_tmp         = op_courante.ordre
            op_courante.ordre = op_cible.ordre
            op_cible.ordre    = ordre_tmp
            session.commit()
            self._afficher_gamme()
            for r in range(self.ops_table.rowCount()):
                if self.ops_table.item(r, 0).data(Qt.UserRole) == id_operation:
                    self.ops_table.selectRow(r)
                    break
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class ComposantDialog(QDialog):
    def __init__(self, parent=None, id_composant=None):
        super().__init__(parent)
        self.id_composant = id_composant
        self.setWindowTitle("Edit Component" if id_composant else "New Component")
        self.setMinimumWidth(460)
        self._build_ui()
        if id_composant:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ref_input  = QLineEdit()
        self.ref_input.setPlaceholderText("Ex: BRI-DN50")
        self.nom_input  = QLineEdit()
        self.nom_input.setPlaceholderText("Component name")
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description")
        self.plan_input = QLineEdit()
        self.plan_input.setPlaceholderText("\\\\server\\plans\\component.pdf")

        form.addRow("Product Code :", self.ref_input)
        form.addRow("Name :", self.nom_input)
        form.addRow("Description :", self.desc_input)
        form.addRow("Plan URL :", self.plan_input)
        layout.addLayout(form)

        # Type
        lbl_type = QLabel("Component Type :")
        lbl_type.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_type)

        self.type_list = QListWidget()
        self.type_list.setFixedHeight(84)
        self.type_list.setStyleSheet(list_style())
        types = [
            ("Machined Part",  "machined"),
            ("Raw Material",   "raw"),
            ("Sub-assembly",   "sub_assembly"),
        ]
        for label, val in types:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, val)
            self.type_list.addItem(item)
        self.type_list.setCurrentRow(0)
        self.type_list.currentRowChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_list)

        # Raw Material section
        self.mat_widget = QWidget()
        mat_layout = QVBoxLayout(self.mat_widget)
        mat_layout.setContentsMargins(0, 0, 0, 0)

        lbl_mat = QLabel("Raw Material :")
        lbl_mat.setFont(QFont("Arial", 10, QFont.Bold))
        mat_layout.addWidget(lbl_mat)

        self.matiere_list = QListWidget()
        self.matiere_list.setFixedHeight(90)
        self.matiere_list.setStyleSheet(list_style())
        none_item = QListWidgetItem("— None —")
        none_item.setData(Qt.UserRole, None)
        self.matiere_list.addItem(none_item)
        self._charger_matieres()
        self.matiere_list.setCurrentRow(0)
        mat_layout.addWidget(self.matiere_list)

        lbl_forme = QLabel("Raw Shape :")
        lbl_forme.setFont(QFont("Arial", 10, QFont.Bold))
        mat_layout.addWidget(lbl_forme)

        self.forme_list = QListWidget()
        self.forme_list.setFixedHeight(90)
        self.forme_list.setStyleSheet(list_style())
        for f in ["— None —", "axe", "tube", "plaque"]:
            self.forme_list.addItem(QListWidgetItem(f))
        self.forme_list.setCurrentRow(0)
        self.forme_list.currentRowChanged.connect(self._on_forme_changed)
        mat_layout.addWidget(self.forme_list)

        # Dimensions
        self.dim_widget = QWidget()
        self.dim_layout = QFormLayout(self.dim_widget)
        self.w_diametre  = QDoubleSpinBox(); self.w_diametre.setSuffix(" mm");  self.w_diametre.setMaximum(99999)
        self.w_longueur  = QDoubleSpinBox(); self.w_longueur.setSuffix(" mm");  self.w_longueur.setMaximum(99999)
        self.w_diam_ext  = QDoubleSpinBox(); self.w_diam_ext.setSuffix(" mm");  self.w_diam_ext.setMaximum(99999)
        self.w_diam_int  = QDoubleSpinBox(); self.w_diam_int.setSuffix(" mm");  self.w_diam_int.setMaximum(99999)
        self.w_largeur   = QDoubleSpinBox(); self.w_largeur.setSuffix(" mm");   self.w_largeur.setMaximum(99999)
        self.w_hauteur   = QDoubleSpinBox(); self.w_hauteur.setSuffix(" mm");   self.w_hauteur.setMaximum(99999)
        self.w_epaisseur = QDoubleSpinBox(); self.w_epaisseur.setSuffix(" mm"); self.w_epaisseur.setMaximum(99999)
        mat_layout.addWidget(self.dim_widget)
        layout.addWidget(self.mat_widget)

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

        self._on_type_changed(0)

    def _charger_matieres(self):
        session = SessionLocal()
        try:
            matieres = session.query(MatierePremiere).order_by(
                MatierePremiere.nom).all()
            for m in matieres:
                item = QListWidgetItem(m.nom)
                item.setData(Qt.UserRole, m.id_matiere)
                self.matiere_list.addItem(item)
        finally:
            session.close()

    def _on_type_changed(self, idx):
        item = self.type_list.item(idx)
        if not item:
            return
        val = item.data(Qt.UserRole)
        self.mat_widget.setVisible(val in ("machined", "raw"))
        self.adjustSize()

    def _clear_dim_layout(self):
        while self.dim_layout.count():
            item = self.dim_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def _on_forme_changed(self, idx):
        self._clear_dim_layout()
        forme = self.forme_list.item(idx).text() if self.forme_list.item(idx) else ""
        if forme == "axe":
            self.dim_layout.addRow("Diameter :", self.w_diametre)
            self.dim_layout.addRow("Length :", self.w_longueur)
        elif forme == "tube":
            self.dim_layout.addRow("Ext. Diameter :", self.w_diam_ext)
            self.dim_layout.addRow("Int. Diameter :", self.w_diam_int)
            self.dim_layout.addRow("Length :", self.w_longueur)
        elif forme == "plaque":
            self.dim_layout.addRow("Width :", self.w_largeur)
            self.dim_layout.addRow("Height :", self.w_hauteur)
            self.dim_layout.addRow("Thickness :", self.w_epaisseur)
        self.dim_widget.setVisible(forme not in ("— None —", ""))
        self.adjustSize()

    def _charger(self):
        session = SessionLocal()
        try:
            c = session.get(Composant, self.id_composant)
            if not c:
                return
            self.ref_input.setText(c.reference or "")
            self.nom_input.setText(c.nom or "")
            self.desc_input.setText(c.description or "")
            self.plan_input.setText(c.plan_url or "")

            type_map = {
                "usine": "machined", "machined": "machined",
                "brut": "raw", "raw": "raw",
                "sous_assemblage": "sub_assembly", "sub_assembly": "sub_assembly",
            }
            type_val = type_map.get(c.type or "", "machined")
            for i in range(self.type_list.count()):
                if self.type_list.item(i).data(Qt.UserRole) == type_val:
                    self.type_list.setCurrentRow(i)
                    break

            if c.id_matiere_brut:
                for i in range(self.matiere_list.count()):
                    if self.matiere_list.item(i).data(Qt.UserRole) == c.id_matiere_brut:
                        self.matiere_list.setCurrentRow(i)
                        break

            forme_map = {"axe": 1, "tube": 2, "plaque": 3}
            self.forme_list.setCurrentRow(forme_map.get(c.forme_brut or "", 0))

            if c.brut_diametre:  self.w_diametre.setValue(float(c.brut_diametre))
            if c.brut_longueur:  self.w_longueur.setValue(float(c.brut_longueur))
            if c.brut_diam_ext:  self.w_diam_ext.setValue(float(c.brut_diam_ext))
            if c.brut_diam_int:  self.w_diam_int.setValue(float(c.brut_diam_int))
            if c.brut_largeur:   self.w_largeur.setValue(float(c.brut_largeur))
            if c.brut_hauteur:   self.w_hauteur.setValue(float(c.brut_hauteur))
            if c.brut_epaisseur: self.w_epaisseur.setValue(float(c.brut_epaisseur))
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return

        type_item  = self.type_list.currentItem()
        forme_item = self.forme_list.currentItem()
        mat_item   = self.matiere_list.currentItem()

        type_val  = type_item.data(Qt.UserRole) if type_item else "machined"
        forme_val = forme_item.text() if forme_item else "— None —"
        if forme_val == "— None —":
            forme_val = None

        session = SessionLocal()
        try:
            if self.id_composant:
                c = session.get(Composant, self.id_composant)
            else:
                c = Composant()
                session.add(c)

            c.reference   = self.ref_input.text().strip() or None
            c.nom         = nom
            c.type        = type_val
            c.description = self.desc_input.text().strip() or None
            c.plan_url    = self.plan_input.text().strip() or None

            if type_val in ("machined", "raw"):
                c.id_matiere_brut = mat_item.data(Qt.UserRole) if mat_item else None
                c.forme_brut      = forme_val
                c.brut_diametre   = self.w_diametre.value() if forme_val == "axe" else None
                c.brut_longueur   = self.w_longueur.value() if forme_val in ("axe", "tube") else None
                c.brut_diam_ext   = self.w_diam_ext.value() if forme_val == "tube" else None
                c.brut_diam_int   = self.w_diam_int.value() if forme_val == "tube" else None
                c.brut_largeur    = self.w_largeur.value() if forme_val == "plaque" else None
                c.brut_hauteur    = self.w_hauteur.value() if forme_val == "plaque" else None
                c.brut_epaisseur  = self.w_epaisseur.value() if forme_val == "plaque" else None
            else:
                c.id_matiere_brut = None
                c.forme_brut      = None

            session.flush()

            if not self.id_composant:
                gamme = Gamme(id_composant=c.id_composant, version=1, active=True)
                session.add(gamme)

            session.commit()

            # Recalcule le prix de revient
            recalculer_et_sauvegarder_composant(session, c.id_composant)
            _recalculer_assemblages_du_composant(session, c.id_composant)
            session.commit()

            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class OperationDialog(QDialog):
    def __init__(self, id_composant, parent=None, id_operation=None):
        super().__init__(parent)
        self.id_composant = id_composant
        self.id_operation = id_operation
        self.setWindowTitle("Edit Step" if id_operation else "Add Step")
        self.setMinimumWidth(450)
        self._build_ui()
        if id_operation:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ordre_spin = QSpinBox()
        self.ordre_spin.setMinimum(1)
        self.ordre_spin.setMaximum(99)

        # Auto-incrémente l'ordre si nouveau
        if not self.id_operation and self.id_composant:
            session = SessionLocal()
            try:
                gamme = session.query(Gamme).filter_by(
                    id_composant=self.id_composant, active=True
                ).first()
                if gamme and gamme.operations:
                    max_ordre = max(op.ordre for op in gamme.operations)
                    self.ordre_spin.setValue(max_ordre + 1)
                else:
                    self.ordre_spin.setValue(1)
            finally:
                session.close()

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Ex: Rough turning")

        self.prep_spin = QSpinBox()
        self.prep_spin.setMinimum(0)
        self.prep_spin.setMaximum(9999)
        self.prep_spin.setSuffix(" min")

        self.exec_spin = QSpinBox()
        self.exec_spin.setMinimum(0)
        self.exec_spin.setMaximum(9999)
        self.exec_spin.setSuffix(" min/unit")

        self.plan_input = QLineEdit()
        self.plan_input.setPlaceholderText("\\\\server\\routings\\op.pdf")

        form.addRow("Order :", self.ordre_spin)
        form.addRow("Description :", self.desc_input)
        form.addRow("Setup time :", self.prep_spin)
        form.addRow("Cycle time :", self.exec_spin)
        form.addRow("Plan URL :", self.plan_input)
        layout.addLayout(form)

        # Step type
        lbl_step = QLabel("Step Type :")
        lbl_step.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_step)

        self.step_type_list = QListWidget()
        self.step_type_list.setFixedHeight(84)
        self.step_type_list.setStyleSheet(list_style())
        for label, val in [
            ("Machine Operation", "machine"),
            ("External Part",     "external"),
            ("Service",           "service"),
        ]:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, val)
            self.step_type_list.addItem(item)
        self.step_type_list.setCurrentRow(0)
        self.step_type_list.currentRowChanged.connect(self._on_step_type_changed)
        layout.addWidget(self.step_type_list)

        # Machine list
        self.machine_widget = QWidget()
        machine_layout = QVBoxLayout(self.machine_widget)
        machine_layout.setContentsMargins(0, 0, 0, 0)
        lbl_machine = QLabel("Machine :")
        lbl_machine.setFont(QFont("Arial", 10, QFont.Bold))
        machine_layout.addWidget(lbl_machine)
        self.machine_list = QListWidget()
        self.machine_list.setFixedHeight(90)
        self.machine_list.setStyleSheet(list_style())
        self._charger_machines()
        machine_layout.addWidget(self.machine_list)
        layout.addWidget(self.machine_widget)

        # External part list
        self.external_widget = QWidget()
        external_layout = QVBoxLayout(self.external_widget)
        external_layout.setContentsMargins(0, 0, 0, 0)
        lbl_ext = QLabel("External Part :")
        lbl_ext.setFont(QFont("Arial", 10, QFont.Bold))
        external_layout.addWidget(lbl_ext)
        self.external_list = QListWidget()
        self.external_list.setFixedHeight(90)
        self.external_list.setStyleSheet(list_style())
        self._charger_externes()
        external_layout.addWidget(self.external_list)
        layout.addWidget(self.external_widget)

        # Service list
        self.service_widget = QWidget()
        service_layout = QVBoxLayout(self.service_widget)
        service_layout.setContentsMargins(0, 0, 0, 0)
        lbl_srv = QLabel("Service :")
        lbl_srv.setFont(QFont("Arial", 10, QFont.Bold))
        service_layout.addWidget(lbl_srv)
        self.service_list = QListWidget()
        self.service_list.setFixedHeight(90)
        self.service_list.setStyleSheet(list_style())
        self._charger_services()
        service_layout.addWidget(self.service_list)
        layout.addWidget(self.service_widget)

        self._on_step_type_changed(0)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #219a52; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _on_step_type_changed(self, idx):
        item = self.step_type_list.item(idx)
        if not item:
            return
        val = item.data(Qt.UserRole)
        self.machine_widget.setVisible(val == "machine")
        self.external_widget.setVisible(val == "external")
        self.service_widget.setVisible(val == "service")
        self.adjustSize()

    def _charger_machines(self):
        session = SessionLocal()
        try:
            machines = session.query(Machine).order_by(Machine.nom).all()
            for m in machines:
                item = QListWidgetItem(f"{m.nom} ({m.type})")
                item.setData(Qt.UserRole, m.id_machine)
                self.machine_list.addItem(item)
        finally:
            session.close()

    def _charger_externes(self):
        from models import PieceExterne
        session = SessionLocal()
        try:
            pieces = session.query(PieceExterne).order_by(PieceExterne.nom).all()
            for p in pieces:
                item = QListWidgetItem(
                    f"{p.nom} ({p.fournisseur or '—'}) — {format_prix(p.prix_unitaire)}"
                )
                item.setData(Qt.UserRole, p.id_piece_externe)
                self.external_list.addItem(item)
        finally:
            session.close()

    def _charger_services(self):
        from models import Service
        session = SessionLocal()
        try:
            services = session.query(Service).order_by(Service.nom).all()
            for s in services:
                cout = format_prix(s.cout_horaire) + "/h" if s.cout_horaire else \
                       format_prix(s.cout_fixe) if s.cout_fixe else "—"
                item = QListWidgetItem(f"{s.nom} ({s.type_service}) — {cout}")
                item.setData(Qt.UserRole, s.id_service)
                self.service_list.addItem(item)
        finally:
            session.close()

    def _charger(self):
        session = SessionLocal()
        try:
            op = session.get(Operation, self.id_operation)
            if not op:
                return
            self.id_composant = op.gamme.id_composant
            self.ordre_spin.setValue(op.ordre)
            self.desc_input.setText(op.description or "")
            self.prep_spin.setValue(op.tps_preparation or 0)
            self.exec_spin.setValue(op.tps_execution or 0)
            self.plan_input.setText(op.plan_url or "")

            if op.id_machine:
                self.step_type_list.setCurrentRow(0)
                for i in range(self.machine_list.count()):
                    if self.machine_list.item(i).data(Qt.UserRole) == op.id_machine:
                        self.machine_list.setCurrentRow(i)
                        break
            elif op.id_piece_externe:
                self.step_type_list.setCurrentRow(1)
                for i in range(self.external_list.count()):
                    if self.external_list.item(i).data(Qt.UserRole) == op.id_piece_externe:
                        self.external_list.setCurrentRow(i)
                        break
            elif op.id_service:
                self.step_type_list.setCurrentRow(2)
                for i in range(self.service_list.count()):
                    if self.service_list.item(i).data(Qt.UserRole) == op.id_service:
                        self.service_list.setCurrentRow(i)
                        break
        finally:
            session.close()

    def _valider(self):
        step_item = self.step_type_list.currentItem()
        if not step_item:
            QMessageBox.warning(self, "Warning", "Please select a step type.")
            return

        step_type      = step_item.data(Qt.UserRole)
        id_machine     = None
        id_piece_ext   = None
        id_service_val = None

        if step_type == "machine":
            machine_item = self.machine_list.currentItem()
            if not machine_item:
                QMessageBox.warning(self, "Warning", "Please select a machine.")
                return
            id_machine = machine_item.data(Qt.UserRole)
        elif step_type == "external":
            ext_item = self.external_list.currentItem()
            if not ext_item:
                QMessageBox.warning(self, "Warning", "Please select an external part.")
                return
            id_piece_ext = ext_item.data(Qt.UserRole)
        elif step_type == "service":
            srv_item = self.service_list.currentItem()
            if not srv_item:
                QMessageBox.warning(self, "Warning", "Please select a service.")
                return
            id_service_val = srv_item.data(Qt.UserRole)

        session = SessionLocal()
        try:
            if self.id_operation:
                op = session.get(Operation, self.id_operation)
            else:
                gamme = session.query(Gamme).filter_by(
                    id_composant=self.id_composant, active=True
                ).first()
                if not gamme:
                    QMessageBox.warning(
                        self, "Warning",
                        "No active routing found for this component.")
                    return
                op = Operation(id_gamme=gamme.id_gamme)
                session.add(op)

            op.ordre            = self.ordre_spin.value()
            op.description      = self.desc_input.text().strip() or None
            op.id_machine       = id_machine
            op.id_piece_externe = id_piece_ext
            op.id_service       = id_service_val
            op.tps_preparation  = self.prep_spin.value()
            op.tps_execution    = self.exec_spin.value()
            op.plan_url         = self.plan_input.text().strip() or None

            session.commit()
            # Recalcule le prix du composant après modification de l'opération
            recalculer_et_sauvegarder_composant(session, self.id_composant)
            _recalculer_assemblages_du_composant(session, self.id_composant)
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()