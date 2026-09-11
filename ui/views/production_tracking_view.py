from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from database import SessionLocal
from models import OrdreFabrication, OFAssemblage, LigneCommande, Commande, OperationPlanifiee


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(dt, with_time=False):
    if not dt:
        return "—"
    if with_time:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d")


def _fmt_duration(minutes):
    """Convert integer minutes to 'Xh YYm' string."""
    if minutes is None:
        return "—"
    minutes = int(minutes)
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _calc_reel_minutes(op_plan):
    """Sum tps_prep_reel + tps_exec_reel if both present, else derive from real dates."""
    prep = op_plan.tps_prep_reel or 0
    exec_ = op_plan.tps_exec_reel or 0
    if prep or exec_:
        return prep + exec_

    if op_plan.date_debut_reelle and op_plan.date_fin_reelle:
        delta = op_plan.date_fin_reelle - op_plan.date_debut_reelle
        return int(delta.total_seconds() / 60)

    return None


def _calc_prevu_minutes(op):
    """Return planned total minutes from operation definition."""
    return (op.tps_preparation or 0) + (op.tps_execution or 0)


# ── main view ─────────────────────────────────────────────────────────────────

class ProductionTrackingView(QWidget):
    def __init__(self):
        super().__init__()
        self._data = []
        self._build_ui()
        self._charger_donnees()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        titre = QLabel("Production Tracking")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet(self._btn_style("#3498db", "#2980b9"))
        btn_refresh.clicked.connect(self._charger_donnees)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        # ── Filter / Sort controls ───────────────────────────────────────────
        controls = QHBoxLayout()
        btn_style_filter = """
            QPushButton {
                background-color: #ecf0f1; color: #2c3e50;
                border: 1px solid #bdc3c7; border-radius: 4px;
                padding: 0 10px; font-size: 12px; height: 28px;
            }
            QPushButton:checked {
                background-color: #2c3e50; color: white;
                border: 1px solid #2c3e50;
            }
            QPushButton:hover:!checked { background-color: #d5d8dc; }
        """

        controls.addWidget(QLabel("Filter :"))
        self._filter_active = "All"
        self._filter_buttons = {}
        for label in ["All", "On Hold", "Planned", "In Progress", "Completed", "Cancelled"]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setStyleSheet(btn_style_filter)
            btn.clicked.connect(lambda checked, l=label: self._on_filter_btn(l))
            controls.addWidget(btn)
            self._filter_buttons[label] = btn
        self._filter_buttons["All"].setChecked(True)

        controls.addSpacing(20)
        controls.addWidget(QLabel("Sort :"))
        self._sort_active = "Order Code"
        self._sort_buttons = {}
        for label in ["Order Code", "Component", "Due Date", "Status"]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setStyleSheet(btn_style_filter)
            btn.clicked.connect(lambda checked, l=label: self._on_sort_btn(l))
            controls.addWidget(btn)
            self._sort_buttons[label] = btn
        self._sort_buttons["Order Code"].setChecked(True)

        controls.addStretch()
        self.lbl_count = QLabel("0 item(s)")
        self.lbl_count.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        controls.addWidget(self.lbl_count)
        layout.addLayout(controls)

        # ── Splitter (top = OF table, bottom = gamme panel) ─────────────────
        splitter = QSplitter(Qt.Vertical)

        # ── Top: OF table ────────────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Code OF", "Order", "Order Date", "Assembly",
            "Component", "Quantity", "Due Date", "Delivery Date", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setStyleSheet(self._table_style())
        self.table.selectionModel().selectionChanged.connect(self._afficher_gamme)
        top_layout.addWidget(self.table)
        splitter.addWidget(top_widget)

        # ── Bottom: Gamme panel ───────────────────────────────────────────────
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 10, 0, 0)

        gamme_header = QHBoxLayout()
        self.gamme_titre = QLabel("Manufacturing Routing")
        self.gamme_titre.setFont(QFont("Arial", 12, QFont.Bold))
        gamme_header.addWidget(self.gamme_titre)
        gamme_header.addStretch()

        # Legend badges
        for txt, color in [
            ("● Planned", "#3498db"),
            ("● In Progress", "#8e44ad"),
            ("● Completed", "#27ae60"),
            ("● On Hold", "#e67e22"),
        ]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; margin-right: 8px;")
            gamme_header.addWidget(lbl)

        bottom_layout.addLayout(gamme_header)

        self.gamme_table = QTableWidget()
        self.gamme_table.setColumnCount(8)
        self.gamme_table.setHorizontalHeaderLabels([
            "Order", "Description", "Resource",
            "Planned Start", "Planned End",
            "Planned Time", "Actual Time", "Status"
        ])
        self.gamme_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.gamme_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.gamme_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.gamme_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.gamme_table.setAlternatingRowColors(True)
        self.gamme_table.setStyleSheet(self._table_style())
        bottom_layout.addWidget(self.gamme_table)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([380, 280])
        layout.addWidget(splitter)

    # ── Style helpers ─────────────────────────────────────────────────────────

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

    # ── Data loading ──────────────────────────────────────────────────────────

    def _charger_donnees(self):
        session = SessionLocal()
        try:
            ofs = session.query(OrdreFabrication).all()
            self._data = []

            statut_map = {
                "a_planifier": ("On Hold",    "#e67e22"),
                "planifie":    ("Planned",    "#3498db"),
                "en_cours":    ("In Progress","#8e44ad"),
                "termine":     ("Completed",  "#27ae60"),
                "annule":      ("Cancelled",  "#e74c3c"),
                "rebute":      ("Scrapped",   "#c0392b"),
            }

            for of in ofs:
                ofa = of.of_assemblage
                if not ofa:
                    continue
                ligne = ofa.ligne_commande
                if not ligne:
                    continue
                commande = ligne.commande
                if not commande:
                    continue

                statut_txt, statut_color = statut_map.get(of.statut, (of.statut, "#95a5a6"))

                self._data.append({
                    "id_of":         of.id_of,
                    "code_of":       of.code_of or "—",
                    "order_code":    commande.code_commande or "—",
                    "order_date":    commande.date_commande,
                    "assembly":      ofa.assemblage.nom if ofa.assemblage else "—",
                    "component":     of.composant.nom if of.composant else "—",
                    "id_composant":  of.id_composant,
                    "quantity":      float(of.quantite),
                    "due_date":      of.date_fin_prevue,
                    "delivery_date": commande.date_livraison,
                    "statut":        of.statut,
                    "statut_txt":    statut_txt,
                    "statut_color":  statut_color,
                })
        finally:
            session.close()

        self._appliquer_filtres()

    # ── Filter / Sort ─────────────────────────────────────────────────────────

    def _on_filter_btn(self, label):
        self._filter_active = label
        for l, btn in self._filter_buttons.items():
            btn.setChecked(l == label)
        self._appliquer_filtres()

    def _on_sort_btn(self, label):
        self._sort_active = label
        for l, btn in self._sort_buttons.items():
            btn.setChecked(l == label)
        self._appliquer_filtres()

    def _appliquer_filtres(self):
        filtre_map = {
            "All":         None,
            "On Hold":     "a_planifier",
            "Planned":     "planifie",
            "In Progress": "en_cours",
            "Completed":   "termine",
            "Cancelled":   "annule",
        }
        statut_filtre = filtre_map.get(self._filter_active)
        data = [
            d for d in self._data
            if statut_filtre is None or d["statut"] == statut_filtre
        ]

        tri_map = {
            "Order Code": lambda d: d["order_code"],
            "Component":  lambda d: d["component"],
            "Due Date":   lambda d: str(d["due_date"] or ""),
            "Status":     lambda d: d["statut"],
        }
        data.sort(key=tri_map.get(self._sort_active, lambda d: d["order_code"]))

        self.table.setRowCount(len(data))
        for row, d in enumerate(data):
            id_item = QTableWidgetItem(d["code_of"])
            id_item.setData(Qt.UserRole, d["id_of"])
            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, QTableWidgetItem(d["order_code"]))
            self.table.setItem(row, 2, QTableWidgetItem(
                _fmt_date(d["order_date"])
            ))
            self.table.setItem(row, 3, QTableWidgetItem(d["assembly"]))
            self.table.setItem(row, 4, QTableWidgetItem(d["component"]))
            self.table.setItem(row, 5, QTableWidgetItem(f"{d['quantity']:.3f}"))
            self.table.setItem(row, 6, QTableWidgetItem(_fmt_date(d["due_date"])))
            self.table.setItem(row, 7, QTableWidgetItem(_fmt_date(d["delivery_date"])))

            statut_item = QTableWidgetItem(d["statut_txt"])
            statut_item.setForeground(QColor(d["statut_color"]))
            statut_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.table.setItem(row, 8, statut_item)

        self.lbl_count.setText(f"{len(data)} item(s)")

        # Clear gamme panel when filter changes
        self.gamme_table.setRowCount(0)
        self.gamme_titre.setText("Manufacturing Routing")

    # ── Gamme panel ───────────────────────────────────────────────────────────

    def _afficher_gamme(self):
        row = self.table.currentRow()
        if row < 0:
            self.gamme_table.setRowCount(0)
            self.gamme_titre.setText("Manufacturing Routing")
            return

        id_of = self.table.item(row, 0).data(Qt.UserRole) if self.table.item(row, 0) else None
        component_name = self.table.item(row, 4).text() if self.table.item(row, 4) else "—"
        order_code = self.table.item(row, 1).text() if self.table.item(row, 1) else "—"

        if id_of is None:
            self.gamme_table.setRowCount(0)
            return

        self.gamme_titre.setText(
            f"Manufacturing Routing  —  {component_name}  |  Order {order_code}"
        )

        # Statut maps
        op_statut_map = {
            "planifiee": ("Planned",     "#3498db"),
            "en_cours":  ("In Progress", "#8e44ad"),
            "terminee":  ("Completed",   "#27ae60"),
            "rebutee":   ("Scrapped",    "#c0392b"),
        }

        session = SessionLocal()
        try:
            of = session.get(OrdreFabrication, id_of)
            if not of:
                self.gamme_table.setRowCount(0)
                return

            # Get all planned operations for this OF, ordered by operation order
            ops_plan = (
                session.query(OperationPlanifiee)
                .filter(OperationPlanifiee.id_of == id_of)
                .join(OperationPlanifiee.operation)
                .order_by(OperationPlanifiee.operation.property.mapper.class_.ordre)
                .all()
            )

            # If no planned ops yet, fall back to the component gamme definition
            if not ops_plan:
                self._afficher_gamme_theorique(of, session, op_statut_map)
                return

            self.gamme_table.setRowCount(len(ops_plan))

            for row_idx, op_plan in enumerate(ops_plan):
                op = op_plan.operation

                # Resource name
                if op_plan.machine:
                    resource = op_plan.machine.nom
                elif op_plan.service:
                    resource = f"[Svc] {op_plan.service.nom}"
                elif op.machine:
                    resource = op.machine.nom
                elif op.piece_externe:
                    resource = f"[Ext] {op.piece_externe.nom}"
                elif op.service:
                    resource = f"[Svc] {op.service.nom}"
                else:
                    resource = "—"

                # Planned time (from operation definition)
                prevu_min = _calc_prevu_minutes(op)

                # Actual time
                reel_min = _calc_reel_minutes(op_plan)

                statut_txt, statut_color = op_statut_map.get(
                    op_plan.statut, (op_plan.statut, "#95a5a6")
                )

                # ── Fill cells ──────────────────────────────────────────────
                ordre_item = QTableWidgetItem(str(op.ordre))
                ordre_item.setTextAlignment(Qt.AlignCenter)
                self.gamme_table.setItem(row_idx, 0, ordre_item)

                self.gamme_table.setItem(row_idx, 1,
                    QTableWidgetItem(op.description or "—"))

                self.gamme_table.setItem(row_idx, 2,
                    QTableWidgetItem(resource))

                self.gamme_table.setItem(row_idx, 3,
                    QTableWidgetItem(_fmt_date(op_plan.date_debut, with_time=True)))

                self.gamme_table.setItem(row_idx, 4,
                    QTableWidgetItem(_fmt_date(op_plan.date_fin, with_time=True)))

                self.gamme_table.setItem(row_idx, 5,
                    QTableWidgetItem(_fmt_duration(prevu_min)))

                # Actual time cell — styled if completed
                reel_item = QTableWidgetItem(_fmt_duration(reel_min))
                if op_plan.statut == "terminee" and reel_min is not None:
                    if reel_min > prevu_min:
                        reel_item.setForeground(QColor("#e74c3c"))  # over time → red
                    else:
                        reel_item.setForeground(QColor("#27ae60"))  # under time → green
                self.gamme_table.setItem(row_idx, 6, reel_item)

                statut_item = QTableWidgetItem(statut_txt)
                statut_item.setForeground(QColor(statut_color))
                statut_item.setFont(QFont("Arial", 10, QFont.Bold))
                statut_item.setTextAlignment(Qt.AlignCenter)
                self.gamme_table.setItem(row_idx, 7, statut_item)

                # Shade completed rows lightly
                if op_plan.statut == "terminee":
                    for col in range(8):
                        cell = self.gamme_table.item(row_idx, col)
                        if cell:
                            cell.setBackground(QColor("#f0faf4"))

        finally:
            session.close()

    def _afficher_gamme_theorique(self, of, session, op_statut_map):
        """
        Fallback: show the gamme definition when no OperationPlanifiee exist yet.
        """
        # Find active gamme for this component
        from models import Gamme
        gamme = (
            session.query(Gamme)
            .filter_by(id_composant=of.id_composant, active=True)
            .first()
        )
        if not gamme or not gamme.operations:
            self.gamme_table.setRowCount(0)
            return

        ops = sorted(gamme.operations, key=lambda o: o.ordre)
        self.gamme_table.setRowCount(len(ops))

        for row_idx, op in enumerate(ops):
            if op.machine:
                resource = op.machine.nom
            elif op.piece_externe:
                resource = f"[Ext] {op.piece_externe.nom}"
            elif op.service:
                resource = f"[Svc] {op.service.nom}"
            else:
                resource = "—"

            prevu_min = _calc_prevu_minutes(op)

            ordre_item = QTableWidgetItem(str(op.ordre))
            ordre_item.setTextAlignment(Qt.AlignCenter)
            self.gamme_table.setItem(row_idx, 0, ordre_item)

            self.gamme_table.setItem(row_idx, 1, QTableWidgetItem(op.description or "—"))
            self.gamme_table.setItem(row_idx, 2, QTableWidgetItem(resource))

            # No planning dates yet
            self.gamme_table.setItem(row_idx, 3, QTableWidgetItem("—"))
            self.gamme_table.setItem(row_idx, 4, QTableWidgetItem("—"))

            self.gamme_table.setItem(row_idx, 5, QTableWidgetItem(_fmt_duration(prevu_min)))
            self.gamme_table.setItem(row_idx, 6, QTableWidgetItem("—"))

            statut_item = QTableWidgetItem("Not Planned")
            statut_item.setForeground(QColor("#95a5a6"))
            statut_item.setFont(QFont("Arial", 10, QFont.Bold))
            statut_item.setTextAlignment(Qt.AlignCenter)
            self.gamme_table.setItem(row_idx, 7, statut_item)