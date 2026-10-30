[← Longshot](../README.md) · [Harnesses & services](harnesses.md) · [Accounts](accounts.md) · [Telemetry](telemetry.md) · [SKILL.state](skill-state.md) · [Architecture](architecture.md) · [In numbers](numbers.md) · [Roadmap](roadmap.md)

# Reading the diagrams

Every flowchart here uses the same eight classes and one palette.

- **Rectangle:** something that acts. Its colour says who acts.
- **Rounded box:** a state reached. Its colour says whether the flow goes on, leaves the diagram,
  or stops.
- **Edge label:** a condition when the edge leaves a gate, the data handed on when it leaves a
  process.
- **Dashed edge:** a read that passes no control.

```mermaid
flowchart TD

L1["Coordinator: model or backend"]
L2["Worker process"]
L3["Longshot engine code"]
L4["Store: database, file, environment"]
L5("Event")
L6("Joint: in from, or out to, the outside")
L7("Refusal or terminal event")
L8{"Decision gate"}

LA["Process"] -->|"output data"| LB{"Gate"}
LB -->|"branch condition"| LC("Event")
LD["Store"] -.->|"read, no transfer of control"| LA

classDef proc fill:#E8F1FB,stroke:#2C5F8A,stroke-width:1.2px,color:#12293D
classDef work fill:#E1F4F7,stroke:#177281,stroke-width:1.2px,color:#0B3A42
classDef auto fill:#F1E9FB,stroke:#6B3FA0,stroke-width:1.4px,color:#2E1A4A
classDef store fill:#ECEDEF,stroke:#6E6E76,stroke-width:1.2px,color:#2B2B30
classDef evt fill:#E9F7E4,stroke:#3E8E41,stroke-width:1.2px,color:#1E4620
classDef io fill:#DCE6EE,stroke:#3F5B72,stroke-width:1.6px,color:#12293D
classDef stop fill:#FBEAE7,stroke:#A33B32,stroke-width:1.3px,color:#5A1E17
classDef gate fill:#FCF3D7,stroke:#A87413,stroke-width:1.3px,color:#4A3208

class L1,LA proc
class L2 work
class L3 auto
class L4,LD store
class L5,LC evt
class L6 io
class L7 stop
class L8,LB gate
```

Sequence diagrams and charts are not flowcharts and do not use these classes.

---

[← Longshot](../README.md)
