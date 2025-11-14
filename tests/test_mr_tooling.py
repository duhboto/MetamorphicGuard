import json

import pytest
from click.testing import CliRunner

from metamorphic_guard.cli.main import main as cli_main
from metamorphic_guard.mr import discover_relations, prioritize_relations
from metamorphic_guard.relations import permute_input
from metamorphic_guard.specs import MetamorphicRelation, Property, Spec, register_spec


@pytest.fixture(scope="module")
def sample_spec_name() -> str:
    spec = Spec(
        gen_inputs=lambda seed, n: [([1, 2, 3, 4], 2)],
        properties=[
            Property(lambda *_args: True, "Ensure robust ranking order under noise"),
            Property(lambda *_args: True, "Maintain monotonic fairness parity targets"),
        ],
        relations=[
            MetamorphicRelation(
                name="permute",
                transform=permute_input,
                category="stability",
                description="Baseline stability guard",
            )
        ],
        equivalence=lambda baseline, candidate: baseline == candidate,
    )
    register_spec("sample_mr_spec", spec, overwrite=True)
    return "sample_mr_spec"


def test_discovery_emits_keyword_categories(sample_spec_name: str) -> None:
    from metamorphic_guard.specs import get_task

    spec = get_task(sample_spec_name)
    suggestions = discover_relations(spec)
    categories = {entry["category"] for entry in suggestions}
    assert "robustness" in categories
    assert any("monotonic" in entry["suggestion"].lower() for entry in suggestions)


def test_prioritize_relations_reports_missing_categories(sample_spec_name: str) -> None:
    from metamorphic_guard.specs import get_task

    spec = get_task(sample_spec_name)
    suggestions, coverage = prioritize_relations(spec, max_items=3)
    assert "robustness" in coverage["missing_categories"]
    assert suggestions, "expected at least one suggestion"
    top = suggestions[0]
    assert "score" in top and top["score"] > 0
    assert top["reason"]


def test_cli_prioritize_json_output(sample_spec_name: str) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["mr", "prioritize", sample_spec_name, "--format", "json", "--limit", "2"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "coverage" in payload and "suggestions" in payload
    assert payload["suggestions"], "CLI should emit suggestion payload"


