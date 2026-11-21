# What We Learned

## Keep profile identity stable across the run

OpenMinion 0.1.24 accepted a profile keyed by `sample` with the name
`Research Brief`, but the turn reselected the profile by name and failed
before reaching the provider. Keeping the name equal to the key fixed the
demo. Carry the canonical profile ID through gateway creation and runtime
caching. Add a regression test that exercises a human-readable name different
from the ID. If the fields are intended to match, validate the invariant at
load time and explain it in the config reference. The
[reproduction](BUILDING_BLOCKS_TESTED.md#reproduced-issue-with-agent-profile-names)
uses the echo provider and takes no model credentials.

## Expose both deadlines and the tool timeline

The Ollama preset's per-request deadline and the SDK turn deadline are
separate settings. On the VM, the preset's 60-second request deadline was hit
while the 180-second turn was still active. A later turn deadline was the
exception exposed to the app. Add a turn diagnostics summary that includes the
effective provider deadline, remaining turn budget, retry count, and a
redacted final provider code. A tool event sequence with the requested name,
the resolved name, and execution status would help applications distinguish a
model decision, a policy denial, a repeated request, and a successful call.
The app currently records tool starts and finishes itself.

## Document a small, keyless reference run

Cortensor and OpenMinion can give hackathon entrants a pinned Ollama profile
with native tool calls, a tested local model digest, a context setting, and
cold versus warm CPU timing. Include a smoke example that performs one
read-only tool call and emits a schema-valid answer. That gives participants
a known baseline for diagnosing the SDK before evaluating a hosted provider.
A complete example profile should show the agent key, display name, and
enabled/default console channel together.

## Make structured evidence reviewable

In 0.1.24, `Agent(output_type=...)` validates the final text after the runtime
returns. A turn reached the closure check, which returned a one-sentence
answer, and then failed schema validation in the SDK. A later reply included
a tool transcript before valid final JSON, and the typed API tried the tool
transcript first. Carry the declared output schema through closure and
separate the final answer from tool transcript text in the SDK result.
Expose whether validation failed on the original synthesis or on a closure
rewrite.

Citation ID validation confirms which excerpts to review. A tagged SDK
example could join typed output to tool receipts so builders can present
reviewers with both the claim and the exact excerpt behind its citation.
The first saved brief cited a real source but missed the example's
`forced_tools` setting. Showing the excerpt beside the citation would
make that omission easier to catch at preview time.
