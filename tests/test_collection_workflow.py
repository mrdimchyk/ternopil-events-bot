from pathlib import Path


def test_collection_workflow_publishes_health_and_source_value_summary() -> None:
    workflow = Path(".github/workflows/collect-karabas.yml").read_text(encoding="utf-8")

    assert "Publish source health and value summary" in workflow
    assert 'report.get("source_value", {})' in workflow
    assert "Unique coverage" in workflow
    assert "overlap_ratio" in workflow
    assert "unique_coverage_ratio" in workflow
