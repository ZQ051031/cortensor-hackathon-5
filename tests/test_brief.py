import pytest
from pydantic import ValidationError

from research_brief.brief import Brief, parse_brief, render_brief
from research_brief.sources import Source


@pytest.fixture
def brief():
    return Brief(
        executive_summary="The schedule is documented.",
        key_points=[{"text": "The event has a deadline.", "sources": ["S1"]}],
        evidence=[{"text": "The entry lists December 18.", "sources": ["S1", "S1"]}],
        open_questions=["When will the results be announced?"],
        next_steps=["Review the submission checklist."],
    )


def test_render_uses_actual_source_and_preserves_all_sections(brief):
    rendered = render_brief(
        "Event schedule",
        brief,
        [Source("S1", "Schedule", "December 18", "https://example.org", True)],
        "brief-test",
    )
    for section in (
        "Executive summary",
        "Key points",
        "Evidence",
        "Open questions",
        "Next steps",
    ):
        assert f"## {section}" in rendered
    assert "- The entry lists December 18. [S1]" in rendered
    assert "- [S1] Schedule — <https://example.org> (excerpt capped)" in rendered


def test_render_rejects_unknown_citations(brief):
    with pytest.raises(ValueError, match="outside the retrieved source list"):
        render_brief(
            "Event schedule", brief, [Source("S2", "Note", "Text")], "brief-test"
        )


def test_render_requires_evidence_when_sources_exist(brief):
    brief.evidence = []
    with pytest.raises(ValueError, match="omitted"):
        render_brief(
            "Event schedule", brief, [Source("S1", "Note", "Text")], "brief-test"
        )


def test_unverified_brief_has_explicit_empty_evidence(brief):
    brief.key_points = brief.evidence = []
    rendered = render_brief("Event schedule", brief, [], "brief-test")
    assert "No usable sources were retrieved." in rendered
    assert "Supply source URLs or notes for a grounded brief." in rendered


def test_schema_rejects_extra_fields_and_out_of_range_ids():
    with pytest.raises(ValidationError):
        Brief(
            executive_summary="Summary",
            key_points=[{"text": "Unsupported claim", "sources": ["S9"]}],
            evidence=[],
            open_questions=["Question"],
            next_steps=["Next step"],
            extra="Unexpected",
        )


@pytest.mark.parametrize("wrapper", ["{}", "```json\n{}\n```", "openminion: {}"])
def test_parse_final_json_after_a_tool_transcript(brief, wrapper):
    prefix = '{"status":"success","summary":"Tool executed successfully"}\n\n'
    answer = wrapper.format(brief.model_dump_json())
    assert parse_brief(f"{prefix}Final answer:\n{answer}") == brief
    assert parse_brief(answer) == brief


def test_render_keeps_model_text_on_one_line(brief):
    brief.executive_summary = "Summary\n# Header <script>\x1b"
    rendered = render_brief(
        "Event schedule", brief, [Source("S1", "Note", "Text")], "brief-test"
    )
    assert "Summary # Header &lt;script&gt;" in rendered
    assert "\x1b" not in rendered
