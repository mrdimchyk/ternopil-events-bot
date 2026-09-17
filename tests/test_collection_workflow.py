from pathlib import Path

import yaml


def test_collection_workflow_publishes_health_and_source_value_summary() -> None:
    workflow = Path(".github/workflows/collect-karabas.yml").read_text(encoding="utf-8")

    assert "Publish source health and value summary" in workflow
    assert 'report.get("source_value", {})' in workflow
    assert "Unique coverage" in workflow
    assert "overlap_ratio" in workflow
    assert "unique_coverage_ratio" in workflow


def test_collection_workflow_does_not_run_on_every_main_push() -> None:
    workflow = yaml.safe_load(
        Path(".github/workflows/collect-karabas.yml").read_text(encoding="utf-8")
    )
    # PyYAML 1.1 resolves the unquoted YAML key `on` as boolean True.
    triggers = workflow.get("on", workflow.get(True, {}))

    assert "workflow_dispatch" in triggers
    assert "schedule" in triggers
    assert "push" not in triggers
