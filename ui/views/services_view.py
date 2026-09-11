from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox,
    QListWidget, QListWidgetItem, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import Service


class ServicesView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_services()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("Services")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Service")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_nouveau.clicked.connect(self._nouveau_service)
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
        btn_modifier.clicked.connect(self._modifier_service)
        header.addWidget(btn_modifier)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Product Code", "Name", "Type",
            "Hourly Rate (€/h)", "Fixed Cost (€)", "Description"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
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

    def _charger_services(self):
        session = SessionLocal()
        try:
            services = session.query(Service).order_by(Service.nom).all()
            self.table.setRowCount(len(services))
            for row, s in enumerate(services):
                id_item = QTableWidgetItem(str(s.id_service))
                id_item.setData(Qt.UserRole, s.id_service)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, QTableWidgetItem(s.code_produit or "—"))
                self.table.setItem(row, 2, QTableWidgetItem(s.nom))

                type_item = QTableWidgetItem(s.type_service)
                type_item.setForeground(QColor(
                    "#3498db" if s.type_service == "internal" else "#e67e22"
                ))
                type_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 3, type_item)

                self.table.setItem(row, 4, QTableWidgetItem(
                    f"{s.cout_horaire} €/h" if s.cout_horaire else "—"
                ))
                self.table.setItem(row, 5, QTableWidgetItem(
                    f"{s.cout_fixe} €" if s.cout_fixe else "—"
                ))
                self.table.setItem(row, 6, QTableWidgetItem(
                    s.description or "—"
                ))
        finally:
            session.close()

    def _get_id_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _nouveau_service(self):
        dialog = ServiceDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_services()

    def _modifier_service(self):
        id_service = self._get_id_selectionne()
        if not id_service:
            QMessageBox.warning(self, "Warning", "Please select a service.")
            return
        dialog = ServiceDialog(self, id_service=id_service)
        if dialog.exec() == QDialog.Accepted:
            self._charger_services()


class ServiceDialog(QDialog):
    def __init__(self, parent=None, id_service=None):
        super().__init__(parent)
        self.id_service = id_service
        self.setWindowTitle("Edit Service" if id_service else "New Service")
        self.setMinimumWidth(420)
        self._build_ui()
        if id_service:
            self._charger()

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

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Ex: SRV-ASM-01")

        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Service name")

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description")

        self.cout_horaire_spin = QDoubleSpinBox()
        self.cout_horaire_spin.setMinimum(0)
        self.cout_horaire_spin.setMaximum(99999)
        self.cout_horaire_spin.setDecimals(2)
        self.cout_horaire_spin.setSuffix(" €/h")

        self.cout_fixe_spin = QDoubleSpinBox()
        self.cout_fixe_spin.setMinimum(0)
        self.cout_fixe_spin.setMaximum(99999)
        self.cout_fixe_spin.setDecimals(2)
        self.cout_fixe_spin.setSuffix(" €")

        form.addRow("Product Code :", self.code_input)
        form.addRow("Name :", self.nom_input)
        form.addRow("Description :", self.desc_input)
        form.addRow("Hourly Rate :", self.cout_horaire_spin)
        form.addRow("Fixed Cost :", self.cout_fixe_spin)
        layout.addLayout(form)

        # Type — QListWidget
        lbl_type = QLabel("Service Type :")
        lbl_type.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_type)

        self.type_list = QListWidget()
        self.type_list.setFixedHeight(56)
        self.type_list.setStyleSheet(self._list_style())
        for t in ["internal", "external"]:
            self.type_list.addItem(QListWidgetItem(t))
        self.type_list.setCurrentRow(0)
        layout.addWidget(self.type_list)

        # Comportement planning
        lbl_planning = QLabel("Scheduling :")
        lbl_planning.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_planning)

        self.chk_multi_taches = QCheckBox(
            "Multi-task — multiple operations can run simultaneously on this service\n"
            "(only the routing order is enforced, service availability is ignored)"
        )
        layout.addWidget(self.chk_multi_taches)

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
            s = session.get(Service, self.id_service)
            if s:
                self.code_input.setText(s.code_produit or "")
                self.nom_input.setText(s.nom or "")
                self.desc_input.setText(s.description or "")
                self.cout_horaire_spin.setValue(
                    float(s.cout_horaire) if s.cout_horaire else 0.0)
                self.cout_fixe_spin.setValue(
                    float(s.cout_fixe) if s.cout_fixe else 0.0)
                self.chk_multi_taches.setChecked(bool(s.multi_taches))
                for i in range(self.type_list.count()):
                    if self.type_list.item(i).text() == s.type_service:
                        self.type_list.setCurrentRow(i)
                        break
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return

        type_sel = self.type_list.currentItem()
        if not type_sel:
            QMessageBox.warning(self, "Warning", "Please select a service type.")
            return

        session = SessionLocal()
        try:
            if self.id_service:
                s = session.get(Service, self.id_service)
            else:
                s = Service()
                session.add(s)

            s.code_produit = self.code_input.text().strip() or None
            s.nom          = nom
            s.description  = self.desc_input.text().strip() or None
            s.type_service = type_sel.text()
            s.cout_horaire = self.cout_horaire_spin.value() or None
            s.cout_fixe    = self.cout_fixe_spin.value() or None
            s.multi_taches = self.chk_multi_taches.isChecked()

            session.commit()
            # Recalcule les composants qui utilisent ce service dans leur gamme
            from services.cout_service import recalculer_et_sauvegarder_composant, _recalculer_assemblages_du_composant
            from models import Operation, Gamme
            session.commit()
            if self.id_service:
                from services.cout_service import recalculer_composants_par_service
                recalculer_composants_par_service(session, self.id_service)
                session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()