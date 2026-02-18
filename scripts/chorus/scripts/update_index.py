# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
from datetime import datetime, timezone
from utils import get_project_root, load_json, save_json

def update_index(branch, summary, decisions="", modules=""):
    root = get_project_root()
    index_path = root / ".cicadas" / "index.json"
    index = load_json(index_path)
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "summary": summary,
        "decisions": decisions,
        "modules": [m.strip() for m in modules.split(",") if m.strip()]
    }
    
    index.setdefault("entries", []).append(entry)
    save_json(index_path, index)
    print(f"Added entry {len(index['entries'])} to artifact index.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--decisions", default="")
    parser.add_argument("--modules", default="")
    args = parser.parse_args()
    update_index(args.branch, args.summary, args.decisions, args.modules)
