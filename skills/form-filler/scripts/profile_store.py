#!/usr/bin/env python3
"""Personal-data store for the form-filler skill.

Layout of the store (ROOT is a folder on the user's computer):
  ROOT/people/<person_id>.json   one file per person
  ROOT/field_registry.json       canonical keys + learned aliases (copy of the default, then extended)

All commands print JSON to stdout so the calling agent can parse it.
Run `profile_store.py --help` or `<command> --help`.
"""
import argparse, datetime as dt, json, re, shutil, sys, unicodedata
from pathlib import Path

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "assets" / "field_registry.default.json"
DATE_FORMATS = {"iso": "%Y-%m-%d", "de": "%d.%m.%Y", "us": "%m/%d/%Y", "uk": "%d/%m/%Y"}


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def norm(s):
    """lowercase, strip accents/punctuation/asterisks, collapse whitespace; ae/oe/ue/ss folded."""
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slug(s):
    return norm(s).replace(" ", "-") or "person"


def load_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)  # atomic: never leaves a half-written profile


def require_store(root):
    """A store is a folder with field_registry.json and people/; anything else is reported as no_store."""
    r = Path(root)
    if not (r / "field_registry.json").is_file() or not (r / "people").is_dir():
        out({"error": "no_store", "root": str(r.resolve()),
             "hint": "this folder holds no form-filler data: open the folder that has it, or create one with the form-filler-setup skill"}, 2)


def registry(root):
    require_store(root)
    return load_json(Path(root) / "field_registry.json")


def person_path(root, pid):
    return Path(root) / "people" / f"{pid}.json"


def resolve_person(root, ref):
    """Accept an id, a display name, or a unique prefix/substring."""
    require_store(root)
    people ={p.stem: load_json(p) for p in (Path(root) / "people").glob("*.json")}
    if ref in people:
        return ref
    n = norm(ref)
    hits = [pid for pid, d in people.items() if n in (norm(pid), norm(d.get("display_name", "")))]
    if not hits:
        hits = [pid for pid, d in people.items() if n and (n in norm(d.get("display_name", "")) or n in norm(pid))]
    if len(hits) == 1:
        return hits[0]
    out({"error": "person not found" if not hits else "ambiguous person", "candidates": hits or list(people)}, 3)


def fmt_date(value, fmt):
    try:
        d = dt.date.fromisoformat(value)
    except ValueError:
        return value
    return d.strftime(DATE_FORMATS.get(fmt, fmt))


def get_value(reg, person, key, date_fmt=None, _depth=0, secondary=False):
    """Return (value, status). status: ok | missing | derived-missing.
    secondary=True returns the stored secondary value where one exists, else the primary one
    (a field with no alternative is still the right answer when the user asks for 'secondary data')."""
    spec = reg["keys"].get(key, {})
    tmpl = spec.get("derived")
    if tmpl:
        if tmpl == "@today":
            v = dt.date.today().isoformat()
            return (fmt_date(v, date_fmt) if date_fmt else v), "ok"
        parts = re.findall(r"\{([^}]+)\}", tmpl)
        vals = {}
        for k in parts:
            v, st = get_value(reg, person, k, date_fmt, _depth + 1, secondary) if _depth < 3 else (None, "missing")
            if st != "ok":
                return None, "derived-missing"
            vals[k] = v
        return re.sub(r"\{([^}]+)\}", lambda m: str(vals[m.group(1)]), tmpl), "ok"
    entry = person.get("fields", {}).get(key)
    if not entry or entry.get("value") in (None, ""):
        return None, "missing"
    v = entry["value"]
    if secondary and entry.get("secondary") not in (None, ""):
        v = entry["secondary"]
    if spec.get("type") == "date" and date_fmt:
        v = fmt_date(v, date_fmt)
    return v, "ok"


# ---------------------------------------------------------------- validators
# Each returns None if the value looks right, else a short reason. Reasons never contain the value itself.
def _compact(v):
    return re.sub(r"[\s./-]", "", str(v)).upper()


def check_iban(v):
    s = _compact(v)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return "not an IBAN format"
    if s.startswith("DE") and len(s) != 22:
        return "German IBANs have 22 characters"
    return None if int("".join(str(int(c, 36)) for c in s[4:] + s[:4])) % 97 == 1 else "IBAN checksum fails"


