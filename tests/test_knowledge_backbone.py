import pytest

from app.knowledge.backbone import KnowledgeBackbone


@pytest.fixture
def backbone(tmp_path):
    return KnowledgeBackbone(tmp_path / "knowledge.sqlite3")


def test_empty_graph_escalates(backbone):
    result = backbone.investigate("INC-1", "pipeline-a", {})
    assert result.status == "entity_unverified"
    with pytest.raises(ValueError):
        backbone.register_verified_entity("pipeline-a", "pipeline")
    backbone.register_verified_entity("pipeline-a", "pipeline", verified=True)
    result = backbone.investigate("INC-1", "pipeline-a", {})
    assert result.status == "needs_engineer_review"


def test_engineer_approved_learning_cycle(backbone):
    backbone.register_verified_entity("pipeline-a", "pipeline", verified=True)
    backbone.propose_playbook("lag-v1", "pipeline", "check_lag")
    assert backbone.investigate("INC-1", "pipeline-a", {"check_lag": lambda _: True}).status == "needs_engineer_review"
    with pytest.raises(ValueError):
        backbone.approve_playbook("lag-v1", "engineer", {"other_check"})
    backbone.approve_playbook("lag-v1", "engineer", {"check_lag"})
    result = backbone.investigate("INC-2", "pipeline-a", {"check_lag": lambda _: True})
    assert result.status == "pattern_matched"
    assert result.playbook_id == "lag-v1"


def test_checks_fail_closed(backbone):
    backbone.register_verified_entity("a", "pipeline", verified=True)
    backbone.propose_playbook("p", "pipeline", "check")
    backbone.approve_playbook("p", "engineer", {"check"})
    assert backbone.investigate("1", "a", {}).status == "needs_engineer_review"
    assert backbone.investigate("2", "a", {"check": lambda _: None}).status == "needs_engineer_review"
    assert backbone.investigate("3", "a", {"check": lambda _: False}).status == "needs_engineer_review"


def test_data_persists_across_instances(backbone, tmp_path):
    backbone.register_verified_entity("a", "pipeline", verified=True)
    reopened = KnowledgeBackbone(tmp_path / "knowledge.sqlite3")
    assert reopened.investigate("INC-3", "a", {}).status == "needs_engineer_review"


def test_dependency_requires_verified_endpoints(backbone):
    backbone.register_verified_entity("a", "pipeline", verified=True)
    with pytest.raises(Exception):
        backbone.add_dependency("a", "unknown")
