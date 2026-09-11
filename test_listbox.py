import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class TestDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test ListBox")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Champ texte normal
        self.nom_input = QLineEdit()
        self.nom_input.setPlaceholderText("Component name")
        form.addRow("Name :", self.nom_input)
        layout.addLayout(form)

        # Test ListWidget pour Matière
        lbl_mat = QLabel("Material :")
        lbl_mat.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_mat)

        self.matiere_list = QListWidget()
        self.matiere_list.setFixedHeight(100)
        self.matiere_list.setAlternatingRowColors(True)
        self.matiere_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)

        # Ajoute des items de test
        items = [
            ("— None —", None),
            ("Acier inox 316L", 1),
            ("Acier XC42", 2),
            ("Aluminium 7075", 3),
            ("Laiton CuZn37", 4),
        ]
        for nom, id_val in items:
            item = QListWidgetItem(nom)
            item.setData(Qt.UserRole, id_val)
            self.matiere_list.addItem(item)

        self.matiere_list.setCurrentRow(0)
        layout.addWidget(self.matiere_list)

        # Test ListWidget pour Forme
        lbl_forme = QLabel("Raw shape :")
        lbl_forme.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(lbl_forme)

        self.forme_list = QListWidget()
        self.forme_list.setFixedHeight(80)
        self.forme_list.setAlternatingRowColors(True)
        self.forme_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)

        formes = ["— None —", "axe", "tube", "plaque"]
        for f in formes:
            self.forme_list.addItem(QListWidgetItem(f))
        self.forme_list.setCurrentRow(0)
        layout.addWidget(self.forme_list)

        # Boutons
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; padding: 6px 16px;
            }
        """)
        btn_save.clicked.connect(self._valider)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _valider(self):
        matiere = self.matiere_list.currentItem()
        forme   = self.forme_list.currentItem()
        print(f"Name    : {self.nom_input.text()}")
        print(f"Matière : {matiere.text() if matiere else '—'}")
        print(f"Forme   : {forme.text() if forme else '—'}")
        self.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = TestDialog()
    dialog.exec()