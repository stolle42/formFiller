---
name: form-filler-setup
description: "Set up the personal data store that the form-filler skill fills forms from, in the current folder, and record the first profile(s). Use when the user is starting fresh with form filling, wants to create a new data or profile store, says \"set up form filler\", \"start a new store\", \"Formulardaten einrichten\", or when form-filler reported that this folder has no store. Also use to create a separate store for another household or client in its own folder."
---

# Form-filler setup

Creates the store the `form-filler` skill reads: a `field_registry.json` plus a `people/` folder. form-filler looks
for these in the folder the user is working in: the session's working directory or, in apps where the user grants
folder access, the folder they granted. So the store belongs in the folder the user will open whenever they fill
forms. Usually that's the folder they're in now. If you can't reach the user's files at all, ask for access to a
folder if your environment offers that; otherwise explain that setup needs a session with access to one.

Store commands: `python <skill-dir>/scripts/profile_store.py <command> ...`, where `<skill-dir>` is this skill's
base directory (shortened to `profile_store.py` below). It's the same store tool form-filler uses; this skill
carries its own copy so it works wherever it's installed.

## 1. Check the folder

- **Already a store** (`field_registry.json` and `people/` exist)? Say so, show who's in it
  (`profile_store.py people "<folder>"`), and stop. Never re-initialise or overwrite an existing store: its
  registry holds aliases learned from earlier forms.
- **Looks like something else** (source code, an unrelated project, the home or Desktop folder)? Ask whether this
  really is the folder for their personal data before writing anything. They may have opened the wrong project.
- **Tell the user what will live here.** Names, addresses and birth dates to start with, later IBAN, tax and
  insurance numbers as forms ask for them, all as plain JSON files on their disk. If the folder is synced to a cloud
  (OneDrive, Dropbox, iCloud, Google Drive) or is a git repository, point that out, because the data goes wherever
  the folder goes. For git, check that `.gitignore` excludes both `people/` and `field_registry.json` (a clone of
  the form-filler repository already does, so it's fine as a store); if not, offer to add them. Then wait for
  their go-ahead.

If the user wants the store somewhere else, use that folder, and remind them to open it when filling forms.

## 2. Create the store

`python profile_store.py init "<absolute folder path>"`

This copies the default registry and creates `people/`. The registry holds about 40 common keys: name, birth data,
address, contact, tax, social security, health insurance, bank, passport. form-filler adds new keys and aliases as
forms ask for them. `"existed": true` in the output means a registry was already there and was left alone.

## 3. Record the first person

Ask who the main person is (normally the user), then:
`profile_store.py add-person STORE "<Full name>" --relation self`

Offer to fill in the basics now, so the first form needs fewer questions. The user picks one way:
- **From documents they already have**, such as a filled-in form, CV or onboarding sheet. They give you the path
  or drop it in the folder. Read it, list what you found (sensitive values masked, e.g. `DE39 **** 8954`), and
  store only what they confirm.
- **A short questionnaire, one question per message:** first and last name exactly as in the ID, birth date and
  place, nationality, street and house number, postal code and city, country, mobile phone with country code,
  email. Say up front how many questions there are. Bank, tax and insurance numbers can wait until a form needs
  them, and say so: nobody has to hand over their IBAN on day one.

Store each answer before asking the next: `profile_store.py set STORE <person> key=value --source "setup"`, with
dates as `YYYY-MM-DD` and names exactly as given. `profile_store.py registry STORE` lists the keys. At the end run
`profile_store.py check STORE <person>` and ask about anything it flags.

Skipping this step is fine, because form-filler asks for missing values when a form needs them.

## 4. More people (optional)

Ask whether they also fill forms for others: spouse, children, parents. For each one:
`profile_store.py add-person STORE "<name>" --relation spouse|child|parent|other`, then optionally the same
questionnaire. One profile per person, children included, keeps each section of a family form simple.

## 5. Finish

Tell the user:
- where the store is, and who's in it with how many values each;
- how to use it: open this folder as the working folder, then ask to fill a form (paste a link or give a PDF);
- that the JSON files can be read and edited by hand, and backed up by copying the folder.

Nothing in this skill fills, submits or sends anything; it only creates files in the chosen folder.
