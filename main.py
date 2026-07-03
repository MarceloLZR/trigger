"""
main.py
--------
Punto de entrada de SQL Automation Suite.

Ejecutar:
    python main.py
"""
import sys
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import get_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(get_stylesheet("light"))
    app.setApplicationName("SQL Automation Suite")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
