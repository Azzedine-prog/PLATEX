# PLATEX – Advanced Collaborative LaTeX Editor

## Project Overview
PLATEX is a cross-platform, real-time collaborative LaTeX editing suite composed of three tightly integrated systems:

- **Core Service (Backend/API):** Provides authentication, project/file management, real-time synchronization, version history, and orchestrates compilation jobs.
- **Web Application (Frontend):** React-based client with Monaco/CodeMirror editor integration, PDF previewer, and structured error display.
- **Desktop Application:** Tauri/Electron wrapper that packages the web client into a single-file executable for offline-friendly, native-like distribution.

All components prioritize low latency, horizontal scalability, and secure isolation for arbitrary LaTeX compilation workloads.

## High-Level Architecture
```
[ Web App (React + State Mgmt) ] <---> [ Core Service (REST + WebSockets) ]
                                         |          |
                                         |          +--> [ Real-Time OT/CRDT Engine ]
                                         |
                                         +--> [ Compilation Service (Dockerized LaTeX) ]
                                                        |
                                                        +--> [ Isolated container running pdflatex/xelatex ]
```

### Core Domain Models
The following language-agnostic class/data model sketches outline the MVP entities and relationships. They are intended for the backend implementation (Node.js or Go) and align with a relational schema (PostgreSQL) but can map to document stores if needed.

- **User**
  - `id: uuid`
  - `email: string`
  - `password_hash: string`
  - `display_name: string`
  - `created_at: timestamp`
  - `last_login_at: timestamp`

- **Project**
  - `id: uuid`
  - `owner_id: uuid (User.id)`
  - `name: string`
  - `description: string`
  - `settings: jsonb` (compiler, engine options, TeX Live profile)
  - `created_at: timestamp`
  - `updated_at: timestamp`

- **Document**
  - `id: uuid`
  - `project_id: uuid (Project.id)`
  - `path: string` (e.g., `main.tex`, `sections/intro.tex`)
  - `content: text`
  - `version: integer` (monotonic for OT/CRDT reconciliation)
  - `last_modified_by: uuid (User.id)`
  - `updated_at: timestamp`

- **Asset**
  - `id: uuid`
  - `project_id: uuid (Project.id)`
  - `path: string` (images, `.bib`, style files)
  - `blob_ref: string` (object storage key)
  - `checksum: string`
  - `created_at: timestamp`

- **CollaborationSession**
  - `id: uuid`
  - `project_id: uuid`
  - `document_id: uuid`
  - `connected_users: uuid[]`
  - `ot_state: jsonb` (server-side operational transformation state)
  - `last_sequence: integer`

- **VersionSnapshot**
  - `id: uuid`
  - `project_id: uuid`
  - `label: string` (user-provided milestone name)
  - `created_by: uuid`
  - `created_at: timestamp`
  - `snapshot_ref: string` (pointer to stored tarball/commit hash)

- **CompilationJob**
  - `id: uuid`
  - `project_id: uuid`
  - `requested_by: uuid`
  - `status: enum` (`queued`, `running`, `succeeded`, `failed`)
  - `engine: enum` (`pdflatex`, `xelatex`)
  - `options: jsonb` (flags, timeouts, resource caps)
  - `log_ref: string` (build logs)
  - `pdf_ref: string` (output artifact)
  - `created_at`, `started_at`, `completed_at: timestamp`

### Service-Level Components
- **API Layer (REST + WebSockets):** Authentication (JWT), CRUD for projects/documents/assets, session negotiation, OT/CRDT event relay, compilation job submission, and history retrieval.
- **Real-Time Engine:** Centralized OT processor maintaining document versions, cursor presence, and conflict resolution with idempotent sequencing.
- **Compilation Orchestrator:** Accepts compilation requests, provisions containerized workers, streams logs, and publishes completion events to clients.
- **Storage Layer:** PostgreSQL for metadata; object storage (e.g., S3-compatible) for blobs (PDFs, assets, snapshots, logs).