def check_bic(v):
    return None if re.fullmatch(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?", _compact(v)) else "not a BIC format (8 or 11 characters)"


def check_steuer_id(v):
    """German Steuer-ID: 11 digits, ISO 7064 MOD 11,10."""
    s = _compact(v)
    if not re.fullmatch(r"[1-9]\d{10}", s):
        return "not 11 digits (Steuer-ID)"
    p = 10
    for c in s[:10]:
        p = (2 * ((int(c) + p) % 10 or 10)) % 11
    return None if (11 - p) % 10 == int(s[10]) else "Steuer-ID checksum fails"


def check_rvnr(v):
    """German Rentenversicherungsnummer: area(2) DDMMYY(6) letter serial(2) check(1)."""
    m = re.fullmatch(r"(\d{8})([A-Z])(\d{2})(\d)", _compact(v))
    if not m:
        return "not a German RVNR format (12 characters, letter at position 9)"
    digits = m[1] + f"{ord(m[2]) - 64:02d}" + m[3]
    total = sum(sum(divmod(int(d) * w, 10)) for d, w in zip(digits, [2, 1, 2, 5, 7, 1, 2, 1, 2, 1, 2, 1]))
    return None if total % 10 == int(m[4]) else "RVNR checksum fails"


def check_kvnr(v):
    """German statutory health-insurance number: letter + 8 digits + check digit."""
    m = re.fullmatch(r"([A-Z])(\d{8})(\d)", _compact(v))
    if not m:
        return "not a KVNR format (letter + 9 digits)"
    digits = f"{ord(m[1]) - 64:02d}" + m[2]
    total = sum(sum(divmod(int(d) * (1 + i % 2), 10)) for i, d in enumerate(digits))
    return None if total % 10 == int(m[3]) else "KVNR checksum fails"


def check_email(v):
    return None if re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", str(v).strip()) else "not an email address"


def check_phone(v):
    s = str(v).strip()
    if not re.fullmatch(r"\+?[\d\s()/-]+", s) or not 7 <= len(re.sub(r"\D", "", s)) <= 15:
        return "not a phone number"
    return None if s.startswith("+") or s.startswith("00") else "no country code"


def check_date(v):
    try:
        dt.date.fromisoformat(str(v))
        return None
    except ValueError:
        return "not stored as ISO date (YYYY-MM-DD)"


KEY_CHECKS = {"bank.iban": check_iban, "bank.bic": check_bic, "tax.id": check_steuer_id,
              "social_security.number": check_rvnr, "health_insurance.number": check_kvnr}
TYPE_CHECKS = {"iban": check_iban, "email": check_email, "phone": check_phone, "date": check_date}


# ---------------------------------------------------------------- commands
def cmd_init(a):
    root = Path(a.root)
    rp = root / "field_registry.json"
    existed = rp.exists()
    (root / "people").mkdir(parents=True, exist_ok=True)
    if not existed:  # never overwrite a registry that has learned aliases
        shutil.copy(DEFAULT_REGISTRY, rp)
    out({"ok": True, "root": str(root.resolve()), "registry": str(rp), "existed": existed})


def cmd_add_person(a):
    require_store(a.root)
    pid = a.id or slug(a.name)
    p = person_path(a.root, pid)
    if p.exists():
        out({"error": "person exists", "id": pid}, 3)
    save_json(p, {"id": pid, "display_name": a.name, "relation": a.relation, "fields": {}, "created": dt.date.today().isoformat()})
    out({"ok": True, "id": pid})


def cmd_people(a):
    require_store(a.root)
    rows = []
    for p in sorted((Path(a.root) / "people").glob("*.json")):
        d = load_json(p)
        rows.append({"id": d["id"], "display_name": d.get("display_name"), "relation": d.get("relation"), "fields_stored": len(d.get("fields", {}))})
    out({"people": rows})


def cmd_get(a):
    reg = registry(a.root)
    pid = resolve_person(a.root, a.person)
    person = load_json(person_path(a.root, pid))
    keys = a.keys.split(",") if a.keys else sorted(person["fields"])
    res, missing = {}, []
    for k in keys:
        v, st = get_value(reg, person, k, a.date_format, secondary=a.secondary)
        if st == "ok":
            e = person["fields"].get(k, {})
            res[k] = {"value": v, "sensitive": bool(reg["keys"].get(k, {}).get("sensitive")),
                      "is_secondary": bool(a.secondary and e.get("secondary") not in (None, ""))}
        else:
            missing.append(k)
    out({"person": pid, "mode": "secondary" if a.secondary else "primary", "values": res, "missing": missing})


def cmd_set(a):
    reg = registry(a.root)
    pid = resolve_person(a.root, a.person)
    p = person_path(a.root, pid)
    person = load_json(p)
    changed, unknown = [], []
    for kv in a.pairs:
        k, _, v = kv.partition("=")
        k = k.strip()
        if k not in reg["keys"]:
            unknown.append(k)
            continue
        if reg["keys"][k].get("derived"):
            out({"error": f"{k} is derived; set its components instead"}, 3)
        if reg["keys"][k].get("type") == "bool":
            v = v.strip().lower() in ("1", "true", "yes", "ja", "y")
        old = person["fields"].get(k)
        today = dt.date.today().isoformat()
        if a.secondary:
            # store as the alternative value; the primary stays what forms get by default
            if not old:
                out({"error": f"{k} has no primary value yet; set it first, then add the secondary"}, 3)
            old["secondary"] = v
            old["updated"] = today
        else:
            new = {"value": v, "updated": today, "source": a.source or ""}
            if a.demote and old and old.get("value") not in (None, "", v):
                new["secondary"] = old["value"]  # keep the former primary as the alternative
            elif old and old.get("secondary") not in (None, ""):
                new["secondary"] = old["secondary"]  # a plain overwrite keeps an existing alternative
            person["fields"][k] = new
        changed.append(k)
    if unknown:
        out({"error": "unknown keys - register them first with register-key", "unknown": unknown}, 3)
    save_json(p, person)
    out({"ok": True, "person": pid, "changed": changed})


def cmd_unset(a):
    pid = resolve_person(a.root, a.person)
    p = person_path(a.root, pid)
    person = load_json(p)
    for k in a.keys:
        person["fields"].pop(k, None)
    save_json(p, person)
    out({"ok": True})


def cmd_register_key(a):
    rp = Path(a.root) / "field_registry.json"
    reg = registry(a.root)
    if a.key in reg["keys"] and not a.force:
        out({"error": "key exists; use --force or learn-alias"}, 3)
    reg["keys"][a.key] = {"label": a.label, "type": a.type, "aliases": [norm(x) for x in (a.aliases or [])]}
    if a.sensitive:
        reg["keys"][a.key]["sensitive"] = True
    if a.options:
        reg["keys"][a.key]["options"] = a.options
    save_json(rp, reg)
    out({"ok": True, "key": a.key})


def cmd_learn_alias(a):
    rp = Path(a.root) / "field_registry.json"
    reg = registry(a.root)
    if a.key not in reg["keys"]:
        out({"error": "unknown key"}, 3)
    al = reg["keys"][a.key].setdefault("aliases", [])
    added = [n for n in map(norm, a.labels) if n and n not in al]
    al.extend(added)
    save_json(rp, reg)
    out({"ok": True, "key": a.key, "added": added})


def score_label(label, reg):
    """Return sorted list of (score, key). Exact alias = 1.0, contained multi-word alias = 0.9, token overlap < 0.9."""
    nl = norm(label)
    toks = set(nl.split())
    cands = {}
    for k, spec in reg["keys"].items():
        best = 0.0
        for al in spec.get("aliases", []) + [norm(spec.get("label", ""))]:
            if not al:
                continue
            if al == nl:
                best = max(best, 1.0)
            elif (len(al) >= 6 or " " in al) and re.search(rf"\b{re.escape(al)}\b", nl):
                # longer contained alias is more specific
                best = max(best, min(0.95, 0.80 + 0.01 * len(al)))
            else:
                at = set(al.split())
                if at and toks:
                    j = len(at & toks) / len(at | toks)
                    best = max(best, round(j * 0.75, 2))
        if best > 0:
            cands[k] = best
    return sorted(((s, k) for k, s in cands.items()), reverse=True)[:4]


def cmd_match(a):
    """labels JSON: list of strings or of {"id":..., "label":...}. Reports key candidates + whether the person has a value."""
    reg = registry(a.root)
    person = load_json(person_path(a.root, resolve_person(a.root, a.person))) if a.person else None
    items = json.loads(Path(a.labels).read_text(encoding="utf-8")) if a.labels != "-" else json.load(sys.stdin)
    res = []
    for it in items:
        it = {"id": it, "label": it} if isinstance(it, str) else it
        c = score_label(it["label"], reg)
        top = c[0] if c else (0, None)
        # a clear winner needs to beat the runner-up, otherwise ask the agent to decide
        confident = bool(c) and top[0] >= 0.85 and (len(c) == 1 or top[0] - c[1][0] >= 0.03)
        row = {"id": it["id"], "label": it["label"], "confident": confident, "candidates": [{"key": k, "score": s} for s, k in c]}
        if person is not None and c:
            v, st = get_value(reg, person, top[1], a.date_format)
            row["stored"] = st == "ok"
        res.append(row)
    out({"matches": res})


def cmd_missing(a):
    reg = registry(a.root)
    person = load_json(person_path(a.root, resolve_person(a.root, a.person)))
    miss = [k for k in a.keys.split(",") if get_value(reg, person, k)[1] != "ok"]
    out({"missing": [{"key": k, "label": reg["keys"].get(k, {}).get("label", k), "sensitive": bool(reg["keys"].get(k, {}).get("sensitive"))} for k in miss]})


def cmd_registry(a):
    reg = registry(a.root)
    out({k: {"label": v["label"], "type": v["type"], "sensitive": bool(v.get("sensitive")), "derived": v.get("derived")} for k, v in reg["keys"].items()})


def cmd_check(a):
    """Validate stored values (checksums, formats) without printing them."""
    reg = registry(a.root)
    pid = resolve_person(a.root, a.person)
    person = load_json(person_path(a.root, pid))
    fields = person.get("fields", {})
    keys = a.keys.split(",") if a.keys else sorted(fields)
    res, unchecked = [], []
    for k in keys:
        fn = KEY_CHECKS.get(k) or TYPE_CHECKS.get(reg["keys"].get(k, {}).get("type"))
        # private insurers use their own member numbers, not the statutory KVNR
        if k == "health_insurance.number" and fields.get("health_insurance.is_private", {}).get("value") is True:
            fn = None
        e = fields.get(k)
        if not fn or not e:
            unchecked.append(k)
            continue
        for slot in ("value", "secondary"):
            if e.get(slot) in (None, ""):
                continue
            reason = fn(e[slot])
            row = {"key": k, "status": "invalid" if reason else "ok"}
            if slot == "secondary":
                row["slot"] = "secondary"
            if reason:
                row["reason"] = reason
            res.append(row)
    out({"person": pid, "invalid": sum(r["status"] == "invalid" for r in res), "results": res, "unchecked": unchecked})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *args, **kw):
        sp = sub.add_parser(name, help=kw.get("help"))
        sp.add_argument("root", help="store folder (contains people/ and field_registry.json)")
        for aa, akw in args:
            sp.add_argument(*aa, **akw)
        sp.set_defaults(fn=fn)

    add("init", cmd_init, help="create store")
    add("add-person", cmd_add_person, (["name"], {}), (["--id"], {}), (["--relation"], {"default": "self"}))
    add("people", cmd_people)
    add("get", cmd_get, (["person"], {}), (["--keys"], {"help": "comma list; default all stored"}), (["--date-format"], {"help": "iso|de|us|uk|strftime"}),
        (["--secondary"], {"action": "store_true", "help": "return secondary values where stored (else primary); only when the user explicitly asks for secondary data"}))
    add("set", cmd_set, (["person"], {}), (["pairs"], {"nargs": "+", "help": "key=value ..."}), (["--source"], {"help": "form/doc the value came from"}),
        (["--demote"], {"action": "store_true", "help": "new value becomes primary, the old primary is kept as secondary"}),
        (["--secondary"], {"action": "store_true", "help": "store value as the secondary alternative, primary unchanged"}))
    add("unset", cmd_unset, (["person"], {}), (["keys"], {"nargs": "+"}))
    add("register-key", cmd_register_key, (["key"], {}), (["--label"], {"required": True}), (["--type"], {"default": "string"}),
        (["--aliases"], {"nargs": "*"}), (["--sensitive"], {"action": "store_true"}), (["--options"], {"nargs": "*"}), (["--force"], {"action": "store_true"}))
    add("learn-alias", cmd_learn_alias, (["key"], {}), (["labels"], {"nargs": "+"}))
    add("match", cmd_match, (["labels"], {"help": "JSON file ('-' = stdin): list of strings or {id,label}"}), (["--person"], {}), (["--date-format"], {}))
    add("missing", cmd_missing, (["person"], {}), (["keys"], {"help": "comma list of keys"}))
    add("registry", cmd_registry, help="list canonical keys")
    add("check", cmd_check, (["person"], {}), (["--keys"], {"help": "comma list; default all stored"}),
        help="validate checksums/formats of stored values (values are not printed)")
    sys.stdout.reconfigure(encoding="utf-8")  # names with non-Latin-1 letters must not crash a piped cp1252 stdout
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
