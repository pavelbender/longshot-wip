[← Longshot](../README.md) · [Harnesses & services](harnesses.md) · [Accounts](accounts.md) · [Telemetry](telemetry.md) · **SKILL.state** · [Architecture](architecture.md) · [In numbers](numbers.md) · [Roadmap](roadmap.md)

# SKILL.state: a coordinator without a memory

A coordinator that lives for days is idle most of the time:

```text
turn → delegate → END TURN → (idle: minutes, hours) → woken by events → turn → ...
```

The wake-up worked from the start. What did not was the memory of the step. Every turn ran on
the accumulated conversation, so after a day the prompt was mostly stale observations.

## The paper

*SKILL.state: Scalable Long-Horizon Agent Skills* (arXiv:2608.26263): an append-only history
costs `O(t)` per step and `O(T²)` in total, while an explicit state costs `O(1)` and `O(T)`. At
each step the model sees only the procedure `P`, the state `Σₜ` and the observation `Oₜ`.

| At horizon `T = 100` | History runtime | State runtime |
|---|---|---|
| Total tokens | 1,062,387 | **65,408** |
| Steps to recover after the external world drifts | 5–8 | **0** |

## How Longshot maps it

| The paper | Longshot |
|---|---|
| procedural spec `P` | the **doctrine**, `prompts/coordinator.md`, byte-identical on every carrier |
| state `Σₜ` | the **execution state**: one typed, versioned JSON document per thread |
| state patch `ΔΣₜ` | `orchestration.statePatch`: section replacements; `null` clears a section |
| step | one coordinator **turn** |
| observation `Oₜ` | the wake: mailbox letters plus the turn context |
| discarded reasoning | the **step carrier**: a backend session opened for one turn and closed after it |

The mode belongs to the thread and is fixed at its birth: `historyless` (the default) or
*full history*.

Diagrams use one [fixed vocabulary](diagrams.md).

```mermaid
flowchart TD

IO1("Entry: a wake-up or an operator message")
H1["Open a fresh step carrier<br/>no conversation in it"]
S1["Doctrine P<br/>prompts/coordinator.md"]
S2["Execution state vN<br/>thread_execution_state"]
S3["Letters Oₜ<br/>the mailbox batch that woke the turn"]
P1["Coordinator model<br/>reads P + Σₜ + Oₜ,<br/>delegates, reviews, integrates"]
G1{"Is the patch valid?<br/>schema · limits · expectedVersion"}
E1("Refused: nothing written,<br/>the current version and<br/>the reason go back")
H2["Commit vN+1<br/>journal the revision,<br/>release the named letters"]
H3["Close the carrier<br/>reasoning and tool chatter<br/>discarded"]
IO2("Exit: the turn ends, zero tokens while idle;<br/>the next turn opens on vN+1")

IO1 --> H1
S1 -.-> H1
S2 -.-> H1
S3 -.-> H1
H1 -->|"P, Σₜ, Oₜ"| P1
P1 -->|"orchestration.statePatch ΔΣₜ"| G1
G1 -->|"no: unknown key, broken limit<br/>or stale expectedVersion"| E1
E1 -.-> P1
G1 -->|"yes"| H2
H2 -->|"state vN+1"| H3
H3 --> IO2

classDef proc fill:#E8F1FB,stroke:#2C5F8A,stroke-width:1.2px,color:#12293D
classDef auto fill:#F1E9FB,stroke:#6B3FA0,stroke-width:1.4px,color:#2E1A4A
classDef store fill:#ECEDEF,stroke:#6E6E76,stroke-width:1.2px,color:#2B2B30
classDef io fill:#DCE6EE,stroke:#3F5B72,stroke-width:1.6px,color:#12293D
classDef stop fill:#FBEAE7,stroke:#A33B32,stroke-width:1.3px,color:#5A1E17
classDef gate fill:#FCF3D7,stroke:#A87413,stroke-width:1.3px,color:#4A3208

class P1 proc
class H1,H2,H3 auto
class S1,S2,S3 store
class IO1,IO2 io
class E1 stop
class G1 gate
```

## What the state holds

Nine sections, bounded by design. A state that grew with the turns would bring back the problem.

| Section | What goes in | Bound |
|---|---|---|
| `phase` | `investigate` → `plan` → `delegate` → `verify` → `report` | enum |
| `plan` | steps with `id`, `goal`, `status`, `dependsOn`; failed steps stay, so nobody retries them blindly | 64 items |
| `decisions` | named conclusions, and open questions as `asked:<topic>` | — |
| `notes` | conclusions, never the path to them; appended and numbered by the runtime | 16 × 256 runes |
| `blockers` | what the work waits on, by reference (`job:claude-42`) | — |
| `verification` | checks and their outcome | — |
| `artifactRefs` | branches, files, commits, as references | — |
| `nextActions` | what the next turn should do | 32 |
| `consumedEvents` | the `EventID` of every letter this turn handled | 64 |
| *any string* | | 512 runes |
| *whole document* | compact JSON | **128 Ki runes** |

The bound began at 8,192 characters. Real threads reached 8,187 of it, so it went up to
128 Ki runes. It is still a constant, not a function of the number of turns.

```text
# EXECUTION STATE v7

schemaVersion: 1
phase: delegate
consumedEvents: 2 ids in the current list

## plan
- S1 done: map the schema
- S2 running: migrate the users table (depends on: S1)

## decisions
- storage = sqlite

## notes
- #2 S2: migration must run before the API deploy
- #1 S1: the users table has no index on email

## blockers
- B1: waiting for the migration job (waiting on: job:claude-42)

## verification
- V1 pending: go test ./...

## artifactRefs
- branch: longshot/claude-42
```

