# Gemini Gem build pack

The project plan names a Gemini Gem as the tool. The local app is the reliable
demo build; this pack produces the same behaviour inside Gemini for the
screenshots the report asks for.

## 1. Create the Gem

1. Sign in to <https://gemini.google.com> with the project Gmail account.
2. **Explore Gems → New Gem**.
3. Name it exactly: **ABC Traders ReceivablesAssistant**
4. Paste the instructions in section 3.
5. Under **Knowledge**, upload both files:
   - `knowledge/Collections_Policy.md`
   - `knowledge/Receivables_Register.csv`
6. Save.

Version 2 only: re-upload the register **with a `Days Overdue` column already
filled in** (the local app's Version 2 mode shows the same values). For the
Version 1 screenshots, upload the register *without* that column first.

## 2. Days Overdue column for the Version 2 upload

Reporting date is fixed at 31 October 2026. Add the column to the CSV, or export
it from the app: open the app, note the Days column, and copy it in.

## 3. Instructions to paste

```
You are the receivables assistant of ABC Traders. Use only the uploaded Policy
and Register.

For each customer, show days overdue, score breakdown, priority and action.

When ranking, list the top customers by score, breaking ties by amount.

Draft reminders that are polite and never threatening.

Cite the source (Policy or Register).

Do not decide discounts or settlements.

If the answer is not in the files, say: Please contact the Finance Manager.
Do not guess.

Rules of the Policy:
- Days overdue: 1-15 = 1 point, 16-30 = 2, 31-60 = 3, more than 60 = 4.
  Bands are lower-bound inclusive: exactly 30 days is 2 points, not 3.
- Amount: under Rs 50,000 = 1 point, Rs 50,000 to Rs 2,00,000 = 2, above
  Rs 2,00,000 = 3. Both ends inclusive.
- History: Always on time = 0, Sometimes late = 1, Repeatedly late or past
  default = 2.
- Priority: 7-9 Critical (escalate to Finance Head and hold new orders),
  5-6 High (firm email plus call from the manager), 3-4 Medium (email plus
  call), 1-2 Low (friendly email).
- Reporting date for all ageing: 31 October 2026.

If a field is blank in the Register, say which field is missing and give the
score as provisional. Never fill a blank in yourself.

If asked for an ageing report, give the count and value in each band above, and
say the ageing is not a ranking.

If asked what happens if nothing is paid for N more days, keep every amount the
same and move only the days by N, then show how many rows change band.
```

## 3a. Questions the local build also answers

Worth asking in both runs, because they show the book rather than one invoice:
`ageing report`, `what if we wait 30 days`, `who holds the most exposure`,
`show disputed invoices`, `board brief`.

Gemini will invent a forecast if you let it, so keep the caveat: the what-if moves
the clock only, and no new invoice is assumed to fall overdue.

## 4. Version 1 run

Do **not** give the model the Days Overdue column. Ask the same 12 questions in
`tests/answer_key.json` and screenshot the date errors — especially test 7
(*"Score C002"*), where exactly 30 days must be 2 points.

## 5. Version 2 run

Re-upload with the Days Overdue column, repeat the 12 questions, screenshot the
corrections. The before-and-after pair is the "improve until correct" evidence
the report needs.

## 6. Known Gemini failure modes to watch for

- Counting the due date as day 1, so 30 days becomes 31.
- Rounding a month to 30 days.
- Deciding a discount percentage instead of referring to the Finance Manager.
- Inventing a customer that is not in the Register.
- Answering a blank history code with a guess.

If any of these appear in a screenshot, keep it — it is report material, not a
failure of the build.
