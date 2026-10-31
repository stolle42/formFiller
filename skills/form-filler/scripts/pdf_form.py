#!/usr/bin/env python3
"""PDF form helper: inspect fillable fields, fill them, or overlay text on flat PDFs.

  inspect  in.pdf                      -> JSON list of AcroForm fields (+ nearest label text); empty list => flat PDF
  labels   in.pdf                      -> JSON list of text lines with positions (for flat PDFs)
  fill     in.pdf values.json out.pdf  -> values.json = {"field_name": "text" | true/false (checkbox) | "radio_value"}
  overlay  in.pdf placements.json out.pdf
           placements.json = [{"page":1,"x":120,"y":300,"text":"Max","size":10}]
           x/y are in points measured from the TOP-LEFT of the page (same system `labels` reports).
  render   in.pdf out_dir [--res 80] [--pages 1,3]
           -> one PNG per page in out_dir, for visual checks

Requires: pypdf, pdfplumber, reportlab.
"""
import io, json, sys
from pathlib import Path


def die(msg, code=2):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(code)


def _field_type(f):
    ft = str(f.get("/FT", ""))
    ff = int(f.get("/Ff", 0) or 0)
    if ft == "/Btn":
        if ff & (1 << 16):
            return "button"
        return "radio_group" if ff & (1 << 15) else "checkbox"
    if ft == "/Tx":
        return "text"
    if ft == "/Ch":
        return "choice"
    if ft == "/Sig":
        return "signature"
    return ft or "unknown"


def cmd_inspect(pdf):
    import pdfplumber
    from pypdf import PdfReader
    r = PdfReader(pdf)
    words_by_page = {}
    with pdfplumber.open(pdf) as pl:
        for i, pg in enumerate(pl.pages):
            words_by_page[i] = (pg.height, pg.extract_words())
    fields = []
    for pno, page in enumerate(r.pages):
        for annot in page.get("/Annots", []) or []:
            a = annot.get_object()
            if a.get("/Subtype") != "/Widget":
                continue
            parent = a.get("/Parent")
            src = a if "/FT" in a else (parent.get_object() if parent else a)
            # fully-qualified name
            names, node = [], a
            while node is not None:
                if "/T" in node:
                    names.append(str(node["/T"]))
                node = node["/Parent"].get_object() if "/Parent" in node else None
            name = ".".join(reversed(names))
            t = _field_type(src)
            x0, y0, x1, y1 = [float(v) for v in a["/Rect"]]
            height, words = words_by_page[pno]
            top = height - y1
            # nearest label: words ending left of the field on the same line, else the line just above
            same = [w for w in words if w["x1"] <= x0 + 2 and abs(((w["top"] + w["bottom"]) / 2) - (top + (y1 - y0) / 2)) < 6]
            label = " ".join(w["text"] for w in sorted(same, key=lambda w: w["x0"])[-6:])
            if not label:
                above = [w for w in words if w["bottom"] <= top + 2 and top - w["bottom"] < 18 and w["x0"] < x1 and w["x1"] > x0 - 40]
                label = " ".join(w["text"] for w in sorted(above, key=lambda w: (w["top"], w["x0"]))[-8:])
            entry = {"name": name, "type": t, "page": pno + 1, "rect_top_left": [round(x0, 1), round(top, 1), round(x1, 1), round(height - y0, 1)],
                     "tooltip": str(src.get("/TU", "")), "nearby_label": label, "value": str(src.get("/V", "")) if "/V" in src else ""}
            if t == "choice":
                entry["options"] = [str(o[1] if isinstance(o, list) else o) for o in src.get("/Opt", [])]
            if t in ("checkbox", "radio_group"):
                ap = a.get("/AP", {}).get("/N", {})
                entry["states"] = [k for k in ap.keys() if k != "/Off"] if hasattr(ap, "keys") else []
            if t == "radio_group":
                # merge widgets of same group
                ex = next((f for f in fields if f["name"] == name), None)
                if ex:
                    ex.setdefault("options", []).extend(entry["states"])
                    continue
                entry["options"] = list(entry["states"])
            fields.append(entry)
    print(json.dumps({"fillable": bool(fields), "fields": fields}, ensure_ascii=False, indent=2))


def cmd_labels(pdf):
    import pdfplumber
    out = []
    with pdfplumber.open(pdf) as pl:
        for i, pg in enumerate(pl.pages):
            lines = pg.extract_text_lines()
            for ln in lines:
                out.append({"page": i + 1, "text": ln["text"], "x0": round(ln["x0"], 1), "top": round(ln["top"], 1), "x1": round(ln["x1"], 1), "bottom": round(ln["bottom"], 1)})
            # underscores/lines and rectangles help locate blanks
    print(json.dumps({"page_sizes": [], "lines": out}, ensure_ascii=False, indent=2))


def cmd_fill(pdf, values_path, out_path):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, BooleanObject
    values = json.loads(Path(values_path).read_text(encoding="utf-8"))
    r = PdfReader(pdf)
    w = PdfWriter()
    w.append(r)
    skipped = []
    text_vals = {k: v for k, v in values.items() if not isinstance(v, bool)}
    bool_vals = {k: v for k, v in values.items() if isinstance(v, bool)}
    for page in w.pages:
        if text_vals:
            try:
                w.update_page_form_field_values(page, text_vals, auto_regenerate=False)
            except Exception as e:  # keep going; report
                skipped.append(str(e))
    # checkboxes: need the widget's 'on' state name
    for page in w.pages:
        for annot in page.get("/Annots", []) or []:
            a = annot.get_object()
            if a.get("/Subtype") != "/Widget" or "/T" not in a:
                continue
            nm = str(a["/T"])
            if nm in bool_vals:
                ap = a.get("/AP", {}).get("/N", {})
                on = next((k for k in ap.keys() if k != "/Off"), "/Yes") if hasattr(ap, "keys") else "/Yes"
                state = NameObject(on if bool_vals[nm] else "/Off")
                a[NameObject("/V")] = state
                a[NameObject("/AS")] = state
    if "/AcroForm" in w._root_object:  # ask viewers to render values
        w._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
    with open(out_path, "wb") as f:
        w.write(f)
    print(json.dumps({"ok": True, "out": out_path, "skipped": skipped}))


def cmd_overlay(pdf, placements_path, out_path):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    items = json.loads(Path(placements_path).read_text(encoding="utf-8"))
    r = PdfReader(pdf)
    w = PdfWriter()
    for pno, page in enumerate(r.pages, start=1):
        mine = [i for i in items if i["page"] == pno]
        if mine:
            W, H = float(page.mediabox.width), float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(W, H))
            for it in mine:
                c.setFont("Helvetica", it.get("size", 10))
                c.drawString(it["x"], H - it["y"], str(it["text"]))  # convert top-left -> PDF bottom-left
            c.save()
            buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
        w.add_page(page)
    with open(out_path, "wb") as f:
        w.write(f)
    print(json.dumps({"ok": True, "out": out_path, "placed": len(items)}))


def cmd_render(pdf, out_dir, opts):
    import pdfplumber
    res = int(opts.get("--res", 80))
    pages = {int(p) for p in opts["--pages"].split(",")} if "--pages" in opts else None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    with pdfplumber.open(pdf) as pl:
        for pno, pg in enumerate(pl.pages, start=1):
            if pages and pno not in pages:
                continue
            p = out / f"{Path(pdf).stem}_p{pno}.png"
            pg.to_image(resolution=res).save(str(p))
            paths.append(str(p))
    print(json.dumps({"ok": True, "pages": paths}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # German labels must not crash a piped cp1252 stdout
    a = sys.argv[1:]
    try:
        if len(a) >= 2 and a[0] == "inspect":
            cmd_inspect(a[1])
        elif len(a) >= 2 and a[0] == "labels":
            cmd_labels(a[1])
        elif len(a) == 4 and a[0] == "fill":
            cmd_fill(*a[1:])
        elif len(a) == 4 and a[0] == "overlay":
            cmd_overlay(*a[1:])
        elif len(a) >= 3 and a[0] == "render" and len(a[3:]) % 2 == 0:
            cmd_render(a[1], a[2], dict(zip(a[3::2], a[4::2])))
        else:
            print(__doc__)
            sys.exit(1)
    except ImportError as e:
        die(f"missing dependency: {e}. Install with: pip install pypdf pdfplumber reportlab")
