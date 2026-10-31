#!/usr/bin/env python3
"""Build upload ZIPs for Claude Desktop / claude.ai: dist/<skill>.zip for every folder in skills/.

form-filler-setup ships its own copy of form-filler's store script and default registry, because skills uploaded
to claude.ai can't see each other's files. This script refreshes those copies first, then validates and zips.
"""
import json, re, shutil, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
DIST = ROOT / "dist"
SHARED = ["scripts/profile_store.py", "assets/field_registry.default.json"]


def sync_shared():
    for rel in SHARED:
        shutil.copyfile(SKILLS / "form-filler" / rel, SKILLS / "form-filler-setup" / rel)


def problems(d):
    """Same rules claude.ai applies on upload: kebab-case name = folder, description <= 1024 chars, one SKILL.md."""
    text = (d / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return ["no YAML frontmatter"]
    fm = m.group(1)
    name = (re.search(r"^name: *(.+)$", fm, re.M) or [None, ""])[1].strip()
    desc_m = re.search(r'^description: *(".*")$', fm, re.M)
    desc = json.loads(desc_m.group(1)) if desc_m else ""
    found = []
    if name != d.name or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        found.append(f"name {name!r} must be kebab-case, at most 64 characters, and equal the folder name")
    if not desc or len(desc) > 1024 or "<" in desc or ">" in desc:
        found.append("description must be a quoted string of 1-1024 characters without < or >")
    if len(list(d.rglob("SKILL.md"))) != 1:
        found.append("exactly one SKILL.md allowed")
    return found


def build(d):
    DIST.mkdir(exist_ok=True)
    z = DIST / f"{d.name}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(d.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                zf.write(f, f.relative_to(SKILLS).as_posix())
    return z


def main():
    sync_shared()
    failed = False
    for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        found = problems(d)
        if found:
            failed = True
            print(f"{d.name}: " + "; ".join(found))
        else:
            print(f"{d.name}: {build(d)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
