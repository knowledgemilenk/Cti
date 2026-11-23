#!/usr/bin/env python3
"""Scan public ATS job-board APIs (Greenhouse, Lever, Ashby, SmartRecruiters) for
blue-team roles in Pune / Mumbai / Bengaluru posted within the last N days.

Only official, unauthenticated job-board APIs that companies publish for their own
careers pages are used. No LinkedIn / Naukri scraping.

Usage: python3 scripts/jobs/ats_scan.py [--days 15]
Writes: output/jobs/raw_ats_jobs.json, output/jobs/ats_boards_found.json
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import glob
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rolefilter import classify_title, match_city  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output", "jobs")
UA = {"User-Agent": "Mozilla/5.0 (job-research script)", "Accept": "application/json"}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def slugs(name):
    base = re.sub(r"\(.*?\)", "", name).lower()
    base = re.sub(r"&", "and", base)
    words = re.findall(r"[a-z0-9]+", base)
    stop = {"inc", "ltd", "limited", "india", "the", "group", "technologies", "technology",
            "corporation", "corp", "co", "plc", "llc", "pvt", "private", "software", "global",
            "solutions", "services", "labs", "systems", "networks"}
    core = [w for w in words if w not in stop] or words
    out = ["".join(words), "".join(core), "-".join(core), core[0] if core else ""]
    return [s for s in dict.fromkeys(out) if s and len(s) > 1]


def companies():
    names = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "*.txt"))):
        for line in open(p, encoding="utf-8"):
            f = line.strip().split("|")
            if len(f) == 8 and not line.startswith("#") and f[3] not in ("", "-"):
                names.append(f[0])
    extra = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_companies.txt")
    if os.path.exists(extra):
        names += [l.strip() for l in open(extra) if l.strip() and not l.startswith("#")]
    return list(dict.fromkeys(names))


# ---- per-platform fetchers: return list of normalized jobs or None if board missing ----

def gh(slug):
    try:
        d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    except Exception:
        return None
    jobs = []
    for j in d.get("jobs", []):
        locs = [j.get("location", {}).get("name", "")]
        for m in j.get("metadata") or []:
            v = m.get("value")
            if isinstance(v, list) and "location" in (m.get("name") or "").lower():
                locs += [str(x) for x in v]
        jobs.append({"title": j.get("title", ""), "location": "; ".join(x for x in locs if x),
                     "posted": j.get("first_published") or j.get("updated_at"),
                     "url": j.get("absolute_url"), "company": j.get("company_name")})
    return jobs


def lever(slug):
    try:
        d = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    except Exception:
        return None
    if not isinstance(d, list):
        return None
    jobs = []
    for j in d:
        c = j.get("categories") or {}
        locs = c.get("allLocations") or [c.get("location", "")]
        ts = j.get("createdAt")
        jobs.append({"title": j.get("text", ""), "location": "; ".join(locs),
                     "posted": dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).isoformat() if ts else None,
                     "url": j.get("hostedUrl"), "company": None})
    return jobs


def ashby(slug):
    try:
        d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    except Exception:
        return None
    jobs = []
    for j in d.get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        jobs.append({"title": j.get("title", ""), "location": "; ".join(x for x in locs if x),
                     "posted": j.get("publishedAt"), "url": j.get("jobUrl"), "company": None})
    return jobs


def smartr(slug):
    jobs, offset = [], 0
    try:
        while True:
            d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}&country=in")
            for j in d.get("content", []):
                l = j.get("location") or {}
                jobs.append({"title": j.get("name", ""),
                             "location": ", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x)
                             + ("; Remote" if l.get("remote") else ""),
                             "posted": j.get("releasedDate"),
                             "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                             "company": (j.get("company") or {}).get("name")})
            offset += 100
            if offset >= d.get("totalFound", 0) or offset > 2000:
                break
    except Exception:
        return None if not jobs else jobs
    return jobs or None


PLATFORMS = {"greenhouse": gh, "lever": lever, "ashby": ashby, "smartrecruiters": smartr}


def probe(name):
    found = []
    for plat, fn in PLATFORMS.items():
        for s in slugs(name):
            jobs = fn(s)
            if jobs:  # board exists and has jobs
                found.append((plat, s, jobs))
                break
    return name, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=15)
    a = ap.parse_args()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)
    names = companies()
    print(f"probing {len(names)} companies...", flush=True)
    os.makedirs(OUT, exist_ok=True)
    boards, hits = [], []
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        for i, (name, found) in enumerate(ex.map(probe, names), 1):
            for plat, slug, jobs in found:
                st = {"company": name, "platform": plat, "slug": slug, "total_jobs": len(jobs),
                      "blue_team_roles_any_city": 0, "blue_team_roles_target_cities": 0,
                      "latest_target_city_post": None, "board_url": None}
                boards.append(st)
                for j in jobs:
                    city = match_city(j["location"])
                    role = classify_title(j["title"])
                    if st["board_url"] is None and j.get("url"):
                        st["board_url"] = j["url"]
                    if role:
                        st["blue_team_roles_any_city"] += 1
                    if role and city:
                        st["blue_team_roles_target_cities"] += 1
                        d0 = (j["posted"] or "")[:10]
                        if d0 and (st["latest_target_city_post"] is None or d0 > st["latest_target_city_post"]):
                            st["latest_target_city_post"] = d0
                    if not city or not role or not j["posted"]:
                        continue
                    try:
                        p = dt.datetime.fromisoformat(j["posted"].replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if p.tzinfo is None:
                        p = p.replace(tzinfo=dt.timezone.utc)
                    if p < cutoff:
                        continue
                    hits.append({"company": name, "platform": plat, "title": j["title"],
                                 "role_type": role, "city": city, "location_raw": j["location"],
                                 "posted": p.date().isoformat(), "url": j["url"]})
            if i % 100 == 0:
                print(f"  {i}/{len(names)} boards={len(boards)} hits={len(hits)}", flush=True)
    json.dump(boards, open(os.path.join(OUT, "ats_boards_found.json"), "w"), indent=1)
    json.dump(hits, open(os.path.join(OUT, "raw_ats_jobs.json"), "w"), indent=1)
    print(f"boards={len(boards)} hits={len(hits)} companies_with_hits={len({h['company'] for h in hits})}")


if __name__ == "__main__":
    main()
