# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import subprocess
from utils import get_project_root, load_json

def check_conflicts():
    root = get_project_root()
    cicadas = root / ".cicadas"
    registry = load_json(cicadas / "registry.json")

    # Get current branch
    try:
        curr = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=root
        ).decode().strip()
    except Exception:
        curr = "unknown"

    print(f"Checking status for branch: {curr}")

    # Check registry overlaps
    curr_info = registry.get("branches", {}).get(curr)
    if curr_info:
        my_mods = set(curr_info.get("modules", []))
        for name, info in registry.get("branches", {}).items():
            if name == curr: continue
            overlap = my_mods.intersection(set(info.get("modules", [])))
            if overlap:
                print(f"⚠️  CONFLICT: Branch '{name}' overlaps on modules: {', '.join(overlap)}")

        # Check for signals in linked initiative
        initiative = curr_info.get("initiative")
        if initiative:
            init_info = registry.get("initiatives", {}).get(initiative, {})
            signals = init_info.get("signals", [])
            if signals:
                print(f"\n📡 Signals from initiative '{initiative}':")
                for s in signals:
                    print(f"  [{s['timestamp']}] ({s.get('from_branch', '?')}): {s['message']}")
    else:
        print(f"ℹ️  Current branch '{curr}' is not registered.")

    # Check for main updates
    try:
        log = subprocess.check_output(
            ["git", "log", f"{curr}..main", "--oneline"], cwd=root
        ).decode()
        if log:
            count = len(log.strip().split('\n'))
            print(f"\n📥 {count} new commits on main since you branched.")
    except Exception:
        pass

if __name__ == "__main__":
    check_conflicts()
