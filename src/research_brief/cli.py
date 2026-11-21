"""Preview and save a research brief with explicit operator approval."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from time import monotonic
from uuid import uuid4

from dotenv import load_dotenv
from openminion import ProviderError, TurnTimeoutError
from pydantic import ValidationError

from .agent import Research, draft
from .brief import render_brief
from .sources import MAX_SOURCES


def write_atomic(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        temp_path = Path(handle.name)
        try:
            handle.write(body)
            handle.close()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Topic or research question")
    parser.add_argument(
        "--url", action="append", default=[], help="Public HTTPS source"
    )
    parser.add_argument(
        "--note", action="append", default=[], type=Path, help="UTF-8 note"
    )
    parser.add_argument(
        "--config", help="OpenMinion config path (default: SDK configuration discovery)"
    )
    parser.add_argument(
        "--model", help="Model override for the configured SDK provider"
    )
    args = parser.parse_args(argv)
    question = args.question.strip()
    if not question or len(question) > 1200:
        parser.error("Question must contain between 1 and 1,200 characters.")
    if len(args.url) + len(args.note) > MAX_SOURCES:
        parser.error(f"Supply at most {MAX_SOURCES} sources per session.")

    load_dotenv(Path.cwd() / ".env", interpolate=False)
    config = args.config or os.getenv("RESEARCH_BRIEF_CONFIG") or None
    model = args.model or os.getenv("RESEARCH_BRIEF_MODEL") or None
    now = datetime.now(timezone.utc)
    session_id = f"brief-{uuid4().hex}"
    stem = f"{now:%Y%m%dT%H%M%SZ}-{session_id}"
    brief_path = Path("output") / f"{stem}.md"
    log_path = Path("output/sessions") / f"{stem}.json"
    research = Research(question, args.url, args.note)
    log = {
        "session_id": session_id,
        "started_at": now.isoformat(),
        "model_override": model,
        "events": research.events,
        "status": "started",
    }
    started = monotonic()
    print(f"OpenMinion session: {session_id}", flush=True)
    if not (args.url or args.note):
        print("Source discovery sends a search query to English Wikipedia.", flush=True)

    status = 0
    try:
        brief = draft(research, session_id, config, model)
        markdown = render_brief(question, brief, research.sources, session_id)
        for event in research.events:
            for warning in event.get("source_failures", []):
                print(f"Source warning: {warning}", file=sys.stderr)
        print(f"Collected {len(research.sources)} usable source(s).")
        print("\n--- Preview ---\n")
        print(markdown, end="")
        print("\n--- End preview ---")
        try:
            approved = input(f"Save this brief to {brief_path}? [y/N] ").strip().lower()
        except EOFError:
            approved = ""
        if approved in {"y", "yes"}:
            write_atomic(brief_path, markdown)
            log.update(status="saved", output_file=str(brief_path))
            print(f"Saved: {brief_path}")
        else:
            log["status"] = "declined"
            print("\nDraft discarded.")
    except ValidationError:
        log.update(status="failed", error="BriefValidationError")
        print(
            "OpenMinion returned an invalid brief. Retry or use a stronger model.",
            file=sys.stderr,
        )
        status = 1
    except ProviderError as exc:
        log.update(status="failed", error="ProviderError", provider_code=exc.code)
        print(
            f"Model request failed ({exc.code}). Check the configured provider.",
            file=sys.stderr,
        )
        status = 1
    except TurnTimeoutError:
        log.update(status="failed", error="TurnTimeoutError")
        print(
            "OpenMinion timed out. Try again with fewer sources or a faster model.",
            file=sys.stderr,
        )
        status = 1
    except (OSError, RuntimeError, ValueError) as exc:
        log.update(status="failed", error=type(exc).__name__)
        print(
            f"Run failed ({type(exc).__name__}). Check the SDK config, sources, and output permissions.",
            file=sys.stderr,
        )
        status = 1
    except KeyboardInterrupt:
        log["status"] = "interrupted"
        print("\nRun interrupted.", file=sys.stderr)
        status = 130
    finally:
        log["elapsed_seconds"] = round(monotonic() - started, 3)
        try:
            write_atomic(log_path, json.dumps(log, indent=2) + "\n")
        except OSError:
            print("Could not write the session log.", file=sys.stderr)
            status = 1
        else:
            print(f"Session log: {log_path}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
