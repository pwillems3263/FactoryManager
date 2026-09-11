from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox,
    QSplitter, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import Assemblage, Nomenclature, Composant, Service, PieceExterne


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


class AssemblagesView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_assemblages()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("Assemblies")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Assembly")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet(self._btn_style("#3498db", "#2980b9"))
        btn_nouveau.clicked.connect(self._nouvel_assemblage)
        header.addWidget(btn_nouveau)

        btn_modifier = QPushButton("✏ Edit")
        btn_modifier.setFixedHeight(36)
        btn_modifier.setStyleSheet(self._btn_style("#8e44ad", "#7d3c98"))
        btn_modifier.clicked.connect(self._modifier_assemblage)
        header.addWidget(btn_modifier)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Vertical)

        # Assemblies table
        asm_widget = QWidget()
        asm_layout = QVBoxLayout(asm_widget)
        asm_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Reference", "Name", "Cost Price", "Plan URL", "Description"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self._table_style())
        self.table.selectionModel().selectionChanged.connect(
            self._afficher_nomenclature
        )
        asm_layout.addWidget(self.table)
        splitter.addWidget(asm_widget)

        # Nomenclature table
        nom_widget = QWidget()
        nom_layout = QVBoxLayout(nom_widget)
        nom_layout.setContentsMargins(0, 10, 0, 0)

        nom_header = QHBoxLayout()
        self.nom_titre = QLabel("Bill of Materials")
        self.nom_titre.setFont(QFont("Arial", 12, QFont.Bold))
        nom_header.addWidget(self.nom_titre)
        nom_header.addStretch()

        btn_add_comp = QPushButton("+ Component")
        btn_add_comp.setFixedHeight(30)
        btn_add_comp.setStyleSheet(self._btn_style("#27ae60", "#219a52"))
        btn_add_comp.clicked.connect(self._ajouter_composant)
        nom_header.addWidget(btn_add_comp)

        btn_add_ext = QPushButton("+ External Part")
        btn_add_ext.setFixedHeight(30)
        btn_add_ext.setStyleSheet(self._btn_style("#e67e22", "#d35400"))
        btn_add_ext.clicked.connect(self._ajouter_piece_externe)
        nom_header.addWidget(btn_add_ext)

        btn_add_srv = QPushButton("+ Service")
        btn_add_srv.setFixedHeight(30)
        btn_add_srv.setStyleSheet(self._btn_style("#8e44ad", "#7d3c98"))
        btn_add_srv.clicked.connect(self._ajouter_service)
        nom_header.addWidget(btn_add_srv)

        # ── NOUVEAU BOUTON ──────────────────────────────────────────────
        btn_edit_qty = QPushButton("✏ Edit Qty")
        btn_edit_qty.setFixedHeight(30)
        btn_edit_qty.setStyleSheet(self._btn_style("#2c3e50", "#34495e"))
        btn_edit_qty.clicked.connect(self._modifier_nomenclature)
        nom_header.addWidget(btn_edit_qty)
        # ────────────────────────────────────────────────────────────────

        btn_retirer = QPushButton("✕ Remove")
        btn_retirer.setFixedHeight(30)
        btn_retirer.setStyleSheet(self._btn_style("#e74c3c", "#c0392b"))
        btn_retirer.clicked.connect(self._retirer_element)
        nom_header.addWidget(btn_retirer)

        nom_layout.addLayout(nom_header)

        self.nom_table = QTableWidget()
        self.nom_table.setColumnCount(5)
        self.nom_table.setHorizontalHeaderLabels([
            "Type", "Reference", "Name", "Quantity", "Details"
        ])
        self.nom_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.nom_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.nom_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.nom_table.setAlternatingRowColors(True)
        self.nom_table.setStyleSheet(self._table_style())
        nom_layout.addWidget(self.nom_table)
        splitter.addWidget(nom_widget)
        splitter.setSizes([300, 250])
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

    def _get_id_assemblage_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _charger_assemblages(self):
        session = SessionLocal()
        try:
            assemblages = session.query(Assemblage).order_by(Assemblage.nom).all()
            self.table.setRowCount(len(assemblages))
            for row, a in enumerate(assemblages):
                ref_item = QTableWidgetItem(a.reference or "—")
                ref_item.setData(Qt.UserRole, a.id_assemblage)
                self.table.setItem(row, 0, ref_item)
                self.table.setItem(row, 1, QTableWidgetItem(a.nom))
                self.table.setItem(row, 2, QTableWidgetItem(
                    f"{a.prix_revient} €" if a.prix_revient else "—"))
                self.table.setItem(row, 3, QTableWidgetItem(a.plan_url or "—"))
                self.table.setItem(row, 4, QTableWidgetItem(a.description or "—"))
        finally:
            session.close()

    def _afficher_nomenclature(self):
        id_assemblage = self._get_id_assemblage_selectionne()
        if not id_assemblage:
            return

        row = self.table.currentRow()
        nom = self.table.item(row, 1).text()
        self.nom_titre.setText(f"Bill of Materials — {nom}")
        self.nom_table.setRowCount(0)

        session = SessionLocal()
        try:
            nomenclatures = session.query(Nomenclature).filter_by(
                id_parent=id_assemblage,
                type_parent="assemblage"
            ).all()

            for row_n, n in enumerate(nomenclatures):
                self.nom_table.insertRow(row_n)

                if n.composant:
                    type_item = QTableWidgetItem("Component")
                    type_item.setForeground(QColor("#27ae60"))
                    ref  = n.composant.reference or "—"
                    name = n.composant.nom
                    details = n.composant.type or "—"
                elif n.piece_externe:
                    type_item = QTableWidgetItem("External Part")
                    type_item.setForeground(QColor("#e67e22"))
                    ref  = n.piece_externe.code_produit or "—"
                    name = n.piece_externe.nom
                    details = f"{n.piece_externe.fournisseur or '—'} — {n.piece_externe.prix_unitaire or '—'} €"
                elif n.service:
                    type_item = QTableWidgetItem("Service")
                    type_item.setForeground(QColor("#8e44ad"))
                    ref  = n.service.code_produit or "—"
                    name = n.service.nom
                    if n.service.cout_horaire:
                        details = f"{n.service.type_service} — {n.service.cout_horaire} €/h"
                    elif n.service.cout_fixe:
                        details = f"{n.service.type_service} — {n.service.cout_fixe} € fixed"
                    else:
                        details = n.service.type_service
                else:
                    type_item = QTableWidgetItem("Unknown")
                    ref = name = details = "—"

                # Stocke les IDs dans type_item (colonne 0) pour le Remove et l'Edit
                type_item.setData(Qt.UserRole, {
                    "id_composant":     n.id_composant,
                    "id_service":       n.id_service,
                    "id_piece_externe": n.id_piece_externe,
                    "id_parent":        n.id_parent,
                    "type_parent":      n.type_parent,
                })
                type_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.nom_table.setItem(row_n, 0, type_item)
                self.nom_table.setItem(row_n, 1, QTableWidgetItem(ref))
                self.nom_table.setItem(row_n, 2, QTableWidgetItem(name))
                self.nom_table.setItem(row_n, 3, QTableWidgetItem(str(n.quantite)))
                self.nom_table.setItem(row_n, 4, QTableWidgetItem(details))

        finally:
            session.close()

    def _nouvel_assemblage(self):
        dialog = AssemblageDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_assemblages()

    def _modifier_assemblage(self):
        id_assemblage = self._get_id_assemblage_selectionne()
        if not id_assemblage:
            QMessageBox.warning(self, "Warning", "Please select an assembly.")
            return
        dialog = AssemblageDialog(self, id_assemblage=id_assemblage)
        if dialog.exec() == QDialog.Accepted:
            self._charger_assemblages()
            self._afficher_nomenclature()

    def _ajouter_composant(self):
        id_assemblage = self._get_id_assemblage_selectionne()
        if not id_assemblage:
            QMessageBox.warning(self, "Warning", "Please select an assembly.")
            return
        dialog = AjouterElementDialog(id_assemblage, "component", self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_assemblages()
            self._afficher_nomenclature()

    def _ajouter_piece_externe(self):
        id_assemblage = self._get_id_assemblage_selectionne()
        if not id_assemblage:
            QMessageBox.warning(self, "Warning", "Please select an assembly.")
            return
        dialog = AjouterElementDialog(id_assemblage, "external", self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_assemblages()
            self._afficher_nomenclature()

    def _ajouter_service(self):
        id_assemblage = self._get_id_assemblage_selectionne()
        if not id_assemblage:
            QMessageBox.warning(self, "Warning", "Please select an assembly.")
            return
        dialog = AjouterElementDialog(id_assemblage, "service", self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_assemblages()
            self._afficher_nomenclature()

    # ── NOUVELLE MÉTHODE ────────────────────────────────────────────────
    def _modifier_nomenclature(self):
        id_assemblage = self._get_id_assemblage_selectionne()
        if not id_assemblage:
            QMessageBox.warning(self, "Warning", "Please select an assembly.")
            return
        row = self.nom_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select an element in the BOM.")
            return
        item = self.nom_table.item(row, 0)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        dialog = ModifierNomenclatureDialog(data, id_assemblage, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_assemblages()
            self._afficher_nomenclature()
    # ────────────────────────────────────────────────────────────────────

    def _retirer_element(self):
        row = self.nom_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select an element.")
            return

        reply = QMessageBox.question(
            self, "Remove Element",
            "Remove this element from the assembly?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        item = self.nom_table.item(row, 0)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return

        session = SessionLocal()
        try:
            q = session.query(Nomenclature).filter_by(
                id_parent=data["id_parent"],
                type_parent=data["type_parent"],
            )
            if data["id_composant"] is not None:
                q = q.filter_by(id_composant=data["id_composant"])
            elif data["id_piece_externe"] is not None:
                q = q.filter_by(id_piece_externe=data["id_piece_externe"])
            elif data["id_service"] is not None:
                q = q.filter_by(id_service=data["id_service"])
            n = q.first()
            if n:
                session.delete(n)
                session.commit()
                from services.cout_service import recalculer_assemblage
                recalculer_assemblage(session, data["id_parent"])
                session.commit()
                self._charger_assemblages()
                self._afficher_nomenclature()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class AssemblageDialog(QDialog):
    def __init__(self, parent=None, id_assemblage=None):
        super().__init__(parent)
        self.id_assemblage = id_assemblage
        self.setWindowTitle("Edit Assembly" if id_assemblage else "New Assembly")
        self.setMinimumWidth(420)
        self._build_ui()
        if id_assemblage:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.ref_input  = QLineEdit()
        self.ref_input.setPlaceholderText("Reference code")
        self.nom_input  = QLineEdit()
        self.nom_input.setPlaceholderText("Assembly name")
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description")

        self.plan_input = QLineEdit()
        self.plan_input.setPlaceholderText("\\\\server\\plans\\assembly.pdf")

        form.addRow("Reference :", self.ref_input)
        form.addRow("Name :", self.nom_input)
        form.addRow("Description :", self.desc_input)
        form.addRow("Plan URL :", self.plan_input)
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

    def _charger(self):
        session = SessionLocal()
        try:
            a = session.get(Assemblage, self.id_assemblage)
            if a:
                self.ref_input.setText(a.reference or "")
                self.nom_input.setText(a.nom or "")
                self.desc_input.setText(a.description or "")
                self.plan_input.setText(a.plan_url or "")
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return

        session = SessionLocal()
        try:
            if self.id_assemblage:
                a = session.get(Assemblage, self.id_assemblage)
                if a:
                    a.reference   = self.ref_input.text().strip() or None
                    a.nom         = nom
                    a.description = self.desc_input.text().strip() or None
                    a.plan_url    = self.plan_input.text().strip() or None
            else:
                a = Assemblage(
                    reference=self.ref_input.text().strip() or None,
                    nom=nom,
                    description=self.desc_input.text().strip() or None,
                    plan_url=self.plan_input.text().strip() or None
                )
                session.add(a)
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class AjouterElementDialog(QDialog):
    def __init__(self, id_assemblage: int, element_type: str, parent=None):
        super().__init__(parent)
        self.id_assemblage = id_assemblage
        self.element_type  = element_type
        titles = {
            "component": "Add Component",
            "external":  "Add External Part",
            "service":   "Add Service",
        }
        self.setWindowTitle(titles.get(element_type, "Add Element"))
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Liste selon le type
        labels = {
            "component": "Select Component :",
            "external":  "Select External Part :",
            "service":   "Select Service :",
        }
        lbl = QLabel(labels.get(self.element_type, "Select :"))
        lbl.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl)

        self.item_list = QListWidget()
        self.item_list.setFixedHeight(150)
        self.item_list.setStyleSheet(list_style())
        self._charger_elements()
        layout.addWidget(self.item_list)

        form = QFormLayout()
        self.quantite_spin = QDoubleSpinBox()
        self.quantite_spin.setMaximum(99999)

        if self.element_type == "component":
            self.quantite_spin.setMinimum(0.001)
            self.quantite_spin.setDecimals(3)
            self.quantite_spin.setValue(1.0)
            qty_label = "Quantity :"
        elif self.element_type == "external":
            self.quantite_spin.setMinimum(1)
            self.quantite_spin.setDecimals(0)
            self.quantite_spin.setValue(1)
            qty_label = "Quantity (pcs) :"
        elif self.element_type == "service":
            self.quantite_spin.setMinimum(0.01)
            self.quantite_spin.setDecimals(2)
            self.quantite_spin.setValue(1.0)
            qty_label = "Qty / Time (h) :"

        form.addRow(qty_label, self.quantite_spin)
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

    def _charger_elements(self):
        session = SessionLocal()
        try:
            if self.element_type == "component":
                elements = session.query(Composant).order_by(Composant.nom).all()
                for e in elements:
                    item = QListWidgetItem(
                        f"{e.nom} ({e.reference or '—'})"
                    )
                    item.setData(Qt.UserRole, e.id_composant)
                    self.item_list.addItem(item)
            elif self.element_type == "external":
                elements = session.query(PieceExterne).order_by(PieceExterne.nom).all()
                for e in elements:
                    item = QListWidgetItem(
                        f"{e.nom} ({e.fournisseur or '—'}) — {e.prix_unitaire or '—'} €"
                    )
                    item.setData(Qt.UserRole, e.id_piece_externe)
                    self.item_list.addItem(item)
            elif self.element_type == "service":
                elements = session.query(Service).order_by(Service.nom).all()
                for e in elements:
                    item = QListWidgetItem(f"{e.nom} ({e.type_service})")
                    item.setData(Qt.UserRole, e.id_service)
                    self.item_list.addItem(item)
        finally:
            session.close()

    def _valider(self):
        selected = self.item_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an element.")
            return

        session = SessionLocal()
        try:
            if self.element_type == "component":
                n = Nomenclature(
                    id_parent=self.id_assemblage,
                    type_parent="assemblage",
                    id_composant=selected.data(Qt.UserRole),
                    id_service=None,
                    id_piece_externe=None,
                    quantite=self.quantite_spin.value()
                )
            elif self.element_type == "external":
                n = Nomenclature(
                    id_parent=self.id_assemblage,
                    type_parent="assemblage",
                    id_composant=None,
                    id_piece_externe=selected.data(Qt.UserRole),
                    id_service=None,
                    quantite=self.quantite_spin.value()
                )
            elif self.element_type == "service":
                n = Nomenclature(
                    id_parent=self.id_assemblage,
                    type_parent="assemblage",
                    id_composant=None,
                    id_piece_externe=None,
                    id_service=selected.data(Qt.UserRole),
                    quantite=self.quantite_spin.value()
                )

            session.add(n)
            session.commit()
            from services.cout_service import recalculer_assemblage
            recalculer_assemblage(session, self.id_assemblage)
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


# ── NOUVELLE CLASSE ─────────────────────────────────────────────────────────
class ModifierNomenclatureDialog(QDialog):
    """
    Dialog pour modifier la quantité d'un élément dans la nomenclature (BOM).
    Reçoit le dict 'data' stocké dans UserRole de la colonne 0 de nom_table,
    et recalcule automatiquement le prix de revient de l'assemblage après sauvegarde.
    """
    def __init__(self, data: dict, id_assemblage: int, parent=None):
        super().__init__(parent)
        self.data          = data   # {id_composant, id_service, id_piece_externe, id_parent, type_parent}
        self.id_assemblage = id_assemblage
        self._prix_unitaire = 0.0
        self.setWindowTitle("Edit BOM Quantity")
        self.setMinimumWidth(380)
        self._build_ui()
        self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet(
            "color: #2c3e50; font-weight: bold; font-size: 11px;"
            "padding: 6px; background-color: #ecf0f1; border-radius: 4px;"
        )
        layout.addWidget(self.lbl_info)

        form = QFormLayout()

        self.qte_spin = QDoubleSpinBox()
        self.qte_spin.setMinimum(0.001)
        self.qte_spin.setMaximum(99999.0)
        self.qte_spin.setDecimals(3)
        self.qte_spin.setSingleStep(1.0)
        self.qte_spin.setFixedHeight(32)
        self.qte_spin.setStyleSheet("""
            QDoubleSpinBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QDoubleSpinBox:focus { border-color: #3498db; }
        """)
        form.addRow("Quantity :", self.qte_spin)

        self.lbl_prix = QLabel("—")
        self.lbl_prix.setStyleSheet("color: #27ae60; font-size: 11px;")
        form.addRow("Estimated cost :", self.lbl_prix)

        layout.addLayout(form)

        self.qte_spin.valueChanged.connect(self._maj_prix_estime)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾 Save & Recalculate")
        btn_save.setFixedHeight(34)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 12px;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        btn_save.clicked.connect(self._valider)

        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _charger(self):
        """Charge la ligne de nomenclature existante et pré-remplit la quantité."""
        session = SessionLocal()
        try:
            q = session.query(Nomenclature).filter_by(
                id_parent=self.data["id_parent"],
                type_parent=self.data["type_parent"],
            )
            if self.data["id_composant"] is not None:
                q = q.filter_by(id_composant=self.data["id_composant"])
            elif self.data["id_piece_externe"] is not None:
                q = q.filter_by(id_piece_externe=self.data["id_piece_externe"])
            elif self.data["id_service"] is not None:
                q = q.filter_by(id_service=self.data["id_service"])
            n = q.first()
            if not n:
                return

            # Label et prix unitaire selon le type d'élément
            if n.composant:
                label = n.composant.nom
                self._prix_unitaire = float(n.composant.prix_revient or 0)
            elif n.piece_externe:
                label = f"[EXT] {n.piece_externe.nom}"
                self._prix_unitaire = float(n.piece_externe.prix_unitaire or 0)
            elif n.service:
                label = f"[SRV] {n.service.nom}"
                self._prix_unitaire = float(n.service.cout_fixe or 0)
            else:
                label = "Unknown"
                self._prix_unitaire = 0.0

            self.lbl_info.setText(f"Element : {label}")
            self.qte_spin.setValue(float(n.quantite))
            self._maj_prix_estime(float(n.quantite))
        finally:
            session.close()

    def _maj_prix_estime(self, qte: float):
        """Met à jour l'estimation de coût en temps réel."""
        from services.cout_service import format_prix
        cout = self._prix_unitaire * qte
        self.lbl_prix.setText(
            f"{format_prix(self._prix_unitaire)} × {qte:.3f} = {format_prix(cout)}"
        )

    def _valider(self):
        """Sauvegarde la nouvelle quantité et recalcule le prix de revient."""
        from services.cout_service import recalculer_assemblage, format_prix

        nouvelle_qte = self.qte_spin.value()
        if nouvelle_qte <= 0:
            QMessageBox.warning(self, "Warning", "Quantity must be greater than 0.")
            return

        session = SessionLocal()
        try:
            q = session.query(Nomenclature).filter_by(
                id_parent=self.data["id_parent"],
                type_parent=self.data["type_parent"],
            )
            if self.data["id_composant"] is not None:
                q = q.filter_by(id_composant=self.data["id_composant"])
            elif self.data["id_piece_externe"] is not None:
                q = q.filter_by(id_piece_externe=self.data["id_piece_externe"])
            elif self.data["id_service"] is not None:
                q = q.filter_by(id_service=self.data["id_service"])
            n = q.first()

            if not n:
                QMessageBox.critical(self, "Error", "BOM line not found.")
                return

            n.quantite = nouvelle_qte
            session.flush()

            # Recalcule le prix de revient de l'assemblage
            nouveau_prix = recalculer_assemblage(session, self.id_assemblage)
            session.commit()

            QMessageBox.information(
                self, "Updated",
                f"Quantity updated to {nouvelle_qte:.3f}.\n\n"
                f"Assembly cost price recalculated : {format_prix(nouveau_prix)}"
            )
            self.accept()

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()
# ────────────────────────────────────────────────────────────────────────────