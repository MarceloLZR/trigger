"""
ui.main_window
------------------
Ventana principal: sidebar de navegación, barra superior con búsqueda
y toggle de tema, barra de estado, y un QStackedWidget con todas las
vistas. Es el "Composition Root" de la UI: instancia las vistas e
inyecta las dependencias de infrastructure/application.
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel,
    QPushButton, QStackedWidget, QLineEdit, QStatusBar, QButtonGroup, QApplication
)

from core.models import ProcessDefinition
from infrastructure.db.connection_manager import ConnectionManager
from infrastructure.process_repository import ProcessRepository
from infrastructure.workflow_repository import WorkflowRepository
from infrastructure.sql_template_engine import SqlTemplateEngine
from infrastructure.excel_exporter import ExcelExporter
from infrastructure.csv_exporter import CsvExporter
from infrastructure.email_sender import EmailSender
from application.history_service import HistoryService

from ui.theme import get_stylesheet
from ui.views.dashboard_view import DashboardView
from ui.views.module_processes_view import ModuleProcessesView
from ui.views.process_run_view import ProcessRunView
from ui.views.quick_execution_view import QuickExecutionView
from ui.views.workflows_view import WorkflowsView
from ui.views.settings_view import SettingsView
from ui.views.history_view import HistoryView

import sys

if getattr(sys, 'frozen', False):
    # If bundled via PyInstaller, use the temporary _MEIPASS folder (for -F) 
    # or the bundle directory (for -D)
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQL Automation Suite — Área de Negocio")
        self.resize(1280, 800)

        self.theme = "light"

        # ---- Composition root: dependencias compartidas ----
        self.connection_manager = ConnectionManager.instance()
        self.process_repository = ProcessRepository(PROJECT_ROOT / "processes")
        self.workflow_repository = WorkflowRepository(PROJECT_ROOT / "workflows")
        self.template_engine = SqlTemplateEngine()
        self.excel_exporter = ExcelExporter()
        self.csv_exporter = CsvExporter()
        self.email_sender = EmailSender()
        self.history_service = HistoryService()

        self.processes: list[ProcessDefinition] = self.process_repository.load_all()
        self.workflows = self.workflow_repository.load_all()

        self._build_ui()
        self._reload_data()

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_sidebar())

        right_panel = QVBoxLayout()
        right_panel.setSpacing(0)
        right_panel.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        right_panel.addWidget(self.stack, 1)

        right_container = QWidget()
        right_container.setLayout(right_panel)
        outer.addWidget(right_container, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo.")

        # ---- vistas ----
        self.dashboard_view = DashboardView()
        self.module_view = ModuleProcessesView()
        self.process_run_view = ProcessRunView(
            self.connection_manager, self.template_engine, self.excel_exporter, 
            self.csv_exporter, self.email_sender, self.history_service
        )
        self.quick_execution_view = QuickExecutionView(
            self.connection_manager, self.template_engine, self.history_service
        )
        self.workflows_view = WorkflowsView(
            self.connection_manager, self.template_engine, self.process_repository, self.history_service
        )
        self.settings_view = SettingsView(self.connection_manager)
        self.history_view = HistoryView(self.history_service)

        for view in [
            self.dashboard_view, self.module_view, self.process_run_view,
            self.quick_execution_view, self.workflows_view, self.settings_view, self.history_view
        ]:
            self.stack.addWidget(view)

        self.dashboard_view.module_selected.connect(self._open_module)
        self.module_view.back_requested.connect(lambda: self.stack.setCurrentWidget(self.dashboard_view))
        self.module_view.process_selected.connect(self._open_process)
        self.process_run_view.back_requested.connect(lambda: self.stack.setCurrentWidget(self.module_view))

        self.stack.setCurrentWidget(self.dashboard_view)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(2)

        title = QLabel("SQL Automation\nSuite")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("🏠  Panel principal", "dashboard"),
            ("⚡  Ejecución rápida", "quick"),
            ("🔗  Workflows", "workflows"),
            ("🕘  Historial", "history"),
            ("⚙️  Configuración", "settings"),
        ]
        self._nav_buttons = {}
        for label, key in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self.nav_group.addButton(btn)
            layout.addWidget(btn)
            self._nav_buttons[key] = btn

        self._nav_buttons["dashboard"].setChecked(True)
        layout.addStretch()
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(56)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(16, 8, 16, 8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchBar")
        self.search_input.setPlaceholderText("Buscar proceso...")
        self.search_input.setFixedWidth(320)
        self.search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_input)
        layout.addStretch()

        self.theme_btn = QPushButton("🌙 Tema oscuro")
        self.theme_btn.setObjectName("SecondaryButton")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        return topbar

    # ------------------------------------------------------------------
    def _reload_data(self):
        self.processes = self.process_repository.load_all()
        self.workflows = self.workflow_repository.load_all()
        self.dashboard_view.set_processes(self.processes)
        self.quick_execution_view.set_processes(self.processes)
        self.workflows_view.set_workflows(self.workflows)
        self.status_bar.showMessage(
            f"{len(self.processes)} procesos y {len(self.workflows)} workflows cargados."
        )

    def _navigate(self, key: str):
        mapping = {
            "dashboard": self.dashboard_view,
            "quick": self.quick_execution_view,
            "workflows": self.workflows_view,
            "history": self.history_view,
            "settings": self.settings_view,
        }
        view = mapping[key]
        if key == "history":
            self.history_view.refresh()
        self.stack.setCurrentWidget(view)

    def _open_module(self, module_name: str):
        self.module_view.set_module(module_name, self.processes)
        self.stack.setCurrentWidget(self.module_view)

    def _open_process(self, process_id: str):
        process = self.process_repository.get_by_id(process_id)
        self.process_run_view.set_process(process)
        self.stack.setCurrentWidget(self.process_run_view)

    def _on_search(self):
        query = self.search_input.text().strip().lower()
        if not query:
            return
        matches = [p for p in self.processes if query in p.name.lower()]
        if matches:
            self._open_process(matches[0].id)
            self.status_bar.showMessage(f"{len(matches)} resultado(s) para '{query}'.")
        else:
            self.status_bar.showMessage(f"Sin resultados para '{query}'.")

    def _toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        QApplication.instance().setStyleSheet(get_stylesheet(self.theme))
        self.theme_btn.setText("☀️ Tema claro" if self.theme == "dark" else "🌙 Tema oscuro")