[← Longshot](../README.md) · [Harnesses & services](harnesses.md) · [Accounts](accounts.md) · [Telemetry](telemetry.md) · [SKILL.state](skill-state.md) · **Architecture** · [In numbers](numbers.md) · [Roadmap](roadmap.md)

# Architecture

Diagrams use one [fixed vocabulary](diagrams.md).

## How a subagent is assembled

There is no fixed set of agents. The coordinator composes one per task, and each axis is checked
against the live inventory:

```text
subagent = runner + account + model + effort + role + tool grant + workspace/isolation + task
```

| Axis | What it is | Example |
|---|---|---|
| **runner** | the CLI that does the work | Claude Code, Codex CLI, Copilot CLI, opencode, Qoder, PowerShell |
| **account** | one credential set, one quota pool | `codex:work`, `codex:personal`, `claude:work`, `claude:ollama` |
| **model provider** | who serves inference behind it | Anthropic, ChatGPT, OpenRouter, Ollama, GitHub Copilot |
| **model** + **effort** | what the account offers, how hard it thinks | `gpt-6.1-sol@high`, `claude-opus-5-5`, `glm-5.3:cloud` |
| **role** | a reusable prompt with no task in it | `planner`, `code-implementer`, `reviewer`, `verifier` |
| **tool grant** | what the worker may do in its process | permission mode, allowed tools, sandbox level |
| **isolation** | where it writes | its own worktree and branch, or read-only in the repository |
| **task** | the self-contained brief | written by the coordinator |

