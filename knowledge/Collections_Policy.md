# ABC Traders — Collections Policy (v1.0)

**Document:** Collections Policy — overdue receivables
**Owner:** Accounts Receivable / Finance Manager
**Effective:** 26 October 2026
**Reporting date for all ageing calculations:** 31 October 2026

## 1. Purpose

This policy fixes how overdue invoices are scored, ranked and chased. The scoring
rules are fixed so that every answer the receivables assistant gives can be
checked by hand. The assistant only **recommends**; Accounts Receivable owns the
output.

## 2. Scope

Applies to all open B2B invoices in the Receivables Register. Customers are
identified by Customer ID only (C001, C002, ...). No customer names are used.

## 3. Days overdue

Days overdue = **31 October 2026 − Due Date**, counted in whole days.

Bands are read as **lower bound inclusive**, so a boundary day scores in the
lower band:

- exactly 15 days overdue scores 1 point
- exactly 30 days overdue scores 2 points, **not** 3
- exactly 60 days overdue scores 3 points, **not** 4

## 4. Scoring table

### 4.1 Days overdue

| Factor | Rule | Points |
|---|---|---|
| Days overdue | 1–15 days | 1 |
| Days overdue | 16–30 days | 2 |
| Days overdue | 31–60 days | 3 |
| Days overdue | 60+ days (more than 60) | 4 |

### 4.2 Invoice amount

| Factor | Rule | Points |
|---|---|---|
| Invoice amount | Under Rs 50,000 | 1 |
| Invoice amount | Rs 50,000 to Rs 2,00,000 (both ends inclusive) | 2 |
| Invoice amount | Above Rs 2,00,000 | 3 |

An amount of exactly Rs 50,000 scores 2 points. An amount of exactly
Rs 2,00,000 scores 2 points.

### 4.3 Payment history

| Factor | Rule | Points |
|---|---|---|
| Payment history | Always on time (`OnTime`) | 0 |
| Payment history | Sometimes late (`SometimesLate`) | 1 |
| Payment history | Repeatedly late or past default (`RepeatedlyLate`) | 2 |

### 4.4 Total score

Total score = days overdue points + invoice amount points + payment history
points. The total is therefore between 2 and 9 for any invoice that is overdue.

An invoice that is not yet due scores 0 days points; its total is shown with a
"not yet due" note.

## 5. Priority bands and actions

| Total score | Priority | Action |
|---|---|---|
| 7 to 9 | Critical | Escalate to Finance Head and hold new orders |
| 5 to 6 | High | Firm email plus call from the manager |
| 3 to 4 | Medium | Email plus call |
| 1 to 2 | Low | Friendly email |

## 6. Ranking rule

Rank customers by **total score, highest first**. Where two customers have the
same score, the **larger invoice amount ranks higher**.

## 7. Reminder rules

- Reminders are polite and are never threatening.
- Every reminder states the invoice number, due date, days overdue, amount and
  the priority-driven action.
- Low priority: friendly reminder tone.
- Medium priority: polite but direct, with a call promised.
- High priority: firm, manager call named.
- Critical priority: firm, escalation to Finance Head and hold on new orders
  named.

## 8. Discounts and settlements

Any discount or settlement is **approved only by the Finance Manager**. The
assistant must not decide a discount or a settlement; it refers the question to
the Finance Manager.

## 9. Sources of truth

Only two sources may be used: this Policy and the Receivables Register. Every
answer cites its source as `Policy §n` or `Register row <Customer ID>`. If the
answer is not in these files the assistant replies exactly:

> Please contact the Finance Manager.

It does not guess.

## 10. Known limitations

- The register is a monthly extract as on 31 October 2026, not a live feed.
- English only.
- No login system, so any user of the assistant sees all Customer IDs.
