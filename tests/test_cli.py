import json
from pathlib import Path

from openminion import TurnTimeoutError
import pytest

from research_brief import cli
from research_brief.brief import Brief, parse_brief
from research_brief.sources import Source


@pytest.fixture
def draft_stub(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def draft(research, session_id, config, model):
        research.sources.append(Source("S1", "Local note", "Tested behavior"))
        research.events.append({"event": "agent_finished", "session_id": session_id})
        return Brief(
            executive_summary="Summary",
            key_points=[{"text": "Point", "sources": ["S1"]}],
            evidence=[{"text": "Evidence", "sources": ["S1"]}],
            open_questions=["Question?"],
            next_steps=["Next step"],
        )

    monkeypatch.setattr(cli, "draft", draft)


def session_log():
    (path,) = Path("output/sessions").glob("*.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_approval_saves_exact_preview(draft_stub, monkeypatch, capsys):
    def approve(_):
        assert list(Path("output").glob("*.md")) == []
        return "yes"

    monkeypatch.setattr("builtins.input", approve)
    assert cli.main(["Check the workflow", "--note", "note.md"]) == 0
    output = capsys.readouterr().out
    (path,) = Path("output").glob("*.md")
    preview = output.split("--- Preview ---\n\n", 1)[1].split("\n--- End preview ---")[
        0
    ]
    assert path.read_text(encoding="utf-8") == preview
    log = session_log()
    assert log["status"] == "saved"
    assert log["output_file"] == str(path)
    assert log["session_id"] in path.name


@pytest.mark.parametrize("response", ["no", "", None])
def test_decline_or_eof_leaves_no_brief(draft_stub, monkeypatch, response):
    def decline(_):
        if response is None:
            raise EOFError
        return response

    monkeypatch.setattr("builtins.input", decline)
    assert cli.main(["Check the workflow", "--note", "note.md"]) == 0
    assert list(Path("output").glob("*.md")) == []
    assert session_log()["status"] == "declined"


def test_output_validation_failure_does_not_echo_raw_model_text(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)

    def fail(*_):
        return parse_brief("private content")

    monkeypatch.setattr(cli, "draft", fail)
    assert cli.main(["Check the workflow"]) == 1
    assert "private content" not in capsys.readouterr().err
    assert list(Path("output").glob("*.md")) == []
    assert session_log()["error"] == "BriefValidationError"


def test_sdk_deadline_records_failure_without_writing_brief(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)

    def fail(*_):
        raise TurnTimeoutError("Turn execution timed out after 300.00 seconds.")

    monkeypatch.setattr(cli, "draft", fail)
    assert cli.main(["Check the workflow"]) == 1
    assert "OpenMinion timed out." in capsys.readouterr().err
    assert list(Path("output").glob("*.md")) == []
    log = session_log()
    assert log["status"] == "failed"
    assert log["error"] == "TurnTimeoutError"
