# Report notes (CLA-2)

Everything below maps a required report section to an artifact already in this
folder, so the writing is assembly rather than invention.

## Business value arithmetic

Plan figures: 150 overdue invoices a month, 8 minutes manual → 2 minutes with the
tool.

- 150 × 8 min = 1,200 min = **20 hours** a month manual
- 150 × 2 min = 300 min = **5 hours** a month with the tool
- Saving = **15 hours** a month

Money: state the assumed staff cost. At an assumed Rs 400/hour that is
Rs 6,000 a month, Rs 72,000 a year. Label it an illustration and name the
assumption — the plan asks for exactly that.

## Section → artifact

| Report section | Use |
|---|---|
| Business problem | README opening; the 20-hour manual baseline |
| Why AI | `README.md` "Asking in your own words" and "Why rule-based and not an LLM"; the test table |
| Tool used | `docs/GEM_INSTRUCTIONS.md`; the local app is the demo build |
| Data used | `knowledge/Collections_Policy.md`, `knowledge/Receivables_Register.csv` — 40 made-up rows, Customer IDs only |
| How you built it | `docs/GEM_INSTRUCTIONS.md` steps, Version 1 → Version 2 screenshots in `docs/screenshots/` |
| Testing | `docs/TEST_RESULTS.md` — 20/21 before, 21/21 after; `docs/FEATURE_TESTS.md` — 35/35 on the analysis, record-keeping and import features; plus the live `/policy-check` page (22 hand-written assertions and 28 derived from the Policy file) |
| Other datasets | **Import a dataset…** — any CSV, headers matched or mapped by hand, as-on date chosen at import; the Policy still has to suit the book |
| Business value | arithmetic above |
| Risks | table below |
| Limitations | below |

## Screenshots to use

- `docs/screenshots/v1-score-C002.png` — 30 days shown as **31**, promoted to a
  higher band (the failure)
- `docs/screenshots/v2-score-C002.png` — same question, 30 days = 2 points, total
  7, Critical (the fix)
- `docs/screenshots/v2-listing.png` — "give me all the over due list", the sloppy
  phrasing understood
- `docs/screenshots/v2-aggregate.png` — "how many are critical?" as a count and a value
- `docs/screenshots/v2-ranking.png` — top 3, tie-break by amount
- `docs/screenshots/v2-reminder.png` — Critical-tone reminder draft
- `docs/screenshots/v2-exposure.png` — open value by band
- `docs/screenshots/policy-check.png` — the boundary assertions passing
- `docs/screenshots/v2-followup.png` — promise log, broken promise first
- `docs/screenshots/v2-ageing.png` — the ageing table on the Policy's own bands
- `docs/screenshots/v2-whatif.png` — cost of delay: Critical 12 → 20, value more than half again
- `docs/screenshots/v2-concentration.png` — the top five accounts and their share
- `docs/screenshots/v2-boundary.png` — "how close is this to moving" in an explanation
- `docs/screenshots/v2-import.png` — the import dialog, with the as-on date and the
  column mapping it has to confirm

## Risks and controls

| Risk | Why it matters | Control |
|---|---|---|
| Wrong scores | A date error ranks the wrong customer first | Human checks the Critical list; Version 2 reads the Days Overdue column; 21-test matrix; `/policy-check` re-asserts every boundary |
| Misread question | A parser can misread an unusual phrasing | Every answer shows its working and citation; a grey "Understood as" line exposes the reading; when nothing scores well it offers guesses instead of guessing |
| Privacy | Anyone can ask for another customer's dues | Customer IDs only, no names; login access needed for real use |
| Fairness | History points can penalise small customers | Review the scoring rules periodically |
| Tone | A bad reminder damages a relationship | Every draft is reviewed before sending; tone is tied to the Policy action, not to mood |
| API dependency | The reading assist needs a valid key and the network | The parser answers alone on any failure; the badge says so; the arithmetic never depends on the key |
| Question text leaves the machine | The assist sends the question to Google | The register is not uploaded, and it holds IDs rather than names; renaming `config.json` switches the assist off |
| Key stored in a file | `config.json` sits in the project folder | It is gitignored; the environment variable overrides it |
| Accountability | Who answers if the bot is wrong? | Accounts Receivable / Finance Manager owns the output; the bot only recommends; every question is written to the audit log |

## Limitations to state

- Monthly data extract, not a live feed.
- The import accepts other datasets, but only the **shape**: a different book still
  needs `Collections_Policy.md` changed with it, because the bands, actions and the
  refusal rule are ABC Traders'. The engine follows the Policy file; it cannot invent
  a policy for a stranger's book.
- Currency is rupees and formatting is Indian grouping throughout. A non-INR dataset
  needs `engine.inr` changed.
- Repeated customer IDs fold into one customer (earliest due, amounts added), because
  promises, contacts and the queue are per customer — a dataset that needs per-invoice
  chase would need the key changed to the invoice.
- Chat is English; drafts can be English or Hindi.
- Date windows resolve against the fixed reporting date; there is no live clock.
- The assist adds 1–3 seconds and needs the key to stay valid; without it the parser
  alone runs, and every test passes that way too.
- The parser is keyword-weighted, not semantic — an unusual phrasing can be
  misread, in which case it offers guesses rather than guessing silently.
- No login system.
- Arithmetic is exact but the **policy** is a simplification of a real credit
  function — the bands are fixed by design so answers stay checkable.
- The bot recommends; it never sends, never decides a discount.

## Future improvements

Connect to the accounting software for a live feed; move the promise log, contact
log and audit trail to a shared database with per-customer login; send reminders
through the mail server instead of copy/WhatsApp handoff.

## What to say about the analysis features

Three additions are worth a line each in the report, because they are cheap and
they change what the tool is for:

- **Ageing and concentration** are the two views a Finance Head asks for first. The
  ageing table is built on the Policy's own day bands, so it cannot disagree with
  the score; concentration says the top five accounts hold a third of the book, which
  is a risk statement no per-invoice list can make.
- **Cost of delay** keeps every invoice and every amount fixed and only moves the
  clock. Critical goes from 12 to 20 invoices and the value in Critical from
  Rs 37,10,000 to Rs 58,36,000 in thirty days. Nothing new has to go wrong.
- **Boundary proximity** is the honest answer to "why is this one Critical and that
  one High, they look the same" — the explanation names the exact edge and the gap.

State the caveat plainly: the what-if is a clock projection, not a forecast. It
assumes no new invoice falls overdue and nobody pays.

## Facts to keep consistent

- Reporting date **31 October 2026**.
- 40 invoices, Customer IDs C001–C040, no names.
- Version 1: 20/21. Version 2: 21/21.
- Critical band is 7–9 and the action is *escalate to Finance Head and hold new
  orders*.
- Exactly 30 days is 2 points.
- Open exposure Rs 71,59,000 across 39 invoices; Rs 37,10,000 of it in Critical.
- Ageing: 11 / Rs 15,32,000 in 0–15 days, 7 / Rs 24,50,000 past 60; value-weighted
  age 43.9 days.
- In thirty days of inaction: Critical 12 → 20, value in Critical Rs 37,10,000 →
  Rs 58,36,000, 19 rows change band.
- The five largest accounts hold 33.7% of the book.
