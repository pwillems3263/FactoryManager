from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QFrame, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QBrush
from database import SessionLocal
from models.user import User, hash_password, verify_password, hash_pin, verify_pin


# ---------------------------------------------------------------------------
# Singleton session: logged-in user
# ---------------------------------------------------------------------------
class CurrentUser:
    _instance: User | None = None

    @classmethod
    def set(cls, user: User):
        cls._instance = user

    @classmethod
    def get(cls) -> User | None:
        return cls._instance

    @classmethod
    def can(cls, action: str) -> bool:
        u = cls._instance
        return u.can(action) if u else False

    @classmethod
    def niveau(cls) -> int:
        return cls._instance.niveau if cls._instance else 0


# ---------------------------------------------------------------------------
# Login screen (desktop — unchanged)
# ---------------------------------------------------------------------------
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FactoryManager — Login")
        self.setMinimumWidth(380)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)

        from db_config import load_env, test_connection
        self._db_ok, self._db_msg = test_connection(load_env())

        if self._db_ok:
            self._ensure_admin_exists()

        self._build_ui()

    def _ensure_admin_exists(self):
        """Create a default admin if the table is empty."""
        try:
            session = SessionLocal()
            try:
                if session.query(User).count() == 0:
                    h, s = hash_password("admin")
                    admin = User(
                        username="admin",
                        full_name="Administrator",
                        password_hash=h,
                        password_salt=s,
                        niveau=4,
                        actif=True
                    )
                    session.add(admin)
                    session.commit()
            finally:
                session.close()
        except Exception:
            pass

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        title = QLabel("FactoryManager")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        sub = QLabel("Please sign in to continue")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(sub)

        self.db_banner = QLabel("")
        self.db_banner.setWordWrap(True)
        self.db_banner.setAlignment(Qt.AlignCenter)
        self.db_banner.setMinimumHeight(50)
        self.db_banner.setStyleSheet("""
            background: #fdedec; color: #c0392b;
            border: 1px solid #f5b7b1; border-radius: 6px;
            padding: 8px 12px; font-size: 12px;
        """)
        self.db_banner.setVisible(False)
        layout.addWidget(self.db_banner)

        if not self._db_ok:
            short_msg = self._db_msg[:100] + ("…" if len(self._db_msg) > 100 else "")
            self.db_banner.setText(
                f"⚠  Cannot connect to database.\n"
                f"Configure the DB settings before signing in.\n"
                f"({short_msg})"
            )
            self.db_banner.setVisible(True)

        layout.addSpacing(6)

        form = QFormLayout()
        form.setSpacing(10)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        self.user_input.setMinimumHeight(36)
        self.user_input.setStyleSheet(self._input_style())
        self.user_input.setEnabled(self._db_ok)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setMinimumHeight(36)
        self.pass_input.setStyleSheet(self._input_style())
        self.pass_input.returnPressed.connect(self._login)
        self.pass_input.setEnabled(self._db_ok)

        form.addRow("Username :", self.user_input)
        form.addRow("Password :", self.pass_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self.error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.error_label)

        self.btn_login = QPushButton("Sign In")
        self.btn_login.setMinimumHeight(40)
        self.btn_login.setEnabled(self._db_ok)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 6px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1a6fa8; }
            QPushButton:disabled { background-color: #bdc3c7; color: #ecf0f1; }
        """)
        self.btn_login.clicked.connect(self._login)
        layout.addWidget(self.btn_login)

        self.btn_db = QPushButton("⚙  DB Settings")
        self.btn_db.setMinimumHeight(34)
        self._style_btn_db()
        self.btn_db.clicked.connect(self._open_db_config)
        layout.addWidget(self.btn_db)

    def closeEvent(self, event):
        event.accept()
        QApplication.quit()

    def _style_btn_db(self):
        if not self._db_ok:
            self.btn_db.setStyleSheet("""
                QPushButton {
                    color: white; background: #e67e22; border: none;
                    border-radius: 6px; font-size: 13px; font-weight: bold;
                    padding: 4px 12px;
                }
                QPushButton:hover { background: #d35400; }
            """)
        else:
            self.btn_db.setStyleSheet("""
                QPushButton {
                    color: #7f8c8d; background: transparent; border: none;
                    font-size: 11px; text-decoration: underline;
                }
                QPushButton:hover { color: #2c3e50; }
            """)

    def _open_db_config(self):
        from ui.views.db_config_view import DBConfigView
        dlg = DBConfigView(self)
        if dlg.exec() == QDialog.Accepted:
            from db_config import load_env, test_connection
            self._db_ok, self._db_msg = test_connection(load_env())
            if self._db_ok:
                self.db_banner.setVisible(False)
                self.user_input.setEnabled(True)
                self.pass_input.setEnabled(True)
                self.btn_login.setEnabled(True)
                self._style_btn_db()
                self.error_label.setText("")
                self._ensure_admin_exists()
                self.user_input.setFocus()
            else:
                short_msg = self._db_msg[:100] + ("…" if len(self._db_msg) > 100 else "")
                self.db_banner.setText(f"⚠  Still cannot connect to database.\n({short_msg})")
                self.db_banner.setVisible(True)

    def _input_style(self):
        return """
            QLineEdit {
                border: 1px solid #bdc3c7; border-radius: 4px;
                padding: 4px 8px; font-size: 13px;
            }
            QLineEdit:focus { border-color: #3498db; }
            QLineEdit:disabled { background: #f0f3f4; color: #aab; }
        """

    def _login(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text()

        if not username or not password:
            self.error_label.setText("Please enter username and password.")
            return

        try:
            session = SessionLocal()
            try:
                user = session.query(User).filter_by(username=username, actif=True).first()
                if not user or not verify_password(password, user.password_hash, user.password_salt):
                    self.error_label.setText("Invalid username or password.")
                    self.pass_input.clear()
                    return
                session.expunge(user)
                CurrentUser.set(user)
                self.accept()
            finally:
                session.close()
        except Exception as e:
            short_msg = str(e)[:120]
            self.db_banner.setText(
                f"⚠  Database error: {short_msg}\nPlease check your DB Settings."
            )
            self.db_banner.setVisible(True)
            self._db_ok = False
            self._style_btn_db()
            self.btn_login.setEnabled(False)
            self.error_label.setText("")


# ---------------------------------------------------------------------------
# User Management view (level 4 only)
# ---------------------------------------------------------------------------
class UsersView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._charger_users()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        titre = QLabel("User Management")
        titre.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(titre)
        header.addStretch()

        btn_nouveau = QPushButton("+ New User")
        btn_nouveau.setFixedHeight(36)
        btn_nouveau.setStyleSheet(self._btn_style("#3498db", "#2980b9"))
        btn_nouveau.clicked.connect(self._nouveau_user)
        header.addWidget(btn_nouveau)

        btn_modifier = QPushButton("✏ Edit")
        btn_modifier.setFixedHeight(36)
        btn_modifier.setStyleSheet(self._btn_style("#8e44ad", "#7d3c98"))
        btn_modifier.clicked.connect(self._modifier_user)
        header.addWidget(btn_modifier)

        btn_reset = QPushButton("🔑 Reset Password")
        btn_reset.setFixedHeight(36)
        btn_reset.setStyleSheet(self._btn_style("#e67e22", "#d35400"))
        btn_reset.clicked.connect(self._reset_password)
        header.addWidget(btn_reset)

        # ── NEW: Reset PIN button ────────────────────────────────────────
        btn_pin = QPushButton("🔢 Reset PIN")
        btn_pin.setFixedHeight(36)
        btn_pin.setStyleSheet(self._btn_style("#16a085", "#138d75"))
        btn_pin.clicked.connect(self._reset_pin)
        header.addWidget(btn_pin)
        # ────────────────────────────────────────────────────────────────

        # ── NEW: Unblock Kiosk button ────────────────────────────────
        btn_unblock = QPushButton("🔓 Unblock Kiosk")
        btn_unblock.setFixedHeight(36)
        btn_unblock.setStyleSheet(self._btn_style("#c0392b", "#a93226"))
        btn_unblock.clicked.connect(self._unblock_kiosk)
        header.addWidget(btn_unblock)
        # ────────────────────────────────────────────────────────────

        btn_toggle = QPushButton("⏸ Enable / Disable")
        btn_toggle.setFixedHeight(36)
        btn_toggle.setStyleSheet(self._btn_style("#e74c3c", "#c0392b"))
        btn_toggle.clicked.connect(self._toggle_actif)
        header.addWidget(btn_toggle)

        layout.addLayout(header)

        legend = QHBoxLayout()
        for niveau, label, color in [
            (1, "Operator",       "#27ae60"),
            (2, "Coordinator",    "#3498db"),
            (3, "Manager",        "#e67e22"),
            (4, "Administrator",  "#e74c3c"),
        ]:
            dot = QLabel(f"● Level {niveau} — {label}")
            dot.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
            legend.addWidget(dot)
        legend.addStretch()
        layout.addLayout(legend)

        self.table = QTableWidget()
        # ── Added "PIN" column ───────────────────────────────────────────
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Username", "Full Name", "Level", "Role", "PIN", "Kiosk Status", "Status"
        ])
        # ────────────────────────────────────────────────────────────────
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dde; border-radius: 4px; background-color: white;
            }
            QHeaderView::section {
                background-color: #2c3e50; color: white; padding: 8px;
            }
            QTableWidget::item:selected { background-color: #3498db; color: white; }
        """)
        layout.addWidget(self.table)

    def _btn_style(self, color, hover):
        return f"""
            QPushButton {{
                background-color: {color}; color: white;
                border-radius: 4px; padding: 0 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """

    def _get_id_selectionne(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _charger_users(self):
        session = SessionLocal()
        try:
            users = session.query(User).order_by(User.username).all()
            self.table.setRowCount(len(users))
            for row, u in enumerate(users):
                id_item = QTableWidgetItem(str(u.id_user))
                id_item.setData(Qt.UserRole, u.id_user)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, QTableWidgetItem(u.username))
                self.table.setItem(row, 2, QTableWidgetItem(u.full_name or "—"))

                niv_item = QTableWidgetItem(str(u.niveau))
                niv_item.setForeground(QColor(User.NIVEAU_COLORS.get(u.niveau, "#999")))
                niv_item.setFont(QFont("Arial", 10, QFont.Bold))
                niv_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, niv_item)

                role_item = QTableWidgetItem(User.NIVEAU_LABELS.get(u.niveau, "?"))
                role_item.setForeground(QColor(User.NIVEAU_COLORS.get(u.niveau, "#999")))
                self.table.setItem(row, 4, role_item)

                # ── PIN status column ────────────────────────────────────
                pin_set = bool(u.pin_hash and u.pin_salt)
                pin_item = QTableWidgetItem("✔  Set" if pin_set else "—  Not set")
                pin_item.setForeground(
                    QColor("#16a085") if pin_set else QColor("#bdc3c7")
                )
                pin_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 5, pin_item)
                # ────────────────────────────────────────────────────────

                # ── Kiosk Status column ─────────────────────────────────
                from datetime import datetime, timezone
                blocked = False
                blocked_txt = "—  OK"
                blocked_color = "#bdc3c7"
                if u.kiosk_blocked_until:
                    bu = u.kiosk_blocked_until
                    if bu.tzinfo is None:
                        bu = bu.replace(tzinfo=timezone.utc)
                    if bu > datetime.now(timezone.utc):
                        blocked = True
                        remaining = int((bu - datetime.now(timezone.utc)).total_seconds() / 60)
                        blocked_txt = f"🔒  Locked ({remaining} min)"
                        blocked_color = "#e74c3c"
                    else:
                        blocked_txt = "✔  OK"
                        blocked_color = "#27ae60"
                else:
                    blocked_txt = "✔  OK"
                    blocked_color = "#27ae60"
                kiosk_item = QTableWidgetItem(blocked_txt)
                kiosk_item.setForeground(QColor(blocked_color))
                kiosk_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 6, kiosk_item)
                # ────────────────────────────────────────────────────────

                status_item = QTableWidgetItem("Active" if u.actif else "Disabled")
                status_item.setForeground(
                    QColor("#27ae60") if u.actif else QColor("#e74c3c")
                )
                status_item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table.setItem(row, 7, status_item)
        finally:
            session.close()

    def _nouveau_user(self):
        dialog = UserDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._charger_users()

    def _modifier_user(self):
        id_user = self._get_id_selectionne()
        if not id_user:
            QMessageBox.warning(self, "Warning", "Please select a user.")
            return
        dialog = UserDialog(self, id_user=id_user)
        if dialog.exec() == QDialog.Accepted:
            self._charger_users()

    def _reset_password(self):
        id_user = self._get_id_selectionne()
        if not id_user:
            QMessageBox.warning(self, "Warning", "Please select a user.")
            return
        dialog = ResetPasswordDialog(id_user, self)
        if dialog.exec() == QDialog.Accepted:
            QMessageBox.information(self, "Success", "Password updated successfully.")

    # ── NEW: Reset PIN ───────────────────────────────────────────────────────
    def _reset_pin(self):
        id_user = self._get_id_selectionne()
        if not id_user:
            QMessageBox.warning(self, "Warning", "Please select a user.")
            return
        dialog = ResetPinDialog(id_user, self)
        if dialog.exec() == QDialog.Accepted:
            QMessageBox.information(self, "Success", "Kiosk PIN updated successfully.")
            self._charger_users()
    # ────────────────────────────────────────────────────────────────────────

    # ── NEW: Unblock kiosk ──────────────────────────────────────────────────
    def _unblock_kiosk(self):
        id_user = self._get_id_selectionne()
        if not id_user:
            QMessageBox.warning(self, "Warning", "Please select a user.")
            return
        session = SessionLocal()
        try:
            u = session.get(User, id_user)
            if not u:
                return
            if not u.kiosk_blocked_until:
                QMessageBox.information(self, "Info", f"{u.full_name or u.username} is not blocked.")
                return
            u.kiosk_blocked_until = None
            # Also clear login attempts
            session.execute(
                __import__('sqlalchemy').text("DELETE FROM login_attempts WHERE id_user = :id"),
                {"id": id_user}
            )
            session.commit()
            QMessageBox.information(self, "Success",
                f"{u.full_name or u.username} has been unblocked successfully.")
            self._charger_users()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()
    # ────────────────────────────────────────────────────────────────────────

    def _toggle_actif(self):
        id_user = self._get_id_selectionne()
        if not id_user:
            QMessageBox.warning(self, "Warning", "Please select a user.")
            return
        current = CurrentUser.get()
        if current and current.id_user == id_user:
            QMessageBox.warning(self, "Warning", "You cannot disable your own account.")
            return
        session = SessionLocal()
        try:
            u = session.get(User, id_user)
            if u:
                u.actif = not u.actif
                session.commit()
                self._charger_users()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Create / Edit user dialog
# ---------------------------------------------------------------------------
class UserDialog(QDialog):
    def __init__(self, parent=None, id_user=None):
        super().__init__(parent)
        self.id_user = id_user
        self.setWindowTitle("Edit User" if id_user else "New User")
        self.setMinimumWidth(420)
        self._build_ui()
        if id_user:
            self._charger()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        form = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. jdupont")

        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("e.g. Jean Dupont")

        form.addRow("Username :", self.username_input)
        form.addRow("Full Name :", self.fullname_input)

        if not self.id_user:
            # New user: password is required
            self.password_input = QLineEdit()
            self.password_input.setPlaceholderText("Initial password")
            self.password_input.setEchoMode(QLineEdit.Password)
            form.addRow("Password :", self.password_input)

            # New user: optional PIN at creation time
            self.pin_input = QLineEdit()
            self.pin_input.setPlaceholderText("4-digit kiosk PIN (optional)")
            self.pin_input.setMaxLength(4)
            self.pin_input.setEchoMode(QLineEdit.Password)
            pin_hint = QLabel("Leave blank to set the PIN later via 'Reset PIN'.")
            pin_hint.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            form.addRow("Kiosk PIN :", self.pin_input)
            layout.addLayout(form)
            layout.addWidget(pin_hint)
        else:
            layout.addLayout(form)

        # Access level list
        lbl_niv = QLabel("Access Level :")
        lbl_niv.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_niv)

        self.niveau_list = QListWidget()
        self.niveau_list.setFixedHeight(108)
        self.niveau_list.setStyleSheet("""
            QListWidget { border: 1px solid #bdc3c7; border-radius: 4px; }
            QListWidget::item { padding: 6px 10px; }
            QListWidget::item:selected { background-color: #3498db; color: white; }
        """)
        for niveau, label, desc, color in [
            (1, "Level 1 — Operator",      "Time tracking only (kiosk)",             "#27ae60"),
            (2, "Level 2 — Coordinator",   "Components, assemblies, orders",          "#3498db"),
            (3, "Level 3 — Manager",       "Machines, costs, services, ext. parts",   "#e67e22"),
            (4, "Level 4 — Administrator", "Full access + user management",           "#e74c3c"),
        ]:
            item = QListWidgetItem(f"{label}  —  {desc}")
            item.setData(Qt.UserRole, niveau)
            item.setForeground(QColor(color))
            self.niveau_list.addItem(item)
        self.niveau_list.setCurrentRow(0)
        layout.addWidget(self.niveau_list)

        if self.id_user:
            self.actif_check = QCheckBox("Account active")
            self.actif_check.setChecked(True)
            layout.addWidget(self.actif_check)

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
            u = session.get(User, self.id_user)
            if u:
                self.username_input.setText(u.username)
                self.fullname_input.setText(u.full_name or "")
                for i in range(self.niveau_list.count()):
                    if self.niveau_list.item(i).data(Qt.UserRole) == u.niveau:
                        self.niveau_list.setCurrentRow(i)
                        break
                if hasattr(self, "actif_check"):
                    self.actif_check.setChecked(u.actif)
        finally:
            session.close()

    def _valider(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Warning", "Username is required.")
            return

        niv_item = self.niveau_list.currentItem()
        if not niv_item:
            QMessageBox.warning(self, "Warning", "Please select an access level.")
            return
        niveau = niv_item.data(Qt.UserRole)

        session = SessionLocal()
        try:
            if self.id_user:
                # Edit existing user
                u = session.get(User, self.id_user)
                if u:
                    u.username  = username
                    u.full_name = self.fullname_input.text().strip() or None
                    u.niveau    = niveau
                    if hasattr(self, "actif_check"):
                        u.actif = self.actif_check.isChecked()
            else:
                # Create new user
                password = self.password_input.text()
                if not password:
                    QMessageBox.warning(self, "Warning", "Password is required.")
                    return
                h, s = hash_password(password)
                u = User(
                    username=username,
                    full_name=self.fullname_input.text().strip() or None,
                    password_hash=h,
                    password_salt=s,
                    niveau=niveau,
                    actif=True
                )
                # Optional PIN at creation
                pin_val = self.pin_input.text().strip() if hasattr(self, "pin_input") else ""
                if pin_val:
                    if not _validate_pin(pin_val):
                        QMessageBox.warning(
                            self, "Warning",
                            "PIN must be exactly 4 digits (0–9)."
                        )
                        return
                    ph, ps = hash_pin(pin_val)
                    u.pin_hash = ph
                    u.pin_salt = ps
                session.add(u)

            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            if "UNIQUE" in str(e).upper():
                QMessageBox.critical(self, "Error", f"Username '{username}' already exists.")
            else:
                QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Reset Password dialog (unchanged)
# ---------------------------------------------------------------------------
class ResetPasswordDialog(QDialog):
    def __init__(self, id_user: int, parent=None):
        super().__init__(parent)
        self.id_user = id_user
        self.setWindowTitle("Reset Password")
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        form = QFormLayout()
        self.new_pass = QLineEdit()
        self.new_pass.setEchoMode(QLineEdit.Password)
        self.new_pass.setPlaceholderText("New password")
        self.confirm_pass = QLineEdit()
        self.confirm_pass.setEchoMode(QLineEdit.Password)
        self.confirm_pass.setPlaceholderText("Confirm password")
        form.addRow("New Password :", self.new_pass)
        form.addRow("Confirm :", self.confirm_pass)
        layout.addLayout(form)
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
        p1 = self.new_pass.text()
        p2 = self.confirm_pass.text()
        if not p1:
            QMessageBox.warning(self, "Warning", "Password cannot be empty.")
            return
        if p1 != p2:
            QMessageBox.warning(self, "Warning", "Passwords do not match.")
            return
        session = SessionLocal()
        try:
            u = session.get(User, self.id_user)
            if u:
                h, s = hash_password(p1)
                u.password_hash = h
                u.password_salt = s
                session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


# ---------------------------------------------------------------------------
# NEW: Reset PIN dialog
# ---------------------------------------------------------------------------
class ResetPinDialog(QDialog):
    """
    Allows an administrator to set or change the 4-digit kiosk PIN for a user.
    The PIN is stored hashed (SHA-256 + salt), same mechanism as passwords.
    Leave both fields blank and click Save to REMOVE the PIN entirely.
    """
    def __init__(self, id_user: int, parent=None):
        super().__init__(parent)
        self.id_user = id_user
        self.setWindowTitle("Set / Reset Kiosk PIN")
        self.setMinimumWidth(380)
        self._build_ui()
        self._load_user_info()

    def _load_user_info(self):
        session = SessionLocal()
        try:
            u = session.get(User, self.id_user)
            if u:
                name = u.full_name or u.username
                has = bool(u.pin_hash)
                self.lbl_user.setText(f"User: {name}")
                self.lbl_status.setText(
                    "Current PIN: ✔  already set" if has else "Current PIN: —  not set"
                )
                self.lbl_status.setStyleSheet(
                    f"color: {'#16a085' if has else '#bdc3c7'}; font-size: 12px;"
                )
        finally:
            session.close()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.lbl_user = QLabel("")
        self.lbl_user.setFont(QFont("Arial", 11, QFont.Bold))
        layout.addWidget(self.lbl_user)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

        info = QLabel(
            "Enter a new 4-digit PIN (digits 0–9 only).\n"
            "Leave blank to remove the PIN."
        )
        info.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.pin1 = QLineEdit()
        self.pin1.setMaxLength(4)
        self.pin1.setEchoMode(QLineEdit.Password)
        self.pin1.setPlaceholderText("New PIN (4 digits)")

        self.pin2 = QLineEdit()
        self.pin2.setMaxLength(4)
        self.pin2.setEchoMode(QLineEdit.Password)
        self.pin2.setPlaceholderText("Confirm PIN")

        form.addRow("New PIN :", self.pin1)
        form.addRow("Confirm :", self.pin2)
        layout.addLayout(form)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #e74c3c; font-size: 12px;")
        layout.addWidget(self.error_lbl)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save PIN")
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
        p1 = self.pin1.text().strip()
        p2 = self.pin2.text().strip()

        # Both blank → remove PIN
        if not p1 and not p2:
            reply = QMessageBox.question(
                self, "Remove PIN",
                "Both fields are empty. This will REMOVE the kiosk PIN for this user.\nContinue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            self._save_pin(None, None)
            return

        # Validate format
        if not _validate_pin(p1):
            self.error_lbl.setText("PIN must be exactly 4 digits (0–9).")
            return
        if p1 != p2:
            self.error_lbl.setText("PINs do not match.")
            return

        ph, ps = hash_pin(p1)
        self._save_pin(ph, ps)

    def _save_pin(self, pin_hash, pin_salt):
        session = SessionLocal()
        try:
            u = session.get(User, self.id_user)
            if u:
                u.pin_hash = pin_hash
                u.pin_salt = pin_salt
                session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _validate_pin(pin: str) -> bool:
    """Returns True if pin is exactly 4 numeric digits."""
    return len(pin) == 4 and pin.isdigit()