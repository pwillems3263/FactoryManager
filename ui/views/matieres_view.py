from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from database import SessionLocal
from models import MatierePremiere


class MatieresView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_matieres()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("Materials")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Material")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_nouveau.clicked.connect(self._nouvelle_matiere)
        header.addWidget(btn_nouveau)

        btn_modifier = QPushButton("✏ Edit")
        btn_modifier.setFixedHeight(36)
        btn_modifier.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #7d3c98; }
        """)
        btn_modifier.clicked.connect(self._modifier_matiere)
        header.addWidget(btn_modifier)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Unit", "Current Stock",
            "Density (kg/cm³)", "Price (€/kg)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
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
        """)
        layout.addWidget(self.table)

    def _charger_matieres(self):
        session = SessionLocal()
        try:
            matieres = session.query(MatierePremiere).order_by(
                MatierePremiere.nom
            ).all()
            self.table.setRowCount(len(matieres))
            for row, m in enumerate(matieres):
                id_item = QTableWidgetItem(str(m.id_matiere))
                id_item.setData(Qt.UserRole, m.id_matiere)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, QTableWidgetItem(m.nom))
                self.table.setItem(row, 2, QTableWidgetItem(m.unite or ""))
                self.table.setItem(row, 3, QTableWidgetItem(
                    str(m.stock_actuel) if m.stock_actuel is not None else "0"
                ))
                self.table.setItem(row, 4, QTableWidgetItem(
                    str(m.poids_volumique) if m.poids_volumique else "—"
                ))
                self.table.setItem(row, 5, QTableWidgetItem(
                    f"{m.prix_au_kg} €/kg" if m.prix_au_kg else "—"
                ))
        finally:
            session.close()

    def _get_id_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _nouvelle_matiere(self):
        dialog = MatiereDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_matieres()

    def _modifier_matiere(self):
        id_matiere = self._get_id_selectionne()
        if not id_matiere:
            QMessageBox.warning(self, "Warning", "Please select a material.")
            return
        dialog = MatiereDialog(self, id_matiere=id_matiere)
        if dialog.exec() == QDialog.Accepted:
            self._charger_matieres()


class MatiereDialog(QDialog):
    def __init__(self, parent=None, id_matiere=None):
        super().__init__(parent)
        self.id_matiere = id_matiere
        self.setWindowTitle("Edit Material" if id_matiere else "New Material")
        self.setMinimumWidth(380)
        self._build_ui()
        if id_matiere:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Ex: Stainless steel 316L")

        self.unite_input = QLineEdit()
        self.unite_input.setPlaceholderText("Ex: kg, ml, piece")

        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setMinimum(0)
        self.stock_spin.setMaximum(999999)
        self.stock_spin.setDecimals(3)

        self.poids_spin = QDoubleSpinBox()
        self.poids_spin.setMinimum(0)
        self.poids_spin.setMaximum(99)
        self.poids_spin.setDecimals(6)
        self.poids_spin.setSuffix(" kg/cm³")
        self.poids_spin.setSingleStep(0.001)

        self.prix_spin = QDoubleSpinBox()
        self.prix_spin.setMinimum(0)
        self.prix_spin.setMaximum(99999)
        self.prix_spin.setDecimals(4)
        self.prix_spin.setSuffix(" €/kg")

        form.addRow("Name :", self.nom_input)
        form.addRow("Unit :", self.unite_input)
        form.addRow("Current stock :", self.stock_spin)
        form.addRow("Density :", self.poids_spin)
        form.addRow("Price per kg :", self.prix_spin)
        layout.addLayout(form)

        info = QLabel(
            "Density is used to automatically calculate\n"
            "the raw material weight and cost of a component."
        )
        info.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(info)

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
            m = session.get(MatierePremiere, self.id_matiere)
            if m:
                self.nom_input.setText(m.nom or "")
                self.unite_input.setText(m.unite or "")
                self.stock_spin.setValue(
                    float(m.stock_actuel) if m.stock_actuel else 0)
                self.poids_spin.setValue(
                    float(m.poids_volumique) if m.poids_volumique else 0)
                self.prix_spin.setValue(
                    float(m.prix_au_kg) if m.prix_au_kg else 0)
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return
        unite = self.unite_input.text().strip()
        if not unite:
            QMessageBox.warning(self, "Warning", "Unit is required.")
            return

        session = SessionLocal()
        try:
            if self.id_matiere:
                m = session.get(MatierePremiere, self.id_matiere)
            else:
                m = MatierePremiere()
                session.add(m)

            m.nom             = nom
            m.unite           = unite
            m.stock_actuel    = self.stock_spin.value()
            m.poids_volumique = self.poids_spin.value() or None
            m.prix_au_kg      = self.prix_spin.value() or None

            session.commit()
            # Recalcule les composants qui utilisent cette matière
            from services.cout_service import recalculer_composants_par_matiere
            if self.id_matiere:
                recalculer_composants_par_matiere(session, self.id_matiere)
                session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()