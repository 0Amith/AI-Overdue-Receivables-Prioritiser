# ABC Traders — AI Overdue Receivables Prioritiser

CLA-2 mini project build: a working receivables assistant that scores overdue
invoices against a fixed Collections Policy, ranks the customers to chase, and
drafts the reminder — politely, with a citation for every figure.

Runs **entirely on this machine**. No install, no cloud account, no build step. The
only network call is the optional Gemini reading assist, and every answer still works
without it.

```
python run.py
```

The browser opens on `http://127.0.0.1:8000/`. All scoring and arithmetic are local,
which is why the demo cannot break in the presentation — if the Wi-Fi dies, the badge
says *rules only* and the answers keep coming.

---

## What it does

| Ask | Answer |
|---|---|
| `give me all the overdue list` | the whole queue, ranked, with totals |
| `how many are critical?` | count and value by band |
| `which invoices are above 4 lakh?` | filter by amount, days or missing data |
| `top 3 customers to chase` | ranked table, score, priority, action, tie-break by amount |
| `score C002` | full breakdown: days, amount, history → total → priority → action |
| `why is C017 first?` | the ranking arithmetic, so a position can be defended |
| `draft a reminder for C017` | tone-matched reminder draft, ready to review and send |
| `draft a reminder for C017 in Hindi` | the same draft in Devanagari |
| `what is due for follow-up?` | broken promises first, then pending ones |
| `what is days overdue?` | the definition, from the Policy |
| `compare C002 and C003` | side by side, with the tie-break explained |
| `show me another customer's dues` | privacy answer: IDs only, no login, limitation stated |
| `can we give C005 a discount?` | refuses to decide, refers to the Finance Manager |
| anything not in the files | **Please contact the Finance Manager.** |

## Asking in your own words

You do not have to learn commands. A small parser normalises the sentence, expands
synonyms (`over due`, `dues`, `outstanding`, `arrears` all mean overdue), scores each
intent, and pulls out the filters — priority, amount, days, date window, missing data,
customer ID.

So all of these work without being taught:

- "give me all the over due list"
- "show me everyone who is late"
- "which customers owe us the most"
- "any invoices over 60 days"
- "total value of critical invoices"
- "list customers with missing data"

### Hinglish

The same parser accepts the way people actually type in an Indian office, and the
answer comes back in English:

| You type | Read as |
|---|---|
| `saari overdue list dikhao` | show all overdue |
| `total baki kitna hai` | total overdue amount |
| `50 hazaar se zyada wale` | overdue above Rs 50,000 |
| `1 lakh se kam baki` | overdue under Rs 1,00,000 |
| `kaun sabse pehle chase karna hai` | who to chase first |
| `C002 ka score batao` | score C002 |

`baki`/`baaki`/`udhaar` mean overdue, `dikhao`/`batao` mean show, `kitna` means how
much, and `se zyada` / `se kam` flip to *more than* / *under* with the amount kept in
place. Reminder drafts can also be produced in Hindi — the chat itself stays English.

### Date windows

"Overdue" on its own means the whole book, which is rarely what someone wants. Time
phrases are resolved against the reporting date (31 October 2026) and the window is
printed in the answer, so a short list can never be mistaken for the full one:

| You type | Window applied |
|---|---|
| `overdue last month` | 1–30 September 2026 |
| `total overdue for this month only` | 1–31 October 2026 |
| `overdue for last 1 month` | trailing 30 days, 2–31 October 2026 |
| `overdue for more than a month` | everything due on or before 30 September 2026 |
| `overdue in august` | 1–31 August 2026 |
| `late this week` | the last 7 days |

Ask "names" and it also tells you the register holds Customer IDs only, rather than
letting you wonder where the names went.

### When the phrasing is unusual

It is a parser, not a language model, so the same sentence always lands on the same
intent — which is what keeps the test matrix meaningful. When nothing scores well it
says so, offers its two closest guesses as buttons, and falls back to *Please contact
the Finance Manager* rather than inventing a reading.

### Gemini assist (on)

The parser's keyword reading is blunt by nature, so a Gemini key is wired in and
already active in this copy (`config.json`). The model takes over the *understanding*
step — and only that step:

- It returns a JSON query: intent, customer IDs, date window, amount bounds.
- The rule engine still computes every score, total and band, so arithmetic stays
  exact and reproducible and the 21 tests still hold.
- Every answer that used it shows a grey **"Understood as: …"** line, so you can see
  the reading and disagree with it. The audit log records the same per question.
- Customer IDs it invents are checked against the register and dropped.

Reliability is handled rather than hoped for: Google retires and throttles models, so
the layer tries a preferred list in order, remembers whichever answered last, caches
repeats, and gives up after 6 seconds. On any failure the parser answers alone and the
header badge reads *rules only* instead of *Gemini reading questions*. Answers are
always correct without it; it widens the phrasing, not the arithmetic.

