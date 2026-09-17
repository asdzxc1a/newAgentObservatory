# ChatGPT Native Subagent Primitive

This turns **subagents into tools ChatGPT can call** from a normal conversation.

It is deliberately two-layered:

1. **Preferred path — OpenAI hosted multi-agent (experimental):** the server uses `OpenAIHostedMultiAgentModel`, so a GPT-5.6 root model can create and coordinate server-hosted subagents.
2. **Fallback path — explicit Agents SDK fan-out/fan-in:** the server launches specialist `Agent` runs concurrently with `asyncio.gather`, then a synthesizer agent merges the results.

The whole thing is exposed as a standard **MCP Streamable HTTP server**, which ChatGPT can attach as a custom connector/app. Once connected, `delegate` and `swarm` show up to the model as normal tools — effectively a subagent primitive inside chat.

## Tools

### `delegate`
Run one specialist subagent.

Example intent:

> Use delegate as a security reviewer and inspect this design for attack surfaces.

### `swarm`
Run multiple specialists, then synthesize a final answer.

Example intent:

> Use swarm on this architecture with roles: distributed-systems engineer, security engineer, product architect, and skeptic. Work in parallel and synthesize one plan.

Modes:

- `auto` — prefer hosted multi-agent, fall back to explicit parallel agents.
- `hosted` — require the experimental hosted multi-agent path.
- `local` — force explicit Agents SDK parallel fan-out/fan-in.

## Why this is materially different from prompt-only role play

Each fallback specialist is an independent Agents SDK run with its own agent instructions and model turn. The hosted path is stronger: OpenAI's experimental Responses multi-agent runtime creates and coordinates subagents server-side.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...
python server.py
```

Your MCP endpoint is:

```text
http://localhost:8000/mcp
```

For a public tunnel, set `MCP_PUBLIC_HOST` to the tunnel hostname (without `https://`) before starting the server, then connect ChatGPT to the public `/mcp` URL. The server keeps MCP DNS-rebinding protection enabled and allowlists local hosts plus configured public hosts.

## Put it in ChatGPT

1. Deploy this directory to a public HTTPS host (Render config is included), or expose the local port with a secure tunnel.
2. Set `OPENAI_API_KEY` as a secret environment variable on the host.
3. In ChatGPT, enable Developer Mode.
4. Go to **Settings → Connectors** and add the public MCP endpoint, e.g. `https://your-service.onrender.com/mcp`.
5. Add/select the connector in your conversation.
6. Ask ChatGPT to use `swarm` or `delegate`.

## Recommended parent-agent instruction

```text
You have a subagent primitive. Use `delegate` for one bounded specialist task. Use `swarm` when the task benefits from independent parallel perspectives, adversarial review, decomposition, or research branches. Do not delegate trivial work. When using `swarm`, choose non-overlapping roles, preserve disagreements, and synthesize rather than majority-vote.
```

## Render

The Blueprint is `chatgpt_subagent_mcp/render.yaml`. When creating a Render Blueprint from this repository, select the `chatgpt-native-subagents` branch and set the **Blueprint Path** to `chatgpt_subagent_mcp/render.yaml`. The service itself sets `rootDir: chatgpt_subagent_mcp`, so builds run from the correct monorepo directory.

The only required secret is `OPENAI_API_KEY`. Render injects `RENDER_EXTERNAL_HOSTNAME` automatically, and the server uses it to build its MCP Host/Origin allowlist. If you later put the service behind another public hostname, set `MCP_PUBLIC_HOST` to that hostname too.

For broad/public distribution, add connector authentication and normal production controls (rate limits, budgets, logging/redaction policy) around the MCP endpoint.

## Why the server calls OpenAI directly

ChatGPT Apps/custom MCP connectors currently do not expose MCP Sampling to servers, so a connector cannot ask the ChatGPT host to create nested model turns for it. More importantly, MCP Sampling was deprecated in the 2026-07-28 protocol revision, whose guidance tells new implementations to integrate directly with LLM provider APIs. This server therefore uses `OPENAI_API_KEY` server-side on purpose: it is both compatible with ChatGPT today and aligned with the current MCP direction.
