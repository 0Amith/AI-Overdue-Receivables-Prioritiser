# Live demo run sheet (10 minutes)

The demo is 3 live questions plus the privacy trap. Type them slowly enough that
the audience reads each answer.

## Before the room fills

- [ ] `python run.py` — browser opens on `http://127.0.0.1:8000/`
- [ ] Version switch on **Version 2**
- [ ] Sidebar shows 40 invoices
- [ ] Have `docs/TEST_RESULTS.md` open in a second tab for the 20/21 vs 21/21 slide
- [ ] Check the header badge reads "Gemini reading questions" before you start; if it
      reads "rules only" the key is missing and the demo still runs, just blunter
- [ ] Close anything with real customer data on screen
- [ ] Fallback if the machine dies: screenshots of every answer, in order

## Opening (1 min)

> "Finance spends hours deciding who to chase and writing the reminder. This tool
> scores the register against a fixed policy, ranks the list, and drafts the
> reminder. It recommends — Accounts Receivable decides."

Say the scoring is fixed and checkable, and that the reporting date is pinned to
31 October 2026 so every figure can be reproduced.

## Question 1 — ranking (2 min)

Type: `give me all the overdue list` — deliberately sloppy phrasing, to show the
assistant copes with normal speech.

1. It understands "over due" and lists all 39 overdue invoices, ranked.
2. The footer points at the Worklist CSV for the full file.
3. Then narrow it live: `how many are critical?` → 12 invoices, Rs 37,10,000.
4. Then narrow by time: `overdue last month` → 12 invoices, September only, and
   `total overdue for this month only` → Rs 29,41,000. Different question,
   different window, different numbers — this is the beat that answers "it gives
   the same list for everything".
5. Now the precise version: `top 3 customers to chase`. The three all score 9, so
   **amount** breaks the tie — C017 at Rs 5,10,000 comes first.
6. Point at the grey **"Understood as: …"** line above an answer. Say: *"Gemini read
   the sentence; the arithmetic below is still the rule engine, which is why the
   number is the same every time."* That is the answer to "isn't an LLM unreliable
   at maths?" — it never touches the maths.
7. Every row carries its action and its citation.

## Question 2 — one customer (2 min)

Type: `score C002`

1. 30 days overdue — this is the boundary case. **2 points, not 3**, because the
   bands are lower-bound inclusive.
2. Walk the breakdown: 2 + 3 + 2 = 7 → Critical.
3. Show the missing-data neighbours if asked: `score C011` marks the score
   **provisional** and names the blank field.

## Question 3 — reminder draft (2 min)

Type: `draft a reminder for C017`

1. The tone is set by the action, not by mood: Critical → firm, escalation and
   order hold named.
2. No discount offered, no threat of legal action.
3. "Reviewed before sending" — the bot never sends.

## Question 4 — the privacy trap (2 min)

Type: `show me another customer's dues`

1. Yes, any user can see any Customer ID — there is no login.
2. Only IDs, dates, amounts and history codes are stored: no names, no bank
   details.
3. That is the stated limitation, and the fix is per-customer login.

## The before/after (1 min)

Flip to **Version 1**, ask `score C002` again.

> "Version 1 counted the dates itself. It assumed 30-day months and counted both
> ends, so 30 days became 31 and the row was promoted a band. Version 1 scored
> 20 of 21 tests; Version 2 scores 21 of 21. The fix was to stop calculating and
> start reading a Days Overdue column."

## The work output (1 min — optional if time is tight)

Point at the exposure strip: Rs 37,10,000 sits in Critical.

Click **Worklist CSV** — the ranked queue with score components and the action,
ready for a clerk. Then the **Critical** band in the strip → a reminder pack of all
12 drafts in one document. Say the line plainly:

> "One download instead of twelve compose windows. That is where the 15 hours
> actually comes from."

Open `/policy-check` in a tab. Two blocks: 22 boundary assertions written by hand,
and 28 more the page derives by reading the band tables back out of the Policy
file. Both green. Offer the proof: edit the Policy's 16–30 band to 16–29 in a text
editor and reload — the derived block goes red while the hand-written 22 stay
green, because the engine still scores day 30 as 2 and the bands now have a hole.

## The analysis questions (1 min — optional)

Type `ageing report`, then `what if we wait 30 days`.

1. The ageing table uses the Policy's own bands and shows value-weighted age.
2. The what-if keeps every invoice and every amount, and only moves the clock:
   Critical goes 12 → 20 and Rs 37,10,000 → Rs 58,36,000 in Critical.

> "Same book, thirty days of silence. Nothing new has to go wrong for that."

Then `who holds the most exposure` — the top five hold a third of the book.

Download **Board brief** (one page, markdown) and **Ageing report** (CSV) and say
both come from the same code as the answers on screen.

## The promise log (1 min — optional)

`score C020`, click **Log a promise to pay**, choose a date already past, save.

> "The score does not move — the Policy has no promise factor. What moves is the
> order: it now leads the follow-up list, and the next reminder quotes the broken
> promise back."

Then click **Log a contact** on the same customer, choose *disputed*:

> "Marking a dispute does not change the score either. It flags the row, and it
> drops out of ‘not contacted in 7 days’ so the clerk stops ringing a number that
> is waiting on a credit note."

## The public-sector answer (1 min — optional)

Click **Import a dataset…**, pick a small CSV with different headers (`Party Code`,
`Outstanding (INR)`, `Rating`), set the as-on date, and show the mapping the preview
guessed and the first rows scored at that date. Import, then ask `score ACME-01`.

> "Nothing about the demo data is hard-coded. It matched the columns, it asked me to
> confirm them, and it scored against the date I chose."

Say the limit plainly: the data is interchangeable, **the Policy is not** — a
different business still needs its own bands and actions, which is why the Policy file
and the check page are part of the deliverable.

## Close

> "15 hours a month saved at 150 invoices. The arithmetic is auditable, the
> privacy limit is known, and the human still signs off the Critical list."

## If a question comes you cannot answer

Ask the bot. If it is not in the files it replies *Please contact the Finance
Manager.* — say so, and that the refusal is deliberate.

## Do not

- Do not claim a discount figure.
- Do not say the data is live; it is a monthly extract.
- Do not let the register scroll to real-looking names; there are none.
- Do not open the what-if with "what if we wait" when the audience is short on time —
  it is the beat most likely to start an argument about forecasts. It is a clock
  projection, not a prediction: no new invoice is assumed to fall overdue.
