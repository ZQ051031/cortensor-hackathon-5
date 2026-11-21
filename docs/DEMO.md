# Demo recording script

Aim for about three minutes. Use a terminal in the repo with the virtual
environment active, Ollama running, the model already pulled, and
`OPENMINION_HOME` exported as in the [README](../README.md). Use the public
inputs below. Keep the terminal wide enough to show source IDs and filenames.

## Run on camera

```bash
openminion --version
ollama list
research-brief 'What does READ_ONLY declare in the OpenMinion Python SDK lookup_order example? Paraphrase the evidence.' \
  --url https://raw.githubusercontent.com/openminion/openminion/v0.1.24/examples/sdk/tool_agent.py \
  --note examples/scope-notes.md \
  --config config/ollama.json \
  --model qwen2.5:3b-instruct
```

Wait for the preview to appear. Show the source IDs, scroll to the open
questions and next steps, then type `y`. Copy the displayed JSON path into
`python -m json.tool <session-log-path>` and show its successful tool event
and save status. If inference runs slowly, trim the wait between launch and
preview and label the cut.

## Spoken transcript

**0:00–0:25**

> This is a Research Brief Agent for Cortensor Hackathon #5. It turns a
> developer’s question and a few references into a Markdown brief with
> evidence, open questions, and next steps. Today I’m asking what the
> read-only scope declares in OpenMinion’s tagged Python example.

**0:25–1:00**

> I’m running OpenMinion 0.1.24 and Qwen2.5 3B Instruct locally through
> Ollama. The SDK runs the model in a new session and dispatches our read-only
> Python tool. The model supplies a research plan, and the tool reads the
> tagged SDK example and the scope note I supplied.

**1:00–2:15**

> Here’s the preview. The key points and evidence cite source IDs, and the
> source list shows where I can check each claim. The Markdown is still a
> draft. I can read it and press Enter to discard it. I’ll type yes to write
> the timestamped file.

**2:15–2:55**

> The separate JSON log records which source IDs were retrieved, the SDK
> session and run IDs, and whether I saved the draft. One thing I would
> improve in the SDK is how it reports what happened between a model tool
> decision and the actual invocation. The repository has the setup, a real
> example, and the full findings.

Check that the edit shows the actual preview and save, and that the final
video is between one and five minutes. Include the video link with the
public repo and findings when you submit.