To point it elsewhere, set `$env:GEMINI_API_KEY` (the environment wins over the file).
To switch the model off, rename `config.json`; nothing else changes.

**Privacy note:** with the assist on, the *question text* goes to Google. The register
itself is not uploaded, and the register holds Customer IDs rather than names.

## Working the list, not just talking about it

The assistant produces artifacts a finance team can use:

- **Worklist CSV** — the whole ranked queue with score components, action, data-quality
  flag and promise state. This is the file that goes to the collections clerk.
- **Reminder pack** — every draft for one priority band in a single document, English
  or Hindi. At 13 High invoices that is one download instead of 13 compose windows;
  it is where the 15-hour saving actually lands.
- **Exposure strip** — open value by band (Rs 37,10,000 sits in Critical), so the
  Finance Head sees money at stake, not just a count.
- **Promise-to-pay log** — record "customer promised 12 Nov". Broken promises rise
  to the top of the follow-up view and get quoted back in the reminder.
- **Contact log** — record what actually happened (no answer, spoke, disputed, part
  paid). A dispute flags the row and keeps it out of "not contacted in 7 days", so
  nobody rings a number that is waiting on a credit note.
- **Ageing report** — the export a Finance Head asks for first, built on the Policy's
  own day bands so it cannot disagree with the score.
- **Board brief** — one page: ageing, concentration, cost of delay, work in hand, top
  of the queue. Markdown, ready to paste into a month-end note.
- **Policy self-check** — `/policy-check` runs 22 boundary assertions against the live
  scoring function, plus 28 more it derives by reading the band tables back out of
  `Collections_Policy.md`. Edit the Policy without following it in the code and the
  derived block turns red.
- **Audit log** — every question, mode and answer summary, downloadable as CSV. This
  is the control behind the "who answers if the bot is wrong?" risk row.
- **Dataset import** — see below. Any CSV, any header names, any ID scheme, any
  as-on date.

## Bringing your own data

The demo register is one dataset, not a hard-coded one. **Import a dataset…** in the
sidebar takes any CSV: headers are matched by name against a synonym list
(`Party Code` → customer, `Outstanding (INR)` → amount, `Payment Due Date` → due
date, `Rating` → history), and you can override every guess with a dropdown before
committing.

Three things it asks for, and why:

1. **The as-on date.** Every day count is measured from it, so it is chosen at import
   and shown in the header, never assumed.
2. **A confirmed column mapping.** The preview says which columns are still missing
   and refuses to import until the three required ones are mapped.
3. **A look at the first rows, scored at that date**, so a wrong column is visible
   before it becomes a wrong answer.

What it handles: `Rs`, `₹`, comma grouping, `(5,000)` and `-5,000` for negatives;
ISO, `dd/mm/yyyy` and `dd-Mon-yyyy` dates; IDs like `C001`, `ACME-01`, `S/1042` or a
customer name; repeated IDs (rows fold into one customer — earliest due date, amounts
added, because promises, contacts and the queue are per customer).

What it does **not** do: the **Policy is still ABC Traders' policy**. A different
book with different bands or actions needs `knowledge/Collections_Policy.md` changed
with it — `/policy-check` derives its cases from that file, so the two cannot drift
apart silently. The header keeps an "imported dataset" badge up until you restore the
demo register, and `state/uploaded_register.json` remembers the mapping and date
across restarts.

`/?import=1` opens the dialog straight away, and `/?q=ageing%20report` loads a question
into the chat — handy for screenshots and for links you want to hand to someone.

## Questions about the shape of the book

Three questions the old build could not answer, because they are about the book
rather than about one invoice:

- **`ageing report`** — invoices and value per day band, plus value-weighted age
  (43.9 days). Says where the money is stuck.
- **`what if we wait 30 days?`** — keeps every invoice and amount, moves only the
  clock, and re-scores. Critical goes from 12 invoices to 20 and the value in
  Critical from Rs 37,10,000 to Rs 58,36,000. Nothing new has to go wrong.
- **`who holds the most exposure?`** — the top five accounts hold a third of the open
  book. A risk statement no per-invoice list can make.

All three are still arithmetic on the same Policy, and all three say so: ageing is
"not a ranking", concentration is "not a ranking", and the what-if is a clock
projection, not a forecast.

Answers also state **boundary proximity** — "exactly on the 15-day boundary",
"Rs 15,000 short of the Rs 2,00,000 boundary" — so a borderline row is visible
instead of looking the same as its neighbour.

## Why rule-based and not an LLM

