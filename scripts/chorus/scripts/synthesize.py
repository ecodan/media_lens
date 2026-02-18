# Copyright 2026 Cicadas Contributors
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
import re
from pathlib import Path
from utils import get_project_root, load_json

def gather_context(name, is_initiative=False):
    root = get_project_root()
    cicadas = root / ".cicadas"
    registry = load_json(cicadas / "registry.json")

    context = {
        "active_docs": {},
        "code_context": {},
        "canon_docs": {}
    }

    # 1. Gather Active Specs
    source_dir = cicadas / "active" / name

    if source_dir.exists():
        for doc in source_dir.glob("*.md"):
            context["active_docs"][doc.name] = doc.read_text()

    # 2. Gather Code Context (if branch)
    modules = []
    if not is_initiative:
        branch_info = registry.get("branches", {}).get(name, {})
        modules = branch_info.get("modules", [])

    for mod in modules:
        # Simplistic mapping: mod.name -> src/mod/
        mod_path = root / "src" / mod.replace(".", "/")
        if not mod_path.exists():
            mod_path = root / mod.replace(".", "/") # Try without src

        if mod_path.exists():
            for py_file in mod_path.glob("**/*.py"):
                rel_path = py_file.relative_to(root)
                context["code_context"][str(rel_path)] = py_file.read_text()

    # 3. Gather Existing Canon
    canon_dir = cicadas / "canon"
    if canon_dir.exists():
        for doc in canon_dir.glob("*.md"):
            context["canon_docs"][doc.name] = doc.read_text()
        # Also gather module snapshots
        modules_dir = canon_dir / "modules"
        if modules_dir.exists():
            for doc in modules_dir.glob("*.md"):
                context["canon_docs"][f"modules/{doc.name}"] = doc.read_text()

    # 4. Gather Change Ledger
    index = load_json(cicadas / "index.json")
    context["index"] = index

    return context

def generate_prompt(context):
    root = get_project_root()
    prompt_template = Path(__file__).parent.parent / "templates" / "synthesis-prompt.md"

    template_text = prompt_template.read_text()

    prompt = f"{template_text}\n\n"
    prompt += "### DATA CONTEXT ###\n\n"

    prompt += "#### EXISTING CANON ####\n"
    for name, content in context["canon_docs"].items():
        prompt += f"File: canon/{name}\n```markdown\n{content}\n```\n\n"

    prompt += "#### ACTIVE SPECS ####\n"
    for name, content in context["active_docs"].items():
        prompt += f"File: {name}\n```markdown\n{content}\n```\n\n"

    prompt += "#### CODE CONTEXT ####\n"
    for path, content in context["code_context"].items():
        prompt += f"File: {path}\n```python\n{content}\n```\n\n"

    prompt += "#### CHANGE LEDGER ####\n"
    prompt += f"```json\n{json.dumps(context.get('index', {}), indent=2)}\n```\n\n"

    return prompt

def apply_response(response_text):
    root = get_project_root()
    cicadas = root / ".cicadas"
    canon_dir = cicadas / "canon"

    # Regex to find code blocks with file names
    pattern = r"File: (canon/[\w\/\.-]+)\n```(?:markdown|python)?\n(.*?)\n```"
    matches = re.findall(pattern, response_text, re.DOTALL)

    if not matches:
        print("No file content blocks found in response.")
        return

    for file_path, content in matches:
        target = cicadas / file_path.replace("canon/", "canon/", 1)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.strip() + "\n")
        print(f"✅ Updated {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthesis Orchestrator — gather context and generate prompt")
    parser.add_argument("name", help="Name of the branch or initiative")
    parser.add_argument("--initiative", action="store_true", help="Synthesize for an initiative")
    parser.add_argument("--apply", help="Path to a file containing the LLM response to apply to the canon")

    args = parser.parse_args()

    if args.apply:
        response_path = Path(args.apply)
        if response_path.exists():
            apply_response(response_path.read_text())
        else:
            print(f"Error: Response file {args.apply} not found.")
    else:
        ctx = gather_context(args.name, is_initiative=args.initiative)
        print(generate_prompt(ctx))
