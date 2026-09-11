from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QComboBox, QToolTip,
    QDialog, QMessageBox, QFormLayout,
    QDateTimeEdit, QSpinBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QColor
from PySide6.QtCore import QDateTime
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QCursor, QPixmap
)
from database import SessionLocal
from models import Machine, OperationPlanifiee
from services.planning_service import valider_deplacement, deplacer_operation, recalculer_planning_global
from services.planning_service import SHIFTS_DEF
from datetime import datetime, timedelta


COULEURS_STATUT = {
    "planifiee": QColor("#3498db"),
    "en_cours":  QColor("#e67e22"),
    "terminee":  QColor("#27ae60"),
    "rebutee":   QColor("#e74c3c"),
}

ROW_HEIGHT    = 50
HEADER_HEIGHT = 80  # Two rows: top=dates (40px), bottom=hours (40px)
DAY_ROW_H = 40
HOUR_ROW_H = 40
LABEL_WIDTH   = 160

PERIODES = {
    "1 day":     24,
    "3 days":    72,
    "1 week":    168,
    "2 weeks":   336,
    "1 month":   720,
}

# Interval de grille (en heures) par échelle
GRID_STEP = {
    "1 day":    1,
    "3 days":   3,
    "1 week":   6,
    "2 weeks":  12,
    "1 month":  24,
}

# 3x8h shifts: (start_hour, end_hour, label)
SHIFTS = [
    (6,  14, "6h–14h"),
    (14, 22, "14h–22h"),
    (22,  6, "22h–6h"),   # crosses midnight → end is next day
]
# Background colors alternating per shift
SHIFT_COLORS = [
    QColor("#f0f4f8"),   # shift 1  — light blue-grey
    QColor("#e8ecf0"),   # shift 2  — slightly darker
    QColor("#dde4ec"),   # shift 3  — night shift, darkest
]
SHIFT_HEADER_COLORS = [
    QColor("#2c3e50"),
    QColor("#34495e"),
    QColor("#253545"),
]


