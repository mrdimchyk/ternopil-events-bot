from pathlib import Path


def test_tests_workflow_avoids_duplicate_post_merge_run():
    workflow = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")
    trigger_block = workflow.split("jobs:", 1)[0]

    assert "pull_request:" in trigger_block
    assert "branches: [main]" in trigger_block
    assert "workflow_dispatch:" in trigger_block
    assert "push:" not in trigger_block
