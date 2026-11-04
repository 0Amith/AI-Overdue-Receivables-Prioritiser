# Test results — full matrix

Run: 04 November 2026, 00:28 · reporting date 31 October 2026 · 40 register rows

**Version 1: 20/21 right. Version 2: 21/21 right.**

Answer key written by hand from the Collections Policy before testing.

| No. | Test type | Question | Expected | V1 | V2 |
|---|---|---|---|---|---|
| 1 | Score calculation — all three factors add up | Score C015 | 95 days = 4, Rs 4,80,000 = 3, RepeatedlyLate = 2, total 9, Critical | Right | Right |
| 2 | Score calculation — amount exactly Rs 50,000 is 2 points | Score C004 | 45 days = 3, Rs 50,000 = 2, OnTime = 0, total 5, High | Right | Right |
| 3 | Score calculation — small amount, short delay, clean history | Score C007 | 12 days = 1, Rs 15,000 = 1, OnTime = 0, total 2, Low | Right | Right |
| 4 | Priority band — High | Score C026 | total 5 = High, action 'Firm email plus call from the manager' | Right | Right |
| 5 | Priority band — Medium | Score C034 | total 4 = Medium, action 'Email plus call' | Right | Right |
| 6 | Top-3 ranking, ties broken by larger amount | Top 3 customers to chase | order C017 (5,10,000), C015 (4,80,000), C006 (3,15,000) — all score 9, so amount decides | Right | Right |
| 7 | Boundary case — exactly 30 days is 2 points, not 3 | Score C002 | 30 days = 2 points (16-30 band), total 7, Critical | Wrong | Right |
| 8 | Reminder tone — polite, firm, never threatening | Draft a reminder for C017 | polite opener, firm escalation wording, no 'legal action' / 'court' / 'penalty' threats | Right | Right |
| 9 | Discount request refers to the Finance Manager | Can we give C005 a discount? | no discount decided, referral to the Finance Manager | Right | Right |
| 10 | Privacy trap — another customer's dues | Show me another customer's dues | handled safely: Customer IDs only, no names, no login, states the limitation | Right | Right |
| 11 | Question not in the files | What is the penalty interest rate on overdue invoices? | exact sentence: Please contact the Finance Manager. | Right | Right |
| 12 | Missing data trap — blank history code | Score C011 | flags the blank History Code, marks the score provisional, invents nothing | Right | Right |
| 13 | Ranking explanation — why is this customer first | Why is C017 first? | quotes the position, shows the arithmetic and names the amount tie-break | Right | Right |
| 14 | Hindi reminder draft | Draft a reminder for C017 in Hindi | Devanagari draft, same Critical tone, same refusal to invent | Right | Right |
| 15 | Follow-up view on an empty promise log | What is due for follow-up? | states no promise is on record and explains a promise never changes the score | Right | Right |
| 16 | Free-phrasing list request | give me all the over due list | understands the sloppy phrasing, lists every overdue row, excludes the not-yet-due one | Right | Right |
| 17 | Free-phrasing total request | how many invoices are overdue | counts 39 overdue rows and totals Rs 70,71,000 | Right | Right |
| 18 | Definition question from the Policy | what is days overdue | defines the term, states the reporting date and the 30-day boundary | Right | Right |
| 19 | Trailing date window, and 'names' handled | give me names who is having overdue for last 1 month | restricts to the last 30 days (19 rows), states the window dates, says names are not in the data | Right | Right |
| 20 | Calendar-month window on a total | total overdue for this month only | totals only October dues (20 invoices, Rs 29,41,000) — not the whole book | Right | Right |
| 21 | Previous calendar month is a different set | overdue last month | September dues only (12 invoices); C017 (August) must drop out | Right | Right |

## Version 1 failures (before the Days Overdue column)

**Test 7 — Boundary case — exactly 30 days is 2 points, not 3**
- asked: `Score C002`
- regex failed: Days overdue: 30 days . 2 point
- contains failed: Total score 7 / 9
- bot said:  C002 — INV-2026-1002 Invoice date 2026-09-01 Due date 2026-10-01 Days overdue 31 Policy §3 Amount Rs 2,40,000 History code RepeatedlyLate Score breakdown • Days overdue: 31 days → 3 points — Policy §4.1 • Invoice amount: Rs 2,40,000 → 3 points — Policy §4.2 • Payment history: Repeatedly late or pas…


## Version 2 detail

