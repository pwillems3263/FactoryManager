"""
ui/views/pointage_view.py
Operator time tracking view — by machine.
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QSplitter,
    QGroupBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from database import SessionLocal
from models.ressource import Machine
from models.production import OperationPlanifiee
from services.pointage_service import (
    pointer_debut_operation,
    pointer_pause_debut,
    pointer_pause_fin,
    pointer_fin_operation,
    get_pauses,
    get_duree_pauses_min,
    get_ops_machine_du_jour,
)


# Copié exactement de composants_view.py
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


STATUT_STYLE = {
    "planifiee": ("#3498db", "Planned"),
    "en_cours":  ("#8e44ad", "In Progress"),
    "terminee":  ("#27ae60", "Completed"),
    "rebutee":   ("#c0392b", "Scrapped"),
}

MACHINE_STATUT_LABEL = {
    "disponible":     "",
    "available":      "",
    "maintenance":    "maintenance",
    "hors_service":   "out of service",
    "out_of_service": "out of service",
}

MOTIFS = ["repas", "panne", "attente_matiere", "formation", "autre"]
MOTIFS_LABEL = {
    "repas":           "Meal break",
    "panne":           "Machine breakdown",
    "attente_matiere": "Waiting for material",
    "formation":       "Training / meeting",
    "autre":           "Other",
}


def _fmt_hhmm(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "—"


def _fmt_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# Stopwatch panel (right side)
# ─────────────────────────────────────────────────────────────────────────────

class ChronoWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._id_op_plan: int | None = None
        self._statut: str = "planifiee"
        self._debut_ts: datetime | None = None
        self._pauses_ms: int = 0
        self._pause_debut_ts: datetime | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.lbl_op_nom = QLabel("Select an operation")
        self.lbl_op_nom.setFont(QFont("Arial", 15, QFont.Bold))
        layout.addWidget(self.lbl_op_nom)

        self.lbl_op_detail = QLabel("")
        self.lbl_op_detail.setStyleSheet("color: #555; font-size: 12px;")
        self.lbl_op_detail.setWordWrap(True)
        layout.addWidget(self.lbl_op_detail)

        self.lbl_statut = QLabel("")
        self.lbl_statut.setFont(QFont("Arial", 11, QFont.Bold))
        layout.addWidget(self.lbl_statut)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ddd;")
        layout.addWidget(sep)

        self.lbl_chrono = QLabel("00:00:00")
        self.lbl_chrono.setFont(QFont("Courier New", 36, QFont.Bold))
        self.lbl_chrono.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_chrono)

        self.lbl_debut_info = QLabel("")
        self.lbl_debut_info.setAlignment(Qt.AlignCenter)
        self.lbl_debut_info.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.lbl_debut_info)

        self.lbl_prevu_info = QLabel("")
        self.lbl_prevu_info.setAlignment(Qt.AlignCenter)
        self.lbl_prevu_info.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.lbl_prevu_info)

        layout.addSpacing(8)

        motif_row = QHBoxLayout()
        motif_row.addWidget(QLabel("Pause reason:"))
        self.combo_motif = QComboBox()
        for k in MOTIFS:
            self.combo_motif.addItem(MOTIFS_LABEL[k], k)
        motif_row.addWidget(self.combo_motif)
        layout.addLayout(motif_row)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self.btn_debut   = QPushButton("▶  Start")
        self.btn_pause   = QPushButton("⏸  Pause")
        self.btn_reprise = QPushButton("▶  Resume")
        self.btn_fin     = QPushButton("■  End")

        for btn, color, hover in [
            (self.btn_debut,   "#27ae60", "#219a52"),
            (self.btn_pause,   "#e67e22", "#d35400"),
            (self.btn_reprise, "#27ae60", "#219a52"),
            (self.btn_fin,     "#c0392b", "#a93226"),
        ]:
            btn.setFixedHeight(44)
            btn.setFont(QFont("Arial", 11, QFont.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}; color: white;
                    border: none; border-radius: 6px; padding: 0 12px;
                }}
                QPushButton:hover {{ background-color: {hover}; }}
                QPushButton:disabled {{ background-color: #bdc3c7; color: #7f8c8d; }}
            """)
            btn_layout.addWidget(btn)

        self.btn_debut.clicked.connect(self._action_debut)
        self.btn_pause.clicked.connect(self._action_pause)
        self.btn_reprise.clicked.connect(self._action_reprise)
        self.btn_fin.clicked.connect(self._action_fin)
        layout.addLayout(btn_layout)

        self.grp_pauses = QGroupBox("Breaks")
        pauses_layout = QVBoxLayout(self.grp_pauses)
        self.lbl_pauses = QLabel("No breaks")
        self.lbl_pauses.setStyleSheet("font-size: 11px; color: #666;")
        self.lbl_pauses.setWordWrap(True)
        pauses_layout.addWidget(self.lbl_pauses)
        layout.addWidget(self.grp_pauses)

        layout.addStretch()

        self.grp_recap = QGroupBox("Summary")
        self.grp_recap.setStyleSheet(
            "QGroupBox { font-size: 12px; color: #27ae60; font-weight: bold; }"
        )
        recap_layout = QVBoxLayout(self.grp_recap)
        self.lbl_recap = QLabel("")
        self.lbl_recap.setStyleSheet("font-size: 12px;")
        self.lbl_recap.setWordWrap(True)
        recap_layout.addWidget(self.lbl_recap)
        self.grp_recap.setVisible(False)
        layout.addWidget(self.grp_recap)

        self._reset_ui()

    def load_operation(self, id_op_plan: int):
        self._timer.stop()
        session = SessionLocal()
        try:
            op = session.get(OperationPlanifiee, id_op_plan)
            if not op:
                return
            self._id_op_plan = id_op_plan
            self._statut = op.statut

            op_nom    = op.operation.description if op.operation else None
            op_nom    = op_nom or f"Op. {id_op_plan}"
            of_code   = op.of.code_of if op.of else "—"
            composant = op.of.composant.nom if op.of and op.of.composant else "—"
            machine   = op.machine.nom if op.machine else (
                op.service.nom if op.service else "—"
            )
            prevu_min = int(
                (op.operation.tps_preparation or 0) +
                (op.operation.tps_execution or 0) * float(op.of.quantite or 1)
            ) if op.operation else 0

            self.lbl_op_nom.setText(op_nom)
            self.lbl_op_detail.setText(
                f"Work order: {of_code}  ·  Component: {composant}  ·  "
                f"Machine: {machine}  ·  Planned: {prevu_min} min"
            )
            self.lbl_prevu_info.setText(f"Planned time: {prevu_min} min")

            color, label = STATUT_STYLE.get(op.statut, ("#888", op.statut))
            self.lbl_statut.setText(label)
            self.lbl_statut.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: bold;"
            )

            pauses = get_pauses(session, id_op_plan)
            self._pauses_ms = sum(
                (p.duree_min or 0) * 60 * 1000
                for p in pauses if p.fin_pause is not None
            )
            pause_ouverte = next((p for p in pauses if p.fin_pause is None), None)

            if op.statut == "en_cours" and op.date_debut_reelle:
                self._debut_ts = op.date_debut_reelle
                if pause_ouverte:
                    self._pause_debut_ts = pause_ouverte.debut_pause
                    self._statut = "pause"
                else:
                    self._pause_debut_ts = None
                    self._timer.start()
            elif op.statut == "terminee" and op.date_debut_reelle:
                self._debut_ts = op.date_debut_reelle
                self._pause_debut_ts = None
            else:
                self._debut_ts = None
                self._pause_debut_ts = None

            if op.date_debut_reelle:
                self.lbl_debut_info.setText(f"Started at {_fmt_hhmm(op.date_debut_reelle)}")
            else:
                self.lbl_debut_info.setText(f"Scheduled at {_fmt_hhmm(op.date_debut)}")

            self._refresh_pauses_label(pauses)
            self._update_buttons()
            self._tick()

            if op.statut == "terminee":
                self._show_recap(op, session)
            else:
                self.grp_recap.setVisible(False)

        finally:
            session.close()

    def _reset_ui(self):
        self._id_op_plan = None
        self._statut = "planifiee"
        self._debut_ts = None
        self._pauses_ms = 0
        self._pause_debut_ts = None
        self.lbl_op_nom.setText("Select an operation")
        self.lbl_op_detail.setText("")
        self.lbl_statut.setText("")
        self.lbl_chrono.setText("00:00:00")
        self.lbl_chrono.setStyleSheet("color: #2c3e50;")
        self.lbl_debut_info.setText("")
        self.lbl_prevu_info.setText("")
        self.lbl_pauses.setText("No breaks")
        self.grp_recap.setVisible(False)
        self._update_buttons()

    def _action_debut(self):
        if not self._id_op_plan:
            return
        session = SessionLocal()
        try:
            pointer_debut_operation(session, self._id_op_plan)
            session.commit()
            self.load_operation(self._id_op_plan)
            self._timer.start()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _action_pause(self):
        if not self._id_op_plan:
            return
        motif = self.combo_motif.currentData()
        session = SessionLocal()
        try:
            pointer_pause_debut(session, self._id_op_plan, motif)
            session.commit()
            self._pause_debut_ts = datetime.now()
            self._statut = "pause"
            self._update_buttons()
            self._refresh_pauses_from_db()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _action_reprise(self):
        if not self._id_op_plan:
            return
        session = SessionLocal()
        try:
            pause = pointer_pause_fin(session, self._id_op_plan)
            session.commit()
            if pause.duree_min:
                self._pauses_ms += pause.duree_min * 60 * 1000
            self._pause_debut_ts = None
            self._statut = "en_cours"
            self._update_buttons()
            self._refresh_pauses_from_db()
            if not self._timer.isActive():
                self._timer.start()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _action_fin(self):
        if not self._id_op_plan or not self._debut_ts:
            return
        now         = datetime.now()
        total_ms    = (now - self._debut_ts).total_seconds() * 1000
        travail_ms  = max(0, total_ms - self._pauses_ms)
        travail_min = max(1, int(travail_ms / 60000))
        tps_prep = max(1, travail_min // 5)
        tps_exec = travail_min - tps_prep

        reply = QMessageBox.question(
            self, "Confirm end",
            f"Working time: {travail_min} min\n"
            f"  Setup time:  {tps_prep} min\n"
            f"  Run time:    {tps_exec} min\n\n"
            f"Confirm end of operation?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        session = SessionLocal()
        try:
            pointer_fin_operation(session, self._id_op_plan, tps_prep, tps_exec)
            session.commit()
            self._timer.stop()
            self._statut = "terminee"
            self.load_operation(self._id_op_plan)
            parent = self.parent()
            if parent and hasattr(parent, '_charger_file'):
                parent._charger_file()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _tick(self):
        if not self._debut_ts:
            return
        now = datetime.now()
        pause_courante_ms = (
            (now - self._pause_debut_ts).total_seconds() * 1000
            if self._pause_debut_ts else 0
        )
        travail_ms = max(
            0,
            (now - self._debut_ts).total_seconds() * 1000
            - self._pauses_ms - pause_courante_ms
        )
        self.lbl_chrono.setText(_fmt_duration(int(travail_ms / 1000)))
        if self._statut == "pause":
            self.lbl_chrono.setStyleSheet("color: #e67e22;")
        elif self._statut == "terminee":
            self.lbl_chrono.setStyleSheet("color: #27ae60;")
        else:
            self.lbl_chrono.setStyleSheet("color: #2c3e50;")

    def _update_buttons(self):
        s      = self._statut
        has_op = self._id_op_plan is not None
        self.btn_debut.setEnabled(has_op and s == "planifiee")
        self.btn_pause.setEnabled(has_op and s == "en_cours")
        self.btn_reprise.setEnabled(has_op and s == "pause")
        self.btn_fin.setEnabled(has_op and s in ("en_cours", "pause"))
        self.combo_motif.setEnabled(has_op and s == "en_cours")

    def _refresh_pauses_from_db(self):
        if not self._id_op_plan:
            return
        session = SessionLocal()
        try:
            pauses = get_pauses(session, self._id_op_plan)
            self._refresh_pauses_label(pauses)
        finally:
            session.close()

    def _refresh_pauses_label(self, pauses: list):
        terminées = [p for p in pauses if p.fin_pause is not None]
        ouverte   = next((p for p in pauses if p.fin_pause is None), None)
        if not terminées and not ouverte:
            self.lbl_pauses.setText("No breaks")
            return
        lignes = []
        for p in terminées:
            motif_lbl = MOTIFS_LABEL.get(p.motif, p.motif or "—")
            lignes.append(
                f"• {_fmt_hhmm(p.debut_pause)} → {_fmt_hhmm(p.fin_pause)} "
                f"({p.duree_min} min) — {motif_lbl}"
            )
        if ouverte:
            motif_lbl = MOTIFS_LABEL.get(ouverte.motif, ouverte.motif or "—")
            lignes.append(f"• {_fmt_hhmm(ouverte.debut_pause)} → ongoing — {motif_lbl}")
        total = sum(p.duree_min or 0 for p in terminées)
        lignes.append(f"\nTotal breaks: {total} min")
        self.lbl_pauses.setText("\n".join(lignes))

    def _show_recap(self, op: OperationPlanifiee, session):
        tps_reel  = (op.tps_prep_reel or 0) + (op.tps_exec_reel or 0)
        tps_prevu = int(
            (op.operation.tps_preparation or 0) +
            (op.operation.tps_execution or 0) * float(op.of.quantite or 1)
        ) if op.operation else 0
        pauses_min = get_duree_pauses_min(session, op.id_op_plan)
        ecart = tps_reel - tps_prevu
        signe = "+" if ecart >= 0 else ""
        self.lbl_recap.setText(
            f"Working time : {tps_reel} min\n"
            f"Total breaks : {pauses_min} min\n"
            f"Planned time : {tps_prevu} min\n"
            f"Variance     : {signe}{ecart:.0f} min"
        )
        self.grp_recap.setVisible(True)


# ─────────────────────────────────────────────────────────────────────────────
# Main view
# ─────────────────────────────────────────────────────────────────────────────

class PointageView(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._id_machine: int | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self._charger_file)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        titre = QLabel("Operator time tracking")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        header.addWidget(QLabel("Machine:"))

        # QListWidget hauteur fixe dans le header — même style que composants_view
        self.machine_list = QListWidget()
        self.machine_list.setFixedHeight(80)
        self.machine_list.setFixedWidth(260)
        self.machine_list.setStyleSheet(list_style())
        self.machine_list.currentRowChanged.connect(self._on_machine_row_changed)
        header.addWidget(self.machine_list)

        btn_refresh = QPushButton("🔄  Refresh")
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border: none; border-radius: 4px; padding: 0 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_refresh.clicked.connect(self._charger_file)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        # Splitter ops / chrono
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)

        lbl_file = QLabel("Today's queue")
        lbl_file.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_file.setStyleSheet("color: #2c3e50;")
        left_layout.addWidget(lbl_file)

        self.lbl_date = QLabel(datetime.now().strftime("%A %d %B %Y"))
        self.lbl_date.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        left_layout.addWidget(self.lbl_date)

        self.list_ops = QListWidget()
        self.list_ops.setStyleSheet(list_style())
        self.list_ops.currentRowChanged.connect(self._on_op_selected)
        left_layout.addWidget(self.list_ops)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        left_layout.addWidget(self.lbl_count)

        self.chrono_widget = ChronoWidget(self)
        self.chrono_widget.setMinimumWidth(460)

        splitter.addWidget(left)
        splitter.addWidget(self.chrono_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

    def _charger_machines(self):
        self.machine_list.blockSignals(True)
        self.machine_list.clear()

        session = SessionLocal()
        try:
            machines = session.query(Machine).order_by(Machine.nom).all()
            for m in machines:
                if not m.nom or not m.nom.strip():
                    continue
                statut_lbl = MACHINE_STATUT_LABEL.get(m.statut or "", "")
                label = f"{m.nom}  [{statut_lbl}]" if statut_lbl else m.nom
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, m.id_machine)
                self.machine_list.addItem(item)
        finally:
            session.close()

        self.machine_list.blockSignals(False)

        if self.machine_list.count() > 0:
            self.machine_list.setCurrentRow(0)

    def _on_machine_row_changed(self, row: int):
        if row < 0:
            return
        item = self.machine_list.item(row)
        if item:
            self._id_machine = item.data(Qt.UserRole)
            self._charger_file()
            self._refresh_timer.start()

    def _charger_file(self):
        if not self._id_machine:
            self.list_ops.clear()
            self.lbl_count.setText("No machine selected")
            return

        self.list_ops.blockSignals(True)
        self.list_ops.clear()

        session = SessionLocal()
        try:
            ops = get_ops_machine_du_jour(session, self._id_machine)

            for op in ops:
                op_nom    = op.operation.description if op.operation else None
                op_nom    = op_nom or f"Op. {op.id_op_plan}"
                of_code   = op.of.code_of if op.of else "—"
                composant = op.of.composant.nom if op.of and op.of.composant else "—"
                heure     = _fmt_hhmm(op.date_debut)
                prevu_min = int(
                    (op.operation.tps_preparation or 0) +
                    (op.operation.tps_execution or 0) * float(op.of.quantite or 1)
                ) if op.operation else 0

                _, statut_lbl = STATUT_STYLE.get(op.statut, ("#888", op.statut))

                texte = (
                    f"{heure}  ·  {op_nom}\n"
                    f"WO: {of_code}  ·  {composant}  ·  {prevu_min} min  ·  {statut_lbl}"
                )

                item = QListWidgetItem(texte)
                item.setData(Qt.UserRole, op.id_op_plan)
                if op.statut == "en_cours":
                    item.setFont(QFont("Arial", 10, QFont.Bold))
                self.list_ops.addItem(item)

            self.lbl_count.setText(
                f"{len(ops)} operation(s) today" if ops
                else "No operations scheduled today"
            )

            selected = False
            for i in range(self.list_ops.count()):
                id_op = self.list_ops.item(i).data(Qt.UserRole)
                op    = session.get(OperationPlanifiee, id_op)
                if op and op.statut == "en_cours":
                    self.list_ops.setCurrentRow(i)
                    selected = True
                    break
            if not selected and self.list_ops.count() > 0:
                self.list_ops.setCurrentRow(0)

        finally:
            session.close()
            self.list_ops.blockSignals(False)

    def _on_op_selected(self, row: int):
        if row < 0:
            self.chrono_widget._reset_ui()
            return
        item = self.list_ops.item(row)
        if item:
            id_op_plan = item.data(Qt.UserRole)
            if id_op_plan:
                self.chrono_widget.load_operation(id_op_plan)