#!/usr/bin/env python3
"""Scan public enterprise career-site APIs (Workday CXS, Oracle Recruiting Cloud, Amazon Jobs)
for blue-team roles in Pune / Mumbai / Bengaluru posted within the last N days.

These are the same unauthenticated JSON endpoints the companies' own careers pages call.
Writes output/jobs/raw_enterprise_jobs.json and output/jobs/workday_sites_found.json
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rolefilter import classify_title, match_city  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output", "jobs")
HDR = {"User-Agent": "Mozilla/5.0 (job-research script)", "Accept": "application/json",
       "Content-Type": "application/json"}
KEYWORDS = ["SOC", "security operations", "detection", "threat", "incident response",
            "cyber security", "SIEM", "forensic", "security analyst", "security engineer"]
TODAY = dt.date.today()


import threading
import time
import urllib.error

_lock = threading.Lock()
_last = [0.0]
RATE = 0.35  # min seconds between requests (global) to stay polite / avoid 429


def req(url, body=None, timeout=25, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    for k in range(tries):
        with _lock:
            wait = _last[0] + RATE - time.time()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        r = urllib.request.Request(url, data=data, headers=HDR, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and k < tries - 1:
                time.sleep(20 * (k + 1))
                continue
            raise


# --------------------------- Workday ---------------------------
WD_CANDIDATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workday_tenants.txt")
SITE_GUESSES = ["External", "Careers", "External_Career_Site", "{T}Careers", "{T}_Careers", "careers",
                "jobs", "ExternalCareerSite", "EXT"]
WD_NUMS = ["wd1", "wd3", "wd5", "wd12", "wd10", "wd103"]


def wd_try(host, tenant, site):
    """Fast probe: no global throttle, short timeout; 404 on wrong site comes back in <0.5s."""
    body = json.dumps({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}).encode()
    r = urllib.request.Request(f"https://{host}/wday/cxs/{tenant}/{site}/jobs", data=body, headers=HDR, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=6) as resp:
            return json.loads(resp.read().decode("utf-8", "replace")).get("total", 0) > 0
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(10)
        return False
    except Exception:
        return False


def wd_discover(line):
    """line: company|tenant|wdN(optional)|site(optional)"""
    parts = [p.strip() for p in line.split("|")]
    company, tenant = parts[0], parts[1]
    nums = [parts[2]] if len(parts) > 2 and parts[2] else WD_NUMS[:3]
    sites = [parts[3]] if len(parts) > 3 and parts[3] else \
        [s.replace("{T}", tenant) for s in SITE_GUESSES] + [s.replace("{T}", tenant.capitalize()) for s in SITE_GUESSES if "{T}" in s]
    for n in nums:
        host = f"{tenant}.{n}.myworkdayjobs.com"
        for s in dict.fromkeys(sites):
            if wd_try(host, tenant, s):
                return {"company": company, "host": host, "tenant": tenant, "site": s}
    return None


def posted_days(txt):
    t = (txt or "").lower()
    if "today" in t:
        return 0
    if "yesterday" in t:
        return 1
    m = re.search(r"(\d+)\+?\s*day", t)
    return int(m.group(1)) + (1 if "+" in t else 0) if m else None


def wd_scan(site, days):
    base = f"https://{site['host']}/wday/cxs/{site['tenant']}/{site['site']}"
    seen, hits = {}, []
    for kw in ["SOC", "security operations", "threat", "detection", "incident response", "cyber", "SIEM", "security analyst"]:
        for off in range(0, 60, 20):
            try:
                d = req(base + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": off, "searchText": kw})
            except Exception:
                break
            posts = d.get("jobPostings", [])
            for p in posts:
                seen.setdefault(p.get("externalPath"), p)
            if len(posts) < 20:
                break
    for path, p in seen.items():
        if not path or not classify_title(p.get("title", "")):
            continue
        pd = posted_days(p.get("postedOn"))
        if pd is not None and pd > days:
            continue
        lt = p.get("locationsText", "")
        if not (match_city(lt) or "location" in lt.lower() or "india" in lt.lower()):
            continue
        try:
            info = req(base + path).get("jobPostingInfo", {})
        except Exception:
            continue
        locs = "; ".join([info.get("location", "")] + (info.get("additionalLocations") or []))
        city = match_city(locs)
        start = info.get("startDate")
        if not city or not start:
            continue
        if (TODAY - dt.date.fromisoformat(start[:10])).days > days:
            continue
        hits.append({"company": site["company"], "platform": "workday", "title": info.get("title", p.get("title")),
                     "role_type": classify_title(info.get("title", p.get("title"))), "city": city,
                     "location_raw": locs, "posted": start[:10],
                     "url": info.get("externalUrl") or f"https://{site['host']}/en-US/{site['site']}{path}"})
    return hits


# --------------------------- Oracle Recruiting Cloud ---------------------------
ORACLE_SITES = [  # company, host, siteNumber
    ("JPMorgan Chase", "jpmc.fa.oraclecloud.com", "CX_1001"),
    ("Oracle", "eeho.fa.us2.oraclecloud.com", "CX_45001"),
]


def oracle_scan(company, host, site, days):
    hits = []
    for off in range(0, 4000, 25):
        q = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true"
             f"&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={site},"
             f"limit=25,offset={off},sortBy=POSTING_DATES_DESC")
        try:
            items = req(q).get("items", [])
        except Exception:
            break
        reqs = items[0].get("requisitionList", []) if items else []
        if not reqs:
            break
        oldest = None
        for j in reqs:
            pd = (j.get("PostedDate") or "")[:10]
            if not pd:
                continue
            age = (TODAY - dt.date.fromisoformat(pd)).days
            oldest = age if oldest is None else max(oldest, age)
            locs = "; ".join([j.get("PrimaryLocation", "")] +
                             [x.get("Name", "") for x in j.get("secondaryLocations") or []])
            c, role = match_city(locs), classify_title(j.get("Title", ""))
            if c and role and age <= days:
                hits.append({"company": company, "platform": "oracle", "title": j["Title"], "role_type": role,
                             "city": c, "location_raw": locs, "posted": pd,
                             "url": f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j['Id']}"})
        if oldest is not None and oldest > days:
            break
    return hits


# --------------------------- Amazon ---------------------------
def amazon_scan(days):
    hits, seen = [], set()
    for kw in KEYWORDS:
        for city in ["Bengaluru", "Pune", "Mumbai"]:
            for off in range(0, 300, 100):
                u = ("https://www.amazon.jobs/en/search.json?" + urllib.parse.urlencode(
                    {"base_query": kw, "normalized_country_code[]": "IND", "normalized_city_name[]": city,
                     "result_limit": 100, "offset": off, "sort": "recent"}))
                try:
                    jobs = req(u).get("jobs", [])
                except Exception:
                    break
                for j in jobs:
                    if j["id_icims"] in seen:
                        continue
                    seen.add(j["id_icims"])
                    c, role = match_city(j.get("normalized_location", "") + " " + j.get("location", "")), classify_title(j.get("title", ""))
                    try:
                        pd = dt.datetime.strptime(j.get("posted_date", ""), "%B %d, %Y").date()
                    except ValueError:
                        continue
                    if c and role and (TODAY - pd).days <= days:
                        hits.append({"company": "Amazon (incl. AWS)", "platform": "amazon.jobs", "title": j["title"],
                                     "role_type": role, "city": c, "location_raw": j.get("normalized_location"),
                                     "posted": pd.isoformat(), "url": "https://www.amazon.jobs" + j["job_path"]})
                if len(jobs) < 100:
                    break
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=15)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lines = [l.strip() for l in open(WD_CANDIDATES) if l.strip() and not l.startswith("#")]
    sites = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for i, s in enumerate(ex.map(wd_discover, lines), 1):
            if s:
                sites.append(s)
            if i % 20 == 0:
                print(f"  discovery {i}/{len(lines)} found={len(sites)}", flush=True)
    print(f"workday sites found: {len(sites)}/{len(lines)}", flush=True)
    json.dump(sites, open(os.path.join(OUT, "workday_sites_found.json"), "w"), indent=1)
    hits = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(wd_scan, s, a.days) for s in sites]
        futs += [ex.submit(oracle_scan, c, h, s, a.days) for c, h, s in ORACLE_SITES]
        futs.append(ex.submit(amazon_scan, a.days))
        for n, f in enumerate(cf.as_completed(futs), 1):
            if n % 10 == 0:
                print(f"  scanned {n}/{len(futs)} hits={len(hits)}", flush=True)
            try:
                hits += f.result()
            except Exception as e:  # keep going
                print("scan error:", e, flush=True)
    json.dump(hits, open(os.path.join(OUT, "raw_enterprise_jobs.json"), "w"), indent=1)
    print(f"hits={len(hits)} companies={len({h['company'] for h in hits})}")


if __name__ == "__main__":
    main()
