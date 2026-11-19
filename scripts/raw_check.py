import os, requests
from pathlib import Path

for line in Path(".env").read_text().splitlines():
    if line.startswith("PITCH_KEY="):
        os.environ["PITCH_KEY"] = line.split("=", 1)[1].strip().strip('"')

H = {"X-API-KEY": os.environ["PITCH_KEY"]}
B = "https://api.pitchapi.dev"

for d in ["2026-11-08", "2026-10-24", "2026-05-17"]:
    r = requests.get(f"{B}/v1/date/{d}", headers=H, timeout=30)
    j = r.json()
    ms = j.get("data", {}).get("matches", [])
    print("\nDATE", d, "| http", r.status_code, "| matches", len(ms), "| error", j.get("error"))
    if ms:
        m = ms[0]
        print(m["id"], m["league"]["name"], m["status"], m.get("score_home"), m.get("score_away"))
        e = requests.get(f"{B}/v1/matches/{m['id']}/events", headers=H, timeout=30)
        print("events http", e.status_code)
        print(e.text[:900])