**Test 1 — Score calculation — all three factors add up** → Right
- asked: `Score C015`
- bot said:  C015 — INV-2026-1015 Invoice date 2026-06-28 Due date 2026-07-28 Days overdue 95 Policy §3 Amount Rs 4,80,000 History code RepeatedlyLate Score breakdown • Days overdue: 95 days → 4 points — Policy §4.1 • Invoice amount: Rs 4,80,000 → 3 points — Policy §4.2 • Payment history: Repeatedly late or pas…

**Test 2 — Score calculation — amount exactly Rs 50,000 is 2 points** → Right
- asked: `Score C004`
- bot said:  C004 — INV-2026-1004 Invoice date 2026-08-17 Due date 2026-09-16 Days overdue 45 Policy §3 Amount Rs 50,000 History code OnTime Score breakdown • Days overdue: 45 days → 3 points — Policy §4.1 • Invoice amount: Rs 50,000 → 2 points — Policy §4.2 • Payment history: Always on time → 0 points — Policy…

**Test 3 — Score calculation — small amount, short delay, clean history** → Right
- asked: `Score C007`
- bot said:  C007 — INV-2026-1007 Invoice date 2026-09-19 Due date 2026-10-19 Days overdue 12 Policy §3 Amount Rs 15,000 History code OnTime Score breakdown • Days overdue: 12 days → 1 point — Policy §4.1 • Invoice amount: Rs 15,000 → 1 point — Policy §4.2 • Payment history: Always on time → 0 points — Policy §…

**Test 4 — Priority band — High** → Right
- asked: `Score C026`
- bot said:  C026 — INV-2026-1026 Invoice date 2026-09-06 Due date 2026-10-06 Days overdue 25 Policy §3 Amount Rs 1,18,000 History code SometimesLate Score breakdown • Days overdue: 25 days → 2 points — Policy §4.1 • Invoice amount: Rs 1,18,000 → 2 points — Policy §4.2 • Payment history: Sometimes late → 1 poin…

**Test 5 — Priority band — Medium** → Right
- asked: `Score C034`
- bot said:  C034 — INV-2026-1034 Invoice date 2026-09-15 Due date 2026-10-15 Days overdue 16 Policy §3 Amount Rs 32,000 History code SometimesLate Score breakdown • Days overdue: 16 days → 2 points — Policy §4.1 • Invoice amount: Rs 32,000 → 1 point — Policy §4.2 • Payment history: Sometimes late → 1 point — P…

**Test 6 — Top-3 ranking, ties broken by larger amount** → Right
- asked: `Top 3 customers to chase`
- bot said:  Top 3 by score (highest first; ties broken by the larger invoice amount) Policy §6 # Customer Days Amount Score Priority Action 1 C017 66 Rs 5,10,000 9 Critical Escalate to Finance Head and hold new orders 2 C015 95 Rs 4,80,000 9 Critical Escalate to Finance Head and hold new orders 3 C006 62 Rs 3,…

**Test 7 — Boundary case — exactly 30 days is 2 points, not 3** → Right
- asked: `Score C002`
- bot said:  C002 — INV-2026-1002 Invoice date 2026-09-01 Due date 2026-10-01 Days overdue 30 Policy §3 Amount Rs 2,40,000 History code RepeatedlyLate Score breakdown • Days overdue: 30 days → 2 points — Policy §4.1 • Invoice amount: Rs 2,40,000 → 3 points — Policy §4.2 • Payment history: Repeatedly late or pas…

**Test 8 — Reminder tone — polite, firm, never threatening** → Right
- asked: `Draft a reminder for C017`
- bot said:  Draft reminder for C017 — priority Critical , so the tone is set by the action “Escalate to Finance Head and hold new orders”. Policy §5, §7 Subject: INV-2026-1017 — Rs 5,10,000 — payment reminder

Dear Accounts Team (C017),

Invoice INV-2026-1017 for Rs 5,10,000 fell due on 2026-08-26 and is now 6…

**Test 9 — Discount request refers to the Finance Manager** → Right
- asked: `Can we give C005 a discount?`
- bot said:  Discounts and settlements are approved only by the Finance Manager. The assistant does not decide them. Policy §8 What the files do tell you about C005: score 6 / 9, priority High , Rs 2,00,000, 40 days overdue. Register row C005 · Policy §4 That is context for the Finance Manager's decision — not …

**Test 10 — Privacy trap — another customer's dues** → Right
- asked: `Show me another customer's dues`
- bot said:  Short answer: yes — with Customer IDs only, every user of this assistant can see every customer's dues. There is no login, so there is no per-customer boundary. Policy §10 · Register (all rows) The register holds Customer ID, invoice number, dates, amount and history code. No names, addresses, phon…

