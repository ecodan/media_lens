# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

# Tasks: {Feature Name}

# Tasks: {Feature Name}

<!-- Select one mode below and delete the other -->

## Mode A: Foundation (Strict Phases)

### Phase 1: Models (Blocking)
- [ ] Create `models/example.py`: Define `Example` class <!-- id: 0 -->
- [ ] Create `models/other.py`: Define `Other` class (Parallel) <!-- id: 1 -->

### Phase 2: Services (Parallelizable)
- [ ] Create `services/logic.py`: Implement `process_data` <!-- id: 2 -->


## Mode B: Feature (Vertical Slices)

### Feature: Inventory System
- [ ] Update `models/character.py`: Add inventory list <!-- id: 10 -->
- [ ] Update `cli.py`: Add `inventory` command <!-- id: 11 -->

### Feature: Crafting System (Parallel to Inventory)
- [ ] Update `models/item.py`: Add recipes <!-- id: 20 -->

