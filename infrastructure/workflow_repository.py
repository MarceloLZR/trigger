"""
infrastructure.workflow_repository
------------------------------------
Lee /workflows/*.json y construye objetos Workflow (secuencias de procesos).
"""
from __future__ import annotations
import json
from pathlib import Path

from core.interfaces import IWorkflowRepository
from core.models import Workflow


class WorkflowRepository(IWorkflowRepository):
    def __init__(self, workflows_root: Path):
        self.workflows_root = Path(workflows_root)

    def load_all(self) -> list[Workflow]:
        if not self.workflows_root.exists():
            return []
        workflows = []
        for json_path in sorted(self.workflows_root.glob("*.json")):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            workflows.append(Workflow.from_dict(data, workflow_id=json_path.stem))
        return workflows
