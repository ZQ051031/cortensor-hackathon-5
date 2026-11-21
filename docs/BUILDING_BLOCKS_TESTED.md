# Building Blocks Tested

See [TEST_RESULTS.md](../TEST_RESULTS.md) for commands and observed outputs.
The SDK was installed from PyPI as `openminion==0.1.24` and checked against
upstream tag `v0.1.24`, commit `a52088443c67a47c8fbf660f47ec6f748b3247f3`.
The real provider was local Ollama 0.40.17. The tested models were Qwen3 1.7B,
Qwen3 4B Instruct, and Qwen2.5 3B Instruct, all Q4_K_M.
Version-specific behavior below follows the tagged source.

| Building block | How the project uses it | Observation |
| --- | --- | --- |
| Agent execution | `with Agent(...) as agent` and one synchronous `agent.run(..., timeout_seconds=420)` | The SDK orchestrates the turn and returns final text and run metadata. The CLI validates the final JSON against its Pydantic schema, tool execution, and the retrieved IDs. |
| Models | Ollama provider config, local `/api/chat`, and a `model=` override | Qwen2.5 3B Instruct completed the scoped run. The supplied profile allows 150 seconds per request and uses native tool calls. The default 60 seconds was too short in an early cold CPU run. |
| Tools | `@tool(min_scope="READ_ONLY", idempotent=True)`, `tools=[gather_sources]`, and `forced_tools=["gather_sources"]` | A model turn passed a plan and search query to the tool. Some turns invoked gathering more than once. The app reused the first result to avoid repeating I/O. |
| Permissions | A per-turn allowlist containing one decorated read-only tool | Source collection proceeded without an SDK approval prompt. The CLI requires explicit approval to write a Markdown file after displaying the preview. |
| Sessions | A fresh SDK `session_id` for each invocation, with the configured home holding SQLite state | The application log correlates the same session ID with source outcomes and output approval. The SDK session is separately inspectable through `openminion sessions show`. |
| Diagnostics | `openminion doctor --check-turn`, SDK exception types, `AgentRunResult` identifiers, and an app session log | The doctor exposed an Ollama HTTP 500 when the CPU runner was missing. The successful run and any failed source reads can be diagnosed from the CLI's output and log. |

The official [SDK examples](https://github.com/openminion/openminion/tree/v0.1.24/examples/sdk),
[tagged Agent implementation](https://github.com/openminion/openminion/blob/v0.1.24/src/openminion/api/agent.py),
[tagged decorator](https://github.com/openminion/openminion/blob/v0.1.24/src/openminion/tools/decorator.py),
and [tagged Ollama adapter](https://github.com/openminion/openminion/blob/v0.1.24/src/openminion/modules/llm/providers/ollama/adapter.py)
were used to verify the integration.

## Reproduced issue with agent profile names

**Environment:** OpenMinion 0.1.24, Python 3.11.18, Ubuntu 22.04.
This probe uses the SDK's echo provider and requires no model server or network.

Run this from the active project virtual environment. The temporary home
keeps the probe independent of the app's configuration.

```bash
python - <<'PY'
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from openminion import Agent

with TemporaryDirectory() as temp:
    os.environ["OPENMINION_HOME"] = temp
    path = Path(temp) / "agents.json"
    for name in ("Research Brief", "sample"):
        path.write_text(json.dumps({
            "default_agent": "sample",
            "enabled_channels": ["console"],
            "agents": {"sample": {
                "name": name,
                "provider": "echo",
                "default_channel": "console",
            }},
        }), encoding="utf-8")
        try:
            with Agent(config_path=str(path), tools=[]) as agent:
                result = agent.run("hello", timeout_seconds=15)
            print(f"{name!r}: {result.text}")
        except RuntimeError as exc:
            print(f"{name!r}: {type(exc).__name__}: {exc}")
PY
```

**Expected:** The configured default key `sample` resolves to the same agent
for either value of its `name` field, or config validation explains a
requirement that the two match.

**Actual:** The first turn looked for `Research Brief` as a profile key.
Explicitly passing `agent_id="sample"` produced the same error. Keeping the
config key and name aligned allowed the turn to complete.

```text
'Research Brief': UnknownProfileError: Unknown agent profile 'Research Brief'. Valid profiles: 'sample'.
'sample': sample: hello
```

The gateway resolves a profile by ID, and its runtime builder
[uses `profile.name` for a subsequent lookup](https://github.com/openminion/openminion/blob/v0.1.24/src/openminion/api/core/profiles.py#L672-L691).
This project keeps both fields set to `openminion` in the demo profile.

## CPU deadline and tool retries

The first full attempt used the official Ollama setup preset, an 8,192-token
context and `Agent.run(..., timeout_seconds=180)`. The tool retrieved three
sources. One Ollama chat request hit 60 seconds and the SDK retried. The turn
eventually raised `TurnTimeoutError: Turn execution timed out after 180.00
seconds.` The observed cause was request and turn timing on CPU. The app now
handles that exception and writes a failed session log without a brief.

To repeat the original setup, run the Ollama setup command in the README and
omit `--config` from the example. The installed app now uses a 420-second turn
budget. To reproduce the original deadline exactly, set the turn timeout to
180 in a local copy of `agent.py`. CPU speed, model state, and sampling affect
whether the deadline is reached.

Two later Qwen3 4B Instruct runs reached
`brain.closure_gate.started` after gathering all three sources and then hit
the app's turn deadlines at 300 and 420 seconds. The second attempt had
already logged five completed model calls before starting closure.

Qwen2.5 3B Instruct also gathered all three sources for the broad SDK
question. Its closure verdict returned `satisfied=false` and
`next_action=continue`, citing insufficient coverage in the excerpts.
The turn reached its 420-second deadline. The demo scopes its question to
the read-only tool pattern in the tagged SDK example.

## Typed output after the closure check

Qwen3 1.7B completed closure on the same inputs in a subsequent run. When
the system instructions carried the brief schema and the SDK's user message
contained only the research question, telemetry showed
`brain.closure_gate.completed`, `satisfied=true`, `next_action=close`, and
`finalization_status=final_answer`. The final assistant turn in the SDK's
session database was a prose sentence starting with “OpenMinion 0.1 is a
framework for building agent-based systems.” The CLI logged
`AgentOutputValidationError` and wrote no brief. To probe the behavior, pass
only `research.question` to `Agent.run` in a local copy and use the documented
demo command. Sampling may affect the returned format.

A follow-up restated the schema in the user message. The resulting JSON
merged two required arrays into `key_points_and_evidence`. After the prompt
showed the keys in a literal example, another run returned a tool transcript,
then `Final answer:` followed by a valid brief object. The SDK's
`output_type=Brief` attempted to validate the first JSON object, which was
the tool transcript. Source for that behavior is the tagged
[`Agent._coerce_output`](https://github.com/openminion/openminion/blob/v0.1.24/src/openminion/api/agent.py#L253-L283).

A later run persisted a valid JSON assistant turn but prefixed its returned
outbound message with `openminion: `. The shipped CLI reads
`AgentRunResult.text`, isolates the final answer when a standalone
`Final answer:` line is present, removes a profile prefix or JSON fence when
present, and validates the result. Offline regression cases cover each
observed wrapper. To reproduce the typed API behavior, pass
`output_type=Brief` in a local copy and run the sample, or feed a transcript
object followed by a brief object to the tagged parser while testing a patch.
