# Feature test results

Run: 04 November 2026, 00:11 · throwaway store under .tmp/ · register and state/ untouched

**35/35 pass.**

| Case | Asked | Result | Note |
|---|---|---|---|
| ageing uses the Policy bands | `ageing report` | pass | band table and weighted age present |
| ageing totals match the register | `ageing report` | pass | 60+ share reported |
| cost of delay re-bands on the clock | `what if we wait 30 days` | pass | crossings reported |
| cost of delay respects the asked horizon | `what if we wait 10 days` | pass | horizon echoed |
| concentration names the largest accounts | `who holds the most exposure` | pass | share and IDs present |
| concentration is not called a ranking | `who holds the most exposure` | pass | caveat present |
| board brief is offered | `board brief` | pass | brief answer |
| dispute filter is empty at first | `show disputed invoices` | pass | empty window handled |
| dispute filter finds the marked row | `show disputed invoices` | pass | only the disputed row listed |
| dispute is excluded from the cooldown list | `not contacted in 7 days` | pass | both contacted rows absent |
| customer detail shows the last contact | `score C026` | pass | contact line rendered |
| boundary proximity is explained | `why is C001 ranked there` | pass | nearest edge named |
| Hinglish list request is understood | `saari overdue list dikhao` | pass | listing |
| Hinglish amount filter is understood | `50 hazaar se zyada wale` | pass | amount_gt 50000 |
| Hinglish rank request is understood | `kaun sabse pehle chase karna hai` | pass | intent ranking |
| Hinglish total request is understood | `total baki kitna hai` | pass | aggregate intent |
| unknown definition still refuses exactly | `what is the weather like` | pass | refusal sentence intact |
| discount questions still defer | `can we offer a discount` | pass | refers to the Finance Manager |
| policy-derived cases all pass | `policy self-check` | pass | 28 derived cases, 28 pass |
| hand-written cases all pass | `policy self-check` | pass | 22/22 |
| worklist carries the contact columns | `worklist export` | pass | header and value present |
| ageing export sums to the book | `ageing export` | pass | total row equals the register |
| an edited Policy turns the derived check red | `policy drift` | pass | drift caught |
| foreign headers are recognised | `import path` | pass | amount column matched through 'Outstanding (INR)' |
| required columns are reported missing | `import path` | pass | Due Date and Amount flagged |
| duplicate IDs are called out before import | `import path` | pass | duplicate warning |
| comma amounts and text dates parse | `import path` | pass | parsed |
| duplicate rows fold into one customer | `import path` | pass | amounts added, earliest due date kept |
| the as-on date drives the day count | `import path` | pass | 71 and -15 days |
| the shipped register returns to its own date | `import path` | pass | date cleared |
| a foreign ID can be asked about | `score ACME-01` | pass | routed and answered |
| a slashed ID can be asked about | `score S/1042` | pass | routed and answered |
| an unknown ID is refused, not invented | `score ZZZ-9` | pass | no invented customer |
| the queue ranks on the Policy, not on length | `top 3 customers to chase` | pass | S/1042 leads |
| the shipped register is unaffected | `score C002` | pass | C002 still resolves |
