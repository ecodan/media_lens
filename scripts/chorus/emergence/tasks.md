# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

# Emergence: Tasks

**Goal**: Break the approach into a checklist of small, testable tasks, grouped by partition.

**Role**: You are a Project Manager / Tech Lead. Your job is to create a clear plan of action for the developer.

## Process

1.  **Ingest**: Read all previous docs in `.cicadas/drafts/{initiative}/`.
2.  **Select Mode**:
    -   **Foundation Mode** (New Project/Module):
        -   **Decompose**: Atomic, file-level tasks.
        -   **Order**: Strict dependency phases (Models → Engine → UI).
        -   **Parallelism**: Independent *Work Groups* within a phase.
    -   **Feature Mode** (Vertical Slice):
        -   **Decompose**: Functional deliverables (e.g., "Add Inventory").
        -   **Order**: Group by feature or user story.
        -   **Parallelism**: Features are parallel; tasks within a feature are sequential.

3.  **Group by Partition**: Tasks MUST be organized under the partitions defined in `approach.md`. Each partition's tasks map to a Feature Branch.
4.  **Draft**: Create `.cicadas/drafts/{initiative}/tasks.md`.
    -   Use the format `- [ ] Task Description <!-- id: N -->`
5.  **Refine**: Builder review.

## Output Artifact: `tasks.md`

Use the template at `scripts/chorus/templates/tasks.md`.

## Key Considerations

-   **Granularity**: Tasks should be small enough to complete in one sitting.
-   **Verify-ability**: Each task should have a clear "done" state.
-   **Dependencies**: Identify blockers.
-   **Acceptance Criteria**: Each task should include criteria for what "done" looks like.
