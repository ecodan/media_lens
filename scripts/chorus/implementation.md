# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

# Cicadas: Implementation Protocol

This document defines the rules for an **Implementation Agent**. These rules prevent agents from "running amok" and ensure changes are made within the correct safety boundaries.

## 1. The Hard Stop
An agent MUST stop and wait for human review after the **Emergence** phase (generating `tasks.md`).
- **Rule**: Do not start implementing code until the user explicitly says "Kickoff" or "Start a Feature".
- **Why**: The `tasks.md` file often needs human correction for granularity and parallelism.

## 2. Identity Check (Branch Safety)
Before touching any project source code, an agent MUST verify its environment.
- **Rule**: You must only write code if you are on a **registered feature branch** or a **task branch** forked from one. Check `.cicadas/registry.json`.
- **Constraint**: No direct code changes to `main`, `master`, or initiative branches are permitted.

## 3. Execution Scope
When working on a branch:
- **Rule**: Only implement the tasks assigned to your current feature branch partition.
- **Rule**: If you discover that a task requires changing files outside your declared modules, STOP and notify the user.

## 4. Reflect Before PR
Before opening a PR for a task branch:
- **Rule**: Run the Reflect operation — analyze `git diff` against active specs and update them.
- **Rule**: Include Reflect findings in the PR description.

## 5. No Canon on Branches
- **Rule**: Never write to `.cicadas/canon/` on any branch.
- **Why**: Canon is only synthesized on `main` at initiative completion. Writing canon on branches creates merge conflicts.

## 6. Synthesis
When an initiative is complete:
- **Rule**: Merge the initiative branch to `main` first, then synthesize canon on `main`.
- **Rule**: Do not archive active specs until the Builder reviews the synthesized canon.

## 7. Registry Integrity
- **Rule**: NEVER manually edit `registry.json`.
- **Constraint**: ALWAYS use the provided CLI scripts (e.g., `branch.py`, `kickoff.py`, `status.py`) to manage system state.
