"""
ui.theme
--------
Hojas de estilo QSS para tema claro y oscuro. Estilo sobrio tipo
aplicación empresarial (paleta azul marino / grises), sin aspecto
"generado por IA": sin gradientes llamativos, tipografía estándar,
espaciados consistentes.
"""

LIGHT_QSS = """
QMainWindow, QWidget { background-color: #F4F6F8; color: #1C2833; font-family: 'Segoe UI', Arial; font-size: 13px; }
QFrame#Sidebar { background-color: #14213D; }
QLabel#SidebarTitle { color: #FFFFFF; font-size: 16px; font-weight: 600; padding: 18px 16px 8px 16px; }
QPushButton#NavButton { text-align: left; padding: 10px 16px; color: #C9D2E0; background: transparent; border: none; font-size: 13px; }
QPushButton#NavButton:hover { background-color: #1F2E52; color: #FFFFFF; }
QPushButton#NavButton:checked { background-color: #1F6FEB; color: #FFFFFF; font-weight: 600; }
QFrame#TopBar { background-color: #FFFFFF; border-bottom: 1px solid #E0E4E8; }
QLineEdit#SearchBar { padding: 6px 10px; border: 1px solid #D0D5DA; border-radius: 4px; background: #F9FAFB; }
QFrame#Card { background-color: #FFFFFF; border: 1px solid #E0E4E8; border-radius: 6px; }
QFrame#Card:hover { border: 1px solid #1F6FEB; }
QLabel#CardTitle { font-size: 14px; font-weight: 600; color: #14213D; }
QLabel#CardDesc { color: #6B7280; font-size: 12px; }
QPushButton#PrimaryButton { background-color: #1F6FEB; color: white; border-radius: 4px; padding: 8px 18px; font-weight: 600; border: none; }
QPushButton#PrimaryButton:hover { background-color: #1857BF; }
QPushButton#PrimaryButton:disabled { background-color: #A9BDDD; }
QPushButton#SecondaryButton { background-color: #FFFFFF; color: #1F6FEB; border: 1px solid #1F6FEB; border-radius: 4px; padding: 8px 18px; }
QTableView { background-color: #FFFFFF; gridline-color: #E5E7EB; selection-background-color: #DCEBFF; selection-color: #14213D; }
QHeaderView::section { background-color: #EEF1F5; padding: 6px; border: none; border-bottom: 1px solid #D0D5DA; font-weight: 600; }
QPlainTextEdit#ConsoleWidget { background-color: #0D1117; color: #C9D1D9; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 4px; }
QStatusBar { background-color: #FFFFFF; border-top: 1px solid #E0E4E8; }
QProgressBar { border: 1px solid #D0D5DA; border-radius: 3px; text-align: center; background: #EEF1F5; }
QProgressBar::chunk { background-color: #1F6FEB; }
"""

DARK_QSS = """
QMainWindow, QWidget { background-color: #0D1117; color: #E6EDF3; font-family: 'Segoe UI', Arial; font-size: 13px; }
QFrame#Sidebar { background-color: #010409; }
QLabel#SidebarTitle { color: #E6EDF3; font-size: 16px; font-weight: 600; padding: 18px 16px 8px 16px; }
QPushButton#NavButton { text-align: left; padding: 10px 16px; color: #9DA7B3; background: transparent; border: none; font-size: 13px; }
QPushButton#NavButton:hover { background-color: #161B22; color: #FFFFFF; }
QPushButton#NavButton:checked { background-color: #1F6FEB; color: #FFFFFF; font-weight: 600; }
QFrame#TopBar { background-color: #161B22; border-bottom: 1px solid #21262D; }
QLineEdit#SearchBar { padding: 6px 10px; border: 1px solid #30363D; border-radius: 4px; background: #0D1117; color: #E6EDF3; }
QFrame#Card { background-color: #161B22; border: 1px solid #21262D; border-radius: 6px; }
QFrame#Card:hover { border: 1px solid #1F6FEB; }
QLabel#CardTitle { font-size: 14px; font-weight: 600; color: #E6EDF3; }
QLabel#CardDesc { color: #8B949E; font-size: 12px; }
QPushButton#PrimaryButton { background-color: #1F6FEB; color: white; border-radius: 4px; padding: 8px 18px; font-weight: 600; border: none; }
QPushButton#PrimaryButton:hover { background-color: #388BFD; }
QPushButton#SecondaryButton { background-color: transparent; color: #58A6FF; border: 1px solid #1F6FEB; border-radius: 4px; padding: 8px 18px; }
QTableView { background-color: #161B22; gridline-color: #21262D; selection-background-color: #1F3B63; selection-color: #E6EDF3; }
QHeaderView::section { background-color: #21262D; padding: 6px; border: none; border-bottom: 1px solid #30363D; font-weight: 600; color: #E6EDF3; }
QPlainTextEdit#ConsoleWidget { background-color: #010409; color: #C9D1D9; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 4px; }
QStatusBar { background-color: #161B22; border-top: 1px solid #21262D; }
QProgressBar { border: 1px solid #30363D; border-radius: 3px; text-align: center; background: #21262D; color: #E6EDF3; }
QProgressBar::chunk { background-color: #1F6FEB; }
"""


def get_stylesheet(theme: str = "light") -> str:
    return DARK_QSS if theme == "dark" else LIGHT_QSS
