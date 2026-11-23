#!/usr/bin/env python3
"""Merge raw job hits into a company-level hiring report (CSV + XLSX)."""
import csv
import glob
import json
import os
import re
import urllib.parse
from collections import defaultdict

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rolefilter import classify_title  # noqa: E402
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output", "jobs")


CITY = {"B": "Bengaluru", "P": "Pune", "M": "Mumbai"}


def master():
    m = {}
    for p in glob.glob(os.path.join(ROOT, "data", "*.txt")):
        for line in open(p, encoding="utf-8"):
            f = line.strip().split("|")
            if len(f) == 8 and not line.startswith("#") and f[3] not in ("", "-") and not f[0].endswith("?"):
                codes = [c.strip() for c in f[3].split(",")]
                m[f[0]] = {"category": f[1], "hq": f[2], "revenue": f"{f[4]} ({f[5]})",
                           "target_cities": ", ".join(CITY[c] for c in codes if c in CITY)}
    return m


def load_json(name):
    fp = os.path.join(OUT, name)
    return json.load(open(fp)) if os.path.exists(fp) else []


def excluded_rows(meta, hiring):
    """Every company from the master list that is not in the hiring list, with the reason."""
    boards = {}
    for b in load_json("ats_boards_found.json"):
        boards.setdefault(b["company"], b)
    wd = {}
    for sites_file, raw_file in (("workday_sites_found.json", "raw_enterprise_jobs.json"),
                                 ("workday_sites_run1.json", "raw_enterprise_jobs_run2.json")):
        sf, rf = os.path.join(OUT, sites_file), os.path.join(OUT, raw_file)
        if os.path.exists(sf) and os.path.exists(rf) and os.path.getmtime(rf) >= os.path.getmtime(sf):
            wd.update({x["company"]: x for x in load_json(sites_file)})
    enterprise_done = os.path.exists(os.path.join(OUT, "raw_enterprise_jobs_run2.json"))
    special = {"JPMorgan Chase": "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001",
               "Oracle": "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_45001",
               "Amazon (incl. AWS)": "https://www.amazon.jobs/en/search?country=IND"}
    rows = []
    for c, md in sorted(meta.items(), key=lambda kv: kv[0].lower()):
        if c in hiring:
            continue
        b, w = boards.get(c), wd.get(c)
        if not md["target_cities"]:
            reason = "No Pune/Mumbai/Bengaluru office in the master dataset (Hyderabad/other cities only)"
            status, board = "Out of city scope", ""
        elif b:
            board = board_url(b["platform"], b.get("board_url") or "")
            if b.get("blue_team_roles_target_cities"):
                status = "Checked - only older postings"
                reason = (f"{b['blue_team_roles_target_cities']} blue-team role(s) in Pune/Mumbai/Bengaluru on its "
                          f"{b['platform']} board, but none posted in the last 15 days "
                          f"(latest: {b.get('latest_target_city_post') or 'n/a'})")
            elif b.get("blue_team_roles_any_city"):
                status = "Checked - roles in other cities only"
                reason = (f"{b['blue_team_roles_any_city']} blue-team role(s) open on its {b['platform']} board, "
                          f"but none located in Pune/Mumbai/Bengaluru")
            else:
                status = "Checked - no blue-team roles"
                reason = f"{b['total_jobs']} open jobs on its {b['platform']} board; none are SOC/detection/threat/IR roles"
        elif w or (c in special and enterprise_done):
            board = special.get(c) or f"https://{w['host']}/{w['site']}"
            if c in special:
                status = "Checked - unconfirmed"
                reason = ("Career-site API scanned with 0 matches, but the connection was reset several times "
                          "during the scan - treat as unverified and check via the links")
            else:
                status = "Checked - no recent match"
                reason = "Career-site API checked; no SOC/detection/threat/IR role in Pune/Mumbai/Bengaluru posted in the last 15 days"
        else:
            board = ""
            status = "Not verifiable automatically"
            reason = ("Careers site has no public job API reachable from here (custom site, Phenom, SuccessFactors, "
                      "Taleo, iCIMS, Eightfold, etc.) - hiring status unknown; verify via the LinkedIn Jobs link")
        rows.append({
            "Company": c, "Category": md["category"], "Global HQ": md["hq"], "Annual revenue": md["revenue"],
            "Offices in Pune/Mumbai/Bengaluru (dataset)": md["target_cities"],
            "Exclusion status": status, "Reason excluded": reason,
            "Careers / job board": board,
            "Find their recruiters (LinkedIn people search)": li_people(c),
            "Verify on LinkedIn Jobs (last 15 days)": li_jobs(c, md["target_cities"]),
        })
    return rows


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
    for p in ("raw_ats_jobs.json", "raw_enterprise_jobs.json", "raw_enterprise_jobs_run2.json"):
        fp = os.path.join(OUT, p)
        if os.path.exists(fp):
            jobs += json.load(open(fp))
    seen, uniq = set(), []
    for j in jobs:
        j["role_type"] = classify_title(j["title"])
        if not j["role_type"]:
            continue
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

    excl = excluded_rows(meta, set(by))
    os.makedirs(OUT, exist_ok=True)
    for name, rows in (("hiring_companies.csv", comp_rows), ("hiring_jobs.csv", job_rows),
                       ("excluded_companies.csv", excl)):
        if rows:
            with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)

    wb = Workbook()
    fill, font = PatternFill("solid", fgColor="1F3864"), Font(bold=True, color="FFFFFF")
    for title, rows, widths in (("Companies hiring", comp_rows, [34, 26, 26, 26, 24, 12, 40, 12, 70, 45, 45, 45]),
                                ("All postings", job_rows, [30, 60, 30, 16, 40, 12, 14, 70]),
                                ("Excluded companies", excl, [34, 26, 26, 26, 26, 28, 80, 45, 45, 45])):
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
    from collections import Counter
    print(f"companies={len(comp_rows)} postings={len(job_rows)} excluded={len(excl)}")
    for k, v in Counter(r["Exclusion status"] for r in excl).most_common():
        print(f"  excluded: {v:4d}  {k}")
    for r in comp_rows:
        print(f"  {r['Open blue-team roles (posted last 15 days)']:3d}  {r['Company']}  [{r['Cities hiring (Pune/Mumbai/Bengaluru)']}]")


if __name__ == "__main__":
    main()
