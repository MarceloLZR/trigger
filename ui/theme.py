"""
ui.theme
--------
Hojas de estilo QSS para tema claro y oscuro.
Paleta corporativa Caja Cencosud Scotiabank — Gama Naranja:
  - Naranja Cencosud  : #FF6B00  (acento primario / sidebar)
  - Naranja intenso   : #FF8A33  (gradiente / brillo)
  - Naranja oscuro    : #CC5500  (hover / profundidad)
  - Naranja quemado   : #A34400  (pressed / sidebar activo)
  - Ámbar claro       : #FFF3E0  (fondo claro cálido)
  - Ámbar medio       : #FFE0B2  (selecciones, tabs inactivos)

Modo oscuro: fondo GRAFITO NEUTRO (no marrón) para que el naranja resalte
como único color cálido de la interfaz.
  - Grafito fondo     : #14161A
  - Grafito cards     : #1D2026
  - Grafito borde     : #2B2F38
  - Texto claro       : #EDEDEF
"""

# ---------------------------------------------------------------------------
LIGHT_QSS = """
/* === BASE === */
QMainWindow, QDialog { background-color: #F7F5F2; color: #1A1A1A; font-family: 'Segoe UI', Arial; font-size: 13px; }
QWidget { background-color: transparent; color: #1A1A1A; font-family: 'Segoe UI', Arial; font-size: 13px; }
QMainWindow > QWidget { background-color: #F7F5F2; }

/* === SIDEBAR (naranja real) === */
QFrame#Sidebar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF7A1A, stop:1 #F05E00);
}
QLabel#SidebarTitle { color: #FFFFFF; font-size: 16px; font-weight: 800; letter-spacing: 0.5px; padding: 22px 16px 12px 16px; background-color: transparent; }
QPushButton#NavButton { text-align: left; padding: 11px 16px 11px 18px; color: #FFE4CC; background-color: transparent; border: none; border-left: 3px solid transparent; font-size: 13px; font-weight: 500; }
QPushButton#NavButton:hover { background-color: rgba(255, 255, 255, 0.14); color: #FFFFFF; border-left: 3px solid #FFFFFF; }
QPushButton#NavButton:checked { background-color: rgba(0, 0, 0, 0.18); color: #FFFFFF; font-weight: 700; border: none; border-left: 3px solid #FFFFFF; }

/* === TOPBAR === */
QFrame#TopBar { background-color: #FFFFFF; border-bottom: 1px solid #EAE2D8; }
QLineEdit#SearchBar { padding: 7px 12px; border: 1px solid #E0D8CC; border-radius: 16px; background-color: #F7F3EE; color: #1A1A1A; }
QLineEdit#SearchBar:focus { border: 1px solid #FF6B00; background-color: #FFFFFF; }

/* === CARDS === */
QFrame#Card { background-color: #FFFFFF; border: 1px solid #EAE2D8; border-radius: 10px; }
QFrame#Card:hover { border: 2px solid #FF6B00; }
QLabel#CardTitle { font-size: 14px; font-weight: 700; color: #1A1A1A; background-color: transparent; }
QLabel#CardDesc { color: #7A7268; font-size: 12px; background-color: transparent; }

/* === BOTONES === */
QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF8A33, stop:1 #FF6B00);
    color: #FFFFFF; border-radius: 6px; padding: 9px 20px; font-weight: 700; border: none;
}
QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF6B00, stop:1 #E85F00);
}
QPushButton#PrimaryButton:pressed { background-color: #A34400; }
QPushButton#PrimaryButton:disabled { background-color: #F5C090; color: #FFFFFF; }
QPushButton#SecondaryButton { background-color: #FFFFFF; color: #CC5500; border: 1.5px solid #FF6B00; border-radius: 6px; padding: 8px 18px; font-weight: 600; }
QPushButton#SecondaryButton:hover { background-color: #FFF3E0; color: #CC5500; border: 1.5px solid #FF6B00; }
QPushButton#SecondaryButton:pressed { background-color: #FF6B00; color: #FFFFFF; }

/* === TABLA === */
QTableView { background-color: #FFFFFF; color: #1A1A1A; gridline-color: #F0E8DC; selection-background-color: #FFE0B2; selection-color: #1A1A1A; border: 1px solid #EAE2D8; border-radius: 6px; }
QHeaderView::section { background-color: #F05E00; color: #FFFFFF; padding: 8px 6px; border: none; border-right: 1px solid #E05500; font-weight: 700; font-size: 12px; }
QHeaderView::section:last { border-right: none; }
QTableView::item:alternate { background-color: #FDFAF6; }
QTableView::item:selected { background-color: #FFE0B2; color: #1A1A1A; }

/* === INPUTS GENERALES === */
QLineEdit { background-color: #FFFFFF; color: #1A1A1A; border: 1px solid #E0D8CC; border-radius: 4px; padding: 5px 8px; }
QLineEdit:focus { border: 1px solid #FF6B00; }
QComboBox { background-color: #FFFFFF; border: 1px solid #E0D8CC; border-radius: 4px; padding: 5px 8px; color: #1A1A1A; }
QComboBox:focus { border: 1px solid #FF6B00; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background-color: #FFFFFF; color: #1A1A1A; selection-background-color: #FFE0B2; selection-color: #1A1A1A; border: 1px solid #E0D8CC; }
QSpinBox, QDoubleSpinBox { background-color: #FFFFFF; border: 1px solid #E0D8CC; border-radius: 4px; padding: 5px 8px; color: #1A1A1A; }
QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #FF6B00; }
QTextEdit, QPlainTextEdit { background-color: #FFFFFF; color: #1A1A1A; border: 1px solid #E0D8CC; border-radius: 4px; }
QPlainTextEdit#ConsoleWidget { background-color: #1A1A1A; color: #FFC38A; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 4px; border: none; }

/* === OTROS CONTROLES === */
QCheckBox { color: #1A1A1A; background-color: transparent; }
QCheckBox::indicator { width: 15px; height: 15px; border: 2px solid #D4C4AC; border-radius: 4px; background-color: #FFFFFF; }
QCheckBox::indicator:checked { background-color: #FF6B00; border-color: #FF6B00; }
QGroupBox { border: 1px solid #EAE2D8; border-radius: 8px; margin-top: 10px; font-weight: 700; color: #1A1A1A; background-color: transparent; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #CC5500; background-color: transparent; }
QLabel { color: #1A1A1A; background-color: transparent; }

/* === SCROLLBAR === */
QScrollBar:vertical { background: #F0E8DC; width: 8px; margin: 0; border-radius: 4px; }
QScrollBar::handle:vertical { background: #E0B888; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #FF6B00; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #F0E8DC; height: 8px; margin: 0; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #E0B888; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #FF6B00; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* === TABS === */
QTabWidget::pane { border: 1px solid #EAE2D8; background-color: #FFFFFF; border-radius: 6px; }
QTabBar::tab { background-color: #F0E8DC; color: #7A7268; padding: 9px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; border: 1px solid #EAE2D8; }
QTabBar::tab:selected { background-color: #FF6B00; color: #FFFFFF; font-weight: 700; border-color: #FF6B00; }
QTabBar::tab:hover:!selected { background-color: #FFE0B2; color: #CC5500; }

/* === BARRA DE ESTADO === */
QStatusBar { background-color: #F05E00; color: #FFFFFF; font-size: 12px; }

/* === PROGRESS BAR === */
QProgressBar { border: 1px solid #E0D8CC; border-radius: 4px; text-align: center; background-color: #F0E8DC; color: #1A1A1A; }
QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6B00, stop:1 #FF8A33); border-radius: 3px; }

/* === TOOLTIPS === */
QToolTip { background-color: #1A1A1A; color: #FFFFFF; border: 1px solid #FF6B00; padding: 5px 9px; border-radius: 4px; }
"""

