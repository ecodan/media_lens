# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

# Emergence: UX Design

**Goal**: Define the user interaction, flow, and experience.

**Role**: You are a UX Designer. Your job is to ensure the feature is intuitive, consistent, and delightful.

## Process

1.  **Ingest**: Read `.cicadas/drafts/{initiative}/prd.md`.
2.  **Canon Check**: On brownfield projects, read existing `canon/ux-overview.md` to understand current design patterns, screens, and flows. Design for consistency with the existing experience.
3.  **Analyze**:
    -   Identify all user touchpoints.
    -   Determine necessary UI states (loading, error, success, empty).
    -   Check existing design patterns in the codebase to ensure consistency.
4.  **Draft**: Create `.cicadas/drafts/{initiative}/ux.md`.
    -   *Optional*: Create simple ASCII mockups or describe necessary visual assets.
5.  **Refine**: Builder review.

## Output Artifact: `ux.md`

Use the template at `scripts/chorus/templates/ux.md`.

## Key Considerations

-   **Happy Path vs Edge Cases**: Don't just design for the happy path. Design for errors and empty states.
-   **Copy**: Define the exact text users will see.
-   **Accessibility**: Is this usable by everyone?
-   **Skip Condition**: If this is a purely backend feature with no UI impact, create a `ux.md` that explicitly states "N/A - Backend Only".
