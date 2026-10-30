[← Longshot](../README.md) · [Harnesses & services](harnesses.md) · [Accounts](accounts.md) · [Telemetry](telemetry.md) · [SKILL.state](skill-state.md) · [Architecture](architecture.md) · [In numbers](numbers.md) · **Roadmap**

# Status and roadmap

**Public beta**, running real projects. Used daily on Windows 11. Linux is verified in a
container. macOS is built but not yet run.

## Built

- Coordinator host: two backends behind one neutral port, picked automatically when none is named
- Historyless mode on both backends: step carriers, a validated and versioned execution state,
  per-letter confirmation
- Objective amendments; questions kept as state
- Asynchronous workers with durable wake-ups
- Six runners with live capability probing
- Account discovery from credential homes, a metadata overlay, secrets resolved at launch only
- Multi-account, multi-provider inventory: derived quota status, per-folder policy, coordinator
  failover on quota
- Claude sidecar on the TypeScript Agent SDK, shipped inside the npm package
- OpenTelemetry export with a per-folder switch and `agent.usage` for runners without native
  export
- Usage normalisation across Anthropic, Codex and Copilot reports
- Git worktree lifecycle
- Missions with detach, attach and relocation
- Operator TUI: project home, chats, worktrees, Repository setup, Chat settings
- npm distribution for six platforms
- End-to-end live tests and hand-run live drills

## Next

- `longshot usage`: per-job and per-turn accounting, with prices
- Coordinator questions answered in the UI (`AskUserQuestion` is still refused)
- Context fingerprints: a per-turn hash of the assembled and ambient context
- `orchestration.step`: patch the state and act in one call
- A state schema a mission can extend
- Persisted task graphs with dependency constraints
- Routing and retry policies driven by the inventory
- Worker pools and interactive, multi-turn worker control
- Human approval nodes

---

[← In numbers](numbers.md) · [Longshot](../README.md)
