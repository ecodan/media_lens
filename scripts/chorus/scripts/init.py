# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
from pathlib import Path
from utils import save_json, get_project_root

def init_cicadas(root):
    cicadas = root / ".cicadas"
    cicadas.mkdir(exist_ok=True)
    (cicadas / "canon/modules").mkdir(parents=True, exist_ok=True)
    (cicadas / "active").mkdir(exist_ok=True)
    (cicadas / "drafts").mkdir(exist_ok=True)
    (cicadas / "archive").mkdir(exist_ok=True)

    save_json(cicadas / "registry.json", {
        "schema_version": "2.0",
        "initiatives": {},
        "branches": {}
    })
    save_json(cicadas / "index.json", {"schema_version": "2.0", "entries": []})
    save_json(cicadas / "config.json", {"project_name": root.name})

    print(f"Initialized Cicadas in {cicadas}")

if __name__ == "__main__":
    init_cicadas(get_project_root())