## Dockerized Compilation Service Plan (Phase 1, Step 3)
Objective: Execute arbitrary LaTeX code securely and predictably by isolating each build in a short-lived Docker container.

### Execution Flow
1. **Job Submission:** Core Service enqueues a `CompilationJob` with project reference, engine, and options (timeout, memory/CPU caps).
2. **Workspace Assembly:** A temporary build context is created by exporting the project tree and assets from object storage into a ephemeral directory.
3. **Container Launch:** A minimal LaTeX image (e.g., `ghcr.io/platex/texlive:<profile>`) is run with:
   - Read-only root filesystem and mounted workspace at `/workspace` (read-write where necessary).
   - Non-root user (e.g., `uid/gid 1000`).
   - `--cpus`, `--memory`, `--pids-limit`, and `--ulimit nofile` to enforce resource ceilings.
   - `--network=none` to disable outbound/inbound traffic during compilation.
   - Seccomp/AppArmor profiles to block risky syscalls; drop all capabilities except those strictly required by TeX engines.
4. **Compilation:** Run `pdflatex`/`xelatex` with deterministic flags (`-interaction=nonstopmode -file-line-error`) and bounded retry count. Capture stdout/stderr to structured logs.
5. **Artifact Collection:** Copy generated PDFs and logs to object storage; store references in `CompilationJob` record.
6. **Cleanup:** Remove workspace and container; emit WebSocket event with status and artifact locations.

### Safety Measures for Arbitrary LaTeX
- **Container Isolation:** Each job runs in its own container with `network=none`, read-only root FS, and write-only mounted workspace to prevent host access.
- **Resource Limits:** CPU/memory/pid/FD limits plus per-job wall-clock timeout enforced by the orchestrator to mitigate infinite loops or fork bombs.
- **Capability Dropping:** Run as non-root with `--cap-drop=ALL` (or minimal set) and hardened seccomp/AppArmor profiles to reduce kernel attack surface.
- **Filesystem Hygiene:** Mount only the necessary project directory; no host sockets, docker socket, or secret volumes. Use tmpfs for `/tmp` to avoid persistence.
- **Input Validation:** Validate engine selection, filename encodings, and disallow symlinks escaping the workspace when assembling files.
- **Deterministic Toolchain:** Pin LaTeX image versions (Tex Live profile) to guarantee reproducibility and avoid drift.
- **Log Scrubbing:** Sanitize compiler logs before returning them to clients to remove host-specific paths or sensitive data.
- **Audit & Observability:** Emit structured events (job ID, resource usage, exit codes) for monitoring and intrusion detection; keep minimal retention of logs.

### Interfaces & Responsibilities
- **Compilation API Endpoint (POST /projects/:id/compile):** Authenticates user, validates options, enqueues `CompilationJob` with requested engine and timeout.
- **Queue Worker / Orchestrator:** Dequeues jobs, prepares workspace, spawns container, streams logs, updates job status, publishes WebSocket events (`compilation:progress`, `compilation:done`).
- **WebSocket Events:** Clients subscribe per project; payloads include `jobId`, `status`, `progress`, `errors[]` mapped from `.log` file.
- **Storage Contracts:** PDFs saved under `artifacts/{projectId}/{jobId}/output.pdf`; logs under `logs/{projectId}/{jobId}/compile.log` with checksums for integrity.

### Next Steps (Phase 1 Alignment)
1. Establish repository structure (`backend/`, `frontend/`, `desktop/`, `infra/`), with a `docker/latex-runner` image definition.
2. Implement `CompilationJob` schema/migrations and queue plumbing (e.g., BullMQ for Node.js or a Go worker with Redis/Postgres-based queue).
3. Build the orchestrator wrapper around Docker Engine API with hardcoded safety defaults and telemetry hooks.
4. Integrate WebSocket notifications and log ingestion to the frontend for inline error highlighting.

---
This document serves as the authoritative starting point for Phase 1 development, ensuring security and observability are baked into the compilation pipeline from day one.
