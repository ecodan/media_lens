# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

---
name: chorus
description: Orchestrates Cicadas methodology for spec-driven development. Use this skill when performing project lifecycle operations.
---

# Chorus: Cicadas Orchestrator

## Overview

The Cicadas methodology is a sustainable spec-driven development approach where:
- **Active Specs** (PRDs, designs, tasks) are disposable inputs that expire after implementation.
- **Code is the single source of truth** — always authoritative.
- **Canon** is reverse-engineered from code + expiring specs, not maintained in parallel.
- **Work is partitioned** — large initiatives are sliced into independent feature branches.
- **Specs stay current during development** — a "Reflect" operation keeps active specs in sync with code.
- **Teams coordinate asynchronously** — a "Signal" operation broadcasts breaking changes to peer branches.

Chorus is the orchestrator — a set of portable CLI scripts and agent instructions that manages the Cicadas lifecycle: initiative kickoff, branch registration, conflict detection, spec reflection, signaling, synthesis, merging, and queries.

## Directory Structure

Chorus logic resides in `scripts/chorus/`, and manages the `.cicadas/` folder in the project root:

```
project-root/
├── src/                              # Existing source code
├── scripts/
│   └── chorus/                       # Chorus orchestrator
│       ├── SKILL.md                  # Agent skill definition (this file)
│       ├── implementation.md         # Agent guardrails
│       ├── reverse-engineering.md    # Bootstrapping guide for existing codebases
│       ├── scripts/                  # Python orchestration scripts
│       │   ├── utils.py              # Shared utilities
│       │   ├── init.py               # Bootstrap .cicadas/ structure
│       │   ├── kickoff.py            # Promote drafts → active, register initiative
│       │   ├── branch.py             # Register a feature branch
│       │   ├── status.py             # Show initiatives, branches, signals
│       │   ├── check.py              # Check for conflicts & main updates
│       │   ├── signal.py             # Broadcast a change to peer branches
│       │   ├── archive.py            # Move active specs → archive, deregister
│       │   ├── update_index.py       # Append to change ledger
│       │   └── prune.py              # Rollback branch or initiative → restore to drafts
│       ├── templates/                # Markdown templates
│       │   ├── synthesis-prompt.md   # LLM prompt for canon synthesis
│       │   ├── product-overview.md   # Canon template
│       │   ├── ux-overview.md        # Canon template
│       │   ├── tech-overview.md      # Canon template
│       │   ├── module-snapshot.md    # Canon template (per module)
│       │   ├── prd.md                # Active spec template
│       │   ├── ux.md                 # Active spec template
│       │   ├── tech-design.md        # Active spec template
│       │   ├── approach.md           # Active spec template
│       │   └── tasks.md              # Active spec template
│       └── emergence/                # Subagent definitions for spec authoring
│           ├── emergence.md          # Emergence phase overview
│           ├── clarify.md            # PRD refinement subagent
│           ├── ux.md                 # UX design subagent
│           ├── tech-design.md        # Architecture subagent
│           ├── approach.md           # Partitioning & sequencing subagent
│           └── tasks.md              # Task breakdown subagent
└── .cicadas/                         # Cicadas artifacts (managed by scripts)
    ├── config.json                   # Local configuration
    ├── registry.json                 # Global registry (initiatives + feature branches)
    ├── index.json                    # Change ledger (append-only)
    ├── canon/                        # Canon (authoritative, generated)
    │   ├── product-overview.md
    │   ├── ux-overview.md
    │   ├── tech-overview.md
    │   └── modules/
    │       └── {module-name}.md
    ├── drafts/                       # Pre-kickoff staging area
    │   └── {initiative-name}/
    │       ├── prd.md
    │       ├── ux.md
    │       ├── tech-design.md
    │       ├── approach.md
    │       └── tasks.md
    ├── active/                       # Live specs for in-flight work
    │   └── {initiative-name}/
    └── archive/                      # Expired specs (timestamped)
        └── {timestamp}-{name}/
```

## Process

### Outer Loop — Initiative Lifecycle

1. **Emergence**: Draft specs in `.cicadas/drafts/{initiative}/` using subagents or manual authoring.
2. **Kickoff**: Promote drafts to active, register initiative, create initiative branch.
3. **Feature Branches**: For each partition defined in `approach.md`, start a registered feature branch.
4. **Task Branches**: For each task, create ephemeral unregistered task branches off the feature branch.
5. **Complete Feature**: Merge feature branch into initiative branch. No synthesis yet.
6. **Complete Initiative**: Merge initiative branch to `main`, synthesize canon on `main`, archive specs.

### Inner Loop — Daily Coding

1. Create task branch from feature branch: `git checkout -b task/{feature}/{task-name}`
2. Implement code.
3. **Reflect**: Keep active specs current as code diverges from plan.
4. Open a **PR** against the feature branch. Include Reflect findings in the PR description.
5. Builder reviews and approves the PR.
6. Merge the PR, delete the task branch.

### Branch Hierarchy

