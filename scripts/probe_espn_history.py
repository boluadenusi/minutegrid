#!/usr/bin/env python3
"""How far back does ESPN go? Checks whether an ESPN-only Minute Grid could
fill the rolling 10-year window (from 18 Nov 2016). Read-only.

1. Catalogue: every ESPN soccer competition with its name and the seasons
   ESPN lists for it (first, last, count).
2. Depth: for each competition Minute Grid covers that ESPN also has, sample
   real match days from the start of the window (late 2016 / the first
   edition after it) and, for leagues, a later season too. For each sample:
   matches, matches with goals, how many carry goal details, scorer ids and
   readable clocks. A listed season does not guarantee goal-level data, so
   this is the part that matters.
3. Quality: the sampled goals are compared with Transfermarkt minutes
   (all samples are before Transfermarkt's 2026-07-06 cut-off).

Responses are cached in data/espn_cache/, so reruns only fetch what failed.
Roughly 450-700 requests on a first run (about 5-8 minutes).

Usage:
  python scripts/probe_espn_history.py
  python scripts/probe_espn_history.py --skip-catalogue
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

if __package__:
    from .probe_espn import (BASE, CORE, ROOT, compare_with_transfermarkt, days_in, describe, get_json,
                             goal_details, match_goals, slug_from_ref, summary_goals)
else:
    from probe_espn import (BASE, CORE, ROOT, compare_with_transfermarkt, days_in, describe, get_json,
                            goal_details, match_goals, slug_from_ref, summary_goals)

OUT = ROOT / "data" / "espn_history.json"
WINDOW_START = "20161118"

EURO_LEAGUE = (("20161119", "20161127"), ("20201121", "20201129"))   # just after the window start; a later season
CALENDAR_LEAGUE = (("20170506", "20170520"), ("20210508", "20210522"))  # spring/summer seasons

# ESPN code -> (Transfermarkt id, name, sample windows YYYYMMDD start/end). The first window is the
# earliest that falls inside the 10-year window; competitions founded later say so in the name.
TARGETS = {
    "eng.1": ("GB1", "Premier League", EURO_LEAGUE),
    "esp.1": ("ES1", "LaLiga", EURO_LEAGUE),
    "ger.1": ("L1", "Bundesliga", EURO_LEAGUE),
    "ita.1": ("IT1", "Serie A", EURO_LEAGUE),
    "fra.1": ("FR1", "Ligue 1", EURO_LEAGUE),
    "ned.1": ("NL1", "Eredivisie", EURO_LEAGUE),
    "por.1": ("PO1", "Liga Portugal", EURO_LEAGUE),
    "sco.1": ("SC1", "Scottish Premiership", EURO_LEAGUE),
    "bel.1": ("BE1", "Belgian Pro League", EURO_LEAGUE),
    "aut.1": ("A1", "Austrian Bundesliga", EURO_LEAGUE),
    "den.1": ("DK1", "Danish Superliga", EURO_LEAGUE),
    "gre.1": ("GR1", "Greek Super League", EURO_LEAGUE),
    "tur.1": ("TR1", "Süper Lig", EURO_LEAGUE),
    "rus.1": ("RU1", "Russian Premier League", EURO_LEAGUE),
    "ksa.1": ("SA1", "Saudi Pro League", EURO_LEAGUE),
    "arg.1": ("ARG1", "Argentine Primera", EURO_LEAGUE),
    "mex.1": ("MEX1", "Liga MX", EURO_LEAGUE),
    "aus.1": ("AUS1", "A-League Men", EURO_LEAGUE),
    "nor.1": ("NO1", "Eliteserien", CALENDAR_LEAGUE),
    "swe.1": ("SE1", "Allsvenskan", CALENDAR_LEAGUE),
    "jpn.1": ("JAP1", "J1 League", CALENDAR_LEAGUE),
    "bra.1": ("BRA1", "Brasileirão", CALENDAR_LEAGUE),
    "usa.1": ("MLS1", "MLS", CALENDAR_LEAGUE),
    "uefa.champions": ("CL", "Champions League", (("20161122", "20161123"), ("20201201", "20201202"))),
    "uefa.europa": ("EL", "Europa League", (("20161124", "20161124"), ("20201203", "20201203"))),
    "uefa.europa.conf": ("UCOL", "Conference League (since 2021)", (("20210916", "20210916"),)),
    "uefa.champions_qual": ("CLQ", "Champions League qualifying", (("20170711", "20170719"),)),
    "uefa.europa_qual": ("ELQ", "Europa League qualifying", (("20170713", "20170720"),)),
    "uefa.europa.conf_qual": ("ECLQ", "Conference League qualifying (since 2021)", (("20210708", "20210715"),)),
    "uefa.super_cup": ("USC", "UEFA Super Cup", (("20170805", "20170810"),)),
    "fifa.world": ("FIWC", "World Cup 2018", (("20180614", "20180618"),)),
    "uefa.euro": ("EURO", "Euro 2020 (played 2021)", (("20210611", "20210615"),)),
    "conmebol.america": ("COPA", "Copa América 2019", (("20190614", "20190618"),)),
    "caf.nations": ("AFCN", "Africa Cup of Nations 2017", (("20170114", "20170120"),)),
    "afc.asian.cup": ("AFAC", "Asian Cup 2019", (("20190105", "20190110"),)),
    "eng.fa": ("FAC", "FA Cup", (("20170106", "20170109"),)),
    "esp.copa_del_rey": ("CDR", "Copa del Rey", (("20170103", "20170105"),)),
    "ger.dfb_pokal": ("DFB", "DFB-Pokal", (("20170207", "20170208"),)),
    "ita.coppa_italia": ("CIT", "Coppa Italia", (("20170111", "20170119"),)),
    "ned.cup": ("NLP", "KNVB Beker", (("20161213", "20161215"),)),
    "sco.tennents": ("SFA", "Scottish Cup", (("20170121", "20170122"),)),
    "eng.charity": ("GBCS", "Community Shield", (("20170805", "20170807"),)),
    "ger.super_cup": ("DFL", "German Supercup", (("20170804", "20170806"),)),
    "ita.super_cup": ("SCI", "Supercoppa Italiana", (("20161222", "20161224"),)),
    "ned.supercup": ("NLSC", "Johan Cruijff Schaal", (("20170804", "20170806"),)),
    "fra.super_cup": ("FRCH", "Trophée des Champions", (("20170728", "20170730"),)),
    "esp.super_cup": ("SUC", "Supercopa de España", (("20170812", "20170817"),)),
}

SEASON = re.compile(r"/seasons/(\d{4})")
ENOUGH = 3       # matches with goals per window: stop scanning that window early
SUMMARY_PER_WINDOW = 3


def season_years(refs):
    return sorted({int(m.group(1)) for m in (SEASON.search(r or "") for r in refs) if m})


def catalogue():
    status, body = get_json(f"{CORE}/leagues?limit=1000")
    if status != 200:
        print(f"League list: HTTP {status}")
        return []
    rows = []
    slugs = sorted({s for s in (slug_from_ref(i.get("$ref")) for i in body.get("items", [])) if s})
    for index, slug in enumerate(slugs, start=1):
        _s, league = get_json(f"{CORE}/leagues/{slug}")
        _s2, seasons = get_json(f"{CORE}/leagues/{slug}/seasons?limit=200")
        years = season_years(item.get("$ref") for item in (seasons or {}).get("items", [])) \
            if isinstance(seasons, dict) else []
        rows.append({"code": slug, "name": (league or {}).get("name") if isinstance(league, dict) else None,
                     "first": years[0] if years else None, "last": years[-1] if years else None,
                     "seasons": len(years)})
        if index % 25 == 0:
            print(f"  catalogue: {index}/{len(slugs)}", flush=True)
    return rows


def sample(code, cid, start, end):
    """Scan days in [start, end]; stop once ENOUGH finished matches with goals are seen."""
    result = {"window": f"{start}-{end}", "days": 0, "matches": 0, "with_goals": 0, "with_details": 0,
              "goals": [], "errors": 0}
    summaries = SUMMARY_PER_WINDOW
    for day in days_in(f"{start}-{end}"):
        status, body = get_json(f"{BASE}/{code}/scoreboard?dates={day}&limit=200")
        result["days"] += 1
        if status != 200:
            result["errors"] += 1
            continue
        for event in body.get("events", []):
            if not ((event.get("status") or {}).get("type") or {}).get("completed"):
                continue
            result["matches"] += 1
            if match_goals(event) == 0:
                continue
            result["with_goals"] += 1
            details = goal_details(event)
            if not details and summaries > 0:
                summaries -= 1
                _st, details = summary_goals(code, event.get("id"))
            if details:
                result["with_details"] += 1
            result["goals"].extend(describe(code, cid, (event.get("date") or "")[:10], event, d) for d in details)
        if result["with_goals"] >= ENOUGH:
            break
    return result


def verdict(windows):
    first = windows[0] if windows else None
    if not first or first["errors"] and not first["matches"]:
        return "unknown (requests failed; rerun)"
    if not first["matches"]:
        return "no matches found in the sample"
    if not first["with_goals"]:
        return "matches found, none with goals in the sample"
    ratio = first["with_details"] / first["with_goals"]
    ids = sum(1 for g in first["goals"] if g["athlete_id"])
    clocks = sum(1 for g in first["goals"] if g["minute"] is not None)
    if ratio >= 0.9 and first["goals"]:
        if ids == len(first["goals"]) and clocks == len(first["goals"]):
            return "full goal detail at the window start"
        return (f"goal detail, but {len(first['goals']) - ids} goals without scorer id and "
                f"{len(first['goals']) - clocks} without a minute")
    if ratio > 0:
        return f"partial: {first['with_details']}/{first['with_goals']} matches with goal detail"
    return "scores only, no goal detail"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-catalogue", action="store_true", help="skip listing all ESPN competitions")
    args = parser.parse_args()

    rows = [] if args.skip_catalogue else catalogue()
    if rows:
        print(f"\n--- ESPN soccer competitions ({len(rows)}), oldest season first ---")
        for r in sorted(rows, key=lambda r: (r["first"] or 9999, r["code"])):
            span = f"{r['first']}-{r['last']} ({r['seasons']} seasons)" if r["first"] else "no seasons listed"
            print(f"{r['code']:32} {span:26} {r['name'] or '?'}")

    print("\n--- depth for Minute Grid competitions (sampled match days) ---")
    results, all_goals = {}, []
    for code, (cid, name, windows) in TARGETS.items():
        listed = next((r for r in rows if r["code"] == code), None)
        sampled = [sample(code, cid, start, end) for start, end in windows]
        for s in sampled:
            all_goals.extend(s["goals"])
        results[code] = {"tm": cid, "name": name, "listed": listed,
                         "samples": [{k: v for k, v in s.items() if k != "goals"} for s in sampled],
                         "verdict": verdict(sampled)}
        parts = []
        for s in sampled:
            ids = sum(1 for g in s["goals"] if g["athlete_id"])
            parts.append(f"{s['window']}: matches {s['matches']}, with goals {s['with_goals']}, "
                         f"with goal detail {s['with_details']}, goals {len(s['goals'])} (scorer ids {ids})"
                         + (f", failed days {s['errors']}" if s["errors"] else ""))
        seasons = f" | ESPN lists {listed['first']}-{listed['last']}" if listed and listed["first"] else ""
        print(f"{code:24} {cid:5} {name}{seasons}\n    " + "\n    ".join(parts) + f"\n    => {results[code]['verdict']}",
              flush=True)

    tally = Counter(r["verdict"].split(":")[0] for r in results.values())
    print("\n--- summary ---")
    for label, count in tally.most_common():
        print(f"{count:3}  {label}")
    OUT.write_text(json.dumps({"window_start": WINDOW_START, "catalogue": rows, "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    compare_with_transfermarkt(all_goals)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