The coordinator routes on the inventory, which is narrowed to what the folder allows. The account
rows are on [Accounts](accounts.md#check-what-longshot-sees). The model table:

```text
## MODELS
MODEL         PROVIDER  EFFORTS          DEF   TOOLS  CTX     BEST_FOR
gpt-5.6-sol   chatgpt   low,medium,high  high  ?      ?
llama3:tools  ollama    -                -     yes    262144
```

- `STATUS` comes from what the provider did. After a quota refusal the account reads `limited`
  until its window resets.
- `BEST_FOR` is the operator's note, kept in a CSV file and re-read without a restart.
- `digest=` answers *has anything changed?* in one line. `-` means not applicable, `?` means
  unknown.

## From `agents.spawn` to a running process

```mermaid
flowchart TD

IO1("Entry: the coordinator calls agents.spawn<br/>task · runtime · account · model ·<br/>effort · role · isolation")
G1{"Are account, model, effort and role<br/>valid for this runtime, and does<br/>the folder policy allow the target?"}
E1("Refused, with the list<br/>of accepted values")
H1["Resolve the account<br/>CODEX_HOME · CLAUDE_CONFIG_DIR ·<br/>ANTHROPIC_BASE_URL; key read at launch"]
H2["Read the role file<br/>tools/agents/RUNNER/ROLE.md"]
G2{"Which runner?"}
H3["codex exec<br/>role body before the task"]
H4["claude -p<br/>--append-system-prompt"]
H5["copilot -p<br/>--agent=NAME"]
H6["opencode run · qoder -p · pwsh<br/>no role axis"]
G3{"Is a slot free<br/>under MaxConcurrentPerRuntime?"}
E2("Refused: the runtime<br/>is at its limit")
G4{"isolation: worktree?"}
H7["git worktree<br/>REPO.worktrees/JOBID,<br/>branch longshot/JOBID"]
H8["The repository checkout"]
H9["Telemetry overlay<br/>on: OTLP env or -c otel options<br/>off: every OTEL_ variable scrubbed"]
W1["Headless worker process<br/>no operator settings, hooks or MCP;<br/>log in .longshot/logs/JOBID"]
E3("Receipt returned at once:<br/>job id, status running")
E4("Terminal event, later,<br/>into the mailbox")

IO1 --> G1
G1 -->|"no"| E1
G1 -->|"yes"| H1
H1 -->|"environment overlay"| H2
H2 -->|"role body"| G2
G2 -->|"codex"| H3
G2 -->|"claude-code"| H4
G2 -->|"copilot"| H5
G2 -->|"opencode, qoder, shell"| H6
H3 -->|"argv"| G3
H4 -->|"argv"| G3
H5 -->|"argv"| G3
H6 -->|"argv"| G3
G3 -->|"no"| E2
G3 -->|"yes"| G4
G4 -->|"yes"| H7
G4 -->|"no"| H8
H7 -->|"cwd"| H9
H8 -->|"cwd"| H9
H9 -->|"argv, env, cwd"| W1
W1 -->|"job id"| E3
W1 -->|"exit code, outcome"| E4

classDef work fill:#E1F4F7,stroke:#177281,stroke-width:1.2px,color:#0B3A42
classDef auto fill:#F1E9FB,stroke:#6B3FA0,stroke-width:1.4px,color:#2E1A4A
classDef evt fill:#E9F7E4,stroke:#3E8E41,stroke-width:1.2px,color:#1E4620
classDef io fill:#DCE6EE,stroke:#3F5B72,stroke-width:1.6px,color:#12293D
classDef stop fill:#FBEAE7,stroke:#A33B32,stroke-width:1.3px,color:#5A1E17
classDef gate fill:#FCF3D7,stroke:#A87413,stroke-width:1.3px,color:#4A3208

class W1 work
class H1,H2,H3,H4,H5,H6,H7,H8,H9 auto
class E3,E4 evt
class IO1 io
class E1,E2 stop
class G1,G2,G3,G4 gate
```

- **Refuse, never default.** A wrong axis is refused with the accepted values, never replaced in
  silence.
- **Enumerate, don't gatekeep.** A model newer than any list can still be spawned by name.
- **Report quota, don't refuse it.** Spending a limited account is the coordinator's call.
- **Isolation is a boundary.** Two writers never share a checkout. Worktrees live beside the
  repository and survive `git clean`.

## The engine

```mermaid
flowchart TD

IO1("Operator: TUI, console, CLI<br/>longshot · losh · doctor ·<br/>inventory · state")
H1["Control socket<br/>.longshot/sessions/mission.sock"]
H2["Coordinator manager<br/>turn admission · wake-ups ·<br/>recovery · reseat · quota failover"]
H3["Manager.turnContext<br/>eight blocks, each under a deadline"]
H4["Step carrier<br/>one fresh backend session per turn"]
G1{"Which backend<br/>owns the thread?"}
P1["Codex App Server<br/>codex app-server --stdio,<br/>tools as dynamic tools"]
P2["Claude Agent SDK<br/>Node.js sidecar,<br/>tools over in-process MCP"]
H5["Tool surface<br/>agents · jobs · workspaces ·<br/>orchestration · inventory"]
H6["Dispatch inventory<br/>discovered accounts · limits ·<br/>models · roles · folder policy"]
H7["Jobs domain<br/>internal/jobs,<br/>imports no internal package"]
H8["Worktree manager<br/>REPO.worktrees/JOBID"]
H9["Runners<br/>argv · env · role · telemetry"]
W1["Workers<br/>Claude Code · Codex CLI · Copilot CLI ·<br/>opencode · Qoder · PowerShell"]
H10["Durable mailbox<br/>persist · dedupe · batch · confirm"]
H11["agent.usage sender<br/>runtimes without native export"]
S1["state.db, one per mission<br/>threads · jobs · events · mailbox ·<br/>execution state + revisions · lease"]
S2["app.db, one per machine<br/>accounts · limits · observations ·<br/>policy · telemetry switch"]
IO2("Your OTLP/HTTP collector<br/>OTEL_EXPORTER_OTLP_ENDPOINT")

IO1 -->|"objective, commands"| H1
H1 -->|"control frames"| H2
H2 -->|"turn request"| H3
S1 -.-> H3
S2 -.-> H6
H6 -.-> H3
H3 -->|"context half + letters"| H4
H4 --> G1
G1 -->|"codex"| P1
G1 -->|"claude"| P2
P1 -->|"tool calls"| H5
P2 -->|"tool calls"| H5
H6 -.-> H5
H5 -->|"statePatch"| S1
H5 -->|"agents.spawn"| H7
H7 -->|"worktree request"| H8
H8 -->|"cwd"| H9
H7 -->|"StartSpec"| H9
H9 -->|"headless process"| W1
W1 -->|"terminal event"| H10
H10 -->|"letters"| S1
H10 -->|"wake-up"| H2
H10 -->|"job finished on a runtime<br/>without native export"| H11
H11 -->|"agent.usage"| IO2
P1 -.->|"native OTel"| IO2
P2 -.->|"native OTel"| IO2
W1 -.->|"native OTel: Claude Code, Codex"| IO2

classDef proc fill:#E8F1FB,stroke:#2C5F8A,stroke-width:1.2px,color:#12293D
classDef work fill:#E1F4F7,stroke:#177281,stroke-width:1.2px,color:#0B3A42
classDef auto fill:#F1E9FB,stroke:#6B3FA0,stroke-width:1.4px,color:#2E1A4A
classDef store fill:#ECEDEF,stroke:#6E6E76,stroke-width:1.2px,color:#2B2B30
classDef io fill:#DCE6EE,stroke:#3F5B72,stroke-width:1.6px,color:#12293D
classDef gate fill:#FCF3D7,stroke:#A87413,stroke-width:1.3px,color:#4A3208

class P1,P2 proc
class W1 work
class H1,H2,H3,H4,H5,H6,H7,H8,H9,H10,H11 auto
class S1,S2 store
class IO1,IO2 io
class G1 gate
```

The design is hexagonal: the jobs domain imports nothing internal, adapters are written against
frozen contracts, and the backend port is vendor-neutral. A test enforces each of these rules.
The test suite also pins the interface sentences of the documentation, and the inventory format
byte for byte.

## What it deliberately does not do

- Fork Codex or implement a model runtime.
- Keep a turn open while work runs. There is no `wait_for` tool.
- Carry reasoning between turns. Only the state survives.
- Parse worker stdout as a protocol. Job events are the protocol.
- Give a worker the state, the doctrine or the inventory.
- Store a credential. It keeps the auth mode only.
- Send telemetry nobody asked for, or leak an inherited `OTEL_*` setting.
- Let a worker reach into the coordinator, or relax isolation for convenience.

---

[← SKILL.state](skill-state.md) · [In numbers →](numbers.md)
