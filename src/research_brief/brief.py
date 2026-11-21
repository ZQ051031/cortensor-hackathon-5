"""The typed model output and its deterministic Markdown rendering."""

from html import escape
import re
import unicodedata
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .sources import Source


Line = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=650)
]
SourceID = Annotated[str, StringConstraints(pattern=r"^S[1-4]$")]


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Line
    sources: list[SourceID] = Field(min_length=1, max_length=4)


class Brief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: Line
    key_points: list[Claim] = Field(max_length=5)
    evidence: list[Claim] = Field(max_length=5)
    open_questions: list[Line] = Field(min_length=1, max_length=4)
    next_steps: list[Line] = Field(min_length=1, max_length=4)


def parse_brief(text: str) -> Brief:
    # The SDK reply can include a tool transcript or a profile name prefix.
    candidate = f"\n{text.strip()}".rpartition("\nFinal answer:\n")[2].strip()
    candidate = re.sub(r"^[\w.-]+:[ \t]+", "", candidate, count=1)
    if candidate.startswith("```json\n") and candidate.endswith("\n```"):
        candidate = candidate.removeprefix("```json\n").removesuffix("\n```")
    return Brief.model_validate_json(candidate)


def markdown_text(text: str) -> str:
    visible = "".join(
        " " if char.isspace() else char
        for char in text
        if char.isspace() or unicodedata.category(char) not in {"Cc", "Cf"}
    )
    single_line = " ".join(visible.split())
    return re.sub(r"([\\`*_{}\[\]()])", r"\\\1", escape(single_line, quote=False))


def render_brief(
    question: str,
    brief: Brief,
    sources: list[Source],
    session_id: str,
) -> str:
    source_ids = {source.id for source in sources}
    used_ids = {
        source_id
        for claim in brief.key_points + brief.evidence
        for source_id in claim.sources
    }
    if used_ids - source_ids:
        raise ValueError("The model cited an ID outside the retrieved source list.")
    if sources and (not brief.key_points or not brief.evidence):
        raise ValueError("The model omitted cited key points or evidence.")

    lines = [
        f"# Research brief: {markdown_text(question)}",
        "",
        f"OpenMinion session: `{session_id}`",
        "",
        "## Executive summary",
        "",
        markdown_text(brief.executive_summary),
    ]
    for heading, claims in (
        ("Key points", brief.key_points),
        ("Evidence", brief.evidence),
    ):
        lines.extend(["", f"## {heading}", ""])
        for claim in claims:
            citations = ", ".join(dict.fromkeys(claim.sources))
            lines.append(f"- {markdown_text(claim.text)} [{citations}]")
        if not claims:
            lines.append("No usable sources were retrieved.")
    lines.extend(["", "### Sources", ""])
    for source in sources:
        label = markdown_text(source.label)
        link = f" — <{source.url}>" if source.url else " — local note"
        scope = " (excerpt capped)" if source.truncated else ""
        lines.append(f"- [{source.id}] {label}{link}{scope}")
    if not sources:
        lines.append("Supply source URLs or notes for a grounded brief.")
    for heading, values in (
        ("Open questions", brief.open_questions),
        ("Next steps", brief.next_steps),
    ):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {markdown_text(value)}" for value in values)
    return "\n".join(lines) + "\n"
