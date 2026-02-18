# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

# Reverse Engineering: The Cicadas Bootstrap

**Goal**: Transform a "non-Cicadas" codebase into a documented system with an authoritative **Canon**.

## The Challenge
Non-Cicadas projects often have:
1. **Implicit Architecture**: Decisions are in the code, not docs.
2. **Outdated Specs**: If docs exist, they are likely stale.
3. **High Context Debt**: New agents/members must "read everything" to understand anything.

## The Workflow

### Phase 1: Initialize
Run the setup script once: `python scripts/chorus/scripts/init.py`.

### Phase 2: Agent Discovery
Tell the agent: **"I need to reverse engineer this project. Scan the code and report on the architecture and core boundaries."**
The agent will:
- Breadth-first scan.
- Identify entry points and dependencies.
- Map authoritative data state.

### Phase 3: Canonization
Tell the agent: **"Synthesize the baseline Canon. Create a product overview and module snapshots for the critical areas you found."**
The agent will:
- Draft `.cicadas/canon/product-overview.md`.
- Create module-specific baseline docs in `.cicadas/canon/modules/`.
- Mark implicit decisions and open questions in the docs.

### Phase 4: Genesis
Tell the agent: **"Set the Genesis point. Update the history index to record this bootstrap."**
The agent will:
- Execute `update_index.py` with the "bootstrap" summary.
- Registry state is now authoritative for future work.

## Guidelines for the Bootstrap Agent

- **Mental Models Over Lines of Code**: Describe what a human needs to understand to work safely.
- **Mark Uncertainties**: If the "Why" is missing (as it often is in legacy), label it as an `Open Question`.
- **Target Stability**: Baseline the stable core first. The volatility will be captured in future branches.

> [!IMPORTANT]
> **Be Descriptive, Not Exhaustive**: Don't try to document every line. Focus on the "Mental Model" a developer needs to work in the code safely.

- **Look for Patterns**: Identify naming conventions, error handling styles, and testing patterns.
- **Admit Uncertainty**: If the "Why" behind a piece of code is unclear, mark it in `Open Questions` within the canon.
- **Prioritize Stability**: Document the stable parts of the system first. Volatile parts are better addressed during subsequent initiative-based work.

## Next Steps
Once the Canon is established, all future work follows the standard **Emergence** path, building on top of the newly created authoritative documentation.
