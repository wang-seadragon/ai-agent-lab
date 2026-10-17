"""Knowledge graph and investigation value objects."""
from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedEntity:
    entity_id: str
    kind: str


@dataclass(frozen=True)
class Relationship:
    source_id: str
    target_id: str


@dataclass(frozen=True)
class Investigation:
    incident_id: str
    entity_id: str
    status: str
    findings: tuple[str, ...]
    playbook_id: str | None = None
