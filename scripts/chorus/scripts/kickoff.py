# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from utils import get_project_root, load_json, save_json

def kickoff(name, intent, owner="unknown"):
    root = get_project_root()
    cicadas = root / ".cicadas"
    registry = load_json(cicadas / "registry.json")

    if name in registry.get("initiatives", {}):
        print(f"Error: Initiative {name} already exists.")
        return

    active_dir = cicadas / "active" / name
    active_dir.mkdir(parents=True, exist_ok=True)

    # Promote drafts
    drafts_dir = cicadas / "drafts" / name
    if drafts_dir.exists():
        print(f"Promoting drafts for initiative: {name}...")
        for item in drafts_dir.iterdir():
            if item.name.startswith("."): continue
            shutil.move(str(item), str(active_dir / item.name))
        try:
            drafts_dir.rmdir()
        except OSError:
            pass
    else:
        print(f"Warning: No drafts found for {name}. Creating empty initiative.")

    # Register
    registry.setdefault("initiatives", {})[name] = {
        "intent": intent,
        "owner": owner,
        "signals": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_json(cicadas / "registry.json", registry)

    # Create initiative branch
    branch_name = f"initiative/{name}"
    try:
        subprocess.run(["git", "checkout", "-b", branch_name], check=True, cwd=root)
        print(f"Created initiative branch: {branch_name}")
    except subprocess.CalledProcessError:
        print(f"Warning: Could not create git branch {branch_name}")

    print(f"Initiative kicked off: {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kickoff an initiative: promote drafts to active, register, create branch")
    parser.add_argument("name")
    parser.add_argument("--intent", required=True)
    args = parser.parse_args()
    kickoff(args.name, args.intent)
