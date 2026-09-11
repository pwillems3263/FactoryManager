from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QStackedWidget, QLabel,
    QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.views.accueil_view import AccueilView
from ui.views.commandes_view import CommandesView
from ui.views.production_tracking_view import ProductionTrackingView
from ui.views.planning_view import PlanningView
from ui.views.of_view import OFView
from ui.views.rebuts_view import RebutsView
from ui.views.assemblages_view import AssemblagesView
from ui.views.composants_view import ComposantsView
from ui.views.services_view import ServicesView
from ui.views.pieces_externes_view import PiecesExternesView
from ui.views.matieres_view import MatieresView
from ui.views.machines_view import MachinesView
from ui.views.users_view import UsersView, CurrentUser
from ui.views.db_config_view import DBConfigView
from ui.views.pointage_view import PointageView


# Page index constants — single source of truth
PAGE_DASHBOARD          = 0
PAGE_ORDERS             = 1
PAGE_PRODUCTION         = 2
PAGE_PLANNING           = 3
PAGE_OF                 = 4
PAGE_SCRAP              = 5
PAGE_ASSEMBLIES         = 6
PAGE_COMPONENTS         = 7
PAGE_SERVICES           = 8
PAGE_EXTERNAL_PARTS     = 9
PAGE_MATERIALS          = 10
PAGE_MACHINES           = 11
PAGE_USERS              = 12
PAGE_TIME_TRACKING      = 13


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FactoryManager")
        self.setMinimumSize(1280, 800)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Navigation sidebar ────────────────────────────────────────────────
        nav = QWidget()
        nav.setFixedWidth(210)
        nav.setStyleSheet("background-color: #2c3e50;")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        user = CurrentUser.get()
        user_label = f"{user.full_name or user.username}\n{user.niveau_label()}" if user else "—"
        user_color = user.niveau_color() if user else "#7f8c8d"

        title_widget = QWidget()
        title_widget.setFixedHeight(70)
        title_widget.setStyleSheet("background-color: #1a252f;")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(10, 8, 10, 8)
        title_layout.setSpacing(2)

        app_title = QLabel("FactoryManager")
        app_title.setAlignment(Qt.AlignCenter)
        app_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")

        user_info = QLabel(user_label)
        user_info.setAlignment(Qt.AlignCenter)
        user_info.setStyleSheet(f"color: {user_color}; font-size: 10px; font-weight: bold;")

        title_layout.addWidget(app_title)
        title_layout.addWidget(user_info)
        nav_layout.addWidget(title_widget)

        btn_style = """
            QPushButton {
                color: #ecf0f1;
                background-color: transparent;
                border: none;
                text-align: left;
                padding-left: 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:checked {
                background-color: #3498db;
                border-left: 4px solid #2980b9;
            }
        """

        def section_label(text):
            lbl = QLabel(text)
            lbl.setFixedHeight(28)
            lbl.setStyleSheet("""
                color: #7f8c8d;
                font-size: 10px;
                font-weight: bold;
                padding-left: 16px;
                background-color: #1a252f;
                letter-spacing: 1px;
            """)
            return lbl

        production_modules = [
            ("🏠  Dashboard",           PAGE_DASHBOARD,     "dashboard"),
            ("📋  Orders",              PAGE_ORDERS,        "orders"),
            ("🔄  Assemblies Orders",   PAGE_OF,            "planning"),
            ("📅  Planning",            PAGE_PLANNING,      "planning"),
            ("📊  Production Tracking", PAGE_PRODUCTION,    "production"),
            ("🕐  Time Tracking",       PAGE_TIME_TRACKING, "production"),
            ("⚠️   Scrap",              PAGE_SCRAP,         "scrap"),
        ]
        config_modules = [
            ("🔩  Assemblies",      PAGE_ASSEMBLIES,    "assemblies"),
            ("⚙️   Components",     PAGE_COMPONENTS,    "components"),
            ("🔧  Services",        PAGE_SERVICES,      "services"),
            ("📦  External Parts",  PAGE_EXTERNAL_PARTS,"external_parts"),
            ("🧱  Materials",       PAGE_MATERIALS,     "materials"),
            ("🏭  Machines",        PAGE_MACHINES,      "machines"),
            ("👤  Users",           PAGE_USERS,         "users"),
        ]

        self.nav_buttons = []
        first_allowed = None

        nav_layout.addWidget(section_label("── PRODUCTION ──"))
        for label, index, perm in production_modules:
            btn = QPushButton(label)
            btn.setFixedHeight(46)
            btn.setStyleSheet(btn_style)
            btn.setCheckable(True)
            allowed = CurrentUser.can(perm)
            btn.setVisible(allowed)
            if allowed:
                btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
                self.nav_buttons.append((index, btn))
                if first_allowed is None:
                    first_allowed = index
            nav_layout.addWidget(btn)

        nav_layout.addWidget(section_label("── CONFIGURATION ──"))
        for label, index, perm in config_modules:
            btn = QPushButton(label)
            btn.setFixedHeight(46)
            btn.setStyleSheet(btn_style)
            btn.setCheckable(True)
            allowed = CurrentUser.can(perm)
            btn.setVisible(allowed)
            if allowed:
                btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
                self.nav_buttons.append((index, btn))
                if first_allowed is None:
                    first_allowed = index
            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        if CurrentUser.can("users"):
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #34495e;")
            nav_layout.addWidget(sep)

            btn_db = QPushButton("⚙  DB Config")
            btn_db.setFixedHeight(38)
            btn_db.setStyleSheet(btn_style)
            btn_db.clicked.connect(lambda: DBConfigView(self).exec())
            nav_layout.addWidget(btn_db)

        version = QLabel("v0.2.0")
        version.setAlignment(Qt.AlignCenter)
        version.setFixedHeight(30)
        version.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        nav_layout.addWidget(version)

        # ── Pages (must be added in index order 0..N) ─────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #f5f6fa;")

        # All 14 pages in order — index matches PAGE_* constants above
        all_pages = [
            (AccueilView,            "dashboard"),       # 0
            (CommandesView,          "orders"),          # 1
            (ProductionTrackingView, "production"),      # 2
            (PlanningView,           "planning"),        # 3
            (OFView,                 "planning"),        # 4
            (RebutsView,             "scrap"),           # 5
            (AssemblagesView,        "assemblies"),      # 6
            (ComposantsView,         "components"),      # 7
            (ServicesView,           "services"),        # 8
            (PiecesExternesView,     "external_parts"),  # 9
            (MatieresView,           "materials"),       # 10
            (MachinesView,           "machines"),        # 11
            (UsersView,              "users"),           # 12
            (PointageView,           "production"),      # 13
        ]

        for cls, perm in all_pages:
            if CurrentUser.can(perm):
                self.stack.addWidget(cls())
            else:
                self.stack.addWidget(QWidget())

        layout.addWidget(nav)
        layout.addWidget(self.stack)

        if first_allowed is not None:
            self._switch_page(first_allowed)

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for idx, btn in self.nav_buttons:
            btn.setChecked(idx == index)

        try:
            w = self.stack.widget(index)
            if index == PAGE_DASHBOARD and hasattr(w, '_charger_donnees'):
                w._charger_donnees()
            elif index == PAGE_COMPONENTS and hasattr(w, '_charger_composants'):
                w._charger_composants()
            elif index == PAGE_ASSEMBLIES and hasattr(w, '_charger_assemblages'):
                w._charger_assemblages()
            elif index == PAGE_PRODUCTION and hasattr(w, '_charger_donnees'):
                w._charger_donnees()
            elif index == PAGE_PLANNING and hasattr(w, '_charger_planning'):
                w._charger_planning()
            elif index == PAGE_OF and hasattr(w, '_charger_ofs'):
                w._charger_ofs()
            elif index == PAGE_TIME_TRACKING and hasattr(w, '_charger_machines'):
                w._charger_machines()
        except Exception as e:
            print(f"[switch_page] Error loading page {index}: {e}")