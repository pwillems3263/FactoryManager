from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QComboBox,
    QCheckBox,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox,
    QSplitter, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import Machine, ArretMachine, TypeMachine


class MachinesView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_machines()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("Machines")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New Machine")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet(self._btn_style("#3498db", "#2980b9"))
        btn_nouveau.clicked.connect(self._nouvelle_machine)
        header.addWidget(btn_nouveau)

        btn_types = QPushButton("⚙ Machine Types")
        btn_types.setFixedHeight(36)
        btn_types.setStyleSheet(self._btn_style("#16a085", "#138d75"))
        btn_types.clicked.connect(self._gerer_types)
        header.addWidget(btn_types)

        btn_modifier = QPushButton("✏ Edit")
        btn_modifier.setFixedHeight(36)
        btn_modifier.setStyleSheet(self._btn_style("#8e44ad", "#7d3c98"))
        btn_modifier.clicked.connect(self._modifier_machine)
        header.addWidget(btn_modifier)

        btn_statut = QPushButton("Change Status")
        btn_statut.setFixedHeight(36)
        btn_statut.setStyleSheet(self._btn_style("#e67e22", "#d35400"))
        btn_statut.clicked.connect(self._changer_statut)
        header.addWidget(btn_statut)

        btn_arret = QPushButton("⚠ New Event")
        btn_arret.setFixedHeight(36)
        btn_arret.setStyleSheet(self._btn_style("#e74c3c", "#c0392b"))
        btn_arret.clicked.connect(self._declarer_arret)
        header.addWidget(btn_arret)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Type", "Capacity (h/d)",
            "Machine Rate (€/h)", "Operator Cost (€/h)",
            "Operator Load (%)", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self._table_style())
        self.table.selectionModel().selectionChanged.connect(self._afficher_arrets)
        splitter.addWidget(self.table)

        arret_widget = QWidget()
        arret_layout = QVBoxLayout(arret_widget)
        arret_layout.setContentsMargins(0, 10, 0, 0)

        arret_header = QHBoxLayout()
        self.arret_titre = QLabel("Event History")
        self.arret_titre.setFont(QFont("Arial", 12, QFont.Bold))
        arret_header.addWidget(self.arret_titre)
        arret_header.addStretch()

        btn_cloture = QPushButton("✓ Close Event")
        btn_cloture.setFixedHeight(30)
        btn_cloture.setStyleSheet(self._btn_style("#27ae60", "#219a52"))
        btn_cloture.clicked.connect(self._cloturer_arret)
        arret_header.addWidget(btn_cloture)
        arret_layout.addLayout(arret_header)

        self.arret_table = QTableWidget()
        self.arret_table.setColumnCount(5)
        self.arret_table.setHorizontalHeaderLabels([
            "ID", "Event Type", "Start", "End", "Duration (h)"
        ])
        self.arret_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.arret_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.arret_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.arret_table.setAlternatingRowColors(True)
        self.arret_table.setStyleSheet(self._table_style())
        arret_layout.addWidget(self.arret_table)
        splitter.addWidget(arret_widget)
        splitter.setSizes([300, 250])
        layout.addWidget(splitter)

    def _btn_style(self, color, hover):
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
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

    def _statut_couleur(self, statut):
        return {
            "available":      "#27ae60",
            "maintenance":    "#e67e22",
            "out_of_service": "#e74c3c",
            "disponible":     "#27ae60",
            "hors_service":   "#e74c3c",
        }.get(statut, "#95a5a6")

    def _charger_machines(self):
        session = SessionLocal()
        try:
            machines = session.query(Machine).order_by(Machine.nom).all()
            self.table.setRowCount(len(machines))
            for row, m in enumerate(machines):
                self.table.setItem(row, 0, QTableWidgetItem(str(m.id_machine)))
                self.table.setItem(row, 1, QTableWidgetItem(m.nom))
                self.table.setItem(row, 2, QTableWidgetItem(m.type or ""))
                self.table.setItem(row, 3, QTableWidgetItem(
                    str(m.capacite_h_jour) if m.capacite_h_jour else "—"))
                self.table.setItem(row, 4, QTableWidgetItem(
                    f"{m.tarif_horaire} €/h" if m.tarif_horaire else "—"))
                self.table.setItem(row, 5, QTableWidgetItem(
                    f"{m.cout_operateur} €/h" if m.cout_operateur else "—"))
                self.table.setItem(row, 6, QTableWidgetItem(
                    f"{m.charge_operateur} %" if m.charge_operateur else "—"))
                statut_item = QTableWidgetItem(m.statut)
                statut_item.setForeground(QColor(self._statut_couleur(m.statut)))
                statut_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 7, statut_item)
        finally:
            session.close()

    def _afficher_arrets(self):
        row = self.table.currentRow()
        if row < 0:
            return
        id_machine  = int(self.table.item(row, 0).text())
        nom_machine = self.table.item(row, 1).text()
        self.arret_titre.setText(f"Event History — {nom_machine}")
        self.arret_table.setRowCount(0)

        session = SessionLocal()
        try:
            arrets = session.query(ArretMachine).filter_by(
                id_machine=id_machine
            ).order_by(ArretMachine.date_debut.desc()).all()

            for row_a, a in enumerate(arrets):
                self.arret_table.insertRow(row_a)
                self.arret_table.setItem(row_a, 0, QTableWidgetItem(str(a.id_arret)))
                self.arret_table.setItem(row_a, 1, QTableWidgetItem(a.type_arret))
                self.arret_table.setItem(row_a, 2, QTableWidgetItem(
                    str(a.date_debut)[:16] if a.date_debut else "—"))
                self.arret_table.setItem(row_a, 3, QTableWidgetItem(
                    str(a.date_fin)[:16] if a.date_fin else "In progress"))
                if a.date_fin:
                    duree = (a.date_fin - a.date_debut).total_seconds() / 3600
                    self.arret_table.setItem(row_a, 4, QTableWidgetItem(f"{duree:.2f}"))
                else:
                    item = QTableWidgetItem("In progress")
                    item.setForeground(QColor("#e74c3c"))
                    self.arret_table.setItem(row_a, 4, item)
        finally:
            session.close()

    def _gerer_types(self):
        dialog = GererTypesMachineDialog(self)
        dialog.exec()

    def _nouvelle_machine(self):
        dialog = NouvelleMachineDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_machines()

    def _modifier_machine(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a machine.")
            return
        id_machine = int(self.table.item(row, 0).text())
        dialog = NouvelleMachineDialog(self, id_machine=id_machine)
        if dialog.exec() == QDialog.Accepted:
            self._charger_machines()

    def _changer_statut(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a machine.")
            return
        id_machine = int(self.table.item(row, 0).text())
        dialog = ChangerStatutDialog(id_machine, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_machines()

    def _declarer_arret(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a machine.")
            return
        id_machine = int(self.table.item(row, 0).text())
        dialog = DeclarerArretDialog(id_machine, self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_machines()
            self._afficher_arrets()

    def _cloturer_arret(self):
        row_a = self.arret_table.currentRow()
        if row_a < 0:
            QMessageBox.warning(self, "Warning", "Please select an event.")
            return
        id_arret = int(self.arret_table.item(row_a, 0).text())
        session = SessionLocal()
        try:
            from datetime import datetime
            arret = session.get(ArretMachine, id_arret)
            if arret and not arret.date_fin:
                arret.date_fin = datetime.now()
                machine = session.get(Machine, arret.id_machine)
                if machine:
                    machine.statut = "available"
                session.commit()
                self._charger_machines()
                self._afficher_arrets()
            else:
                QMessageBox.information(self, "Info", "This event is already closed.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class NouvelleMachineDialog(QDialog):
    def __init__(self, parent=None, id_machine=None):
        super().__init__(parent)
        self.id_machine = id_machine
        self.setWindowTitle("Edit Machine" if id_machine else "New Machine")
        self.setMinimumWidth(400)
        self._build_ui()
        if id_machine:
            self._charger_machine()

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

        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Machine name")
        form.addRow("Name :", self.nom_input)
        layout.addLayout(form)

        # Type
        lbl_type = QLabel("Type :")
        lbl_type.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_type)

        type_header = QHBoxLayout()
        type_header.addWidget(lbl_type)
        type_header.addStretch()
        btn_new_type = QPushButton("+ New Type")
        btn_new_type.setFixedHeight(24)
        btn_new_type.setStyleSheet("""
            QPushButton {
                background-color: #16a085; color: white;
                border-radius: 3px; padding: 0 8px; font-size: 11px;
            }
            QPushButton:hover { background-color: #138d75; }
        """)
        btn_new_type.clicked.connect(self._creer_type_rapide)
        type_header.addWidget(btn_new_type)
        layout.addLayout(type_header)

        self.type_list = QListWidget()
        self.type_list.setFixedHeight(110)
        self.type_list.setStyleSheet(self._list_style())
        self._recharger_types()
        layout.addWidget(self.type_list)

        form2 = QFormLayout()

        self.capacite_combo = QComboBox()
        for val in ["8", "16", "24"]:
            self.capacite_combo.addItem(f"{val} h/day", userData=int(val))
        self.capacite_combo.setCurrentIndex(0)  # 8h par défaut
        self.capacite_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: white;
                color: #2c3e50;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #2c3e50;
                selection-background-color: #3498db;
                selection-color: white;
            }
        """)

        self.tarif_spin = QDoubleSpinBox()
        self.tarif_spin.setMinimum(0)
        self.tarif_spin.setMaximum(9999)
        self.tarif_spin.setSuffix(" €/h")
        self.tarif_spin.setDecimals(2)

        self.cout_operateur_spin = QDoubleSpinBox()
        self.cout_operateur_spin.setMinimum(0)
        self.cout_operateur_spin.setMaximum(9999)
        self.cout_operateur_spin.setSuffix(" €/h")
        self.cout_operateur_spin.setDecimals(2)

        self.charge_operateur_spin = QDoubleSpinBox()
        self.charge_operateur_spin.setMinimum(0)
        self.charge_operateur_spin.setMaximum(100)
        self.charge_operateur_spin.setSuffix(" %")
        self.charge_operateur_spin.setDecimals(0)
        self.charge_operateur_spin.setValue(100)

        form2.addRow("Capacity :", self.capacite_combo)
        form2.addRow("Machine rate :", self.tarif_spin)
        form2.addRow("Operator cost :", self.cout_operateur_spin)
        form2.addRow("Operator load :", self.charge_operateur_spin)
        layout.addLayout(form2)
        # Working days + multi-tâches
        lbl_jours = QLabel("Working days :")
        lbl_jours.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_jours)

        jours_layout = QHBoxLayout()
        self.chk_samedi = QCheckBox("Saturday")
        self.chk_dimanche = QCheckBox("Sunday")
        jours_layout.addWidget(self.chk_samedi)
        jours_layout.addWidget(self.chk_dimanche)
        jours_layout.addStretch()
        layout.addLayout(jours_layout)

        # Comportement planning
        lbl_planning = QLabel("Scheduling :")
        lbl_planning.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_planning)

        self.chk_multi_taches = QCheckBox(
            "Multi-task — multiple operations can run simultaneously on this machine\n"
            "(only the routing order is enforced, machine availability is ignored)"
        )
        layout.addWidget(self.chk_multi_taches)

        # Status
        lbl_statut = QLabel("Status :")
        lbl_statut.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_statut)

        self.statut_list = QListWidget()
        self.statut_list.setFixedHeight(84)
        self.statut_list.setStyleSheet(self._list_style())
        for s in ["available", "maintenance", "out_of_service"]:
            self.statut_list.addItem(QListWidgetItem(s))
        self.statut_list.setCurrentRow(0)
        layout.addWidget(self.statut_list)

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

    def _recharger_types(self, select_id=None):
        """Recharge la liste des types depuis la DB."""
        self.type_list.clear()
        session = SessionLocal()
        try:
            types = session.query(TypeMachine).order_by(TypeMachine.nom).all()
            for t in types:
                item = QListWidgetItem(t.nom)
                item.setData(Qt.UserRole, t.id_type)
                self.type_list.addItem(item)
            # Sélectionner par id si fourni
            if select_id is not None:
                for i in range(self.type_list.count()):
                    if self.type_list.item(i).data(Qt.UserRole) == select_id:
                        self.type_list.setCurrentRow(i)
                        return
            if self.type_list.count() > 0:
                self.type_list.setCurrentRow(0)
        finally:
            session.close()

    def _creer_type_rapide(self):
        """Ouvre un mini-dialog pour créer un type à la volée."""
        dialog = NouveauTypeRapideDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._recharger_types(select_id=dialog.new_id)

    def _charger_machine(self):
        session = SessionLocal()
        try:
            machine = session.get(Machine, self.id_machine)
            if machine:
                self.nom_input.setText(machine.nom or "")

                # Sélectionne le type par id_type_machine d'abord, sinon par nom (legacy)
                target_id = machine.id_type_machine
                if target_id:
                    self._recharger_types(select_id=target_id)
                else:
                    # fallback legacy : cherche par nom dans la liste
                    for i in range(self.type_list.count()):
                        if self.type_list.item(i).text() == (machine.type or ""):
                            self.type_list.setCurrentRow(i)
                            break

                cap = int(float(machine.capacite_h_jour)) if machine.capacite_h_jour else 8
                for i in range(self.capacite_combo.count()):
                    if self.capacite_combo.itemData(i) == cap:
                        self.capacite_combo.setCurrentIndex(i)
                        break
                self.chk_samedi.setChecked(bool(machine.travaille_samedi))
                self.chk_dimanche.setChecked(bool(machine.travaille_dimanche))
                self.chk_multi_taches.setChecked(bool(machine.multi_taches))
                self.tarif_spin.setValue(
                    float(machine.tarif_horaire) if machine.tarif_horaire else 0.0)
                self.cout_operateur_spin.setValue(
                    float(machine.cout_operateur) if machine.cout_operateur else 0.0)
                self.charge_operateur_spin.setValue(
                    float(machine.charge_operateur) if machine.charge_operateur else 100.0)

                for i in range(self.statut_list.count()):
                    if self.statut_list.item(i).text() == (machine.statut or ""):
                        self.statut_list.setCurrentRow(i)
                        break
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return

        type_sel   = self.type_list.currentItem()
        statut_sel = self.statut_list.currentItem()
        if not type_sel or not statut_sel:
            QMessageBox.warning(self, "Warning", "Please select a type and status.")
            return

        id_type = type_sel.data(Qt.UserRole)
        nom_type = type_sel.text()

        session = SessionLocal()
        try:
            if self.id_machine:
                machine = session.get(Machine, self.id_machine)
                if machine:
                    # Mémorise l'ancienne capacité avant modification
                    ancienne_capacite = float(machine.capacite_h_jour) if machine.capacite_h_jour else None
                    nouvelle_capacite = self.capacite_combo.currentData()

                    machine.nom              = nom
                    machine.type             = nom_type
                    machine.id_type_machine  = id_type
                    machine.capacite_h_jour  = nouvelle_capacite
                    machine.tarif_horaire    = self.tarif_spin.value() or None
                    machine.cout_operateur   = self.cout_operateur_spin.value() or None
                    machine.charge_operateur = self.charge_operateur_spin.value() or None
                    machine.statut           = statut_sel.text()
                    machine.travaille_samedi = self.chk_samedi.isChecked()
                    machine.travaille_dimanche = self.chk_dimanche.isChecked()
                    machine.multi_taches     = self.chk_multi_taches.isChecked()

                    capacite_changee = (ancienne_capacite != nouvelle_capacite)
            else:
                machine = Machine(
                    nom=nom,
                    type=nom_type,
                    id_type_machine=id_type,
                    capacite_h_jour=self.capacite_combo.currentData(),
                    tarif_horaire=self.tarif_spin.value() or None,
                    cout_operateur=self.cout_operateur_spin.value() or None,
                    charge_operateur=self.charge_operateur_spin.value() or None,
                    statut=statut_sel.text(),
                    multi_taches=self.chk_multi_taches.isChecked()
                )
                session.add(machine)
                capacite_changee = False
            session.commit()
            # Si la capacité change → supprimer les configs shifts explicites
            # pour que le fallback capacite_h_jour reprenne la main
            if self.id_machine and capacite_changee:
                try:
                    from models.production import MachineShiftConfig
                    session.query(MachineShiftConfig).filter_by(
                        id_machine=self.id_machine).delete()
                    session.commit()
                except Exception:
                    pass
            # Recalcule les composants qui utilisent cette machine
            from services.cout_service import recalculer_composants_par_machine
            if self.id_machine:
                recalculer_composants_par_machine(session, self.id_machine)
                session.commit()

            # Si la capacité horaire a changé, proposer de recalculer le planning
            if self.id_machine and capacite_changee:
                reply = QMessageBox.question(
                    self,
                    "Recalculate planning?",
                    f"The daily capacity of this machine has changed "
                    f"({ancienne_capacite or '?'} h → {nouvelle_capacite} h/day).\n\n"
                    f"Do you want to recalculate the planning to apply the new "
                    f"schedule constraints?\n\n"
                    f"(All planned operations will be rescheduled at the earliest possible time.)",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    try:
                        from services.planning_service import recalculer_planning_global
                        from database import SessionLocal as SL
                        s2 = SL()
                        result = recalculer_planning_global(s2)
                        s2.commit()
                        s2.close()
                        QMessageBox.information(
                            self,
                            "Planning recalculated",
                            f"{result['nb_ofs']} production order(s), "
                            f"{result['nb_ops']} operation(s) rescheduled."
                        )
                    except Exception as e2:
                        QMessageBox.warning(
                            self, "Planning error",
                            f"Planning recalculation failed:\n{e2}"
                        )

            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class ChangerStatutDialog(QDialog):
    def __init__(self, id_machine: int, parent=None):
        super().__init__(parent)
        self.id_machine = id_machine
        self.setWindowTitle("Change Status")
        self.setMinimumWidth(300)
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

        lbl = QLabel("New status :")
        lbl.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl)

        self.statut_list = QListWidget()
        self.statut_list.setFixedHeight(84)
        self.statut_list.setStyleSheet(self._list_style())
        for s in ["available", "maintenance", "out_of_service"]:
            self.statut_list.addItem(QListWidgetItem(s))

        session = SessionLocal()
        try:
            machine = session.get(Machine, self.id_machine)
            if machine:
                for i in range(self.statut_list.count()):
                    if self.statut_list.item(i).text() == (machine.statut or ""):
                        self.statut_list.setCurrentRow(i)
                        break
        finally:
            session.close()

        layout.addWidget(self.statut_list)

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
        statut_sel = self.statut_list.currentItem()
        if not statut_sel:
            QMessageBox.warning(self, "Warning", "Please select a status.")
            return
        session = SessionLocal()
        try:
            machine = session.get(Machine, self.id_machine)
            if machine:
                machine.statut = statut_sel.text()
                session.commit()
                # Recalcule les composants qui utilisent cette machine
                from services.cout_service import recalculer_composants_par_machine
                if self.id_machine:
                    recalculer_composants_par_machine(session, self.id_machine)
                    session.commit()
                self.accept()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class DeclarerArretDialog(QDialog):
    def __init__(self, id_machine: int, parent=None):
        super().__init__(parent)
        self.id_machine = id_machine
        self.setWindowTitle("New Machine Event")
        self.setMinimumWidth(380)
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

        lbl = QLabel("Event Type :")
        lbl.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl)

        self.type_list = QListWidget()
        self.type_list.setFixedHeight(90)
        self.type_list.setStyleSheet(self._list_style())
        for t in [
            "breakdown",
            "preventive_maintenance",
            "corrective_maintenance",
            "cleaning"
        ]:
            self.type_list.addItem(QListWidgetItem(t))
        self.type_list.setCurrentRow(0)
        layout.addWidget(self.type_list)

        form = QFormLayout()
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description (optional)")
        form.addRow("Description :", self.desc_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Declare")
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

    def _valider(self):
        type_sel = self.type_list.currentItem()
        if not type_sel:
            QMessageBox.warning(self, "Warning", "Please select an event type.")
            return
        session = SessionLocal()
        try:
            from datetime import datetime
            arret = ArretMachine(
                id_machine=self.id_machine,
                type_arret=type_sel.text(),
                date_debut=datetime.now(),
                description=self.desc_input.text().strip() or None
            )
            session.add(arret)
            machine = session.get(Machine, self.id_machine)
            if machine:
                machine.statut = "maintenance"
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

# ---------------------------------------------------------------------------
# Dialog : création rapide d'un type (depuis NouvelleMachineDialog)
# ---------------------------------------------------------------------------

class NouveauTypeRapideDialog(QDialog):
    """Mini-dialog pour ajouter un type de machine à la volée."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.new_id = None
        self.setWindowTitle("New Machine Type")
        self.setMinimumWidth(320)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.nom_input  = QLineEdit()
        self.nom_input.setPlaceholderText("Type name (e.g. CNC Turning)")
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description (optional)")

        form.addRow("Name :", self.nom_input)
        form.addRow("Description :", self.desc_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Create")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #16a085; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #138d75; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return
        session = SessionLocal()
        try:
            existing = session.query(TypeMachine).filter_by(nom=nom).first()
            if existing:
                QMessageBox.warning(self, "Warning", f'Type "{nom}" already exists.')
                return
            t = TypeMachine(nom=nom, description=self.desc_input.text().strip() or None)
            session.add(t)
            session.commit()
            self.new_id = t.id_type
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Dialog : gestion complète des types de machines
# ---------------------------------------------------------------------------

class GererTypesMachineDialog(QDialog):
    """CRUD complet pour la table TypeMachine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Machine Types")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self._build_ui()
        self._charger_types()

    def _btn_style(self, color, hover):
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                border-radius: 4px; padding: 0 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        titre = QLabel("Machine Types")
        titre.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(titre)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.setFixedHeight(32)
        btn_add.setStyleSheet(self._btn_style("#16a085", "#138d75"))
        btn_add.clicked.connect(self._ajouter)
        toolbar.addWidget(btn_add)

        self.btn_edit = QPushButton("✏ Edit")
        self.btn_edit.setFixedHeight(32)
        self.btn_edit.setStyleSheet(self._btn_style("#8e44ad", "#7d3c98"))
        self.btn_edit.clicked.connect(self._modifier)
        toolbar.addWidget(self.btn_edit)

        self.btn_del = QPushButton("🗑 Delete")
        self.btn_del.setFixedHeight(32)
        self.btn_del.setStyleSheet(self._btn_style("#e74c3c", "#c0392b"))
        self.btn_del.clicked.connect(self._supprimer)
        toolbar.addWidget(self.btn_del)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
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
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #16a085;
                color: white;
            }
        """)
        layout.addWidget(self.table)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def _charger_types(self):
        session = SessionLocal()
        try:
            types = session.query(TypeMachine).order_by(TypeMachine.nom).all()
            self.table.setRowCount(len(types))
            for row, t in enumerate(types):
                self.table.setItem(row, 0, QTableWidgetItem(str(t.id_type)))
                self.table.setItem(row, 1, QTableWidgetItem(t.nom))
                self.table.setItem(row, 2, QTableWidgetItem(t.description or ""))
        finally:
            session.close()

    def _ajouter(self):
        dialog = _EditTypeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_types()

    def _modifier(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a type.")
            return
        id_type = int(self.table.item(row, 0).text())
        dialog = _EditTypeDialog(self, id_type=id_type)
        if dialog.exec() == QDialog.Accepted:
            self._charger_types()

    def _supprimer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a type.")
            return
        id_type  = int(self.table.item(row, 0).text())
        nom_type = self.table.item(row, 1).text()
        reply = QMessageBox.question(
            self, "Confirm",
            f'Delete type "{nom_type}"?\n\nMachines using this type will have their type cleared.',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        session = SessionLocal()
        try:
            # Détache les machines qui utilisent ce type
            machines = session.query(Machine).filter_by(id_type_machine=id_type).all()
            for m in machines:
                m.id_type_machine = None
            t = session.get(TypeMachine, id_type)
            if t:
                session.delete(t)
            session.commit()
            self._charger_types()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class _EditTypeDialog(QDialog):
    """Dialog interne : créer ou modifier un TypeMachine."""

    def __init__(self, parent=None, id_type=None):
        super().__init__(parent)
        self.id_type = id_type
        self.setWindowTitle("Edit Type" if id_type else "New Type")
        self.setMinimumWidth(340)
        self._build_ui()
        if id_type:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.nom_input  = QLineEdit()
        self.nom_input.setPlaceholderText("Type name")
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Description (optional)")

        form.addRow("Name :", self.nom_input)
        form.addRow("Description :", self.desc_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #16a085; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #138d75; }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _charger(self):
        session = SessionLocal()
        try:
            t = session.get(TypeMachine, self.id_type)
            if t:
                self.nom_input.setText(t.nom or "")
                self.desc_input.setText(t.description or "")
        finally:
            session.close()

    def _valider(self):
        nom = self.nom_input.text().strip()
        if not nom:
            QMessageBox.warning(self, "Warning", "Name is required.")
            return
        session = SessionLocal()
        try:
            # Vérifie unicité
            q = session.query(TypeMachine).filter(TypeMachine.nom == nom)
            if self.id_type:
                q = q.filter(TypeMachine.id_type != self.id_type)
            if q.first():
                QMessageBox.warning(self, "Warning", f'Type "{nom}" already exists.')
                return
            if self.id_type:
                t = session.get(TypeMachine, self.id_type)
                if t:
                    t.nom = nom
                    t.description = self.desc_input.text().strip() or None
            else:
                t = TypeMachine(nom=nom, description=self.desc_input.text().strip() or None)
                session.add(t)
            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()