class GanttWidget(QWidget):
    def __init__(self, machines, operations, date_debut, date_fin,
                 px_per_hour=80, on_deplacement=None):
        super().__init__()
        self.machines      = machines
        self.operations    = operations
        self.date_debut    = date_debut
        self.date_fin      = date_fin
        self.px_per_hour   = px_per_hour
        self.on_deplacement = on_deplacement  # callback après déplacement
        self.total_hours   = max(
            (date_fin - date_debut).total_seconds() / 3600, 1
        )
        self._hovered_op   = None
        self._selected_op         = None
        self._selected_composant_id = None

        # Drag & drop
        self._dragging       = False
        self._drag_pending   = False
        self._drag_start_pos = None
        self._drag_op        = None
        self._drag_offset_x  = 0
        self._drag_current_x = 0
        self._drag_machine_idx = None

        self.setMouseTracking(True)
        self._update_size()

    def set_px_per_hour(self, px_per_hour, date_debut, date_fin):
        self.px_per_hour = px_per_hour
        self.date_debut  = date_debut
        self.date_fin    = date_fin
        self.total_hours = max(
            (date_fin - date_debut).total_seconds() / 3600, 1
        )
        self._update_size()
        self.update()

    def _update_size(self):
        w = int(LABEL_WIDTH + self.total_hours * self.px_per_hour) + 40
        h = HEADER_HEIGHT + len(self.machines) * ROW_HEIGHT + 20
        self.setMinimumSize(w, h)
        self.resize(w, h)

    def _op_rect(self, op, row_y):
        """Premier segment visible — utilisé pour hover/clic."""
        segs = self._op_segments(op, row_y)
        return segs[0] if segs else QRect()

    def _op_hit(self, op, row_y, pos):
        """Retourne True si pos est dans l'un des segments de l'opération."""
        for rect in self._op_segments(op, row_y):
            if rect.contains(pos):
                return True
        return False

    def _op_segments(self, op, row_y, machine=None):
        """
        Retourne la liste des QRect à dessiner pour cette opération,
        en découpant selon la plage horaire de la machine (si définie).
        machine = dict depuis self.machines avec clé 'capacite_h_jour'.
        """
        from datetime import time as dtime

        date_debut = op["date_debut"]
        date_fin   = op["date_fin"]

        # Récupère la capacité depuis le dict machine passé ou en cherchant dans self.machines
        cap = None
        if machine is not None:
            cap = machine.get("capacite_h_jour")
        else:
            for m in self.machines:
                if m.get("row_id") == op.get("row_id"):
                    cap = m.get("capacite_h_jour")
                    break

        # Pas de plage si service, machine 24h ou cap non définie
        if cap is None or float(cap) >= 24 or op.get("row_id", "").startswith("s_"):
            rect = self._op_rect_raw(date_debut, date_fin, row_y)
            return [rect] if rect.width() > 0 else []

        cap = float(cap)
        if cap <= 8:
            h_debut, h_fin = dtime(6, 0), dtime(14, 0)
        else:  # 16h
            h_debut, h_fin = dtime(6, 0), dtime(22, 0)

        segments = []
        cur = date_debut
        while cur < date_fin:
            # Début de plage ce jour
            plage_start = datetime.combine(cur.date(), h_debut)
            plage_end   = datetime.combine(cur.date(), h_fin)

            seg_start = max(cur, plage_start)
            seg_end   = min(date_fin, plage_end)

            if seg_start < seg_end:
                rect = self._op_rect_raw(seg_start, seg_end, row_y)
                if rect.width() > 2:
                    segments.append(rect)

            # Passer au lendemain
            cur = datetime.combine(cur.date() + timedelta(days=1), h_debut)

        return segments if segments else [self._op_rect_raw(date_debut, date_fin, row_y)]

    def _op_rect_raw(self, date_debut, date_fin, row_y):
        """Convertit deux datetime en QRect sans tenir compte des plages."""
        x_start = int(
            LABEL_WIDTH +
            (date_debut - self.date_debut).total_seconds()
            / 3600 * self.px_per_hour
        )
        x_end = int(
            LABEL_WIDTH +
            (date_fin - self.date_debut).total_seconds()
            / 3600 * self.px_per_hour
        )
        x_start = max(x_start, LABEL_WIDTH)
        x_end   = max(x_end, x_start + 6)
        return QRect(x_start, row_y + 5, x_end - x_start, ROW_HEIGHT - 10)

    def _x_to_datetime(self, x):
        """Convertit une position X en datetime."""
        heures = (x - LABEL_WIDTH) / self.px_per_hour
        return self.date_debut + timedelta(hours=heures)

    def _y_to_machine_idx(self, y):
        """Retourne l'index de la machine à la position Y."""
        idx = (y - HEADER_HEIGHT) // ROW_HEIGHT
        if 0 <= idx < len(self.machines):
            return idx
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        pos = event.position().toPoint()

        # Clic sur une tâche → prépare drag, dialog s'ouvrira au release
        for i, machine in enumerate(self.machines):
            row_y = HEADER_HEIGHT + i * ROW_HEIGHT
            for op in self.operations:
                if op.get("row_id") != machine.get("row_id"):
                    continue
                segs = self._op_segments(op, row_y)
                if any(r.contains(pos) for r in segs):
                    rect = segs[0]
                    self._selected_op           = op
                    self._selected_composant_id = op.get("id_of")
                    self._drag_pending          = True
                    self._dragging              = False
                    self._drag_op               = op
                    self._drag_offset_x         = pos.x() - rect.x()
                    self._drag_current_x        = rect.x()
                    self._drag_machine_idx      = i
                    self._drag_start_pos        = pos
                    self.update()
                    return

        # Clic dans le vide → désélectionne
        self._selected_op           = None
        self._selected_composant_id = None
        self._hovered_op            = None
        self._drag_pending          = False
        self._dragging              = False
        self._drag_op               = None
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()

        # Double-clic sur le label machine → liste des jobs
        if pos.x() < LABEL_WIDTH:
            for i, machine in enumerate(self.machines):
                row_y = HEADER_HEIGHT + i * ROW_HEIGHT
                if row_y <= pos.y() < row_y + ROW_HEIGHT:
                    self._open_machine_jobs(machine)
                    return

        # Double-clic sur une tâche → dialog détail
        for i, machine in enumerate(self.machines):
            row_y = HEADER_HEIGHT + i * ROW_HEIGHT
            for op in self.operations:
                if op.get("row_id") != machine.get("row_id"):
                    continue
                if self._op_hit(op, row_y, pos):
                    self._open_op_detail(op)
                    return

    def _open_machine_jobs(self, machine):
        pv = self.parent()
        if hasattr(pv, '_dialog_open'):
            pv._dialog_open = True
        ops = [op for op in self.operations if op.get("row_id") == machine.get("row_id")]
        ops.sort(key=lambda o: o.get("date_debut") or "")
        dlg = MachineJobsDialog(machine, ops, self,
                                on_reload=self.on_deplacement)
        dlg.exec()
        if hasattr(pv, '_dialog_open'):
            pv._dialog_open = False

    def _open_op_detail(self, op):
        # Get PlanningView to block auto-refresh while dialog is open
        pv = self.parent()
        if hasattr(pv, '_dialog_open'):
            pv._dialog_open = True
        dlg = OperationDetailDialog(op["id_op_plan"], self)
        if dlg.exec():
            if hasattr(pv, '_dialog_open'):
                pv._dialog_open = False
            if self.on_deplacement:
                self.on_deplacement()
        else:
            if hasattr(pv, '_dialog_open'):
                pv._dialog_open = False

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        # Démarre le drag réel si souris a bougé de plus de 8px
        if self._drag_pending and self._drag_op and not self._dragging:
            dx = abs(pos.x() - self._drag_start_pos.x())
            dy = abs(pos.y() - self._drag_start_pos.y())
            if dx > 8 or dy > 8:
                self._dragging = True
                self._drag_pending = False
                self.setCursor(Qt.ClosedHandCursor)

        if self._dragging and self._drag_op:
            self._drag_current_x = pos.x() - self._drag_offset_x
            self._drag_machine_idx = self._y_to_machine_idx(pos.y())
            self.update()
            return

        # Hover tooltip
        found = None
        for i, machine in enumerate(self.machines):
            row_y = HEADER_HEIGHT + i * ROW_HEIGHT
            for op in self.operations:
                if op.get("row_id") != machine.get("row_id"):
                    continue
                if self._op_hit(op, row_y, pos):
                    found = op
                    break
            if found:
                break

        if found != self._hovered_op:
            self._hovered_op = found
            self.update()

        if found and not self._dragging:
            date_debut_reelle = found.get("date_debut_reelle")
            if date_debut_reelle:
                debut = date_debut_reelle.strftime("%d/%m %H:%M") + " ✓"
            else:
                debut = found["date_debut"].strftime("%d/%m %H:%M")
            fin   = found["date_fin"].strftime("%d/%m %H:%M")
            # Durée de travail = tps_prep + tps_exec de la gamme (indépendant des shifts)
            duree = found.get("duree_gamme_min")
            if duree is None:
                duree = int((found["date_fin"] - found["date_debut"]).total_seconds() / 60)
            # Compter les autres opérations du même OF (gamme complète)
            id_of_found = found.get("id_of")
            gamme_ops = [op for op in self.operations if op.get("id_of") == id_of_found]
            gamme_ops.sort(key=lambda o: o.get("date_debut") or datetime.min)
            nb_ops = len(gamme_ops)
            idx_in_gamme = next(
                (i + 1 for i, o in enumerate(gamme_ops)
                 if o.get("id_op_plan") == found.get("id_op_plan")),
                "?"
            )
            gamme_hint = (
                f"\n── Routing ({idx_in_gamme}/{nb_ops} ops) ─────────────\n"
                + "\n".join(
                    f"  {'▶' if o.get('id_op_plan') == found.get('id_op_plan') else '·'} "
                    f"{(o.get('description') or '—')[:30]}  "
                    f"[{o.get('machine_nom', '—')}]"
                    for o in gamme_ops
                )
            ) if nb_ops > 1 else ""
            statut_labels = {
                "planifiee": "Planned",
                "en_cours":  "In Progress",
                "terminee":  "Completed",
                "rebutee":   "Scrapped",
            }
            statut_txt = statut_labels.get(found['statut'], found['statut'])
            QToolTip.showText(
                QCursor.pos(),
                f"OF Code: {found['code_of']}\n"
                f"Order: {found['num_commande']}\n"
                f"Component: {found['composant']}\n"
                f"Operation: {found['description']}\n"
                f"Start  : {debut}\n"
                f"End    : {fin}\n"
                f"Duration: {duree} min\n"
                f"Status : {statut_txt}"
                f"{gamme_hint}",
                self
            )
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        self._drag_pending = False

        if not self._dragging or not self._drag_op:
            # Simple clic sans drag → ouvre le dialog de détail
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            if self._selected_op is not None:
                op = self._selected_op
                self._selected_op = None
                self._drag_op     = None
                self.update()
                self._open_op_detail(op)
            else:
                self.update()
            return

        self._dragging = False
        self.setCursor(Qt.ArrowCursor)

        pos = event.position().toPoint()

        # Calcule la nouvelle date de début
        nouvelle_date_debut = self._x_to_datetime(
            self._drag_current_x
        )

        # Détermine la machine cible
        machine_idx = self._y_to_machine_idx(pos.y())
        id_nouvelle_machine = None
        if machine_idx is not None:
            id_nouvelle_machine = self.machines[machine_idx]["id"]

        # Vérifie si le déplacement est significatif (> 5 min)
        ecart = abs(
            (nouvelle_date_debut - self._drag_op["date_debut"]).total_seconds()
        )
        machine_changee = (
            id_nouvelle_machine is not None and
            id_nouvelle_machine != self._drag_op["id_machine"]
        )

        if ecart < 300 and not machine_changee:
            self.update()
            return

        # Validation
        session = SessionLocal()
        try:
            ok, message = valider_deplacement(
                session=session,
                id_op_plan=self._drag_op["id_op_plan"],
                nouvelle_date_debut=nouvelle_date_debut,
                id_nouvelle_machine=id_nouvelle_machine
            )

            if not ok:
                print(f"[drag] VALIDATION FAILED: {message}")
                self._drag_op = None  # ← ligne ajoutée
                QMessageBox.warning(
                    self, "Cannot reschedule", message
                )
                self.update()
                return
            print(f"[drag] validation OK")

            # Dialogue de confirmation
            duree_min = int(
                (self._drag_op["date_fin"] -
                 self._drag_op["date_debut"]).total_seconds() / 60
            )
            nouvelle_date_fin = nouvelle_date_debut + timedelta(minutes=duree_min)

            machine_nom = self._drag_op["machine_nom"]
            if id_nouvelle_machine:
                for m in self.machines:
                    if m["id"] == id_nouvelle_machine:
                        machine_nom = m["nom"]
                        break

            msg = (
                f"OF Code: {self._drag_op['code_of']}\n"
                f"Order: {self._drag_op['num_commande']}\n"
                f"Component: {self._drag_op['composant']}\n"
                f"Operation: '{self._drag_op['description']}'\n\n"
                f"Previous slot:\n"
                f"  {str(self._drag_op['date_debut'])[:16]} → "
                f"{str(self._drag_op['date_fin'])[:16]}\n\n"
                f"New slot:\n"
                f"  {str(nouvelle_date_debut)[:16]} → "
                f"{str(nouvelle_date_fin)[:16]}\n"
                f"  Machine: {machine_nom}\n\n"
                f"Following operations in the routing\n"
                f"will be automatically rescheduled."
            )

            reply = QMessageBox.question(
                self, "Confirm rescheduling", msg,
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                print(f"[drag] Calling deplacer_operation op={self._drag_op['id_op_plan']} → {str(nouvelle_date_debut)[:16]}")
                deplacer_operation(
                    session=session,
                    id_op_plan=self._drag_op["id_op_plan"],
                    nouvelle_date_debut=nouvelle_date_debut,
                    id_nouvelle_machine=id_nouvelle_machine
                )
                session.commit()
                print(f"[drag] commit done")

                # Notifie la vue parente pour recharger (différé pour éviter
                # de détruire le widget pendant mouseReleaseEvent)
                if self.on_deplacement:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self.on_deplacement)


        except Exception as e:
            session.rollback()
            self._drag_op = None  # ← ligne ajoutée
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

        self._drag_op = None
        # Ne pas appeler self.update() ici — le widget sera reconstruit par on_deplacement

    def leaveEvent(self, event):
        self._hovered_op = None
        QToolTip.hideText()
        self.update()

    def paintEvent(self, event):
        from datetime import time as dtime
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#f5f6fa"))
        painter.fillRect(0, 0, LABEL_WIDTH, h, QColor("#2c3e50"))

        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(QRect(0, 0, LABEL_WIDTH, HEADER_HEIGHT),
                         Qt.AlignCenter, "Machine")

        # ── Header background ──────────────────────────────────────────
        step = self._grid_step if hasattr(self, "_grid_step") else 1
        px   = self.px_per_hour
        show_hours = step < 12  # hide bottom row for 2-week / 1-month
        effective_day_h = HEADER_HEIGHT if not show_hours else DAY_ROW_H

        # Top header row background
        painter.fillRect(LABEL_WIDTH, 0, w - LABEL_WIDTH, effective_day_h, QColor("#1a252f"))
        # Bottom shift-label row background
        if show_hours:
            painter.fillRect(LABEL_WIDTH, DAY_ROW_H, w - LABEL_WIDTH, HOUR_ROW_H, QColor("#34495e"))

        # Helper: convert a datetime to an X pixel position
        def dt_to_x(dt):
            return int(LABEL_WIDTH + (dt - self.date_debut).total_seconds() / 3600 * px)

        # Helper: iterate over every shift interval visible in the window.
        # Yields (shift_idx 0-2, shift_start datetime, shift_end datetime).
        def iter_shifts():
            # Walk day by day starting from the day of date_debut
            day = self.date_debut.replace(hour=0, minute=0, second=0, microsecond=0)
            # Go back one day to catch overnight shifts that started the previous day
            day -= timedelta(days=1)
            while day <= self.date_fin + timedelta(days=1):
                # Shift 0: 06:00 → 14:00
                s0 = datetime.combine(day.date(), dtime(6, 0))
                e0 = datetime.combine(day.date(), dtime(14, 0))
                yield 0, s0, e0
                # Shift 1: 14:00 → 22:00
                s1 = datetime.combine(day.date(), dtime(14, 0))
                e1 = datetime.combine(day.date(), dtime(22, 0))
                yield 1, s1, e1
                # Shift 2: 22:00 → 06:00 next day
                s2 = datetime.combine(day.date(), dtime(22, 0))
                e2 = datetime.combine(day.date() + timedelta(days=1), dtime(6, 0))
                yield 2, s2, e2
                day += timedelta(days=1)

        # ── Draw shift background columns in data area ───────────────
        max_y = HEADER_HEIGHT + len(self.machines) * ROW_HEIGHT
        for shift_idx, s_start, s_end in iter_shifts():
            x1 = dt_to_x(s_start)
            x2 = dt_to_x(s_end)
            x1c = max(x1, LABEL_WIDTH)
            x2c = min(x2, w)
            if x2c > x1c:
                painter.fillRect(x1c, HEADER_HEIGHT, x2c - x1c,
                                 max_y - HEADER_HEIGHT, SHIFT_COLORS[shift_idx])

        # ── Day labels in top header row ─────────────────────────────
        cur_day = self.date_debut.replace(hour=0, minute=0, second=0, microsecond=0)
        while cur_day <= self.date_fin:
            next_day = cur_day + timedelta(days=1)
            x_start = max(dt_to_x(cur_day), LABEL_WIDTH)
            x_end   = min(dt_to_x(next_day), w)
            col_w   = x_end - x_start
            if col_w > 4:
                if step >= 12:
                    day_label = cur_day.strftime("%d/%m")
                    painter.setFont(QFont("Arial", 7))
                else:
                    day_label = cur_day.strftime("%a %d/%m")
                    painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.setPen(QColor("white"))
                painter.drawText(QRect(x_start + 2, 0, col_w - 4, effective_day_h),
                                 Qt.AlignCenter, day_label)
            # Day separator (header)
            x_sep = dt_to_x(next_day)
            if LABEL_WIDTH < x_sep < w:
                painter.setPen(QPen(QColor("#7f8c8d"), 1))
                painter.drawLine(x_sep, 0, x_sep, effective_day_h)
            cur_day = next_day

        # ── Shift labels in bottom header row ────────────────────────
        if show_hours:
            shift_label_texts = ["6h–14h", "14h–22h", "22h–6h"]
            # Collect all inactive shifts across all machines for visual hint
            all_inactive: set[int] = set()
            for m in self.machines:
                if m.get("type") == "machine":
                    active = m.get("active_shifts") or {0, 1, 2}
                    for si in range(3):
                        if si not in active:
                            all_inactive.add(si)

            for shift_idx, s_start, s_end in iter_shifts():
                x1 = max(dt_to_x(s_start), LABEL_WIDTH)
                x2 = min(dt_to_x(s_end), w)
                col_w = x2 - x1
                if col_w > 10:
                    if shift_idx in all_inactive:
                        bg_col = QColor("#7f8c8d")   # grey = at least one machine inactive
                    else:
                        bg_col = SHIFT_HEADER_COLORS[shift_idx]
                    painter.fillRect(x1, DAY_ROW_H, col_w, HOUR_ROW_H, bg_col)
                    painter.setPen(QColor("#ecf0f1"))
                    painter.setFont(QFont("Arial", 7))
                    lbl = shift_label_texts[shift_idx]
                    if shift_idx in all_inactive:
                        lbl = "🚫 " + lbl
                    painter.drawText(QRect(x1 + 2, DAY_ROW_H + 2, col_w - 4, HOUR_ROW_H - 4),
                                     Qt.AlignCenter, lbl)

        # ── Machine rows ─────────────────────────────────────────────
        for i, machine in enumerate(self.machines):
            y  = HEADER_HEIGHT + i * ROW_HEIGHT

            # Left label column
            lbl_bg = QColor("#2c3e50") if i % 2 == 0 else QColor("#34495e")
            painter.fillRect(0, y, LABEL_WIDTH, ROW_HEIGHT, lbl_bg)

            # Drag highlight
            if self._dragging and self._drag_machine_idx == i:
                painter.fillRect(LABEL_WIDTH, y, w - LABEL_WIDTH, ROW_HEIGHT, QColor(214, 234, 248, 120))
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QColor("white"))
            painter.drawText(QRect(5, y, LABEL_WIDTH - 10, ROW_HEIGHT),
                             Qt.AlignVCenter | Qt.AlignLeft, machine["nom"])
            painter.setPen(QPen(QColor("#a0aab4"), 1))
            painter.drawLine(0, y + ROW_HEIGHT, w, y + ROW_HEIGHT)

            # ── Hatch off-shift zones for machines ───────────────────
            cap_machine   = machine.get("capacite_h_jour")
            active_shifts = machine.get("active_shifts")   # None = pas de config explicite
            is_machine_row = machine.get("type") == "machine"

            # Priorité 1 : config explicite (DB ou mémoire après toggle)
            # Priorité 2 : déduire depuis capacite_h_jour (avant migration)
            if active_shifts is not None:
                effective_active = active_shifts
            elif cap_machine is not None:
                cap_f = float(cap_machine)
                if cap_f <= 8:
                    effective_active = {0}
                elif cap_f <= 16:
                    effective_active = {0, 1}
                else:
                    effective_active = {0, 1, 2}
            else:
                effective_active = {0, 1, 2}

            # Draw hatches on inactive shifts
            if is_machine_row and len(effective_active) < 3:
                tile = QPixmap(10, 10)
                tile.fill(Qt.transparent)
                tp = QPainter(tile)
                tp.setPen(QPen(QColor("#8a96a3"), 1.0))
                tp.drawLine(0, 10, 10, 0)
                tp.drawLine(-2, 10, 10, -2)
                tp.drawLine(0, 12, 12, 0)
                tp.end()
                hatch_brush = QBrush(tile)

                painter.setBrush(hatch_brush)
                painter.setPen(Qt.NoPen)
                for shift_idx, s_start, s_end in iter_shifts():
                    if shift_idx in effective_active:
                        continue
                    x1 = max(dt_to_x(s_start), LABEL_WIDTH)
                    x2 = min(dt_to_x(s_end), w)
                    if x2 > x1:
                        painter.drawRect(x1, y, x2 - x1, ROW_HEIGHT)

            for op in self.operations:
                if op.get("row_id") != machine.get("row_id"):
                    continue
                if op["date_fin"] < self.date_debut:
                    continue
                if op["date_debut"] > self.date_fin:
                    continue

                # Si c'est la tâche en cours de drag → affiche fantôme
                if self._dragging and self._drag_op and \
                        op["id_op_plan"] == self._drag_op["id_op_plan"]:
                    # Fantôme à la position actuelle
                    bar_w = self._op_rect(op, y).width()
                    bar_h = ROW_HEIGHT - 10

                    # Position fantôme sur la machine cible
                    ghost_y = y
                    if self._drag_machine_idx is not None:
                        ghost_y = HEADER_HEIGHT + self._drag_machine_idx * ROW_HEIGHT

                    couleur = COULEURS_STATUT.get(op["statut"], QColor("#95a5a6"))
                    ghost = QColor(couleur)
                    ghost.setAlpha(120)
                    painter.setBrush(QBrush(ghost))
                    painter.setPen(QPen(QColor("white"), 2, Qt.DashLine))
                    painter.drawRoundedRect(
                        self._drag_current_x, ghost_y + 5,
                        bar_w, bar_h, 4, 4
                    )

                    # Position originale en grisé
                    orig_rect = self._op_rect(op, y)
                    orig_color = QColor("#bdc3c7")
                    orig_color.setAlpha(80)
                    painter.setBrush(QBrush(orig_color))
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(orig_rect, 4, 4)
                    continue

                segments = self._op_segments(op, y, machine)
                couleur  = COULEURS_STATUT.get(op["statut"], QColor("#95a5a6"))

                # Sélection + surbrillance composant
                same_composant = (
                    self._selected_composant_id is not None
                    and op.get("id_of") == self._selected_composant_id
                    and not (self._selected_op is not None
                             and op.get("id_op_plan") == self._selected_op.get("id_op_plan"))
                )
                is_selected_op = (
                    self._selected_op is not None
                    and op.get("id_op_plan") == self._selected_op.get("id_op_plan")
                )
                is_hovered = (
                    self._hovered_op is not None
                    and op.get("id_op_plan") == self._hovered_op.get("id_op_plan")
                )
                # Toutes les tâches du même OF (même gamme) que la tâche survolée
                is_same_gamme_hovered = (
                    self._hovered_op is not None
                    and not is_hovered
                    and op.get("id_of") is not None
                    and op.get("id_of") == self._hovered_op.get("id_of")
                )

                if is_selected_op:
                    painter.setBrush(QBrush(couleur.lighter(175)))
                    painter.setPen(QPen(QColor("white"), 2))
                elif same_composant:
                    painter.setBrush(QBrush(couleur.lighter(145)))
                    painter.setPen(QPen(couleur.darker(110), 1))
                elif is_hovered:
                    painter.setBrush(QBrush(couleur.lighter(140)))
                    painter.setPen(QPen(QColor("white"), 2))
                elif is_same_gamme_hovered:
                    # Vert clair pour toutes les tâches de la même gamme
                    gamme_color = QColor("#a8e6b0")  # vert clair
                    painter.setBrush(QBrush(gamme_color))
                    painter.setPen(QPen(QColor("#27ae60"), 2))
                else:
                    painter.setBrush(QBrush(couleur))
                    painter.setPen(QPen(couleur.darker(130), 1))

                for seg in segments:
                    painter.drawRoundedRect(seg, 4, 4)

                # Numéro d'ordre de l'opération dans la gamme (petit badge)
                if is_same_gamme_hovered and segments:
                    seg0 = segments[0]
                    if seg0.width() > 20:
                        painter.setFont(QFont("Arial", 7, QFont.Bold))
                        painter.setPen(QColor("#1a5c2a"))
                        painter.drawText(seg0.adjusted(3, 0, -3, 0),
                                         Qt.AlignVCenter | Qt.AlignLeft,
                                         (op.get("description") or "")[:18])
        # ── Draw vertical shift separators AFTER machine rows ────────
        max_y = HEADER_HEIGHT + len(self.machines) * ROW_HEIGHT
        # Shift boundary separators (at 6h, 14h, 22h of each day)
        shift_boundary_hours = [6, 14, 22]
        cur_day3 = self.date_debut.replace(hour=0, minute=0, second=0, microsecond=0)
        cur_day3 -= timedelta(days=1)
        while cur_day3 <= self.date_fin + timedelta(days=1):
            for bh in shift_boundary_hours:
                from datetime import time as dtime
                dt_b = datetime.combine(cur_day3.date(), dtime(bh, 0))
                x_b = dt_to_x(dt_b)
                if LABEL_WIDTH < x_b < w:
                    if bh == 6:
                        # Day boundary at 6h → strong separator
                        painter.setPen(QPen(QColor("#5d6d7e"), 2))
                    else:
                        # Shift boundary within a day → medium solid line
                        painter.setPen(QPen(QColor("#a0aab4"), 1))
                    painter.drawLine(x_b, HEADER_HEIGHT, x_b, max_y)
            cur_day3 += timedelta(days=1)

        # Ligne verticale "maintenant"
        now = datetime.now()
        if self.date_debut <= now <= self.date_fin:
            x_now = int(
                LABEL_WIDTH +
                (now - self.date_debut).total_seconds()
                / 3600 * self.px_per_hour
            )
            max_y = HEADER_HEIGHT + len(self.machines) * ROW_HEIGHT
            painter.setPen(QPen(QColor("#e74c3c"), 2, Qt.SolidLine))
            painter.drawLine(x_now, HEADER_HEIGHT, x_now, max_y)

            # Label "Maintenant"
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            label_rect = QRect(x_now - 20, DAY_ROW_H + 2, 40, HOUR_ROW_H - 4)
            painter.fillRect(label_rect, QColor("#e74c3c"))
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            painter.drawText(label_rect, Qt.AlignCenter, "Now")
        painter.end()





