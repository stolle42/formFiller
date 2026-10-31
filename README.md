# Form filler skills for Claude

Two skills that let Claude fill out forms with your personal data, so you never type the same name, address or
IBAN twice:

- **form-filler** fills web forms (directly in the page), e-sign widgets such as Adobe Acrobat Sign, and fillable or
  flat PDFs. It takes values from a small data store on your computer. Whenever a form asks for something new, it
  asks you and saves the answer, so the next form needs fewer questions.
- **form-filler-setup** creates that data store in a folder of your choice and records your first profile.

Several people per store are supported (you, a partner, children, parents), each in their own file.

## What it will and won't do

It **will**:
- fill every field it already knows, and ask for the rest one question at a time;
- remember new answers and learn new field labels, in any language;
- confirm sensitive values (IBAN, tax ID, insurance and passport numbers) once per form, shown masked;
- check IBANs, BICs, German tax IDs, social security and health insurance numbers for typos;
- tell you at the end what it filled, what it stored and what's still open.

It **never** signs, submits, sends, saves or uploads anything, never logs in or types passwords, and never clicks
consent or "I agree" buttons without your yes. You review the filled form and submit it yourself.

## Requirements

- A Claude session that can read and write a folder on your computer, for example **Cowork in Claude Desktop**
  (give it access to your store folder) or **Claude Code** (open the store folder). A plain chat without folder
  access can't keep your data between conversations.
- Python 3 (Claude runs the bundled scripts).
- For PDF forms: `pip install pypdf pdfplumber reportlab`. Claude can install these when needed.
- For web forms: a browser tool in your Claude setup, such as Claude in Chrome or the built-in browser. The skill
  works with whatever browser tool is available and doesn't set one up.

## Install

**Claude Desktop / claude.ai**
1. Download `form-filler.zip` and `form-filler-setup.zip` from the
   [Releases](../../releases) page. Don't unzip them.
2. Open Settings → Capabilities, make sure code execution is enabled, then upload both ZIPs under Skills.
   Menu names can differ slightly between app versions.

**Claude Code**
Copy `skills/form-filler` and `skills/form-filler-setup` into `~/.claude/skills/`.

## Getting started

1. Pick a folder for your data (see the two options below) and open it in Cowork or Claude Code.
2. Say **"set up form filler"**. Claude explains what will be stored, creates the store and asks for a few basics
   (you can skip them).
3. To fill a form, open the same folder and say **"fill out this form"** with a link or a PDF.

If Claude says there's no store in the folder, you're probably in a different folder than the one you set up.

## Where to keep your data

You don't need to clone this repository to use the skills; the two ZIPs are enough. Your data goes in a folder of
your choice, in one of two ways:

- **A separate folder (recommended)**, e.g. `Documents/forms`. Code and personal data stay apart, and there's no
  git repository anywhere near your data.
- **Inside your clone of this repository.** If you cloned it anyway (to install the skills in Claude Code, or to
  get updates with `git pull`), you can use the clone as your data folder and keep everything in one place. The
  repository's `.gitignore` keeps `people/` and `field_registry.json` out of git, so pulling, committing and
  pushing never touch them. Don't force-add them (`git add -f`), and check `git status` before every commit.

Either way:
- Everything is stored as plain JSON files: `people/<name>.json` and `field_registry.json`. You can read, edit,
  back up or delete them any time.
- If the folder is synced to a cloud (OneDrive, Dropbox, iCloud, Google Drive), your data is synced too.
- While a form is being filled, Claude reads the values it needs, so they are part of that conversation and are
  processed like anything else you send to Claude.

## Limits

- The checksum checks cover German formats (Steuer-ID, Rentenversicherungsnummer, KVNR) plus IBAN/BIC, email, phone
  numbers and dates. Other countries' numbers are stored and filled, just not checked.
- Signature fields, CAPTCHAs and file uploads are left for you.
- Web forms are filled in the live page and never replaced by a PDF, because the website stores what's entered
  there.

## Repository layout

```
skills/form-filler/         SKILL.md, references/ (web, PDF, data model), scripts/, assets/
skills/form-filler-setup/   SKILL.md, scripts/, assets/
build_zips.py               builds dist/<skill>.zip for upload
```

`form-filler-setup` carries a copy of `scripts/profile_store.py` and `assets/field_registry.default.json` from
`form-filler`, because uploaded skills can't see each other's files. Edit the `form-filler` versions; `python
build_zips.py` copies them over, checks both skills against the upload rules and writes the ZIPs to `dist/`. To
publish a release, attach the two ZIPs from `dist/`.

## License

See [LICENSE](LICENSE).
