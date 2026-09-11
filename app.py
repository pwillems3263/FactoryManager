import sys
from PySide6.QtWidgets import QApplication, QDialog
from ui.main_window import MainWindow
from ui.views.users_view import LoginDialog, CurrentUser


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Login obligatoire au démarrage
    login = LoginDialog()
    if login.exec() != QDialog.Accepted:
        sys.exit(0)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()