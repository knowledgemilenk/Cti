#!/usr/bin/env python3
"""Merge raw job hits into a company-level hiring report (CSV + XLSX)."""
import csv
import glob
import json
import os
import re
import urllib.parse
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output", "jobs")


def master():
    m = {}
    for p in glob.glob(os.path.join(ROOT, "data", "*.txt")):
        for line in open(p, encoding="utf-8"):
            f = line.strip().split("|")
            if len(f) == 8 and not line.startswith("#"):
                m[f[0]] = {"category": f[1], "hq": f[2], "revenue": f"{f[4]} ({f[5]})"}
    return m


def board_url(platform, url):
    if not url:
        return ""
    u = urllib.parse.urlparse(url)
    if platform == "greenhouse":
        return f"{u.scheme}://{u.netloc}/" + u.path.strip("/").split("/")[0]
    if platform == "lever":
        return f"https://jobs.lever.co/{u.path.strip('/').split('/')[0]}"
    if platform == "workday":
        parts = u.path.strip("/").split("/")
        return f"{u.scheme}://{u.netloc}/" + "/".join(parts[:2]) if len(parts) >= 2 else url
    if platform == "oracle":
        return url.split("/job/")[0]
    if platform == "amazon.jobs":
        return "https://www.amazon.jobs/en/search?country=IND"
    if platform == "smartrecruiters":
        return f"https://jobs.smartrecruiters.com/{u.path.strip('/').split('/')[0]}"
    if platform == "ashby":
        return f"https://jobs.ashbyhq.com/{u.path.strip('/').split('/')[0]}"
    return f"{u.scheme}://{u.netloc}"


def li_people(company):
    q = f'"{re.sub(r"[(].*?[)]", "", company).strip()}" (recruiter OR "talent acquisition") (security OR cyber)'
    return "https://www.linkedin.com/search/results/people/?keywords=" + urllib.parse.quote(q)


def li_jobs(company, cities):
    q = f'{re.sub(r"[(].*?[)]", "", company).strip()} security'
    loc = cities.split(",")[0].strip() + ", India" if cities else "India"
    return ("https://www.linkedin.com/jobs/search/?f_TPR=r1296000&keywords=" + urllib.parse.quote(q)
            + "&location=" + urllib.parse.quote(loc))


def main():
    jobs = []
    for p in ("raw_ats_jobs.json", "raw_enterprise_jobs.json"):
        fp = os.path.join(OUT, p)
        if os.path.exists(fp):
            jobs += json.load(open(fp))
    seen, uniq = set(), []
    for j in jobs:
        k = (j["company"], j["title"].strip().lower(), j["city"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(j)
    uniq.sort(key=lambda j: (j["company"].lower(), j["posted"]), reverse=False)
    meta = master()
    by = defaultdict(list)
    for j in uniq:
        by[j["company"]].append(j)

    comp_rows = []
    for c, js in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
        cities = sorted({x.strip() for j in js for x in j["city"].split(",")})
        md = meta.get(c, {})
        comp_rows.append({
            "Company": c, "Category": md.get("category", ""), "Global HQ": md.get("hq", ""),
            "Annual revenue": md.get("revenue", ""),
            "Cities hiring (Pune/Mumbai/Bengaluru)": ", ".join(cities),
            "Open blue-team roles (posted last 15 days)": len(js),
            "Role types": ", ".join(sorted({j["role_type"] for j in js})),
            "Latest posting date": max(j["posted"] for j in js),
            "Sample roles": " | ".join(j["title"] for j in js[:5]),
            "Careers / job board (apply here)": board_url(js[0]["platform"], js[0]["url"]),
            "Find their recruiters (LinkedIn people search)": li_people(c),
            "Verify on LinkedIn Jobs (last 15 days)": li_jobs(c, ", ".join(cities)),
        })
    job_rows = [{"Company": j["company"], "Job title": j["title"], "Role type": j["role_type"],
                 "City": j["city"], "Location (as posted)": j["location_raw"], "Posted on": j["posted"],
                 "Source": j["platform"], "Job link": j["url"]} for j in uniq]

    os.makedirs(OUT, exist_ok=True)
    for name, rows in (("hiring_companies.csv", comp_rows), ("hiring_jobs.csv", job_rows)):
        if rows:
            with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)

    wb = Workbook()
    fill, font = PatternFill("solid", fgColor="1F3864"), Font(bold=True, color="FFFFFF")
    for title, rows, widths in (("Companies hiring", comp_rows, [34, 26, 26, 26, 24, 12, 40, 12, 70, 45, 45, 45]),
                                ("All postings", job_rows, [30, 60, 30, 16, 40, 12, 14, 70])):
        ws = wb.active if title == "Companies hiring" else wb.create_sheet(title)
        ws.title = title
        if not rows:
            continue
        ws.append(list(rows[0]))
        for c in ws[1]:
            c.fill, c.font = fill, font
        for r in rows:
            ws.append(list(r.values()))
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
    wb.save(os.path.join(OUT, "india_blue_team_hiring_last15days.xlsx"))
    print(f"companies={len(comp_rows)} postings={len(job_rows)}")
    for r in comp_rows:
        print(f"  {r['Open blue-team roles (posted last 15 days)']:3d}  {r['Company']}  [{r['Cities hiring (Pune/Mumbai/Bengaluru)']}]")


if __name__ == "__main__":
    main()