# ---------------------------------------------------------------------------
# Tema OSCURO — GRAFITO NEUTRO (sin tinte marrón), naranja como único acento
# ---------------------------------------------------------------------------
DARK_QSS = """
/* === BASE === */
QMainWindow, QDialog { background-color: #14161A; color: #EDEDEF; font-family: 'Segoe UI', Arial; font-size: 13px; }
QWidget { background-color: transparent; color: #EDEDEF; font-family: 'Segoe UI', Arial; font-size: 13px; }
QMainWindow > QWidget { background-color: #14161A; }

/* === SIDEBAR (naranja real, sobre grafito) === */
QFrame#Sidebar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF7A1A, stop:1 #E85800);
}
QLabel#SidebarTitle { color: #FFFFFF; font-size: 16px; font-weight: 800; letter-spacing: 0.5px; padding: 22px 16px 12px 16px; background-color: transparent; }
QPushButton#NavButton { text-align: left; padding: 11px 16px 11px 18px; color: #FFE4CC; background-color: transparent; border: none; border-left: 3px solid transparent; font-size: 13px; font-weight: 500; }
QPushButton#NavButton:hover { background-color: rgba(255, 255, 255, 0.14); color: #FFFFFF; border-left: 3px solid #FFFFFF; }
QPushButton#NavButton:checked { background-color: rgba(0, 0, 0, 0.22); color: #FFFFFF; font-weight: 700; border: none; border-left: 3px solid #FFFFFF; }

/* === TOPBAR === */
QFrame#TopBar { background-color: #1B1E24; border-bottom: 1px solid #2B2F38; }
QLineEdit#SearchBar { padding: 7px 12px; border: 1px solid #2B2F38; border-radius: 16px; background-color: #14161A; color: #EDEDEF; }
QLineEdit#SearchBar:focus { border: 1px solid #FF8C2A; }

/* === CARDS === */
QFrame#Card { background-color: #1D2026; border: 1px solid #2B2F38; border-radius: 10px; }
QFrame#Card:hover { border: 2px solid #FF6B00; }
QLabel#CardTitle { font-size: 14px; font-weight: 700; color: #F5F5F5; background-color: transparent; }
QLabel#CardDesc { color: #9A9CA5; font-size: 12px; background-color: transparent; }

/* === BOTONES === */
QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FF8C2A, stop:1 #FF6B00);
    color: #FFFFFF; border-radius: 6px; padding: 9px 20px; font-weight: 700; border: none;
}
QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFA24D, stop:1 #FF8C2A);
}
QPushButton#PrimaryButton:pressed { background-color: #CC5500; }
QPushButton#PrimaryButton:disabled { background-color: #3A3D44; color: #6C6F78; }
QPushButton#SecondaryButton { background-color: transparent; color: #FF8C2A; border: 1.5px solid #FF6B00; border-radius: 6px; padding: 8px 18px; font-weight: 600; }
QPushButton#SecondaryButton:hover { background-color: #2A1E14; color: #FFA24D; border: 1.5px solid #FF8C2A; }
QPushButton#SecondaryButton:pressed { background-color: #CC5500; color: #FFFFFF; }

/* === TABLA === */
QTableView { background-color: #1D2026; color: #EDEDEF; gridline-color: #2B2F38; selection-background-color: #5A3414; selection-color: #FFFFFF; border: 1px solid #2B2F38; border-radius: 6px; }
QHeaderView::section { background-color: #14161A; color: #FF8C2A; padding: 8px 6px; border: none; border-right: 1px solid #2B2F38; font-weight: 700; font-size: 12px; }
QHeaderView::section:last { border-right: none; }
QTableView::item:alternate { background-color: #20232A; }
QTableView::item:selected { background-color: #5A3414; color: #FFFFFF; }

/* === INPUTS GENERALES === */
QLineEdit { background-color: #1D2026; color: #EDEDEF; border: 1px solid #2B2F38; border-radius: 4px; padding: 5px 8px; }
QLineEdit:focus { border: 1px solid #FF8C2A; }
QComboBox { background-color: #1D2026; border: 1px solid #2B2F38; border-radius: 4px; padding: 5px 8px; color: #EDEDEF; }
QComboBox:focus { border: 1px solid #FF8C2A; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background-color: #1D2026; color: #EDEDEF; selection-background-color: #5A3414; selection-color: #FFFFFF; border: 1px solid #2B2F38; }
QSpinBox, QDoubleSpinBox { background-color: #1D2026; border: 1px solid #2B2F38; border-radius: 4px; padding: 5px 8px; color: #EDEDEF; }
QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #FF8C2A; }
QTextEdit, QPlainTextEdit { background-color: #1D2026; color: #EDEDEF; border: 1px solid #2B2F38; border-radius: 4px; }
QPlainTextEdit#ConsoleWidget { background-color: #0C0D10; color: #FFB060; font-family: 'Consolas', monospace; font-size: 12px; border-radius: 4px; border: none; }

/* === OTROS CONTROLES === */
QCheckBox { color: #EDEDEF; background-color: transparent; }
QCheckBox::indicator { width: 15px; height: 15px; border: 2px solid #3A3D44; border-radius: 4px; background-color: #1D2026; }
QCheckBox::indicator:checked { background-color: #FF6B00; border-color: #FF6B00; }
QGroupBox { border: 1px solid #2B2F38; border-radius: 8px; margin-top: 10px; font-weight: 700; color: #EDEDEF; background-color: transparent; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #FF8C2A; background-color: transparent; }
QLabel { color: #EDEDEF; background-color: transparent; }

/* === SCROLLBAR === */
QScrollBar:vertical { background: #1D2026; width: 8px; margin: 0; border-radius: 4px; }
QScrollBar::handle:vertical { background: #3A3D44; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #FF6B00; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1D2026; height: 8px; margin: 0; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #3A3D44; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #FF6B00; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* === TABS === */
QTabWidget::pane { border: 1px solid #2B2F38; background-color: #1D2026; border-radius: 6px; }
QTabBar::tab { background-color: #14161A; color: #9A9CA5; padding: 9px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; border: 1px solid #2B2F38; }
QTabBar::tab:selected { background-color: #FF6B00; color: #FFFFFF; font-weight: 700; border-color: #FF6B00; }
QTabBar::tab:hover:!selected { background-color: #2B2F38; color: #FFB060; }

/* === BARRA DE ESTADO === */
QStatusBar { background-color: #1B1E24; color: #FF8C2A; border-top: 1px solid #2B2F38; font-size: 12px; }

/* === PROGRESS BAR === */
QProgressBar { border: 1px solid #2B2F38; border-radius: 4px; text-align: center; background-color: #1D2026; color: #EDEDEF; }
QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6B00, stop:1 #FF8C2A); border-radius: 3px; }

/* === TOOLTIPS === */
QToolTip { background-color: #1D2026; color: #FFE0B2; border: 1px solid #FF6B00; padding: 5px 9px; border-radius: 4px; }
"""


def get_stylesheet(theme: str = "light") -> str:
    return DARK_QSS if theme == "dark" else LIGHT_QSS