"""Build the synthetic stat-file fixtures for eras with no real file available.

1.9.3: from the real 1.9.5 encoded file, rewritten to the 1.9.2-1.9.4 writer
(MSB_StatTracker.cpp at tag 1.9.3): "Team N Roster M" keys with 0 = away,
"Ranked" instead of "TagSetID", and each team's Captain flag at the other
team's captain index (the captain lookup still used the pre-1.9.2 numbering).

2.3.0: from the real 2.2.0 encoded file, cut after the top of the 3rd and
ended as a crash, rewritten to the 2.3.0 writer: lowercase hex 64-bit GameID,
TagSetID -1 for none, and "Star Swing Five-Star" as cMoonShotStatus (one
failed moonshot).
"""

import json
import sys
from pathlib import Path

fixtures = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parent.parent / "tests/fixtures"
)

# --- 1.9.3 ---
src = fixtures / "stat_files/1.9.5/20230315T212151_MaybeJon-Vs-PeacockSlayer_1867546158.json"
data = json.loads(src.read_text())
out = {}
for key, value in data.items():
    if key == "TagSetID":
        out["Ranked"] = 0
        continue
    if key == "Version":
        value = "1.9.3"
    out[key] = value
stats = data["Character Game Stats"]
captain = {
    side: next(i for i in range(9) if stats[f"{side} Roster {i}"]["Captain"])
    for side in ("Away", "Home")
}
new_stats = {}
for team, side, other in ((0, "Away", "Home"), (1, "Home", "Away")):
    for i in range(9):
        spot = dict(stats[f"{side} Roster {i}"])
        spot["Captain"] = int(i == captain[other])
        new_stats[f"Team {team} Roster {i}"] = spot
out["Character Game Stats"] = new_stats
# Version goes where 1.9.3 wrote it, after Lag Spikes, which is already the case.
(fixtures / "stat_files/1.9.3").mkdir(parents=True, exist_ok=True)
(fixtures / "stat_files/1.9.3/synthetic.MaybeJon-Vs-PeacockSlayer.json").write_text(
    json.dumps(out, indent=2) + "\n"
)

# --- 2.3.0 ---
src = fixtures / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
data = json.loads(src.read_text())
events = data["Events"]
cut = next(i for i, e in enumerate(events) if (e["Inning"], e["Half Inning"]) == (3, 1))
kept = events[:cut]
final = events[cut]
data["Events"] = kept
data["GameID"] = "9f3c2a1b5d7e4f60"
data["TagSetID"] = -1
data["Version"] = "2.3.0"
data["Away Score"] = final["Away Score"]
data["Home Score"] = final["Home Score"]
data["Innings Played"] = 3
data["Quitter Team"] = 2
for event in kept:
    contact = event.get("Pitch", {}).get("Contact")
    if contact is not None and event["Pitch"]["Type of Swing"] == 3:
        contact["Star Swing Five-Star"] = 2
        break
else:
    raise SystemExit("no star swing to mark")
(fixtures / "stat_files/2.3.0").mkdir(parents=True, exist_ok=True)
(fixtures / "stat_files/2.3.0/synthetic.SpiceOrange-Vs-MattGree.json").write_text(
    json.dumps(data, indent=2) + "\n"
)
print("ok", cut)
