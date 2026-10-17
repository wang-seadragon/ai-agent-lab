import pytest

from app.knowledge.repository import KnowledgeRepository
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.models import VerifiedEntity, Relationship
from app.diagnostics.playbooks import DiagnosticPlaybookRegistry
from app.diagnostics.engine import DiagnosticEngine
from app.reviews.service import KnowledgeReviewService
from app.investigations.orchestrator import InvestigationOrchestrator


@pytest.fixture
def system(tmp_path):
    repo = KnowledgeRepository(tmp_path / "knowledge.sqlite3")
    graph = KnowledgeGraph(repo)
    registry = DiagnosticPlaybookRegistry(repo)
    review = KnowledgeReviewService(repo)
    orchestrator = InvestigationOrchestrator(graph, DiagnosticEngine(registry), repo)
    return repo, graph, registry, review, orchestrator


def test_empty_graph_escalates(system):
    _, graph, _, _, orchestrator = system
    assert orchestrator.investigate("INC-1", "pipeline-a", {}).status == "entity_unverified"
    with pytest.raises(ValueError):
        graph.add_entity(VerifiedEntity("pipeline-a", "pipeline"))
    graph.add_entity(VerifiedEntity("pipeline-a", "pipeline"), verified=True)
    assert orchestrator.investigate("INC-1", "pipeline-a", {}).status == "needs_engineer_review"


def test_engineer_approved_learning_cycle(system):
    _, graph, registry, review, orchestrator = system
    graph.add_entity(VerifiedEntity("pipeline-a", "pipeline"), verified=True)
    registry.propose("lag-v1", "pipeline", "check_lag")
    checks = {"check_lag": lambda _: True}
    assert orchestrator.investigate("INC-1", "pipeline-a", checks).status == "needs_engineer_review"
    with pytest.raises(ValueError):
        review.approve("lag-v1", "engineer", {"other_check"})
    review.approve("lag-v1", "engineer", {"check_lag"})
    result = orchestrator.investigate("INC-2", "pipeline-a", checks)
    assert result.status == "pattern_matched"
    assert result.playbook_id == "lag-v1"


def test_checks_fail_closed(system):
    _, graph, registry, review, orchestrator = system
    graph.add_entity(VerifiedEntity("a", "pipeline"), verified=True)
    registry.propose("p", "pipeline", "check")
    review.approve("p", "engineer", {"check"})
    assert orchestrator.investigate("1", "a", {}).status == "needs_engineer_review"
    assert orchestrator.investigate("2", "a", {"check": lambda _: None}).status == "needs_engineer_review"
    assert orchestrator.investigate("3", "a", {"check": lambda _: False}).status == "needs_engineer_review"


def test_data_persists_across_instances(system):
    repo, graph, _, _, _ = system
    graph.add_entity(VerifiedEntity("a", "pipeline"), verified=True)
    reopened = KnowledgeGraph(KnowledgeRepository(repo.path))
    assert reopened.get_entity("a") == VerifiedEntity("a", "pipeline")


def test_dependency_requires_verified_endpoints(system):
    _, graph, _, _, _ = system
    graph.add_entity(VerifiedEntity("a", "pipeline"), verified=True)
    with pytest.raises(Exception):
        graph.add_relationship(Relationship("a", "unknown"))


def test_graph_traversal(system):
    _, graph, _, _, _ = system
    graph.add_entity(VerifiedEntity("a", "pipeline"), verified=True)
    graph.add_entity(VerifiedEntity("b", "database"), verified=True)
    graph.add_relationship(Relationship("a", "b"))
    assert graph.get_dependencies("a") == [VerifiedEntity("b", "database")]
