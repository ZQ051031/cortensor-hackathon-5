# Research brief: What does READ\_ONLY declare in the OpenMinion Python SDK lookup\_order example? Paraphrase the evidence.

OpenMinion session: `brief-48216123b4954e8a897bbef1aa4b74d0`

## Executive summary

READ\_ONLY declares the minimum SDK policy scope for invoking lookup\_order. It does not enforce how the underlying Python function accesses data.

## Key points

- The decorator sets the minimum invocation scope to READ\_ONLY. The Python function determines how it accesses data. [S1, S2]

## Evidence

- Run a tool-using Agent with a verifiable first tool call. from \_\_future\_\_ import annotations import argparse from openminion import Agent, ProviderError, tool @tool\(min\_scope="READ\_ONLY", idempotent=True\) def lookup\_order\(order\_id: str\) -&gt; str: \\"\\"\\"Return the current status for one order.\\"\\"\\" return f\\"order \{order\_id\}: ready\\" [S1]

### Sources

- [S1] https://raw.githubusercontent.com/openminion/openminion/v0.1.24/examples/sdk/tool\_agent.py — <https://raw.githubusercontent.com/openminion/openminion/v0.1.24/examples/sdk/tool_agent.py>
- [S2] scope-notes.md — local note

## Open questions

- What is the purpose of the idempotent=True parameter in the @tool decorator?
- Is there any specific reason for using an idempotent=True decorator for the lookup\_order function?

## Next steps

- Investigate the purpose of the idempotent=True parameter and the potential reasons for its use in the OpenMinion SDK.