class MachineJobsDialog(QDialog):
    """Shows all planned jobs for a machine/service and allows printing a work sheet."""

    def __init__(self, machine, ops, parent=None, on_reload=None):
        super().__init__(parent)
        self._machine   = machine
        self._ops       = ops
        self._on_reload = on_reload
        self.setWindowTitle(f"Jobs — {machine['nom']}")
        self.setMinimumWidth(640)
        self.setMinimumHeight(480)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Header ───────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("background:#2c3e50; border-radius:6px; padding:4px;")
        h_lay = QHBoxLayout(header)
        icon = "⚙" if self._machine["type"] == "service" else "🏭"
        lbl = QLabel(f"{icon}  {self._machine['nom']}  —  {len(self._ops)} job(s) scheduled")
        lbl.setStyleSheet("color:white; font-size:14px; font-weight:bold; background:transparent;")
        h_lay.addWidget(lbl)
        layout.addWidget(header)

        # ── Table ────────────────────────────────────────────────────
        self.table = QTableWidget(len(self._ops), 6)
        self.table.setHorizontalHeaderLabels([
            "OF Code", "Component", "Operation", "Planned Start", "Planned End", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget { border: 1px solid #bdc3c7; border-radius: 4px; }
            QHeaderView::section {
                background: #34495e; color: white;
                padding: 6px; font-weight: bold; border: none;
            }
        """)

        STATUS_COLORS = {
            "planifiee": "#3498db",
            "en_cours":  "#e67e22",
            "terminee":  "#27ae60",
            "rebutee":   "#e74c3c",
        }
        STATUS_LABELS = {
            "planifiee": "Scheduled",
            "en_cours":  "In Progress",
            "terminee":  "Completed",
            "rebutee":   "Scrapped",
        }

        for row, op in enumerate(self._ops):
            debut = op.get("date_debut")
            fin   = op.get("date_fin")
            statut = op.get("statut", "")

            items = [
                op.get("code_of", "—"),
                op.get("composant", "—"),
                op.get("description", "—"),
                debut.strftime("%d/%m/%Y %H:%M") if debut else "—",
                fin.strftime("%d/%m/%Y %H:%M")   if fin   else "—",
                STATUS_LABELS.get(statut, statut),
            ]
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 5:
                    item.setForeground(QColor(STATUS_COLORS.get(statut, "#7f8c8d")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)

        layout.addWidget(self.table)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_print = QPushButton("🖨  Print Work Sheet")
        btn_print.setFixedHeight(36)
        btn_print.setStyleSheet("""
            QPushButton {
                background:#27ae60; color:white;
                border-radius:4px; padding:0 16px; font-size:13px;
            }
            QPushButton:hover { background:#219a52; }
        """)
        btn_print.clicked.connect(self._print_work_sheet)

        btn_shifts = QPushButton("⏱  Configure Shifts")
        btn_shifts.setFixedHeight(36)
        btn_shifts.setStyleSheet("""
            QPushButton {
                background:#2980b9; color:white;
                border-radius:4px; padding:0 16px; font-size:13px;
            }
            QPushButton:hover { background:#2471a3; }
        """)
        btn_shifts.clicked.connect(self._configure_shifts)
        # Only show for machines (not services)
        if self._machine.get("type") != "machine":
            btn_shifts.setVisible(False)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(36)
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_print)
        btn_row.addWidget(btn_shifts)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _configure_shifts(self):
        """Ouvre un dialog pour configurer les pauses actives de cette machine."""
        dlg = ShiftConfigDialog(self._machine, self, on_reload=self._on_reload)
        dlg.exec()

    def _print_work_sheet(self):
        """Generate a printable HTML work sheet and open in browser for printing."""
        import tempfile, os, webbrowser
        from datetime import datetime

        STATUS_LABELS = {
            "planifiee": "Scheduled",
            "en_cours":  "In Progress",
            "terminee":  "Completed",
            "rebutee":   "Scrapped",
        }

        icon = "Service" if self._machine["type"] == "service" else "Machine"
        now  = datetime.now().strftime("%d/%m/%Y %H:%M")

        jobs_html = ""
        for idx, op in enumerate(self._ops, 1):
            debut  = op.get("date_debut")
            fin    = op.get("date_fin")
            statut = STATUS_LABELS.get(op.get("statut", ""), op.get("statut", ""))

            jobs_html += f"""
            <div class="job">
                <div class="job-header">
                    Job {idx} &mdash; <strong>{op.get("code_of","—")}</strong>
                    &nbsp;|&nbsp; {op.get("composant","—")}
                </div>
                <table>
                    <thead>
                        <tr>
                            <th style="width:22%">Field</th>
                            <th style="width:39%">Planned</th>
                            <th style="width:39%">Actual <span class="hint">(filled by operator)</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="field">Operator</td>
                            <td></td>
                            <td class="write"></td>
                        </tr>
                        <tr>
                            <td class="field">Operation</td>
                            <td>{op.get("description","—")}</td>
                            <td class="write"></td>
                        </tr>
                        <tr>
                            <td class="field">Status</td>
                            <td>{statut}</td>
                            <td class="write"></td>
                        </tr>

                        <tr style="height:40px">
                            <td class="field">Notes / Issues</td>
                            <td></td>
                            <td class="write"></td>
                        </tr>
                    </tbody>
                </table>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Work Sheet — {self._machine["nom"]}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; font-size: 11pt;
          color: #2c3e50; padding: 12mm; }}
  .page-header {{ border-bottom: 2px solid #2c3e50; padding-bottom: 8px;
                  margin-bottom: 16px; }}
  .page-header h1 {{ font-size: 18pt; color: #2c3e50; }}
  .page-header p  {{ font-size: 9pt; color: #7f8c8d; margin-top: 4px; }}
  .job {{ margin-bottom: 18px; page-break-inside: avoid; }}
  .job-header {{ background: #34495e; color: white; padding: 6px 10px;
                 font-size: 11pt; border-radius: 3px 3px 0 0; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #2c3e50; color: white; padding: 6px 8px;
        font-size: 9pt; text-align: left; }}
  td {{ padding: 6px 8px; border: 0.5px solid #bdc3c7;
        font-size: 10pt; vertical-align: middle; }}
  td.field {{ background: #ecf0f1; font-weight: bold; font-size: 9pt; }}
  td.write {{ background: #fffef0; }}
  tr:nth-child(even) td {{ background: #f8f9fa; }}
  tr:nth-child(even) td.field {{ background: #e8eaeb; }}
  tr:nth-child(even) td.write {{ background: #fffef0; }}
  .hint {{ font-weight: normal; font-size: 8pt; color: #bdc3c7; }}
  @media print {{
    @page {{
      size: A4;
      margin: 12mm 10mm 10mm 10mm;
    }}
    body {{ padding: 0; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="page-header">
  <h1>Work Sheet &mdash; {self._machine["nom"]}</h1>
  <p>{icon} &nbsp;|&nbsp; Generated: {now} &nbsp;|&nbsp; {len(self._ops)} job(s)</p>
</div>
<div class="no-print" style="margin-bottom:12px">
  <button onclick="window.print()"
          style="background:#27ae60;color:white;border:none;padding:8px 20px;
                 font-size:11pt;border-radius:4px;cursor:pointer;">
    🖨 Print / Save as PDF
  </button>
</div>
{jobs_html}
</body>
</html>"""

        tmp = tempfile.NamedTemporaryFile(
            suffix=".html", delete=False,
            prefix=f"worksheet_{self._machine['nom'].replace(' ','_')}_"
        )
        tmp.write(html.encode("utf-8"))
        tmp.close()
        webbrowser.open(f"file:///{tmp.name.replace(chr(92), '/')}")


class ShiftConfigDialog(QDialog):
    """Dialog pour activer/désactiver les pauses d'une machine."""

    SHIFT_LABELS = ["6h – 14h", "14h – 22h", "22h – 6h"]

    def __init__(self, machine: dict, parent=None, on_reload=None):
        super().__init__(parent)
        self._machine   = machine
        self._on_reload = on_reload
        self.setWindowTitle(f"Shift configuration — {machine['nom']}")
        self.setMinimumWidth(360)
        self._checkboxes = []
        self._build_ui()

    def _get_effective_active(self):
        """Lit les shifts actifs depuis la DB, sinon déduit depuis capacite_h_jour."""
        from database import SessionLocal
        session = SessionLocal()
        try:
            from models.production import MachineShiftConfig
            rows = session.query(MachineShiftConfig).filter_by(
                id_machine=self._machine["id"]
            ).all()
            if rows:
                cfg = {r.shift_index: r.active for r in rows}
                return {i for i in range(3) if cfg.get(i, True)}
        except Exception:
            pass
        finally:
            session.close()
        # Fallback : capacite_h_jour
        cap = self._machine.get("capacite_h_jour")
        if cap is not None:
            cap_f = float(cap)
            if cap_f <= 8:  return {0}
            if cap_f <= 16: return {0, 1}
        return {0, 1, 2}

    def _build_ui(self):
        from PySide6.QtWidgets import QCheckBox, QGroupBox
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel(f"<b>{self._machine['nom']}</b> — active shifts:")
        layout.addWidget(lbl)

        active = self._get_effective_active()
        grp = QGroupBox("Shifts")
        grp_layout = QVBoxLayout(grp)
        for idx, label in enumerate(self.SHIFT_LABELS):
            cb = QCheckBox(label)
            cb.setChecked(idx in active)
            grp_layout.addWidget(cb)
            self._checkboxes.append(cb)
        layout.addWidget(grp)

        warn = QLabel("⚠ Changing shifts will reschedule all planned\noperations on this machine.")
        warn.setStyleSheet("color:#e67e22; font-size:11px;")
        layout.addWidget(warn)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Apply")
        btn_ok.setFixedHeight(34)
        btn_ok.setStyleSheet("background:#2980b9; color:white; border-radius:4px; padding:0 16px;")
        btn_ok.clicked.connect(self._apply)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _apply(self):
        new_active = {i for i, cb in enumerate(self._checkboxes) if cb.isChecked()}
        if not new_active:
            QMessageBox.warning(self, "Invalid", "At least one shift must remain active.")
            return

        from database import SessionLocal
        session = SessionLocal()
        try:
            db_ok = False
            try:
                from services.planning_service import set_shift_active, recalculer_planning_machine
                from models import Machine
                id_machine = self._machine["id"]
                for idx in range(3):
                    set_shift_active(session, id_machine, idx, idx in new_active)
                # Synchronise capacite_h_jour avec les shifts actifs
                nb_actifs = len(new_active)
                nouvelle_cap = nb_actifs * 8  # 8h, 16h ou 24h
                machine_obj = session.get(Machine, id_machine)
                if machine_obj:
                    machine_obj.capacite_h_jour = nouvelle_cap
                result = recalculer_planning_machine(session, id_machine)
                session.commit()
                db_ok = True
                nb_ops = result["nb_ops"]
            except Exception as db_err:
                session.rollback()
                if "machineshiftconfig" in str(db_err).lower() or "no such table" in str(db_err).lower():
                    # Pas encore migré → mise à jour mémoire uniquement
                    self._machine["active_shifts"] = new_active
                    nb_ops = 0
                else:
                    raise

            QMessageBox.information(
                self, "Done",
                f"Shifts updated for {self._machine['nom']}.\n"
                f"{nb_ops} operation(s) rescheduled."
            )
            self.accept()
            # Recharge le planning
            if self._on_reload:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._on_reload)

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


class OperationDetailDialog(QDialog):
    STATUS_MAP = {
        "planifiee": "Scheduled",
        "en_cours":  "In Progress",
        "terminee":  "Completed",
        "rebutee":   "Scrapped",
    }

    def __init__(self, id_op_plan, parent=None):
        super().__init__(parent)
        from database import SessionLocal
        from models import OperationPlanifiee
        self._session = SessionLocal()
        self._op      = self._session.get(OperationPlanifiee, id_op_plan)
        if not self._op:
            self.reject()
            return
        op       = self._op
        resource = op.machine.nom if op.machine else (op.service.nom if op.service else "—")
        self.setWindowTitle(f"{op.of.code_of} — {op.operation.description or 'Operation'}")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._updating = False
        self._build_ui(resource)

    def closeEvent(self, event):
        self._session.close()
        super().closeEvent(event)

    def _build_ui(self, resource):
        op  = self._op
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ── Info header ──────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("QFrame{background:#2c3e50;border-radius:6px;padding:2px;}")
        hl = QVBoxLayout(header)
        hl.setSpacing(2)
        def lbl(txt):
            l = QLabel(txt)
            l.setStyleSheet("color:white;font-size:12px;background:transparent;")
            return l
        hl.addWidget(lbl(f"OF: {op.of.code_of}   |   Component: {op.of.composant.nom}"))
        hl.addWidget(lbl(f"Op {op.operation.ordre}: {op.operation.description or '—'}   |   Resource: {resource}"))
        lay.addWidget(header)

        # ── Status ───────────────────────────────────────────────────
        row_s = QHBoxLayout()
        row_s.addWidget(QLabel("Status:"))
        self.combo_statut = QComboBox()
        self.combo_statut.setStyleSheet("""
            QComboBox{border:1px solid #bdc3c7;border-radius:4px;
                      padding:4px 8px;background:white;color:#2c3e50;font-size:12px;}
            QComboBox QAbstractItemView{background:white;color:#2c3e50;
                selection-background-color:#3498db;selection-color:white;}
        """)
        for db_val, lbl_txt in self.STATUS_MAP.items():
            self.combo_statut.addItem(lbl_txt, db_val)
        idx = list(self.STATUS_MAP.keys()).index(op.statut) if op.statut in self.STATUS_MAP else 0
        self.combo_statut.setCurrentIndex(idx)
        self.combo_statut.currentIndexChanged.connect(self._on_status_changed)
        row_s.addWidget(self.combo_statut)
        row_s.addStretch()
        lay.addLayout(row_s)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#dce0e3;"); lay.addWidget(sep)

        # ── 4 values ─────────────────────────────────────────────────
        dt_style = """
            QDateTimeEdit{border:1px solid #bdc3c7;border-radius:4px;
                padding:4px 8px;background:white;color:#2c3e50;font-size:12px;}
            QCalendarWidget QWidget{background:white;color:#2c3e50;}
            QCalendarWidget QToolButton{color:#2c3e50;background:white;}
        """
        ro_style = """
            QDateTimeEdit{border:1px solid #dce0e3;border-radius:4px;
                padding:4px 8px;background:#f4f6f7;color:#7f8c8d;font-size:12px;}
        """
        def make_dt(val, readonly=False):
            w = QDateTimeEdit()
            w.setDisplayFormat("dd/MM/yyyy HH:mm")
            w.setCalendarPopup(not readonly)
            w.setStyleSheet(ro_style if readonly else dt_style)
            w.setReadOnly(readonly)
            if val:
                w.setDateTime(QDateTime(val.date(), val.time()))
            return w

        is_completed = op.statut in ("terminee", "rebutee")
        is_started   = op.statut in ("en_cours", "terminee", "rebutee")
        form = QFormLayout(); form.setSpacing(8)

        # Durée gamme originale = tps_prep + tps_exec × qté (ne change jamais)
        def _duree_gamme_originale():
            if op.operation and op.of:
                return int(op.operation.tps_preparation +
                           op.operation.tps_execution * float(op.of.quantite))
            if op.date_debut and op.date_fin:
                return int((op.date_fin - op.date_debut).total_seconds() / 60)
            return 0

        # Durée estimée = durée modifiée par l'utilisateur, sinon gamme d'origine
        def _duree_estimee():
            if op.duree_reelle_min:
                return int(op.duree_reelle_min)
            return _duree_gamme_originale()

        duree_initiale = _duree_gamme_originale()
        duree_ref      = _duree_estimee()

        # 1. Initial duration (gamme × quantité, lecture seule)
        lbl_init = QLabel(f"{duree_initiale} min")
        lbl_init.setStyleSheet("color:#7f8c8d;font-size:12px;padding:4px 0;")
        form.addRow("① Initial duration:", lbl_init)

        # 2. Planned start — locked when In Progress
        self.dt_debut = make_dt(op.date_debut, readonly=is_started)
        form.addRow("② Planned start:", self.dt_debut)

        # 3. Estimated end — locked when Completed
        self.dt_fin = make_dt(op.date_fin, readonly=is_completed)
        form.addRow("③ Estimated end:", self.dt_fin)

        # 4. Estimated duration — valeur modifiée (ou gamme si pas encore modifiée)
        self.spin_duree = QSpinBox()
        self.spin_duree.setMinimum(1); self.spin_duree.setMaximum(99999)
        self.spin_duree.setSuffix(" min"); self.spin_duree.setEnabled(not is_completed)
        self.spin_duree.setValue(duree_ref)
        form.addRow("④ Estimated duration:", self.spin_duree)

        lay.addLayout(form)

        # Connect signals only if fields are editable
        if not is_started:
            self.dt_debut.editingFinished.connect(self._on_debut_changed)
        if not is_completed:
            self.dt_fin.editingFinished.connect(self._on_fin_changed)
            self.spin_duree.editingFinished.connect(self._on_duree_changed)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet(
            "QPushButton{background:#3498db;color:white;border-radius:4px;padding:5px 18px;}"
            "QPushButton:hover{background:#2980b9;}"
        )
        btn_save.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

    def _on_status_changed(self):
        pass  # status change handled at save

    def _on_debut_changed(self):
        if self._updating: return
        self._updating = True
        from datetime import timedelta
        from services.planning_service import (
            ajuster_selon_plage_machine, ajuster_date_fin_selon_plage_machine
        )
        op    = self._op
        machine = op.machine if op.machine else None
        debut = self.dt_debut.dateTime().toPython()
        # Ajuster le début selon la plage de la machine
        debut = ajuster_selon_plage_machine(debut, machine)
        self.dt_debut.setDateTime(QDateTime(debut.date(), debut.time()))
        # Calculer la fin en tenant compte de la plage
        duree = timedelta(minutes=self.spin_duree.value())
        _, fin = ajuster_date_fin_selon_plage_machine(debut, duree, machine)
        self.dt_fin.setDateTime(QDateTime(fin.date(), fin.time()))
        self._updating = False

    def _on_fin_changed(self):
        if self._updating: return
        self._updating = True
        from services.planning_service import _plage_machine, calculer_duree_travail_reelle_op
        op = self._op
        machine = op.machine if op.machine else None
        plage = _plage_machine(machine.capacite_h_jour) if machine else None
        debut = self.dt_debut.dateTime().toPython()
        fin = self.dt_fin.dateTime().toPython()
        if fin > debut:
            if plage:
                self.spin_duree.setValue(calculer_duree_travail_reelle_op(debut, fin, plage))
            else:
                self.spin_duree.setValue(int((fin - debut).total_seconds() / 60))
        self._updating = False

    def _on_duree_changed(self):
        if self._updating: return
        self._updating = True
        from datetime import timedelta
        from services.planning_service import ajuster_date_fin_selon_plage_machine
        op      = self._op
        machine = op.machine if op.machine else None
        debut   = self.dt_debut.dateTime().toPython()
        duree   = timedelta(minutes=self.spin_duree.value())
        _, fin  = ajuster_date_fin_selon_plage_machine(debut, duree, machine)
        self.dt_fin.setDateTime(QDateTime(fin.date(), fin.time()))
        self._updating = False

    def _save(self):
        op = self._op
        session = self._session
        new_statut = self.combo_statut.currentData()
        now = __import__('datetime').datetime.now()

        is_started = op.statut in ("en_cours", "terminee", "rebutee")
        is_completed = op.statut in ("terminee", "rebutee")

        nouvelle_debut = self.dt_debut.dateTime().toPython()
        nouvelle_fin = self.dt_fin.dateTime().toPython()

        # Validation : la date de fin doit être strictement après la date de début
        if nouvelle_fin <= nouvelle_debut:
            QMessageBox.warning(
                self,
                "Invalid dates",
                f"End date must be strictly after start date.\n\n"
                f"  Start : {nouvelle_debut.strftime('%d/%m/%Y %H:%M')}\n"
                f"  End   : {nouvelle_fin.strftime('%d/%m/%Y %H:%M')}"
            )
            return

        from services.planning_service import _plage_machine, calculer_duree_travail_reelle_op
        machine = op.machine if op.machine else None
        plage = _plage_machine(machine.capacite_h_jour) if machine else None
        if plage and op.date_debut and op.date_fin:
            duree_originale = calculer_duree_travail_reelle_op(op.date_debut, op.date_fin, plage)
        else:
            duree_originale = int(
                (op.date_fin - op.date_debut).total_seconds() / 60) if op.date_debut and op.date_fin else 0

        duree_nouvelle = self.spin_duree.value()
        duree_changed = (duree_nouvelle != duree_originale)

        # date_debut ne peut pas changer si déjà commencé
        # mais la durée/fin peut toujours être ajustée
        date_changed = (
            duree_changed or
            (not is_started and nouvelle_debut != op.date_debut) or
            (not is_completed and nouvelle_fin != op.date_fin)
        )

        # Lock planned start when moving to In Progress
        if new_statut == "en_cours" and not is_started:
            op.date_debut_reelle = now

        # Lock estimated end + duration when Completed
        if new_statut in ("terminee", "rebutee") and not is_completed:
            op.date_fin_reelle = now

        op.statut = new_statut

        print(
            f"[_save] date_changed={date_changed} spin={self.spin_duree.value()} op.date_debut={op.date_debut} op.date_fin={op.date_fin}")
        print(f"[_save] nouvelle_debut={nouvelle_debut} nouvelle_fin={nouvelle_fin}")
        if date_changed:
            from services.planning_service import deplacer_operation
            try:
                deplacer_operation(
                    session=session,
                    id_op_plan=op.id_op_plan,
                    nouvelle_date_debut=nouvelle_debut,
                    nouvelle_duree_minutes=self.spin_duree.value()
                )
                # Persist the new duration as reference
                op.duree_reelle_min = self.spin_duree.value()
            except ValueError as e:
                QMessageBox.warning(self, "Cannot reschedule", str(e))
                session.rollback()
                return
        else:
            session.flush()

        # Update OF dates and status
        from models import OperationPlanifiee as OP
        of = op.of
        session.expire(of)
        session.refresh(of)
        all_ops = session.query(OP).filter_by(id_of=of.id_of).all()
        if all_ops:
            dates_debut = [o.date_debut for o in all_ops if o.date_debut]
            dates_fin = [o.date_fin for o in all_ops if o.date_fin]
            if dates_debut:
                of.date_lancement = min(dates_debut)
            if dates_fin:
                of.date_fin_prevue = max(dates_fin)

        statuts = [o.statut for o in all_ops]
        if all(s == "terminee" for s in statuts):
            of.statut = "termine"
        elif any(s == "en_cours" for s in statuts):
            of.statut = "en_cours"

        # ← AJOUT : propager la date de fin vers l'OFAssemblage parent
        from models import OFAssemblage, OrdreFabrication
        if of.id_of_assemblage:
            ofa = session.get(OFAssemblage, of.id_of_assemblage)
            if ofa:
                tous_ofs = session.query(OrdreFabrication).filter_by(
                    id_of_assemblage=ofa.id_of_assemblage
                ).all()
                dates_fin_ofa = [o.date_fin_prevue for o in tous_ofs if o.date_fin_prevue]
                if dates_fin_ofa:
                    ofa.date_fin_prevue = max(dates_fin_ofa)

        session.commit()
        print(f"[_save] COMMIT → of.date_fin_prevue={of.date_fin_prevue}")
        self.accept()


class PlanningView(QWidget):
    def __init__(self):
        super().__init__()
        self._gantt         = None
        self._machines_data = []
        self._ops_data      = []
        self._fenetre_debut = None
        self._ops_min_date  = None
        self._build_ui()
        self._charger_planning()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Titre + actualiser
        header = QHBoxLayout()
        titre = QLabel("Planning")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_refresh.clicked.connect(self._charger_planning)
        header.addWidget(btn_refresh)

        btn_recalc = QPushButton("⚙ Recalculate")
        btn_recalc.setFixedHeight(36)
        btn_recalc.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white;
                border-radius: 4px; padding: 0 16px; font-size: 13px;
            }
            QPushButton:hover { background-color: #ca6f1e; }
        """)
        btn_recalc.clicked.connect(self._recalculer_planning)
        header.addWidget(btn_recalc)
        layout.addLayout(header)

        # Ligne 1 — Navigation temporelle + échelle
        ligne1 = QHBoxLayout()

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(36, 36)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50; color: white;
                border-radius: 4px; font-size: 14px;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.btn_prev.clicked.connect(self._periode_precedente)
        ligne1.addWidget(self.btn_prev)

        self.lbl_periode = QLabel("")
        self.lbl_periode.setFixedWidth(220)
        self.lbl_periode.setAlignment(Qt.AlignCenter)
        self.lbl_periode.setStyleSheet("""
            font-size: 11px; font-weight: bold;
            border: 1px solid #bdc3c7; border-radius: 4px;
            padding: 4px; background-color: white;
        """)
        ligne1.addWidget(self.lbl_periode)

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(36, 36)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50; color: white;
                border-radius: 4px; font-size: 14px;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.btn_next.clicked.connect(self._periode_suivante)
        ligne1.addWidget(self.btn_next)

        ligne1.addSpacing(20)
        ligne1.addWidget(QLabel("Scale :"))

        self._periode_courante = "1 week"
        self.periode_buttons = {}
        for nom in PERIODES.keys():
            btn = QPushButton(nom)
            btn.setFixedHeight(30)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ecf0f1; color: #2c3e50;
                    border: 1px solid #bdc3c7; border-radius: 4px;
                    padding: 0 10px; font-size: 12px;
                }
                QPushButton:checked {
                    background-color: #2c3e50; color: white;
                    border: 1px solid #2c3e50;
                }
                QPushButton:hover:!checked { background-color: #d5d8dc; }
            """)
            btn.clicked.connect(lambda checked, n=nom: self._on_periode_btn(n))
            ligne1.addWidget(btn)
            self.periode_buttons[nom] = btn

        self.periode_buttons["1 week"].setChecked(True)
        ligne1.addStretch()
        layout.addLayout(ligne1)

        # Ligne 2 — Légende + info drag
        ligne2 = QHBoxLayout()
        STATUT_LABELS_EN = {
            "planifiee": "Scheduled",
            "en_cours":  "In Progress",
            "terminee":  "Completed",
            "rebutee":   "Scrapped",
        }
        for statut, couleur in COULEURS_STATUT.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {couleur.name()}; font-size: 16px;")
            lbl = QLabel(STATUT_LABELS_EN.get(statut, statut.capitalize()))
            lbl.setStyleSheet("font-size: 12px; margin-right: 12px;")
            ligne2.addWidget(dot)
            ligne2.addWidget(lbl)

        ligne2.addSpacing(20)
        info = QLabel("💡 Drag a task to reschedule it")
        info.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        ligne2.addWidget(info)
        ligne2.addStretch()
        layout.addLayout(ligne2)

        # Ligne 3 — Curseur de défilement temporel
        ligne3 = QHBoxLayout()
        lbl_slider = QLabel("⏱")
        lbl_slider.setStyleSheet("font-size: 14px;")
        ligne3.addWidget(lbl_slider)

        from PySide6.QtWidgets import QSlider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.setValue(500)
        self._slider.setFixedHeight(22)
        self._slider.setStyleSheet("""
                    QSlider::groove:horizontal {
                        height: 6px;
                        background: #bdc3c7;
                        border-radius: 3px;
                    }
                    QSlider::handle:horizontal {
                        background: #2c3e50;
                        border: none;
                        width: 18px; height: 18px;
                        margin: -6px 0;
                        border-radius: 9px;
                    }
                    QSlider::sub-page:horizontal {
                        background: #3498db;
                        border-radius: 3px;
                    }
                """)
        self._slider_updating = False
        self._slider.valueChanged.connect(self._on_slider_changed)
        ligne3.addWidget(self._slider)

        self.lbl_slider_date = QLabel("")
        self.lbl_slider_date.setFixedWidth(130)
        self.lbl_slider_date.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        ligne3.addWidget(self.lbl_slider_date)
        layout.addLayout(ligne3)

        # Zone scrollable
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #dde;
                border-radius: 4px;
                background-color: white;
            }
        """)
        layout.addWidget(self.scroll)
        # Auto-refresh every 60 seconds — skipped if a dialog is open
        from PySide6.QtCore import QTimer
        self._timer = QTimer()
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(60000)
        self._dialog_open = False

        # Debounce resize: rebuild Gantt only after 120ms of no resize events
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._rebuild_gantt)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(120)

    def _on_periode_btn(self, nom):
        self._periode_courante = nom
        for n, btn in self.periode_buttons.items():
            btn.setChecked(n == nom)
        # Recentre sur maintenant lors d'un changement d'échelle
        heures = PERIODES[nom]
        now    = datetime.now().replace(minute=0, second=0, microsecond=0)
        # Snap to the current shift start (6, 14 or 22)
        h = now.hour
        if h < 6:
            shift_start = now.replace(hour=22) - timedelta(days=1)
        elif h < 14:
            shift_start = now.replace(hour=6)
        elif h < 22:
            shift_start = now.replace(hour=14)
        else:
            shift_start = now.replace(hour=22)
        self._fenetre_debut = shift_start - timedelta(hours=heures / 2)
        self._rebuild_gantt()

    def _periode_precedente(self):
        if self._fenetre_debut is None:
            return
        heures = PERIODES[self._periode_courante]
        self._fenetre_debut -= timedelta(hours=heures)
        self._rebuild_gantt()

    def _periode_suivante(self):
        if self._fenetre_debut is None:
            return
        heures = PERIODES[self._periode_courante]
        self._fenetre_debut += timedelta(hours=heures)
        self._rebuild_gantt()

    def _on_slider_changed(self, value):
        if self._slider_updating:
            return
        if self._ops_min_date is None:
            return
        range_start = self._ops_min_date - timedelta(days=7)
        range_end = datetime.now() + timedelta(days=60)
        total_hours = max((range_end - range_start).total_seconds() / 3600, 1)
        offset_hours = (value / 1000.0) * total_hours
        self._fenetre_debut = range_start + timedelta(hours=offset_hours)
        self._rebuild_gantt()

    def _sync_slider_to_fenetre(self):
        if self._fenetre_debut is None or self._ops_min_date is None:
            return
        self._slider_updating = True
        range_start = self._ops_min_date - timedelta(days=7)
        range_end = datetime.now() + timedelta(days=60)
        total_hours = max((range_end - range_start).total_seconds() / 3600, 1)
        offset_hours = (self._fenetre_debut - range_start).total_seconds() / 3600
        val = int(max(0, min(1000, (offset_hours / total_hours) * 1000)))
        self._slider.setValue(val)
        self.lbl_slider_date.setText(self._fenetre_debut.strftime("%d/%m/%Y %H:%M"))
        self._slider_updating = False

    def _rebuild_gantt(self):
        if not self._machines_data or self._fenetre_debut is None:
            return

        heures      = PERIODES[self._periode_courante]
        fenetre_fin = self._fenetre_debut + timedelta(hours=heures)
        grid_step   = GRID_STEP[self._periode_courante]

        fmt_debut = self._fenetre_debut.strftime("%d/%m/%Y %H:%M")
        fmt_fin   = fenetre_fin.strftime("%d/%m/%Y %H:%M")
        self.lbl_periode.setText(f"{fmt_debut}\n→ {fmt_fin}")

        available_w = max(self.scroll.width() - LABEL_WIDTH - 20, 200)
        px_per_hour = available_w / heures

        if self._gantt is None:
            self._gantt = GanttWidget(
                self._machines_data, self._ops_data,
                self._fenetre_debut, fenetre_fin, px_per_hour,
                on_deplacement=self._charger_planning
            )
            self.scroll.setWidget(self._gantt)
        else:
            self._gantt.operations     = self._ops_data
            self._gantt.machines       = self._machines_data
            self._gantt.on_deplacement = self._charger_planning
            self._gantt.set_px_per_hour(px_per_hour,
                                        self._fenetre_debut, fenetre_fin)

        # Transmet le pas de grille au widget
        self._gantt._grid_step = grid_step
        self._gantt.update()
        self._sync_slider_to_fenetre()

    def _auto_refresh(self):
        """Auto-refresh: skip if a dialog is open or a drag is in progress."""
        if self._dialog_open:
            return
        if self._gantt and (self._gantt._dragging or self._gantt._drag_pending):
            return
        self._charger_planning()

    def _recalculer_planning(self):
        """Replanifie toutes les ops planifiées au plus tôt et recharge la vue."""
        reply = QMessageBox.question(
            self,
            "Recalculate planning",
            "This will reschedule ALL planned operations from scratch "
            "(earliest possible, respecting routing order).\n\n"
            "In-progress and completed operations are not affected.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        session = SessionLocal()
        try:
            result = recalculer_planning_global(session)
            session.commit()
            QMessageBox.information(
                self,
                "Done",
                f"Planning recalculated:\n"
                f"  • {result['nb_ofs']} production order(s)\n"
                f"  • {result['nb_ops']} operation(s) rescheduled"
            )
            self._gantt = None
            self._charger_planning()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _charger_planning(self):
        from sqlalchemy.orm import joinedload
        from models import OrdreFabrication, OFAssemblage, LigneCommande, Commande
        session = SessionLocal()
        try:
            machines   = session.query(Machine).order_by(Machine.nom).all()
            operations = session.query(OperationPlanifiee).filter(
                OperationPlanifiee.date_debut.isnot(None),
                OperationPlanifiee.date_fin.isnot(None)
            ).options(
                joinedload(OperationPlanifiee.machine),
                joinedload(OperationPlanifiee.service),
                joinedload(OperationPlanifiee.operation),
                joinedload(OperationPlanifiee.of).joinedload(OrdreFabrication.composant),
                joinedload(OperationPlanifiee.of)
                    .joinedload(OrdreFabrication.of_assemblage)
                    .joinedload(OFAssemblage.ligne_commande)
                    .joinedload(LigneCommande.commande),
            ).all()

            self._ops_min_date = min((op.date_debut for op in operations), default=None)
            if self._fenetre_debut is None:
                # Centre la fenêtre sur maintenant, aligné sur le début de la pause en cours
                heures = PERIODES[self._periode_courante]
                now    = datetime.now().replace(minute=0, second=0, microsecond=0)
                h = now.hour
                if h < 6:
                    shift_start = now.replace(hour=22) - timedelta(days=1)
                elif h < 14:
                    shift_start = now.replace(hour=6)
                elif h < 22:
                    shift_start = now.replace(hour=14)
                else:
                    shift_start = now.replace(hour=22)
                self._fenetre_debut = shift_start - timedelta(hours=heures / 2)

            from models.produit import Service as ServiceModel
            all_services = session.query(ServiceModel).order_by(ServiceModel.nom).all()

            # Build previous active_shifts memory map (id_machine → set)
            prev_shifts = {}
            if self._machines_data:
                for m in self._machines_data:
                    if m.get("type") == "machine" and "active_shifts" in m:
                        prev_shifts[m["id"]] = m["active_shifts"]

            # Load all shift configs in a single query
            shifts_by_machine = {}
            try:
                from models.production import MachineShiftConfig
                shift_rows = session.query(MachineShiftConfig).all()
                for r in shift_rows:
                    shifts_by_machine.setdefault(r.id_machine, {})[r.shift_index] = r.active
            except Exception:
                pass

            def _get_active_shifts(id_machine):
                cfg = shifts_by_machine.get(id_machine)
                if cfg is None:
                    return prev_shifts.get(id_machine, None)
                return {i for i in range(3) if cfg.get(i, True)}

            self._machines_data = [
                {"id": m.id_machine, "nom": m.nom, "type": "machine",
                 "row_id": f"m_{m.id_machine}",
                 "capacite_h_jour": float(m.capacite_h_jour) if m.capacite_h_jour else None,
                 "active_shifts": _get_active_shifts(m.id_machine)}
                for m in machines
            ] + [
                {"id": s.id_service, "nom": s.nom, "type": "service",
                 "row_id": f"s_{s.id_service}"}
                for s in all_services
            ]
            self._ops_data = [
                {
                    "id_op_plan": op.id_op_plan,
                    "id_machine": op.id_machine,
                    "id_service": op.id_service if hasattr(op, "id_service") else None,
                    "row_id": f"m_{op.id_machine}" if op.id_machine else f"s_{op.id_service}",
                    "machine_nom": op.machine.nom if op.machine else (
                        op.service.nom if hasattr(op, "service") and op.service else "—"
                    ),
                    "id_of": op.id_of,
                    "id_composant": op.of.id_composant if op.of else None,
                    "code_of": op.of.code_of if op.of else "—",
                    "statut": op.statut,
                    "date_debut": op.date_debut,
                    "date_fin": op.date_fin,
                    "date_debut_reelle": op.date_debut_reelle,
                    "duree_gamme_min": (
                        int(op.duree_reelle_min) if op.duree_reelle_min
                        else (
                            int(op.operation.tps_preparation +
                                op.operation.tps_execution * float(op.of.quantite))
                            if op.operation and op.of
                            else (
                                int((op.date_fin - op.date_debut).total_seconds() / 60)
                                if op.date_debut and op.date_fin else None
                            )
                        )
                    ),
                    "description": (
                        op.operation.description if op.operation else "—"
                    ),
                    "composant": (
                        op.of.composant.nom
                        if op.of and op.of.composant else "—"
                    ),
                    "num_commande": (
                        str(op.of.of_assemblage.ligne_commande.commande.code_commande
                            or op.of.of_assemblage.ligne_commande.id_commande)
                        if op.of and op.of.of_assemblage
                           and op.of.of_assemblage.ligne_commande
                           and op.of.of_assemblage.ligne_commande.commande
                        else "—"
                    )
                }
                for op in operations
            ]
            # Reset selection state on reload to avoid stale references
            if self._gantt:
                self._gantt._selected_op            = None
                self._gantt._selected_composant_id  = None
                self._gantt._hovered_op            = None
                self._gantt._dragging              = False
                self._gantt._drag_op               = None
            self._gantt = None
            self._rebuild_gantt()

        finally:
            session.close()