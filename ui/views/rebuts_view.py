from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import Rebut, OrdreFabrication, OperationPlanifiee
from services.rebut_service import constater_rebut


class RebutsView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_rebuts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("Scrap")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Scrap Report")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_nouveau.clicked.connect(self._nouveau_rebut)
        header.addWidget(btn_nouveau)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Code OF", "PO", "Component",
            "Operation", "Qty Scrapped", "Cause", "Decision"
        ])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
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

    def _charger_rebuts(self):
        session = SessionLocal()
        try:
            rebuts = session.query(Rebut).order_by(
                Rebut.date_constat.desc()
            ).all()
            self.table.setRowCount(len(rebuts))
            for row, r in enumerate(rebuts):
                composant_nom = "—"
                if r.of and r.of.composant:
                    composant_nom = r.of.composant.nom

                op_desc = "—"
                if r.operation_planifiee and r.operation_planifiee.operation:
                    op_desc = r.operation_planifiee.operation.description or "—"

                self.table.setItem(row, 0, QTableWidgetItem(str(r.id_rebut)))
                self.table.setItem(row, 1, QTableWidgetItem(
                    r.of.code_of if r.of and r.of.code_of else "—"))
                self.table.setItem(row, 2, QTableWidgetItem(str(r.id_of)))
                self.table.setItem(row, 3, QTableWidgetItem(composant_nom))
                self.table.setItem(row, 4, QTableWidgetItem(op_desc))
                self.table.setItem(row, 5, QTableWidgetItem(
                    str(r.quantite_rebutee)))
                self.table.setItem(row, 6, QTableWidgetItem(r.cause or "—"))

                decision_labels = {
                    "rebut_definitif": "Definitive Scrap",
                    "retouche":        "Rework",
                }
                decision_txt = decision_labels.get(r.decision, r.decision)
                decision_item = QTableWidgetItem(decision_txt)
                couleur = (
                    "#e74c3c" if r.decision == "rebut_definitif"
                    else "#e67e22"
                )
                decision_item.setForeground(QColor(couleur))
                decision_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 7, decision_item)
        finally:
            session.close()

    def _nouveau_rebut(self):
        dialog = NouveauRebutDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_rebuts()


class NouveauRebutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Scrap Report")
        self.setMinimumWidth(450)
        self._build_ui()

    def _list_style(self):
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

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # OF selection
        lbl_of = QLabel("Production Order :")
        lbl_of.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_of)

        self.of_list = QListWidget()
        self.of_list.setFixedHeight(90)
        self.of_list.setStyleSheet(self._list_style())
        self._charger_ofs()
        self.of_list.currentRowChanged.connect(self._on_of_changed)
        layout.addWidget(self.of_list)

        # Operation selection
        lbl_op = QLabel("Operation :")
        lbl_op.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_op)

        self.op_list = QListWidget()
        self.op_list.setFixedHeight(90)
        self.op_list.setStyleSheet(self._list_style())
        layout.addWidget(self.op_list)

        # Decision
        lbl_dec = QLabel("Decision :")
        lbl_dec.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_dec)

        self.decision_list = QListWidget()
        self.decision_list.setFixedHeight(56)
        self.decision_list.setStyleSheet(self._list_style())
        item1 = QListWidgetItem("Definitive Scrap")
        item1.setData(Qt.UserRole, "rebut_definitif")
        item2 = QListWidgetItem("Rework")
        item2.setData(Qt.UserRole, "retouche")
        self.decision_list.addItem(item1)
        self.decision_list.addItem(item2)
        self.decision_list.setCurrentRow(0)
        layout.addWidget(self.decision_list)

        form2 = QFormLayout()

        self.quantite_spin = QDoubleSpinBox()
        self.quantite_spin.setMinimum(0.001)
        self.quantite_spin.setMaximum(99999)
        self.quantite_spin.setDecimals(3)
        self.quantite_spin.setValue(1.0)

        self.cause_input = QLineEdit()
        self.cause_input.setPlaceholderText("Describe the cause of scrap...")

        form2.addRow("Quantity scrapped :", self.quantite_spin)
        form2.addRow("Cause :", self.cause_input)
        layout.addLayout(form2)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _charger_ofs(self):
        session = SessionLocal()
        try:
            ofs = session.query(OrdreFabrication).filter(
                OrdreFabrication.statut.in_(["planifie", "en_cours"])
            ).order_by(OrdreFabrication.id_of).all()
            for of in ofs:
                nom = of.composant.nom if of.composant else "—"
                item = QListWidgetItem(
                    f"{of.code_of or of.id_of} — {nom}"
                )
                item.setData(Qt.UserRole, of.id_of)
                self.of_list.addItem(item)
        finally:
            session.close()

    def _on_of_changed(self):
        self.op_list.clear()
        item = self.of_list.currentItem()
        if not item:
            return
        id_of = item.data(Qt.UserRole)

        session = SessionLocal()
        try:
            ops = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.id_of == id_of,
                OperationPlanifiee.statut.in_(["planifiee", "en_cours"])
            ).order_by(OperationPlanifiee.date_debut).all()

            for op in ops:
                desc = op.operation.description if op.operation else "—"
                op_item = QListWidgetItem(
                    f"Op {op.operation.ordre if op.operation else '?'} — {desc}"
                )
                op_item.setData(Qt.UserRole, op.id_op_plan)
                self.op_list.addItem(op_item)
        finally:
            session.close()

    def _valider(self):
        of_item  = self.of_list.currentItem()
        op_item  = self.op_list.currentItem()
        dec_item = self.decision_list.currentItem()

        if not of_item:
            QMessageBox.warning(self, "Warning",
                                "Please select a Production Order.")
            return
        if not op_item:
            QMessageBox.warning(self, "Warning",
                                "Please select an operation.")
            return
        if not dec_item:
            QMessageBox.warning(self, "Warning",
                                "Please select a decision.")
            return

        cause = self.cause_input.text().strip()
        if not cause:
            QMessageBox.warning(self, "Warning", "Cause is required.")
            return

        session = SessionLocal()
        try:
            constater_rebut(
                session=session,
                id_of=of_item.data(Qt.UserRole),
                id_op_plan=op_item.data(Qt.UserRole),
                quantite_rebutee=self.quantite_spin.value(),
                cause=cause,
                decision=dec_item.data(Qt.UserRole)
            )
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()