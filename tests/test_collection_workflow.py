from pathlib import Path
import re


def test_collection_workflow_publishes_health_and_source_value_summary() -> None:
    workflow = Path(".github/workflows/collect-karabas.yml").read_text(encoding="utf-8")

    assert "Publish source health and value summary" in workflow
    assert 'report.get("source_value", {})' in workflow
    assert "Unique coverage" in workflow
    assert "overlap_ratio" in workflow
    assert "unique_coverage_ratio" in workflow


def test_collection_workflow_does_not_run_on_every_main_push() -> None:
    workflow = Path(".github/workflows/collect-karabas.yml").read_text(encoding="utf-8")
    trigger_block = workflow.split("jobs:", 1)[0]

    assert re.search(r"^\s{2}workflow_dispatch:\s*$", trigger_block, re.MULTILINE)
    assert re.search(r"^\s{2}schedule:\s*$", trigger_block, re.MULTILINE)
    assert not re.search(r"^\s{2}push:\s*$", trigger_block, re.MULTILINE)
