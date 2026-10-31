# Data model

```
STORE/
  field_registry.json     canonical keys + aliases (copied from assets/field_registry.default.json on init, then extended)
  people/
    max-mustermann.json   one file per person
    erika-mustermann.json
```

## Person file
```json
{
  "id": "max-mustermann",
  "display_name": "Max Mustermann",
  "relation": "self",              // self | spouse | child | parent | other
  "created": "2026-10-07",
  "fields": {
    "person.first_name": {"value": "Max", "updated": "2026-10-07", "source": "HR onboarding form"},
    "birth.date":        {"value": "1990-01-01", "updated": "...", "source": "..."},
    "bank.iban":         {"value": "DE89...", "updated": "...", "source": "...", "secondary": "DE12..."}
  }
}
```
A field may carry `"secondary": "<alternative value>"` (e.g. the previous phone number). The primary value is the
default. The secondary is used only on explicit request (`get --secondary`), and is written with `set --demote` or
`set --secondary`.

Why one file per person: easy to back up, delete or hand over; no cross-contamination; each write is atomic
per person. Why flat dotted keys: stable and greppable, and forms rarely nest deeper than group.field.

## Registry entry
```json
"bank.iban": {"label": "IBAN", "type": "iban", "sensitive": true, "aliases": ["iban", "international bank account number"]}
```
- `type`: string | date | enum | bool | phone | email | iban
- `aliases`: normalized printed labels (lowercase, no accents or punctuation; ß→ss). Matching scores an exact alias
  1.0, an alias contained in the label as whole words about 0.9, and token overlap lower.
- `derived`: a template built from other keys and never stored (`{address.postal_code} {address.city}`, `@today`).
- `sensitive`: confirm with the user before entering.

## Value conventions
Dates in ISO (`YYYY-MM-DD`); booleans true/false; phone numbers with country code; IBAN without spaces; names exactly
as in the ID document. Format values at fill time; never store formatted copies.

## Commands (`python scripts/profile_store.py --help`)
`init`, `add-person`, `people`, `get`, `set`, `unset`, `match`, `missing`, `register-key`, `learn-alias`,
`registry`, `check`.