```
main
└── initiative/{name}              ← created at kickoff, merges to main once
    ├── feat/{partition-1}         ← registered, forks from initiative
    │   ├── task/.../task-a        ← ephemeral, unregistered
    │   └── task/.../task-b        ← ephemeral, unregistered
    ├── feat/{partition-2}         ← registered, forks from initiative
    └── feat/{partition-3}         ← registered, forks from initiative
```

---

## Operations

### Bootstrap (First-Time Setup)
```
python scripts/chorus/scripts/init.py
```
Creates the `.cicadas/` directory structure. If the project already has code, follow `reverse-engineering.md` to create initial canon.

### Emergence (Drafting Specs)
Progressive spec authoring in `.cicadas/drafts/{initiative-name}/`, using subagents in `emergence/` or manual drafting. See `emergence/emergence.md` for the full workflow.

| Step | Artifact | Focus |
|------|----------|-------|
| 1. Clarify | `prd.md` | **What & Why**. Problem, users, success criteria. |
| 2. UX | `ux.md` | **Experience**. Interaction flow, UI states, copy. |
| 3. Tech | `tech-design.md` | **Architecture**. Components, data flow, schemas. |
| 4. Approach | `approach.md` | **Strategy & Partitioning**. Sequencing, dependencies, and logical partitions that become feature branches. |
| 5. Tasks | `tasks.md` | **Execution**. Ordered, testable checklist grouped by partition. |

**Critical**: `approach.md` MUST define logical partitions with declared module scopes. These become feature branches.

Human review is required after each step. The Agent MUST NOT proceed without Builder approval.

### Kickoff (Initiative Start)
**Trigger**: Drafts reviewed and approved.
```
python scripts/chorus/scripts/kickoff.py {initiative-name} --intent "description"
```
**Effect**:
1. Promotes docs from `.cicadas/drafts/{name}/` to `.cicadas/active/{name}/`.
2. Registers the initiative in `registry.json` under `initiatives`.
3. Creates the initiative branch: `git checkout -b initiative/{name}`.

### Start a Feature Branch (Registered)
**When**: Starting a partition of work defined in `approach.md`.

**Steps**:
1. **Semantic Intent Check (Agent)**: Read `registry.json`. Analyze new intent against all active feature intents for logical conflicts.
2. **Checkout initiative branch**: `git checkout initiative/{name}`
3. **Script**: `python scripts/chorus/scripts/branch.py {branch-name} --intent "description" --modules "mod1,mod2" --initiative {initiative-name}`
4. Review warnings from both the Agent (intent conflicts) and the Script (module overlaps).

### Complete a Feature Branch
**When**: All task branches merged into the feature branch.

**Steps**:
1. **Update index**: `python scripts/chorus/scripts/update_index.py --branch {name} --summary "..."`
2. **Merge to initiative**: `git checkout initiative/{name} && git merge {branch-name}`

**Key**: No synthesis, no archiving at this step. Active specs stay active — they are the living document for the rest of the initiative, continuously updated by Reflect.

### Complete an Initiative
**When**: All feature branches merged into the initiative branch.

**Step 1 — Merge to main**:
```
git checkout main && git merge initiative/{name}
git branch -d initiative/{name}
```

**Step 2 — Synthesize canon on main** (Agent Operation):
- Read: codebase on `main`, active specs, existing canon, change ledger
- Synthesize: create (greenfield) or update (brownfield) canon files
- **Extract Key Decisions** from active specs and embed in canon
- Present to Builder for review

Use the prompt in `scripts/chorus/templates/synthesis-prompt.md` to guide synthesis.

**Step 3 — Archive & commit**:
```
python scripts/chorus/scripts/archive.py {initiative-name} --type initiative
python scripts/chorus/scripts/update_index.py --branch {initiative-name} --summary "..."
git commit -m "chore(cicadas): synthesize canon and archive {initiative-name}"
```

### Check Status & Signals
```
python scripts/chorus/scripts/status.py
python scripts/chorus/scripts/check.py
```
The Agent should check for signals when performing a Check Status operation and assess their relevance.

### Broadcast: Signal
**Trigger**: A change that affects other feature branches.
```
python scripts/chorus/scripts/signal.py "Changed API: renamed login() to authenticate()"
```
Appends a timestamped signal to the initiative's signal board in `registry.json`.

### Prune / Rollback
```
python scripts/chorus/scripts/prune.py {name} --type {branch|initiative}
```
Deletes the git branch, removes from registry, and restores specs to `drafts/`.

---

## Agent Operations (LLM)

These are reasoning + editing operations performed by the Agent, NOT scripts.

### Semantic Intent Check
**Trigger**: Before starting a feature branch.
**Action**: Read `registry.json`, analyze the new intent against all active feature intents for logical conflicts. Module overlap alone is insufficient — this is an LLM reasoning step.

### Reflect
**Trigger**: After significant code changes; before merging a task branch to the feature branch.
**Action**:
1. Analyze `git diff` against the active specs.
2. Update relevant docs in `.cicadas/active/` (e.g., `tech-design.md`, `approach.md`, `tasks.md`) to match code reality.
3. If the change is significant enough to impact other feature branches, proceed to Signal.
4. Include Reflect findings in the PR description.

