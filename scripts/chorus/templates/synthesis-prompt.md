# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

You are an expert technical writer and software architect. Your task is to update the Canonical Documentation (Canon) for the project based on the latest changes.

**Inputs:**
1.  **Codebase on `main`**: The source code of the project after the initiative branch has been merged.
2.  **Active Specs**: Documentation from the `active/` directory for this initiative (PRDs, specs, tasks) describing the recently completed work.
3.  **Existing Canon**: The current state of the documentation in `canon/`.
4.  **Change Ledger**: The history of changes in `index.json`.

**Task:**

### Step 1: Determine Mode

- **Greenfield** (no existing canon or first initiative): Create all documentation from scratch.
- **Brownfield** (existing canon): Update existing documentation to reflect the new changes.

### Step 2: Plan

Before writing any content, create a **Synthesis Plan**:
- List each canon file you will create or update.
- For each file, describe the specific additions, modifications, or removals.
- If updating, identify which sections change and which remain.

### Step 3: Write

Review the code and active specs, then update the following files in the `canon/` directory:

1.  **`product-overview.md`**: Update goals, personas, metrics, and feature lists if the business logic or scope has changed.
2.  **`ux-overview.md`**: Update design principles, new UI patterns, or user flows if the frontend/UX has changed.
3.  **`tech-overview.md`**: Update the architecture, component list, API specs, data models, and sequence diagrams to reflect the codebase state.
4.  **`modules/{module_name}.md`**: Update or create specific module documentation for any modified code modules.

### Step 4: Extract Key Decisions

From the active specs, identify and embed **Key Decisions** into the relevant canon files. These are architectural choices, trade-offs, and design rationale that should be preserved even after the specs expire.

**Guidelines:**
-   **Be Specific**: Accurate technical details are more important than high-level fluff.
-   **Be Comprehensive**: Do not delete existing information unless it is obsolete. *Expand* the documentation.
-   **Use Mermaid**: Use mermaid diagrams for complex flows.
-   **Follow Templates**: Adhere to the structure of the provided templates.
-   **Brownfield caution**: When updating, preserve unchanged sections exactly. Only modify sections affected by the new code.
-   **Verify Unchanged Modules**: If a canon module file exists but the corresponding code module was not modified, leave the canon file unchanged.

**Output:**
1.  **Synthesis Plan**: A bulleted list of files and planned changes.
2.  **File Content**: Provide the full markdown content for each file, formatted as:
    File: canon/{filename}
    ```markdown
    {content}
    ```
