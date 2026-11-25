# Test Results

## Environment

- Ubuntu 22.04.5 LTS, x86-64, CPU inference
- Python 3.11.18 and OpenMinion 0.1.24 (PyPI)
- Ollama 0.40.17 with an 8,192-token context, bound to `127.0.0.1:11434`
- Demo model `qwen2.5:3b-instruct` (Q4_K_M)
- Ollama model manifest digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`

## Clean install and offline verification

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m pip check
```

The current suite passed **28 tests, 0 failed**. `pip check` reported
`No broken requirements found.` The suite exercises URL restrictions, HTML
and note extraction, bounded discovery, partial source failures, schema and
citation validation, final JSON extraction, approval, decline, EOF, exact
preview preservation, timeout handling, and the distinction between
`READ_ONLY` policy scope and Python data access in the sample.
Ruff lint and formatting checks passed for `src/` and `tests/`.
A wheel built successfully with
`python -m pip wheel --no-deps .`.

## Live model verification

### Latency profile and verification command

The profile used the corrected scope wording and the original Ollama
configuration. Each request was timed at the SDK's Ollama HTTP boundary,
and source gathering was timed separately.

| Stage | Calls | Time (seconds) |
| --- | ---: | ---: |
| Automatic fact extraction | 1 | 24.495 |
| Entry | 1 | 23.333 |
| Freshness classification | 1 | 12.146 |
| Source gathering and reuse | 2 | 0.182 |
| Action and synthesis | 5 | 133.785 |
| Closure judge | 1 | 32.901 |

The profiled CLI run took 228.632 seconds, retrieved both source IDs, and
rejected the model's draft because it returned five open questions (the
schema allows four). Ollama requests accounted for 226.660
seconds, with action and synthesis taking the largest share. The single
optimization round disabled the SDK's optional preliminary fact extraction
in the Ollama profile. That call stages candidates for memory. The
research turn still plans, gathers evidence, and drafts the brief through
OpenMinion with the same model and instructions as the profiled run.
[OpenMinion configuration reference](https://github.com/openminion/openminion/blob/v0.1.24/docs/turn-budgets.md#automatic-fact-extraction)

```bash
export OPENMINION_HOME="$PWD/.openminion-home"
printf 'y\n' | research-brief 'What does READ_ONLY declare in the OpenMinion Python SDK lookup_order example?' \
  --url https://raw.githubusercontent.com/openminion/openminion/v0.1.24/examples/sdk/tool_agent.py \
  --note examples/scope-notes.md \
  --config config/ollama.json \
  --model qwen2.5:3b-instruct
```

Both timed runs used that command with `qwen2.5:3b-instruct` and the same
model digest. The SDK logged `brain.auto_fact_extraction.skipped` with
reason `disabled` on both runs.

| Run | Wall clock (seconds) | Sources retrieved | Outcome |
| --- | ---: | --- | --- |
| 1 | **126.721** | S1 and S2 | Exit 1. The reply exceeded the open-question limit and incorrectly claimed that `READ_ONLY` limits subsequent calls. |
| 2 | 98.550 | S1 and S2 | Exit 0. The saved file matched the preview byte for byte. The model still described `READ_ONLY` too broadly as restricting the agent's actions. |

The slower wall-clock time was **126.721 seconds**. It missed the
60-second target and exceeded the 90-second stop line. The checked-in
sample gives the corrected policy-scope explanation. These live runs
showed that the model can still misstate it despite that guidance.

```text
Run 1 log: output/sessions/20261125T071456Z-brief-2c0bbb1a904346e69d43880bc038d407.json
Run 2 log: output/sessions/20261125T071702Z-brief-9af127ae69b646c2b7ec66ba2faa8067.json
Run 2 brief: output/20261125T071702Z-brief-9af127ae69b646c2b7ec66ba2faa8067.md
```

### Historical 118.796-second run

The isolated home, local server, and model were set up using the [README](README.md#prerequisites-and-setup).
The verification command piped the same response an operator can enter at
the prompt.

```bash
export OPENMINION_HOME="$PWD/.openminion-home"
printf 'y\n' | research-brief 'What does READ_ONLY declare in the OpenMinion Python SDK lookup_order example? Paraphrase the evidence.' \
  --url https://raw.githubusercontent.com/openminion/openminion/v0.1.24/examples/sdk/tool_agent.py \
  --note examples/scope-notes.md \
  --config config/ollama.json \
  --model qwen2.5:3b-instruct
```

Exit status was **0**. The tool retrieved `S1` and `S2` with no source
errors. OpenMinion recorded the turn as `completed` and the CLI recorded
`status: saved` after **118.796 seconds**. The timestamped file matched the
five-section preview byte for byte. This command ends with
`Paraphrase the evidence.`, which was absent from the latency verification
command above.

```text
Collected 2 usable source(s).
Saved: output/20261121T184018Z-brief-48216123b4954e8a897bbef1aa4b74d0.md
Session log: output/sessions/20261121T184018Z-brief-48216123b4954e8a897bbef1aa4b74d0.json
```

The original output SHA-256 was
`1e9e92bddda5a68b9fcd75f47405078a9706a81e94935e417ee0dd28c9ae2bc8`.
The [sample brief](examples/sample-brief.md) edits the wording in that
output to clarify that `min_scope="READ_ONLY"` declares the minimum SDK
policy scope for invocation. The Python function determines how it accesses
data.

An earlier run asked “How does the OpenMinion 0.1 SDK register a read-only
Python tool and force it to be called first?” with the same source arguments
and model. It saved in 282.040 seconds. Its generated text correctly cited
the read-only decorator and missed `Agent(forced_tools=...)`, which controls
the forced first call.

Another question, “How does the OpenMinion 0.1 Python SDK example
declare a read-only tool?”, also retrieved both sources and completed the
SDK turn. It returned `key_points` as strings without citations, and
the CLI exited 1 with `BriefValidationError`. No Markdown was written.

## Failures resolved during testing

- An incomplete Ollama archive extraction omitted `llama-server`.
  `openminion doctor --check-turn` reported the underlying provider's
  HTTP 500. Installing the full official archive restored the runner.
- The original SDK setup preset allowed 60 seconds per model request. The
  first CPU attempt logged three retrieved sources and an SDK retry, then
  raised a 180-second turn timeout. The shipped profile uses native tool
  calls and a 150-second per-request budget, and the app uses a 420-second
  turn budget with a graceful timeout error. At 300 and 420 seconds, later
  Qwen3 4B Instruct attempts reached the SDK's closure check before timing
  out. Qwen2.5 3B Instruct retrieved all three sources on the broad SDK
  question, but its closure check requested more evidence and the turn hit
  the 420-second budget. Qwen3 1.7B also reached the deadline on a shorter
  question after retrieving both sources. The demo uses the shorter question
  and explicitly asks the model to report coverage gaps in `open_questions`.
- Qwen3 1.7B reached closure, but the final text was prose and failed the
  SDK's Pydantic validation. A follow-up with a verbal JSON contract returned
  JSON with a combined `key_points_and_evidence` field and also failed
  validation. The app includes a literal JSON shape with both keys in the
  user message that the closure step reads. When a subsequent runtime reply
  put a tool transcript first, `output_type=Brief` tried that JSON object.
  The CLI now isolates the final reply, handles the profile prefix observed
  in the SDK's outbound message, and validates the brief itself.
- A separate display name triggered a profile-lookup failure. Matching
  the name to its config key and enabling the console ingress in the
  example profile resolved setup. The isolated reproduction is in
  [Building Blocks Tested](docs/BUILDING_BLOCKS_TESTED.md#reproduced-issue-with-agent-profile-names).
