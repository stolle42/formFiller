# Filling PDF forms

Script: `scripts/pdf_form.py`. It needs `pypdf`, `pdfplumber` and `reportlab`; if a command reports a missing
dependency, install them with `pip install pypdf pdfplumber reportlab`.
Never overwrite the input: write the result next to the original as `<name>_filled.pdf`.

## Step 1: fillable or flat?
`python scripts/pdf_form.py inspect form.pdf`
- `fillable: true`: use the field list. Each field has `name`, `type`, `page`, `nearby_label`, `tooltip`, and
  `options`/`states` (choices, the checkbox "on" state, radio values).
- `fillable: false`: it's a flat or scanned PDF; go to "Flat PDFs" below.

Field names are often cryptic (`Text12`). Work out the meaning from `tooltip` first, then `nearby_label`, then by
rendering the page and looking. Feed the labels through `profile_store.py match` exactly as for web forms.

## Step 2a: fill fillable PDFs
Build `values.json`:
`{"field_name": "text", "checkbox_name": true, "radio_group": "<option state>", "dropdown": "<option text>"}`
then run `python scripts/pdf_form.py fill form.pdf values.json form_filled.pdf`.
Leave signature fields (`type: signature`) untouched. Check the result by rendering it (below) and looking at
every page. Some viewers ignore values that lack appearance streams, so rendering is the only reliable check.

## Step 2b: flat PDFs
1. `python scripts/pdf_form.py labels form.pdf` lists every text line with `x0, top, x1, bottom` (in points,
   measured from the top-left). Render the pages to see where the blank lines and boxes are.
2. Place each value just right of its label (x = label `x1` + 6, y = label `bottom` - 2), or on the blank line below
   it. Use font size 9-10.
3. `python scripts/pdf_form.py overlay form.pdf placements.json form_filled.pdf`
   (`placements.json` = `[{"page":1,"x":120,"y":300,"text":"Max","size":10}]`), render again, and check that nothing
   overlaps printed text. Adjust and repeat.

Checkboxes: place an "X" inside the box. Dates: use the format the form prints (dd.mm.yyyy on German forms).

## Rendering for visual checks
`python scripts/pdf_form.py render form_filled.pdf <out_dir> [--res 80] [--pages 1,3]` writes one PNG per page and
prints their paths. Open them to look. Raise `--res` to 150 to read small print.