The project's own test plan (test 7: *exactly 30 days gives 2 points, not 3*)
requires arithmetic that is reproducible and checkable by hand. A language model
does date maths probabilistically; this engine does it in one line of Python. The
bot is therefore always right on the arithmetic and can be audited line by line
against the Policy — and the answer key passes 15/15 on Version 2 without
retries.

The Gemini Gem route is still supported: `docs/GEM_INSTRUCTIONS.md` holds the
instruction text and the upload list for the same behaviour in Gemini.

## The files

```
knowledge/Collections_Policy.md       fixed scoring rules, bands, actions, ranking
knowledge/Receivables_Register.csv    40 invoices, reporting date 31 Oct 2026
app/engine.py                         scoring, bands, ranking (transcribed from Policy)
app/nlu.py                            natural-language parser: synonyms, intents, filters
app/llm.py                            optional Gemini reading layer (query only, no maths)
app/bot.py                            answers, citations, reminder tone, Hindi drafts
app/exports.py                        worklist, reminder pack, exposure, policy check
app/state.py                          promise log + audit trail (state/*.json, *.jsonl)
app/server.py                         local HTTP server (stdlib only)
config.json                           the Gemini key (gitignored); config.example.json is the template
web/                                  chat UI, register sidebar, policy-check page
tests/answer_key.json                 hand-written expectations, written before testing
tests/run_tests.py                    runs the 21 tests in both versions (no network)
tests/run_tests_ai.py                 the same 21 with Gemini on, to prove it changes nothing
docs/TEST_RESULTS.md                  generated result table for the report
docs/GEM_INSTRUCTIONS.md              Gemini Gem build pack
docs/DEMO_SCRIPT.md                   the live-demo run sheet
state/                                created on first run; safe to delete to reset
```

## The two versions

The Version switch in the header reproduces the project's improve-until-correct
evidence:

- **Version 1** — the bot counts the dates itself. It assumes 30-day months and
  counts both ends of the range, so every boundary row lands in the next band.
  Wrong days are printed in red.
- **Version 2** — days overdue come from the register column. Exact.

Same question, two runs, side by side.

## Test results

```
python tests/run_tests.py
```

| | Version 1 | Version 2 |
|---|---|---|
| Tests right | 20 / 21 | **21 / 21** |

Tests 1–12 are the ones the plan requires. Tests 13–21 were added for the features
below (ranking explanation, Hindi draft, follow-up log, free phrasing, definitions,
date windows).

The single Version 1 failure is test 7, the 30-day boundary — the defect sits
exactly where dates are calculated instead of read. Full table, with what the bot
actually said, in [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

The same 21 tests pass with the Gemini assist on
(`python tests/run_tests_ai.py`), because the assist never does arithmetic.

```
python tests/run_tests_extra.py
```

35 cases cover the analysis, record-keeping and import features: ageing bands and
their totals, the cost-of-delay horizon, concentration, the dispute and cooldown
filters, boundary proximity, the refusal sentence, the exports, the 28 Policy-derived
assertions (including one that edits the Policy in memory and checks the derived block
catches the drift), and a foreign dataset end to end — header matching, missing
columns, duplicate folding, text dates, comma amounts, a custom as-on date, and an
`ACME-01`-style ID asked about by name. It runs against a throwaway store, so `state/`
is never touched. Results in [docs/FEATURE_TESTS.md](docs/FEATURE_TESTS.md).

## Register design

Deliberate edge cases, per the plan: exactly 15, 30 and 60 days overdue; amounts
of exactly Rs 50,000 and exactly Rs 2,00,000; a blank history code; a blank
amount; a row with both blank; one invoice not yet due. Rows with a missing field
are marked `!` in the sidebar and their scores are labelled **provisional** — the
blank is flagged, never guessed.

Reporting date is fixed at **31 October 2026**, so every figure in a screenshot
stays reproducible.

## Limits

- Monthly extract, not a live feed — no accounting-software connection.
- The parser is keyword-weighted, not semantic, and the assist is a network call of a
  second or two: a very unusual phrasing can still be misread. It then offers guesses
  instead of pretending, and every answer must also work with the assist off.
- No login, so every user sees every Customer ID.
- The promise log, contact log and audit trail are local files, not a shared
  database — two people on two machines do not see each other's promises or calls.
- The what-if is a clock projection: it assumes no new invoice falls overdue and
  nobody pays. It is not a forecast.
- The bot recommends; Accounts Receivable / Finance Manager owns the output.
- Discounts and settlements are never decided by the bot.

## Extending it

`app/engine.py` holds every rule in one place. Change a band there — and in
`Collections_Policy.md`, or `/policy-check` will tell you that you have not — and the
tests and the UI stay in step with it. To wire a real feed, replace
`engine.load_register()`; nothing else reads the CSV.
