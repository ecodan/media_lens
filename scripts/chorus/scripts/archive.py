# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import shutil
from datetime import datetime, timezone
from utils import get_project_root, load_json, save_json

def archive(name, type_="branch"):
    root = get_project_root()
    cicadas = root / ".cicadas"
    registry = load_json(cicadas / "registry.json")

    registry_key = "initiatives" if type_ == "initiative" else "branches"

    if name not in registry.get(registry_key, {}):
        print(f"Error: {type_.capitalize()} {name} not found in registry.")
        return

    # Move active specs to archive
    active = cicadas / "active" / name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    husk = cicadas / "archive" / f"{ts}-{name}"

    if active.exists():
        shutil.move(str(active), str(husk))
        print(f"Archived active specs to {husk.name}")

    # Remove from registry
    del registry[registry_key][name]
    save_json(cicadas / "registry.json", registry)
    print(f"Deregistered {type_}: {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive active specs and deregister from registry")
    parser.add_argument("name")
    parser.add_argument("--type", default="branch", choices=["branch", "initiative"],
                        help="Type to archive: branch or initiative")
    args = parser.parse_args()
    archive(args.name, args.type)
