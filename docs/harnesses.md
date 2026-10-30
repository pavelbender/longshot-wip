[← Longshot](../README.md) · **Harnesses & services** · [Accounts](accounts.md) · [Telemetry](telemetry.md) · [SKILL.state](skill-state.md) · [Architecture](architecture.md) · [In numbers](numbers.md) · [Roadmap](roadmap.md)

# Harnesses & services

Longshot drives the CLIs you already have, headless, each on the account you choose.

## Harnesses

| Harness | As coordinator | As worker | Accounts | Role delivery | Telemetry |
|---|---|---|---|---|---|
| **Claude Code** | ✅ Agent SDK in a Node.js sidecar; Longshot's tools over in-process MCP | ✅ `claude -p` | many: one `CLAUDE_CONFIG_DIR` each, plus an Ollama route | `--append-system-prompt` | native OTel: logs and metrics |
| **Codex CLI** | ✅ `codex app-server`; Longshot's tools as dynamic tools | ✅ `codex exec` | many: one `CODEX_HOME` each | role body before the task | native OTel: logs |
| **GitHub Copilot CLI** | — | ✅ `copilot -p` | one, or a BYOK endpoint | `--agent=NAME` | `agent.usage` from Longshot |
| **opencode** | — | ✅ `opencode run` | one global auth store | — | `agent.usage` from Longshot |
| **Qoder CLI** | — | ✅ headless `-p` | one | — | `agent.usage` from Longshot |
| **PowerShell 7** | — | ✅ runtime `shell` | `shell:local` | — | `agent.usage` from Longshot |

- **Coordinator models:** read from the backend, Codex `model/list` or the Claude CLI's `initialize`.
- **Worker models:** read per account. `model/list` for ChatGPT, `/api/tags` for Ollama,
  `opencode models` for opencode, and otherwise the runner's own list.
- **Roles:** 21 files (Claude Code 7, Codex 9, Copilot 5) holding 11 distinct roles, from
  `planner` to `integration-resolver`. A role file is read at spawn time, so an edit applies
  to the next spawn.

## Services

| Service | Role | Reached through | Inventory row |
|---|---|---|---|
| **Anthropic** | model provider: subscription or API key | Claude Code, the Claude coordinator | `claude:default`, `claude:<name>` |
| **OpenAI**, ChatGPT plans | model provider; live quota windows and plan | Codex, the Codex coordinator | `codex:default`, `codex:<name>` |
| **OpenRouter** or any OpenAI-compatible endpoint | model provider, API key | a Codex home that declares it | `codex:openrouter` |
| **Ollama**, local and `:cloud` | model provider; models, tools and context from `/api/tags` | Claude Code, Copilot BYOK, Codex `--oss` | `claude:ollama`, `copilot:byok` |
| **GitHub Copilot** | model provider, premium requests | Copilot CLI | `copilot:default` |
| **OpenCode** providers | model provider | opencode | `opencode:default` |
| **Qoder** | model provider | Qoder CLI | `qoder:default` |
| **OpenTelemetry** | any OTLP/HTTP collector | `OTEL_EXPORTER_OTLP_ENDPOINT` | — |
| **Git** | one worktree and one branch per job | `git worktree` | — |
| **npm** | win32, linux and darwin, each on x64 and arm64 | `@longshot-harness/longshot` | — |

How to connect each of these: [Accounts](accounts.md).

---

[← Longshot](../README.md) · [Accounts →](accounts.md)
