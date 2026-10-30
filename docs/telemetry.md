[← Longshot](../README.md) · [Harnesses & services](harnesses.md) · [Accounts](accounts.md) · **Telemetry** · [SKILL.state](skill-state.md) · [Architecture](architecture.md) · [In numbers](numbers.md) · [Roadmap](roadmap.md)

# Telemetry (OpenTelemetry)

Telemetry is off by default. Precedence, highest first:

1. `longshot -otel` for one run, or `-otel=false` to silence a folder that is saved on;
2. `LONGSHOT_OTEL=1`;
3. **Repository setup → Telemetry**, saved per folder;
4. otherwise off.

The endpoint is the standard `OTEL_EXPORTER_OTLP_ENDPOINT`, default `http://127.0.0.1:4318`.

Diagrams use one [fixed vocabulary](diagrams.md).

```mermaid
flowchart TD

G1{"Is telemetry on for this run?<br/>-otel · LONGSHOT_OTEL ·<br/>folder switch · else off"}
H1["Scrub every OTEL_* variable and<br/>CLAUDE_CODE_ENABLE_TELEMETRY<br/>from each child's environment"]
H2["Every Codex child gets<br/>-c otel.exporter = none,<br/>metrics and traces none"]
E1("Nothing leaves the machine,<br/>even with OTEL_* set<br/>in the operator's shell")
H3["Stamp resource attributes<br/>agent.harness · agent.role · agent.home ·<br/>gen_ai.provider.name · vcs.repository.name ·<br/>vcs.ref.head.name · agent.worktree · longshot.job.id"]
G2{"Which participant?"}
H4["Claude Code worker or the Claude coordinator<br/>CLAUDE_CODE_ENABLE_TELEMETRY=1,<br/>OTLP http/protobuf"]
H5["Codex worker or the Codex App Server<br/>-c otel.exporter = otlp-http, /v1/logs,<br/>otel.log_user_prompt = false"]
H6["Copilot, opencode, Qoder or shell job ends<br/>Longshot posts one agent.usage record"]
IO1("Your OTLP/HTTP collector<br/>OTEL_EXPORTER_OTLP_ENDPOINT")

G1 -->|"off"| H1
H1 --> H2
H2 --> E1
G1 -->|"on"| H3
H3 -->|"OTEL_RESOURCE_ATTRIBUTES"| G2
G2 -->|"claude-code"| H4
G2 -->|"codex"| H5
G2 -->|"a runtime without native export"| H6
H4 -->|"logs, metrics"| IO1
H5 -->|"logs, no prompts"| IO1
H6 -->|"agent.usage as OTLP/JSON"| IO1

classDef auto fill:#F1E9FB,stroke:#6B3FA0,stroke-width:1.4px,color:#2E1A4A
classDef evt fill:#E9F7E4,stroke:#3E8E41,stroke-width:1.2px,color:#1E4620
classDef io fill:#DCE6EE,stroke:#3F5B72,stroke-width:1.6px,color:#12293D
classDef gate fill:#FCF3D7,stroke:#A87413,stroke-width:1.3px,color:#4A3208

class H1,H2,H3,H4,H5,H6 auto
class E1 evt
class IO1 io
class G1,G2 gate
```

- **Off means off.** Longshot silences every child, so an inherited `OTEL_*` setting cannot leak
  out of a worker.
- **One set of labels.** Split usage by `agent.role` (`coordinator` / `job`), by `agent.home`
  (`codex:work`, `claude:ollama`, …), by repository and branch. Your own
  `OTEL_RESOURCE_ATTRIBUTES` are kept.
- **No silent gaps.** Claude Code and Codex export natively. Every other runner yields one
  `agent.usage` record per job, marked `usage.status=unavailable` with a reason when the job
  cannot be measured.
- **An honest header.** A chat shows `otel` while its coordinator exports. It shows
  `otel pending` or `otel off pending` until the coordinator's next process picks up the new
  value. New jobs follow the switch at once.

## Example stack

```sh
docker run -d --name lgtm -p 3000:3000 -p 4318:4318 grafana/otel-lgtm   # Grafana + Loki + Prometheus
OTEL_RESOURCE_ATTRIBUTES="task.id=release-42" longshot -otel            # your own label rides along
```

```logql
{service_name="longshot"} | event_name="agent.usage" | usage_status="unavailable"
```

---

[← Accounts](accounts.md) · [SKILL.state →](skill-state.md)