### Signal Assessment
**Trigger**: After Reflect discovers a cross-branch impact.
**Action**: The Agent evaluates whether a change affects peer branches and runs `signal.py` autonomously if needed.

### Synthesis
**Trigger**: At initiative completion, on `main`, after the code merge.
**Action**: Generate canon from code + active specs. See the synthesis protocol in the Operations section above.

---

## Guardrails

1. **No Unplanned Work**: Never start writing code until you have a reviewed `tasks.md`.
2. **Branch Only**: Only implement code on a registered feature branch or a task branch off of one. Never on `main` or the initiative branch.
3. **Hard Stop**: After drafting specs, STOP and wait for the Builder to approve. After synthesis, STOP and wait for review.
4. **Tool Mandate**: NEVER manually edit `registry.json`. ALWAYS use the scripts.
5. **Reflect Before PR**: Always run the Reflect operation before opening a PR for a task branch.
6. **No Canon on Branches**: Never write to `.cicadas/canon/` on any branch. Canon is only synthesized on `main` at initiative completion.

## Agent Autonomy Boundaries

| Action | Autonomy | Rationale |
|--------|----------|-----------|
| **Reflect** | Autonomous | Keeping specs current is mechanical. |
| **Signal** | Autonomous | Agent assesses cross-branch impact. |
| **Semantic Intent Check** | Autonomous | Conflict detection is informational. |
| **PR creation** | Autonomous | Agent opens PRs with summaries and Reflect findings. |
| **PR merge** | **Builder approval** | Code review is a human gate. |
| **Synthesis** | Autonomous (execution) | Agent produces canon, but... |
| **Canon commit** | **Builder approval** | ...canon must be reviewed before committing. |
| **Archive** | **Builder approval** | Archiving is irreversible. |

## Builder Commands

The Builder interacts via natural-language commands. The Agent handles all scripts, git operations, and agentic operations behind the scenes.

- **"Initialize cicadas"** → Runs `init.py`. Sets up `.cicadas/` structure.
- **"Kickoff {name}"** → Runs `kickoff.py`. Promotes drafts, registers initiative, creates initiative branch.
- **"Start feature {name}"** → Semantic check + `branch.py`. Creates feature branch from initiative, registers, checks conflicts.
- **"Implement task {X}"** → Creates task branch, implements, Reflects, opens PR with findings.
- **"Signal {message}"** → Runs `signal.py`. Broadcasts change to initiative.
- **"Complete feature {name}"** → Runs `update_index.py`. Merges feature branch into initiative branch.
- **"Complete initiative {name}"** → Merges initiative to `main`, synthesizes canon, archives specs, commits.
- **"Check status"** → Runs `status.py` and `check.py`. Surfaces state, conflicts, signals.
- **"Prune {name}"** → Runs `prune.py`. Rollback and restore to drafts.

---

## CLI Quick Reference

### Scripts (Deterministic)

| Phase | Command | Action |
|-------|---------|--------|
| **Init** | `python scripts/chorus/scripts/init.py` | Bootstrap project structure |
| **Kickoff** | `python scripts/chorus/scripts/kickoff.py {name} --intent "..."` | Promote drafts, register initiative, create branch |
| **Feature** | `python scripts/chorus/scripts/branch.py {name} --intent "..." --modules "..." --initiative {name}` | Register feature branch |
| **Status** | `python scripts/chorus/scripts/status.py` | Show global state & signals |
| **Check** | `python scripts/chorus/scripts/check.py` | Check for conflicts & updates |
| **Signal** | `python scripts/chorus/scripts/signal.py "{message}"` | Broadcast to initiative |
| **Archive** | `python scripts/chorus/scripts/archive.py {name} --type {branch\|initiative}` | Expire active specs |
| **Log** | `python scripts/chorus/scripts/update_index.py --branch {name} --summary "..."` | Record history |
| **Prune** | `python scripts/chorus/scripts/prune.py {name} --type {branch\|initiative}` | Rollback & restore to drafts |

### Agent Operations (LLM)

| Operation | Trigger | Action |
|-----------|---------|--------|
| **Semantic Intent Check** | Before starting a feature branch | Analyze registry intents for logical conflicts |
| **Reflect** | After significant code changes, before PR | Update active specs to match code reality. Include findings in PR. |
| **Signal Assessment** | After Reflect, during status check | Evaluate cross-branch impact. Signal autonomously if needed. |
| **Synthesis** | At initiative completion, on `main` | Generate canon from code + active specs. Requires Builder review. |

## Templates

Use templates in `scripts/chorus/templates/` directory:
- `product-overview.md`, `ux-overview.md`, `tech-overview.md`, `module-snapshot.md`: Canon templates
- `prd.md`, `ux.md`, `tech-design.md`, `approach.md`, `tasks.md`: Active spec templates
- `synthesis-prompt.md`: System prompt for canon synthesis
