# Architecture

Synapse turns a natural-language topic into a verified research report. A user submits a topic; a
three-agent pipeline — **Scout** (research), **Scribe** (synthesis), **Critic** (fact-check) — runs
asynchronously on a worker, streaming progress events to the browser in real time, and persists a
cited, confidence-scored report.

The diagrams below render natively on GitHub.

## Component architecture

```mermaid
flowchart TB
    subgraph client["Browser"]
        FE["React 19 + TS<br/>TanStack Router/Query<br/>Tailwind 4"]
    end

    subgraph backend["Backend — FastAPI (async)"]
        API["app/api<br/>REST routes"]
        WS["WebSocket<br/>/ws/jobs/{id}"]
        AUTH["fastapi-users<br/>cookie auth"]
        SVC["app/services<br/>persistence · export · search · events"]
        AGENTS["app/agents<br/>Scout · Scribe · Critic<br/>LangGraph orchestrator"]
    end

    subgraph workers["Async execution"]
        TASK["taskiq worker<br/>run_research_pipeline"]
    end

    subgraph data["State"]
        PG[("PostgreSQL<br/>SQLAlchemy 2.0")]
        REDIS[("Redis<br/>broker + pub/sub")]
    end

    subgraph external["External APIs"]
        OR["OpenRouter<br/>per-agent LLMs"]
        EXA["Exa<br/>web search"]
    end

    FE -->|"HTTPS / JSON"| API
    FE <-->|"live events"| WS
    API --> AUTH
    API --> SVC
    API -->|"enqueue job"| REDIS
    REDIS --> TASK
    TASK --> AGENTS
    AGENTS --> OR
    AGENTS --> EXA
    AGENTS --> SVC
    SVC --> PG
    TASK -->|"publish events"| REDIS
    REDIS -->|"subscribe"| WS
    AUTH --> PG
```

The API persists a job and enqueues it; the taskiq worker runs the LangGraph pipeline, calling
OpenRouter (LLMs) and Exa (search). Every progress event is written to Postgres (durable log) and
published on Redis, which the WebSocket relays to the browser.

## Agent pipeline — sequence

Event types are the ones defined in `backend/app/models/events.py`.

```mermaid
sequenceDiagram
    actor U as User
    participant API as FastAPI
    participant Q as Redis + taskiq
    participant W as Worker (orchestrator)
    participant S as Scout
    participant SC as Scribe
    participant CR as Critic
    participant DB as Postgres
    participant WS as WebSocket

    U->>API: POST /api/research {topic, models}
    API->>DB: insert research_jobs (pending)
    API->>Q: enqueue run_research_pipeline(job_id)
    API-->>U: 202 {job_id}
    U->>WS: subscribe /ws/jobs/{job_id}

    Q->>W: run_research_pipeline(job_id)

    rect rgb(230, 240, 255)
    note over W,S: Scout — research
    W->>S: decompose + search
    S-->>W: SubQuestionsGenerated
    S-->>W: SourceFound (per result)
    S-->>W: SourceScored (credibility/relevance)
    S-->>W: ScoutComplete
    W->>DB: persist sources
    end

    rect rgb(235, 255, 235)
    note over W,SC: Scribe — synthesis
    W->>SC: draft report from sources
    SC-->>W: SectionDrafted (per section)
    SC-->>W: ScribeComplete
    W->>DB: persist report
    end

    rect rgb(255, 240, 235)
    note over W,CR: Critic — fact-check
    W->>CR: verify claims vs sources
    CR-->>W: ClaimVerified (per claim)
    W->>DB: persist critic_annotations
    end

    W-->>WS: JobCompleted (overall_confidence)
    Note over W,WS: on any failure → JobFailed
    WS-->>U: live events + final report
```

Each emitted event is appended to `job_events` (so a late subscriber can replay state via
`JobSnapshot`) and published to Redis for live delivery.

## Data flow

The orchestrator is a LangGraph state machine (`backend/app/agents/orchestrator.py`): `scout` is the
entry point, and a router advances to the next node only on success, short-circuiting to the end on
failure.

```mermaid
flowchart LR
    START([topic + sub-question overrides]) --> SCOUT

    subgraph pipeline["LangGraph pipeline"]
        direction LR
        SCOUT["scout_node<br/>decompose → search → score"]
        SCRIBE["scribe_node<br/>synthesize sections + citations"]
        CRITIC["critic_node<br/>verify claims + confidence"]
    end

    SCOUT -->|"continue"| SCRIBE
    SCRIBE -->|"continue"| CRITIC
    CRITIC --> DONE([report ready])

    SCOUT -.->|"fail"| FAIL([mark failed])
    SCRIBE -.->|"fail"| FAIL

    SEED["parent report's sources<br/>(follow-up runs)"] -.->|"seed"| SCOUT

    SCOUT -->|"sources"| DB[("Postgres")]
    SCRIBE -->|"report"| DB
    CRITIC -->|"annotations"| DB
```

For follow-up jobs the orchestrator seeds Scout with the parent report's sources (resolved via the
`follow_ups` edge) so the run reuses prior evidence on top of a fresh, question-scoped search.

## Database — ERD

```mermaid
erDiagram
    user ||--o{ research_jobs : owns
    research_jobs ||--o{ sources : "gathered"
    research_jobs ||--o| reports : "produces"
    reports ||--o| critic_annotations : "verified by"
    research_jobs ||--o{ job_events : "logs"
    research_jobs ||--o{ follow_ups : "is parent of"
    research_jobs ||--o{ follow_ups : "is child of"

    user {
        uuid id PK
        string email
        string hashed_password
    }
    research_jobs {
        uuid id PK
        uuid user_id FK
        text topic
        string language
        string depth
        jsonb models
        jsonb sub_questions_override
        string status
        float progress
        text error
        timestamptz created_at
        timestamptz completed_at
    }
    sources {
        uuid id PK
        uuid job_id FK
        text url
        text title
        float credibility
        float relevance
        text snippet
    }
    reports {
        uuid id PK
        uuid job_id FK "unique"
        text title
        text summary_md
        jsonb body
        string model
        timestamptz generated_at
    }
    critic_annotations {
        uuid id PK
        uuid report_id FK "unique"
        jsonb body
        float overall_confidence
        string model
        timestamptz generated_at
    }
    job_events {
        bigint id PK
        uuid job_id FK
        jsonb event
        timestamptz created_at
    }
    follow_ups {
        uuid id PK
        uuid parent_job_id FK
        uuid child_job_id FK
        text question
        timestamptz created_at
    }
```

All child foreign keys are `ON DELETE CASCADE`: deleting a job removes its sources, report,
annotations, events, and follow-up edges. A follow-up's child job survives — only the edge is
dropped — so derived briefs become standalone.
