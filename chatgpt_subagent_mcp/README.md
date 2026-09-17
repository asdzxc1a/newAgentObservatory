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

## Why this is materially different from prompt-only “role play”

Each fallback specialist is an independent Agents SDK run with its own agent instructions and model turn. The hosted path is stronger: OpenAI's experimental Responses multi-agent runtime creates and coordinates subagents server-side.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# export OPENAI_API_KEY=...
python server.py
```

Your MCP endpoint is:

```text
http://localhost:8000/mcp
```

For local ChatGPT testing, expose it with a tunnel such as ngrok and use the public `/mcp` URL.

## Put it in ChatGPT

1. Deploy this directory to a public HTTPS host (Render config is included), or tunnel the local port.
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

`render.yaml` is included. The only required secret is `OPENAI_API_KEY`.

For a hardened public deployment, replace the prototype's disabled DNS-rebinding check with an exact `TransportSecuritySettings(allowed_hosts=[...], allowed_origins=[...])` allowlist for your production hostname, and add connector authentication before broad distribution.

## Current limitation that matters

ChatGPT Apps/custom MCP connectors do not currently expose MCP Sampling to servers, so the server cannot ask the *ChatGPT host itself* to create extra model turns without an API credential. That is why this design calls the OpenAI API server-side. If ChatGPT gains MCP Sampling support later, the same MCP tool surface can be upgraded to use host-provided model calls and potentially remove the separate API-key requirement.
