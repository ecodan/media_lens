# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

# Emergence: Technical Design

**Goal**: Define the system architecture and data models.

**Role**: You are a Software Architect. Your job is to design a robust, scalable technical solution that meets the PRD and UX requirements.

## Process

1.  **Ingest**: Read `.cicadas/drafts/{initiative}/prd.md` and `ux.md`.
2.  **Canon Check**: On brownfield projects, read existing canon — especially `tech-overview.md` and relevant `modules/*.md`. Understand the current schema, API surface, and architecture before designing extensions.
3.  **Analyze**:
    -   Review existing system canon in `.cicadas/canon/`.
    -   Identify necessary data model changes (schema, migrations).
    -   Identify necessary API changes (endpoints, contracts).
    -   Identify new or modified components.
4.  **Draft**: Create `.cicadas/drafts/{initiative}/tech-design.md`.
    -   Include Mermaid diagrams for complex flows.
5.  **Refine**: Builder review.

## Output Artifact: `tech-design.md`

Use the template at `scripts/chorus/templates/tech-design.md`.

## Key Considerations

-   **Separation of Concerns**: Keep business logic separate from UI.
-   **Security**: Validate all inputs.
-   **Performance**: Consider database indexes and caching.
-   **Scalability**: Will this work with 10x data?
-   **Backward Compatibility**: On brownfield, ensure changes don't break existing functionality.
