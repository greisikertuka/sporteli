// Speaker notes (the spoken script, ~720 words for 4:45). The slides carry almost no text.
module.exports = [
// 1 Title — 0:15
`[0:00–0:15]
Good morning. We are Firmat, and this is Sportel, for Challenge 02, the decision-making dashboard.
Sportel gives every head of department numbers they can defend: every number, with its proof.`,

// 2 Problem — 0:45
`[0:15–1:00]
First, credit: in May, Elbasan was named one of three national good-practice models for validating performance indicators. [Confirm the exact wording at the municipal desk.]
Now picture any municipality. Friday afternoon, council on Monday. The deputy mayor asks the head of Public Services: how much of our waste cost does the cleaning fee cover?
The fee sits in one directorate's Excel file, the cost in another's, each with its own layout and units. Staff email spreadsheets and copy totals. A number goes up, but nobody can show which rows it came from.
And the national performance indicators are collected once a year, so a problem visible in March shows up in next year's report. Decisions wait, and they rest on trust.`,

// 3 Solution + demo — 1:30
`[1:00–2:30 · play the demo video, speak over it]
Sportel turns the files departments already have into indicators with proof. One flow, on synthetic files.
I am the head of Public Services. The board shows 6 of 13 indicators with proof. The grey tiles say which export is missing and who owns it.
I ask the deputy mayor's question. Sportel does not guess. It answers "Not answerable": the revenue export is missing, owner: the Local Revenue Directorate.
My colleague in Revenue drops the Excel file they already produce. Code finds the header, the units and the total row, and removes personal columns. The AI suggests which column means what, from the column names only. A person confirms.
The receipt: 100 rows read, 96 loaded, 4 set aside, and the totals match the file's own total.
Same question again: Verified. 55 percent on synthetic data, with the formula and the exact source rows from two directorates. The tile turns green, 8 of 13, and the Excel report has a source column next to every value. That is what I take into the council meeting.`,

// 4 Users — 0:30
`[2:30–3:00]
Three users. The head of department opens the board every month: what is proven, what is off target, and which directorate to ask for data.
Their staff do one thing: upload the Excel file they already make. Next month the format is remembered, so it is one click.
Adoption is decided by the mayor's office, with IT approving one server.
Before: once a year, on trust. After: every month, with proof.`,

// 5 How it works — 0:30
`[3:00–3:30]
The AI does two small jobs: it reads column names, and it understands a question in Albanian. It never sees the numbers: no cell values, no rows, and personal columns are removed first. Code computes every number.
For the pilot, Sportel runs on the municipality's own server. For the AI we offer three levels: a local open model on that server, so nothing leaves the building; an EU-region provider with zero data retention and no training on the data; or, as in today's demo, column names only.
AI declaration: we built with Claude Code; the demo uses GPT-5 mini on the organisers' key.`,

// 6 Market — 0:25
`[3:30–3:55]
Honest arithmetic. All 61 Albanian municipalities report the same national indicators, and with Kosovo's 38 on the same performance-grant model, that is 99 municipalities with this exact duty, out of 450-plus in the region.
Only the Excel layouts change between them, and those are learned once. Pilot in Elbasan, then replicate through the project partners.`,

// 7 Next + cost — 0:40
`[3:55–4:35]
Four weeks of mentoring: week one, real exports with a data agreement. Week two, the Performance Unit validates the formulas. Week three, install on a municipal server and test with heads of department. Week four, rebuild last year's report from exports, cell by cell.
After the pilot: logins per directorate, all 52 national indicators, and a verified feed for the city's AI window.
Cost, as estimates: eight to twelve thousand euros to pilot-ready, two to four thousand for setup and training, under a hundred euros a month to run, four to six thousand a year to maintain. With a local AI model, add about two hundred euros a month for a GPU server, or a one-off card for the municipal server.`,

// 8 Team — 0:10
`[4:35–4:45 · this slide stays up during Q&A]
We are Firmat: Greisi, full stack; Redjon, AI; Martin, backend; Fatjon, DevOps. We built this full loop this weekend. Report once, prove every number. Thank you.`,
];
