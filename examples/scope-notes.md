# Demo scope

Audience: a Python developer building a small agent for Cortensor Hackathon #5.

Focus on the OpenMinion 0.1 Python SDK. Find the minimum useful path from
provider setup and one agent turn to a read-only tool and an inspectable
session. Keep deployment and advanced workflows outside this brief.

In OpenMinion 0.1.24, `min_scope="READ_ONLY"` declares the minimum SDK
policy scope for invoking the tool. It does not enforce how the underlying
Python function accesses data. The SDK compares the effective scope to the
tool's minimum scope before invocation.

Source
https://github.com/openminion/openminion/blob/v0.1.24/src/openminion/modules/tool/runtime/policy_access.py#L55-L69
