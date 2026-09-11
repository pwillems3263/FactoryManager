from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from database import SessionLocal
from models import PieceExterne


class PiecesExternesView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_pieces()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("External Parts")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Part")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_nouveau.clicked.connect(self._nouvelle_piece)
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
        btn_modifier.clicked.connect(self._modifier_piece)
        header.addWidget(btn_modifier)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Product Code", "Name",
            "Supplier", "Unit Price (€)", "Description"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
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

    def _charger_pieces(self):
        session = SessionLocal()
        try:
            pieces = session.query(PieceExterne).order_by(
                PieceExterne.nom
            ).all()
            self.table.setRowCount(len(pieces))
            for row, p in enumerate(pieces):
                id_item = QTableWidgetItem(str(p.id_piece_externe))
                id_item.setData(Qt.UserRole, p.id_piece_externe)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, QTableWidgetItem(
                    p.code_produit or "—"))
                self.table.setItem(row, 2, QTableWidgetItem(p.nom))
                self.table.setItem(row, 3, QTableWidgetItem(
                    p.fournisseur or "—"))
                self.table.setItem(row, 4, QTableWidgetItem(
                    f"{p.prix_unitaire} €" if p.prix_unitaire else "—"))
                self.table.setItem(row, 5, QTableWidgetItem(
                    p.description or "—"))
        finally:
            session.close()

    def _get_id_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _nouvelle_piece(self):
        dialog = PieceExterneDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_pieces()

    def _modifier_piece(self):
        id_piece = self._get_id_selectionne()
        if not id_piece:
            QMessageBox.warning(self, "Warning", "Please select a part.")
            return
        dialog = PieceExterneDialog(self, id_piece_externe=id_piece)
        if dialog.exec() == QDialog.Accepted:
            self._charger_pieces()


class PieceExterneDialog(QDialog):
    def __init__(self, parent=None, id_piece_externe=None):
        super().__init__(parent)
        self.id_piece_externe = id_piece_externe
        self.setWindowTitle(
            "Edit External Part" if id_piece_externe else "New External Part"
        )
        self.setMinimumWidth(420)
        self._build_ui()
        if id_piece_externe:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Ex: EXT-BRG-001")

        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Part name")

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description")

        self.fournisseur_input = QLineEdit()
        self.fournisseur_input.setPlaceholderText("Supplier name")

        self.prix_spin = QDoubleSpinBox()
        self.prix_spin.setMinimum(0)
        self.prix_spin.setMaximum(999999)
        self.prix_spin.setDecimals(4)
        self.prix_spin.setSuffix(" €")

        form.addRow("Product Code :", self.code_input)
        form.addRow("Name :", self.nom_input)
        form.addRow("Description :", self.desc_input)
        form.addRow("Supplier :", self.fournisseur_input)
        form.addRow("Unit Price :", self.prix_spin)
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
            p = session.get(PieceExterne, self.id_piece_externe)
            if p:
                self.code_input.setText(p.code_produit or "")
                self.nom_input.setText(p.nom or "")
                self.desc_input.setText(p.description or "")
                self.fournisseur_input.setText(p.fournisseur or "")
                self.prix_spin.setValue(
                    float(p.prix_unitaire) if p.prix_unitaire else 0.0)
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return

        session = SessionLocal()
        try:
            if self.id_piece_externe:
                p = session.get(PieceExterne, self.id_piece_externe)
            else:
                p = PieceExterne()
                session.add(p)

            p.code_produit  = self.code_input.text().strip() or None
            p.nom           = nom
            p.description   = self.desc_input.text().strip() or None
            p.fournisseur   = self.fournisseur_input.text().strip() or None
            p.prix_unitaire = self.prix_spin.value() or None

            session.commit()
            # Recalcule les composants qui utilisent cette pièce externe dans leur gamme
            from services.cout_service import recalculer_et_sauvegarder_composant, _recalculer_assemblages_du_composant
            from models import Operation
            session.commit()
            if self.id_piece_externe:
                from services.cout_service import recalculer_composants_par_piece_externe
                recalculer_composants_par_piece_externe(session, self.id_piece_externe)
                session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()