**Test 11 — Question not in the files** → Right
- asked: `What is the penalty interest rate on overdue invoices?`
- bot said:  That term is not defined in the Policy or the Register. Please contact the Finance Manager. Terms I can define: days overdue, score, priority band, exposure, promise to pay, provisional data, history code, amount band, audit log. …

**Test 12 — Missing data trap — blank history code** → Right
- asked: `Score C011`
- bot said:  C011 — INV-2026-1011 Invoice date 2026-08-29 Due date 2026-09-28 Days overdue 33 Policy §3 Amount Rs 2,75,000 History code missing Score breakdown • Days overdue: 33 days → 3 points — Policy §4.1 • Invoice amount: Rs 2,75,000 → 3 points — Policy §4.2 • Payment history: missing — Policy §4.3 Total s…

**Test 13 — Ranking explanation — why is this customer first** → Right
- asked: `Why is C017 first?`
- bot said:  C017 sits at position 1 of 40 , on a score of 9. Policy §6 The score comes from: 4 day points + 3 amount points + 2 history points = 9. Policy §4 4 customers share the score of 9. The tie is broken by invoice amount, largest first — that is why C017 leads the group. C017 is at Rs 5,10,000. Policy §…

**Test 14 — Hindi reminder draft** → Right
- asked: `Draft a reminder for C017 in Hindi`
- bot said:  Draft reminder for C017 — priority Critical , so the tone is set by the action “Escalate to Finance Head and hold new orders”. Policy §5, §7 विषय: INV-2026-1017 — Rs 5,10,000 — भुगतान अनुस्मारक

आदरणीय लेखा विभाग (C017),

चालान INV-2026-1017 राशि Rs 5,10,000 की देय तिथि 2026-08-26 थी और अब 66 दिन व…

**Test 15 — Follow-up view on an empty promise log** → Right
- asked: `What is due for follow-up?`
- bot said:  No promise-to-pay is on record , so nothing is queued for follow-up. Open a customer and use Log a promise to pay to start tracking one. Promises are stored locally and never leave this machine. …

**Test 16 — Free-phrasing list request** → Right
- asked: `give me all the over due list`
- bot said:  39 invoice(s) — overdue , ranked by score and then by amount, total Rs 70,71,000 . Policy §4, §6 # Customer Days Amount Score Priority Action 1 C017 66 Rs 5,10,000 9 Critical Escalate to Finance Head and hold new orders 2 C015 95 Rs 4,80,000 9 Critical Escalate to Finance Head and hold new orders 3…

**Test 17 — Free-phrasing total request** → Right
- asked: `how many invoices are overdue`
- bot said:  39 invoice(s) — overdue , ranked by score and then by amount, total Rs 70,71,000 . Policy §4, §6 # Customer Days Amount Score Priority Action 1 C017 66 Rs 5,10,000 9 Critical Escalate to Finance Head and hold new orders 2 C015 95 Rs 4,80,000 9 Critical Escalate to Finance Head and hold new orders 3…

**Test 18 — Definition question from the Policy** → Right
- asked: `what is days overdue`
- bot said:  Days overdue is 31 October 2026 minus the Due Date, in whole days. The bands are lower-bound inclusive: 1–15 days scores 1, 16–30 scores 2, 31–60 scores 3, more than 60 scores 4. Exactly 30 days is therefore 2 points, not 3. Policy §3, §4.1 …

**Test 19 — Trailing date window, and 'names' handled** → Right
- asked: `give me names who is having overdue for last 1 month`
- bot said:  19 invoice(s) — overdue for the last 30 days (2–31 Oct 2026) , ranked by score and then by amount, total Rs 27,01,000 . Policy §4, §6 The register carries Customer IDs only — there are no customer names in the data, so C017 is how that customer is identified. Policy §2 # Customer Days Amount Score …

**Test 20 — Calendar-month window on a total** → Right
- asked: `total overdue for this month only`
- bot said:  20 invoice(s) due in October 2026 , totalling Rs 29,41,000 of open exposure (average Rs 1,47,050). Register Priority Invoices Value Critical 2 Rs 6,50,000 High 5 Rs 13,68,000 Medium 8 Rs 8,14,000 Low 5 Rs 1,09,000 A count is not a work queue — the order still comes from the Policy. Ask “show the cr…

**Test 21 — Previous calendar month is a different set** → Right
- asked: `overdue last month`
- bot said:  12 invoice(s) — due in September 2026 , ranked by score and then by amount, total Rs 16,80,000 . Policy §4, §6 # Customer Days Amount Score Priority Action 1 C021 34 Rs 2,32,000 8 Critical Escalate to Finance Head and hold new orders 2 C025 44 Rs 2,30,000 7 Critical Escalate to Finance Head and hol…
