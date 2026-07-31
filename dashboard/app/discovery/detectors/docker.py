"""Docker / Docker Compose presence -- an automation/deployment signal."""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.detectors.inventory import FolderInventory

COMPOSE_FILE_NAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}


@dataclass
class DockerFindings:
    has_dockerfile: bool = False
    has_docker_compose: bool = False


def detect(inventory: FolderInventory) -> DockerFindings:
    findings = DockerFindings()
    for f in inventory.files:
        if f.stem_lower.startswith("dockerfile"):
            findings.has_dockerfile = True
        if f.stem_lower in COMPOSE_FILE_NAMES:
            findings.has_docker_compose = True
    return findings
