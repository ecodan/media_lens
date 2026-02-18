# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import shutil
import subprocess
from utils import get_project_root, load_json, save_json

def prune(name, type_):
    root = get_project_root()
    cicadas = root / ".cicadas"
    registry = load_json(cicadas / "registry.json")

    if type_ == "branch":
        if name not in registry.get("branches", {}):
            print(f"Error: Branch {name} not found.")
            return
        # Restore active specs to drafts
        active = cicadas / "active" / name
        drafts = cicadas / "drafts" / name
        if active.exists():
            shutil.move(str(active), str(drafts))
            print(f"Restored specs to drafts/{name}")
        # Delete git branch
        try:
            subprocess.run(["git", "checkout", "main"], check=True, cwd=root)
            subprocess.run(["git", "branch", "-D", name], check=True, cwd=root)
        except Exception:
            print(f"Warning: Could not delete git branch {name}")
        del registry["branches"][name]
        save_json(cicadas / "registry.json", registry)
        print(f"Pruned branch: {name}")

    elif type_ == "initiative":
        if name not in registry.get("initiatives", {}):
            print(f"Error: Initiative {name} not found.")
            return
        # Restore specs
        active = cicadas / "active" / name
        drafts = cicadas / "drafts" / name
        if active.exists():
            shutil.move(str(active), str(drafts))
            print(f"Restored specs to drafts/{name}")
        # Delete initiative branch
        branch_name = f"initiative/{name}"
        try:
            subprocess.run(["git", "checkout", "main"], check=True, cwd=root)
            subprocess.run(["git", "branch", "-D", branch_name], check=True, cwd=root)
        except Exception:
            print(f"Warning: Could not delete git branch {branch_name}")
        del registry["initiatives"][name]
        save_json(cicadas / "registry.json", registry)
        print(f"Pruned initiative: {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rollback and restore specs to drafts")
    parser.add_argument("name")
    parser.add_argument("--type", required=True, choices=["branch", "initiative"])
    args = parser.parse_args()
    prune(args.name, args.type)