## The rules that make it hold

- **Patch or lose it.** State moves forward only through `orchestration.statePatch`. Nothing
  parses prose.
- **Optimistic concurrency.** A stale `expectedVersion` is refused, with the current version.
- **All or nothing.** One bad key or limit refuses the whole patch. Each refusal is recorded
  with its reason.
- **Every version is kept.** `orchestration.stateHistory` answers *why the plan looks like
  this*.
- **Reference, never copy.** Jobs, worktrees and quotas live in their own stores. When the store
  and the state disagree, the store wins.
- **Handling is proved.** A letter leaves the queue only when a turn names it in
  `consumedEvents`. A turn that forgot gets it again.
- **A question is state.** It goes into `decisions` as `asked:<topic>`, so `1a 3b` still
  resolves turns later. `# RECENT CONVERSATION` is the backstop.
- **The objective is not state.** No patch can reach it. A redirection is recorded as `clarify`
  or `replace`, with the reason and the old wording.
- **No native subagents.** All delegation goes through `agents.spawn`. On Claude, `Agent` and
  `Task` are withheld.
- **A carrier is never resumed.** After a restart, a crash or a move, the next turn opens a new
  carrier from the state.

| | Full history | Historyless (SKILL.state) |
|---|---|---|
| Prompt size per turn | grows every turn | flat |
| Re-orientation after hours idle | re-read the conversation | read one state block |
| Restart mid-objective | resume the session, if it survived | open a new carrier |
| Move to another backend or account | replay the transcript | the state moves with the thread |
| Wake-up lost in a crash | possible | re-presented until named |

| In use since it became the default on 13 October | |
|---|---|
| Historyless coordinator threads | **27** of 66 |
| Execution-state revisions committed | **385** |
| Patches refused by validation, each with its reason | **34** |
| Objective amendments (`clarify` / `replace`) | **18** |

## What one turn sees

Assembled from durable sources on every turn, in a fixed order. Nothing is remembered;
everything is re-read.

```mermaid
flowchart TD

IO1("Entry: a human message or a wake-up")
A1["Inventory snapshot<br/>+ the pre-turn limits poll"]
A2["Turn origin<br/>human · job-event ·<br/>quota-reset · system-wake"]
A3["Unfinished jobs<br/>and the age of each last report"]
A4["Objective and its amendments<br/>no patch can reach either"]
A5["Last six transcript messages<br/>historyless threads only,<br/>6,000 runes in all"]
A6["Execution state, rendered<br/>cut by section if over budget"]
G1{"What started the turn?"}
H1["Text half: the operator's message"]
H2["Text half: Pending external events,<br/>up to 20 letters per turn"]
S1["~/.longshot/app.db<br/>accounts, limits, observations"]
S2["state.db: mailbox_events"]
S3["state.db: jobs, job_events"]
S4["state.db: thread record,<br/>thread_objective_amendment"]
S5["state.db: transcript_entries"]
S6["state.db: thread_execution_state"]
S7["System prompt, every carrier<br/>prompts/coordinator.md<br/>+ the tool surface"]
P1["Coordinator model<br/>doctrine + context half + text half"]

IO1 --> A1
S1 -.-> A1
A1 -->|"1 · # INVENTORY now=…"| A2
S2 -.-> A2
A2 -->|"2 · # TURN ORIGIN"| A3
S3 -.-> A3
A3 -->|"3 · # JOBS"| A4
S4 -.-> A4
A4 -->|"4 · # OBJECTIVE<br/>5 · # OBJECTIVE AMENDMENTS"| A5
S5 -.-> A5
A5 -->|"6 · # RECENT CONVERSATION"| A6
S6 -.-> A6
A6 -->|"7 · # EXECUTION STATE vN<br/>8 · # STATE RULES"| G1
G1 -->|"a human message"| H1
G1 -->|"a wake-up"| H2
H1 -->|"context half + text half"| P1
H2 -->|"context half + text half"| P1
S7 -.-> P1

classDef proc fill:#E8F1FB,stroke:#2C5F8A,stroke-width:1.2px,color:#12293D
classDef auto fill:#F1E9FB,stroke:#6B3FA0,stroke-width:1.4px,color:#2E1A4A
classDef store fill:#ECEDEF,stroke:#6E6E76,stroke-width:1.2px,color:#2B2B30
classDef io fill:#DCE6EE,stroke:#3F5B72,stroke-width:1.6px,color:#12293D
classDef gate fill:#FCF3D7,stroke:#A87413,stroke-width:1.3px,color:#4A3208

class P1 proc
class A1,A2,A3,A4,A5,A6,H1,H2 auto
class S1,S2,S3,S4,S5,S6,S7 store
class IO1 io
class G1 gate
```

- **A clock.** `now=` in the inventory header tells a thread how long it slept.
- **Progress without noise.** Running workers report only through `# JOBS`. Progress events do
  not wake the coordinator.
- **A failed source costs a line.** Every block reads under a deadline, and one that fails
  degrades to a one-line notice.
- **Batched wake-ups.** Up to 20 letters ride one turn. The window counts from the oldest letter.
- **Workers see none of this.** Each worker gets one self-contained task.

**Next: context fingerprints.** Skills, plugins, MCP servers and `AGENTS.md` that the backend
loads by itself change the next carrier silently. A per-turn hash of both halves will show what
changed between turn N-1 and turn N.

---

[← Telemetry](telemetry.md) · [Architecture →](architecture.md)
