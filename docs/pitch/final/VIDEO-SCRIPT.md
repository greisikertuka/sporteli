# Sportel demo video: script (77 seconds, English UI)

**Selling point in one line:** a head of department can defend every number. Sportel builds the
indicator from the file the directorate already has, and shows where every number came from.
When the data is missing, it says so and names who owes it.

**Data:** `demo/mbetjet_jan-gus_2026_SINTETIKE.csv`, a hand-built synthetic waste export in the
Public Services Directorate's style:

- title rows, a `Gjithsej` total row, Albanian month names, decimal commas;
- 13 administrative units × January–August 2026;
- labelled SINTETIKE, so these are not official figures.

It has a different layout from the sample file, so the AI mapping does real work.

**The video is recorded automatically** by `demo/record.js` (a headless browser with an on-screen
cursor and captions), after a demo reset. The file is `demo/sportel-demo.mp4`.

| t | Screen | Action | Caption on screen |
|---|---|---|---|
| 0–10 s | Board | The counter reads **6/13**. The cursor moves to **Public Services Directorate · unlocks 3 indicators** under *For leadership, this month*, then to the grey **Waste per resident** tile (*Missing export*) | "Head of Public Services: 6 of 13 indicators have proof. Waste has no data yet." |
| 10–19 s | Ask the data | Click *How many kilograms of waste per resident per year?* → **NOT ANSWERABLE** | "Sportel does not guess. It names the missing export and who owns it." |
| 19–42 s | Integrate data | **Choose a file** → the hand-built CSV. The steps under *What the code did* appear: header on row 4, total row set aside, no personal columns | "Upload the file the directorate already has." |
| | Column mapping | The AI proposes all 5 columns (in this take it was confident on every one; if a row is amber, a person clicks **Confirm**) → **Confirm and load** | "The AI read column names only. No values left the server." / "A person checks the mapping, then loads the file." |
| 42–50 s | Load receipt | **104 loaded**, and the total row matches the file | "Every row counted. The totals match the file's own total." |
| 50–60 s | Board | **9/13**. The same waste tiles now show values: 25,621 t collected, 316.6 kg per resident, 10,526 lek per tonne (synthetic) | "The waste KPIs are no longer empty, and each has its proof." |
| 60–74 s | Ask the data | The same question → **VERIFIED**, 316.6 kg/resident/year, scroll past **How it was calculated** (the formula in plain words) to **Sources** (the hand-built CSV plus the population file, with row ranges) | "Same question: verified, with the exact source rows." |
| 74–77 s | End | — | "Sportel · Report once, prove every number." |

**In the pitch:** play it on slide 3 and speak the slide-3 notes over it. The captions carry the
story if the room is loud.

**Result:** `demo/sportel-demo.mp4` (1920×1080, 77 s, 7–8 MB). To re-record, reset the demo and
run `node demo/record.js` with `FFMPEG` set (see the file header). The AI step varies a little:
if the AI is unsure of a column, the video shows a person clicking **Confirm**; if not, the
caption says the person checks the mapping and loads the file.
