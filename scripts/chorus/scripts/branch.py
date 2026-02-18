# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone
from utils import get_project_root, load_json, save_json

def create_branch(name, intent, modules, initiative=None, from_branch=None, owner="unknown"):
    root = get_project_root()
    cicadas = root / ".cicadas"
    registry = load_json(cicadas / "registry.json")

    if name in registry.get("branches", {}):
        print(f"Error: Branch {name} already registered.")
        return

    # Check for module overlaps
    my_mods = set(m.strip() for m in modules.split(",") if m.strip())
    conflicts = []
    for b_name, b_info in registry.get("branches", {}).items():
        overlap = my_mods.intersection(set(b_info.get("modules", [])))
        if overlap:
            conflicts.append(f"{b_name} (Overlaps: {', '.join(overlap)})")

    # Determine parent branch
    if from_branch:
        parent = from_branch
    elif initiative:
        parent = f"initiative/{initiative}"
    else:
        parent = None

    # Checkout parent branch first if specified
    if parent:
        try:
            subprocess.run(["git", "checkout", parent], check=True, cwd=root)
        except subprocess.CalledProcessError:
            print(f"Warning: Could not checkout parent branch {parent}")

    # Git branch creation
    subprocess.run(["git", "checkout", "-b", name], check=True, cwd=root)

    # Register
    branch_info = {
        "intent": intent,
        "modules": list(my_mods),
        "owner": owner,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    if initiative:
        if initiative not in registry.get("initiatives", {}):
            print(f"Warning: Initiative {initiative} not found.")
        else:
            branch_info["initiative"] = initiative

    registry.setdefault("branches", {})[name] = branch_info
    save_json(cicadas / "registry.json", registry)

    (cicadas / "active" / name).mkdir(parents=True, exist_ok=True)

    print(f"Registered feature branch: {name}")
    if conflicts:
        print(f"WARNING: Module overlaps detected: {'; '.join(conflicts)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a feature branch with conflict detection")
    parser.add_argument("name")
    parser.add_argument("--intent", required=True)
    parser.add_argument("--modules", default="")
    parser.add_argument("--initiative", help="Link to an active initiative")
    parser.add_argument("--from", dest="from_branch", help="Parent branch to fork from (defaults to initiative branch)")
    args = parser.parse_args()
    create_branch(args.name, args.intent, args.modules, initiative=args.initiative, from_branch=args.from_branch)
