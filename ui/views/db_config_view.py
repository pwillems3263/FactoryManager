"""
db_config_view.py
-----------------
Dialog PySide6 de configuration de la connexion PostgreSQL.
Nommé *_view.py pour respecter la convention du projet.

Emplacement : ui/views/db_config_view.py

Accessible depuis :
  - LoginDialog  → bouton "⚙ DB Settings" (visible pour tous)
  - MainWindow   → bouton dans la nav (niveau 4 uniquement)

Usage :
    from ui.views.db_config_view import DBConfigView
    dlg = DBConfigView(parent=self)
    dlg.exec()
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from db_config import load_env, save_env, test_connection


class DBConfigView(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Configuration")
        self.setMinimumWidth(440)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self._build_ui()
        self._load_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        # ── Titre ──────────────────────────────────────────────────────
        title = QLabel("🗄  PostgreSQL Connection")
        title.setFont(QFont("Arial", 15, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        sub = QLabel(
            "These settings are saved in the <b>.env</b> file at the project root.<br>"
            "A restart is required after saving."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(sub)

        # ── Séparateur ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #dfe6e9;")
        layout.addWidget(sep)

        # ── Formulaire ─────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("e.g. localhost or 192.168.1.10")
        self.host_input.setMinimumHeight(34)
        self.host_input.setStyleSheet(self._input_style())
        form.addRow("Host :", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(5432)
        self.port_input.setMinimumHeight(34)
        self.port_input.setStyleSheet(self._input_style())
        form.addRow("Port :", self.port_input)

        self.dbname_input = QLineEdit()
        self.dbname_input.setPlaceholderText("e.g. FactoryManager")
        self.dbname_input.setMinimumHeight(34)
        self.dbname_input.setStyleSheet(self._input_style())
        form.addRow("Database :", self.dbname_input)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("e.g. postgres")
        self.user_input.setMinimumHeight(34)
        self.user_input.setStyleSheet(self._input_style())
        form.addRow("Username :", self.user_input)

        # Password + bouton show/hide
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("••••••••")
        self.pass_input.setMinimumHeight(34)
        self.pass_input.setStyleSheet(self._input_style())

        pass_row = QHBoxLayout()
        pass_row.setSpacing(6)
        pass_row.addWidget(self.pass_input)

        btn_eye = QPushButton("👁")
        btn_eye.setFixedSize(34, 34)
        btn_eye.setCheckable(True)
        btn_eye.setStyleSheet("""
            QPushButton {
                border: 1px solid #bdc3c7; border-radius: 4px;
                background: white; font-size: 14px;
            }
            QPushButton:checked { background: #d6eaf8; }
        """)
        btn_eye.toggled.connect(
            lambda on: self.pass_input.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )
        pass_row.addWidget(btn_eye)
        form.addRow("Password :", pass_row)

        layout.addLayout(form)

        # ── Statut test ────────────────────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(28)
        self.status_label.setStyleSheet(
            "border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        # ── Boutons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_test = QPushButton("🔌  Test Connection")
        btn_test.setMinimumHeight(38)
        btn_test.setStyleSheet(self._btn_style("#27ae60", "#1e8449"))
        btn_test.clicked.connect(self._test)
        btn_row.addWidget(btn_test)

        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setMinimumHeight(38)
        btn_cancel.setMinimumWidth(90)
        btn_cancel.setStyleSheet("""
            QPushButton {
                border: 1px solid #bdc3c7; border-radius: 6px;
                background: white; color: #2c3e50; font-size: 13px;
            }
            QPushButton:hover { background: #f0f3f4; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("💾  Save")
        btn_save.setMinimumHeight(38)
        btn_save.setMinimumWidth(100)
        btn_save.setStyleSheet(self._btn_style("#3498db", "#2980b9"))
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _load_current(self):
        params = load_env()
        self.host_input.setText(params.get("DB_HOST", "localhost"))
        self.port_input.setValue(int(params.get("DB_PORT", 5432)))
        self.dbname_input.setText(params.get("DB_NAME", "FactoryManager"))
        self.user_input.setText(params.get("DB_USER", "postgres"))
        self.pass_input.setText(params.get("DB_PASSWORD", ""))

    def _get_params(self) -> dict | None:
        host   = self.host_input.text().strip()
        dbname = self.dbname_input.text().strip()
        user   = self.user_input.text().strip()

        if not host or not dbname or not user:
            QMessageBox.warning(
                self, "Incomplete",
                "Host, Database and Username are required."
            )
            return None

        return {
            "DB_HOST":     host,
            "DB_PORT":     str(self.port_input.value()),
            "DB_NAME":     dbname,
            "DB_USER":     user,
            "DB_PASSWORD": self.pass_input.text(),
        }

    def _test(self):
        params = self._get_params()
        if params is None:
            return

        self.status_label.setText("⏳  Testing connection…")
        self.status_label.setStyleSheet(
            "background: #fef9e7; color: #b7950b; "
            "border-radius: 4px; padding: 4px 8px;"
        )
        self.status_label.repaint()

        ok, msg = test_connection(params)

        if ok:
            self.status_label.setText(f"✅  {msg}")
            self.status_label.setStyleSheet(
                "background: #eafaf1; color: #1e8449; "
                "border-radius: 4px; padding: 4px 8px;"
            )
        else:
            self.status_label.setText(f"❌  {msg}")
            self.status_label.setStyleSheet(
                "background: #fdedec; color: #c0392b; "
                "border-radius: 4px; padding: 4px 8px;"
            )

    def _save(self):
        params = self._get_params()
        if params is None:
            return

        ok, msg = test_connection(params)
        if not ok:
            reply = QMessageBox.question(
                self,
                "Connection Failed",
                f"The connection test failed:\n\n{msg}\n\n"
                "Save these settings anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        save_env(params)

        QMessageBox.information(
            self,
            "Settings Saved",
            "Connection settings have been saved.\n\n"
            "Please restart the application for the changes to take effect."
        )
        self.accept()

    def _input_style(self) -> str:
        return """
            QLineEdit, QSpinBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                background: white;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #3498db;
            }
        """

    def _btn_style(self, color: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                border-radius: 6px; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """