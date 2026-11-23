#!/usr/bin/env python3
"""Build the India blue-team employer dataset from data/*.txt into CSV + XLSX.

Input rows (pipe-delimited):
Company|Category|Global HQ|India location codes|Annual revenue|Period|Basis|Blue-team functions
"""
import csv
import glob
import os
import re
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOCUS = ["B", "P", "M", "H", "R"]
CITY = {
    "B": "Bengaluru", "P": "Pune", "M": "Mumbai/Navi Mumbai", "H": "Hyderabad",
    "R": "Remote/Hybrid", "C": "Chennai", "G": "Gurugram", "N": "Noida",
    "D": "Delhi", "K": "Kolkata", "A": "Ahmedabad", "V": "Vadodara",
    "T": "Thiruvananthapuram", "O": "Other",
}
HEADERS = [
    "S.No", "Company", "Category", "Global HQ", "India locations (all)",
    "Bengaluru", "Pune", "Mumbai", "Hyderabad", "Remote/Hybrid",
    "Annual revenue", "Revenue period", "Revenue basis",
    "Blue-team functions / teams in India",
]


def norm(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", name.lower()))


def load():
    rows, seen, dups = [], {}, []
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*.txt"))):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            f = [x.strip() for x in line.split("|")]
            if len(f) != 8 or f[3] in ("", "-") or f[0].endswith("?"):
                continue
            key = norm(f[0])
            if key in seen:
                dups.append(f[0])
                continue
            seen[key] = True
            codes = [c.strip() for c in f[3].split(",") if c.strip()]
            bad = [c for c in codes if c not in CITY]
            if bad:
                raise SystemExit(f"Unknown city code {bad} in {path}: {f[0]}")
            rows.append({
                "Company": f[0], "Category": f[1], "Global HQ": f[2],
                "codes": codes,
                "India locations (all)": ", ".join(CITY[c] for c in codes),
                "Annual revenue": f[4], "Revenue period": f[5],
                "Revenue basis": f[6], "Blue-team functions / teams in India": f[7],
                "source_file": os.path.basename(path),
            })
    return rows, dups


def main():
    rows, dups = load()
    focus = [r for r in rows if any(c in FOCUS for c in r["codes"])]
    other = [r for r in rows if not any(c in FOCUS for c in r["codes"])]
    focus.sort(key=lambda r: (r["Category"], r["Company"].lower()))
    other.sort(key=lambda r: r["Company"].lower())

    def record(i, r):
        d = {"S.No": i, **{k: r[k] for k in HEADERS if k in r}}
        for code, col in zip(FOCUS, ["Bengaluru", "Pune", "Mumbai", "Hyderabad", "Remote/Hybrid"]):
            d[col] = "Yes" if code in r["codes"] else ""
        return d

    focus_recs = [record(i, r) for i, r in enumerate(focus, 1)]
    other_recs = [record(i, r) for i, r in enumerate(other, 1)]

    out = os.path.join(ROOT, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "india_blue_team_companies.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(focus_recs)

    wb = Workbook()
    hdr_fill = PatternFill("solid", fgColor="1F3864")
    hdr_font = Font(bold=True, color="FFFFFF")
    widths = [6, 42, 34, 32, 44, 10, 8, 9, 10, 13, 34, 14, 11, 70]

    def sheet(ws, recs):
        ws.append(HEADERS)
        for c in ws[1]:
            c.fill, c.font = hdr_fill, hdr_font
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for r in recs:
            ws.append([r[h] for h in HEADERS])
        for i, wdt in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = wdt
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions

    ws = wb.active
    ws.title = "Companies (focus cities)"
    sheet(ws, focus_recs)
    sheet(wb.create_sheet("Other Indian cities"), other_recs)

    s = wb.create_sheet("Summary")
    s.append(["Metric", "Count"])
    s.append(["Companies with cyber teams in Bengaluru/Pune/Mumbai/Hyderabad/Remote", len(focus_recs)])
    s.append(["Additional companies (other Indian cities only)", len(other_recs)])
    s.append([])
    s.append(["By city (focus list)", ""])
    for code, col in zip(FOCUS, ["Bengaluru", "Pune", "Mumbai", "Hyderabad", "Remote/Hybrid"]):
        s.append([col, sum(1 for r in focus if code in r["codes"])])
    s.append([])
    s.append(["By category (focus list)", ""])
    for cat, n in Counter(r["Category"] for r in focus).most_common():
        s.append([cat, n])
    s.append([])
    s.append(["By revenue basis (focus list)", ""])
    for b, n in Counter(r["Revenue basis"] for r in focus).most_common():
        s.append([b, n])
    for c in s[1]:
        c.fill, c.font = hdr_fill, hdr_font
    s.column_dimensions["A"].width = 70
    s.column_dimensions["B"].width = 10

    wb.save(os.path.join(out, "india_blue_team_companies.xlsx"))
    print(f"focus={len(focus_recs)} other={len(other_recs)} duplicates_skipped={dups}")
    for k, v in Counter(r["Category"] for r in focus).most_common():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()
