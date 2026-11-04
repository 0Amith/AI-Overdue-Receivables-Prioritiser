"""Natural-language understanding for the receivables assistant.

A small, deterministic scorer: normalise the sentence, expand synonyms, score
each intent by weighted pattern hits, and pull out the entities that narrow the
answer (priority, amount, days, missing data). No model, so the same sentence
always lands on the same intent — which is what keeps the test matrix meaningful.

When nothing scores well the parser says so, and the bot offers its closest
guesses instead of pretending to understand.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import engine

THRESHOLD = 2.0

SYNONYMS = [
    (r"\bover[\s-]?due\b", "overdue"),
    (r"\bover[\s-]?dues?\b", "overdue"),
    (r"\bdues?\b", "overdue"),
    (r"\boutstandings?\b", "overdue"),
    (r"\barrears?\b", "overdue"),
    (r"\bunpaid\b", "overdue"),
    (r"\breceivables?\b", "overdue"),
    (r"\bpending payments?\b", "overdue"),
    (r"\blate payers?\b", "overdue"),
    (r"\bclients?\b", "customer"),
    (r"\baccounts?\b", "customer"),
    (r"\bpart(?:y|ies)\b", "customer"),
    (r"\binvoices?\b", "invoice"),
    (r"\bbills?\b", "invoice"),
    (r"\bshow\b", "show"),
    (r"\bdisplay\b", "show"),
    (r"\bmail\b", "email"),
    (r"\breminders?\b", "reminder"),
    (r"\bchase\b", "chase"),
    (r"\bworse\b", "worst"),
    (r"\bhighest\b", "top"),
    (r"\bbiggest\b", "top"),
    (r"\blargest\b", "top"),
    # Hinglish, typed the way people actually type it. Amount units and the
    # "X se zyada" comparison are reordered here so the English amount parser
    # sees its own word order ("more than 50000").
    (r"\b(?:baaki|baki|baqi|bakaya|udhaar|udhar)\b", "overdue"),
    (r"\b(?:dikhao|dikha do|dikhaao|batao|bata do|bataao|bataiye|bataye)\b", "show"),
    (r"\b(?:kitna|kitne|kitni)\b", "how much"),
    (r"\b(?:kaun|kaunsa|kis)\b", "which customer"),
    (r"\bsabse pehle\b|\bsabse pehla\b", "first"),
    (r"\bsabse zyada\b|\bsabse zada\b|\bsabse jyada\b", "top"),
    (r"\bhazaar\b|\bhazar\b|\bthousand\b", "k"),
    (r"(\d[\d,.]*(?:\s*(?:k|l|lakh|lac|crore|cr))?)\s*se\s*(?:zyada|zada|jyada|jaada)", r"more than \1"),
    (r"(\d[\d,.]*(?:\s*(?:k|l|lakh|lac|crore|cr))?)\s*se\s*kam", r"under \1"),
    (r"\b(?:rupaye|rupay|rupees)\b", "rs"),
    (r"\b(?:kya hai|kya h|kya)\b", "what is"),
    (r"\b(?:tha|the|rahe|raha|hai|hain|wale|wala|wali)\b", ""),
]

# intent -> [(pattern, weight)]
SPECS: dict[str, list[tuple[str, float]]] = {
    "thanks": [(r"\bthanks?\b", 5), (r"\bthank you\b", 5), (r"\bappreciate\b", 4), (r"\bcheers\b", 4)],
    "bye": [(r"\bbye\b", 5), (r"\bgoodbye\b", 5), (r"\bsee you\b", 4)],
    "greeting": [(r"\bhi\b", 4), (r"\bhello\b", 4), (r"\bhey\b", 4), (r"\bgood (morning|afternoon|evening)\b", 4), (r"\bnamaste\b", 4)],
    "help": [(r"\bhelp\b", 4), (r"\bwhat can you do\b", 5), (r"\bhow do i use\b", 5), (r"\bcapabilit", 4), (r"\bmenu\b", 4), (r"\bwhat can i ask\b", 5)],
    "meta": [(r"\bwhat files?\b", 5), (r"\bwhich files?\b", 5), (r"\bwhere does the data\b", 5), (r"\bhow do you calculate\b", 5), (r"\bhow are you built\b", 5), (r"\bwho are you\b", 5), (r"\bwhat model\b", 5), (r"\bare you (an? )?(ai|bot|llm)\b", 5), (r"\bwhat data\b", 4)],
    "privacy": [(r"\banother customer\b", 6), (r"\bother customer\b", 6), (r"\bprivacy\b", 5), (r"\blogin\b", 4), (r"\bwhose data\b", 5), (r"\bsee others?\b", 5)],
    "discount": [(r"\bdiscounts?\b", 6), (r"\bsettle\b", 5), (r"\bsettlements?\b", 5), (r"\brebates?\b", 4), (r"\bwrite[\s-]?offs?\b", 5)],
    "reminder": [(r"\breminder\b", 5), (r"\bdraft\b", 4), (r"\bemail\b", 4), (r"\bletter\b", 4), (r"\bnudge\b", 4), (r"\bcompose\b", 4), (r"\bask for payment\b", 5)],
    "followup": [(r"\bfollow[\s-]?ups?\b", 6), (r"\bpromise[sd]?\b", 5), (r"\bcall[\s-]?backs?\b", 4), (r"\bbroken\b", 4)],
    "compare": [(r"\bcompare\b", 6), (r"\bversus\b", 5), (r"\bvs\b", 5), (r"\bdifference between\b", 5)],
    "export": [(r"\bexport\b", 5), (r"\bdownload\b", 5), (r"\bcsv\b", 5), (r"\bspreadsheet\b", 4), (r"\bexcel\b", 4)],
    "rank": [(r"\btop\b", 5), (r"\brank", 5), (r"\bworst\b", 5), (r"\bprioriti[sz]e\b", 5), (r"\bpriority order\b", 5), (r"\bwho should (we|i) chase\b", 5), (r"\bchase first\b", 5), (r"\bfirst\s+chase\b", 5), (r"\bwho owes\b", 6), (r"\bwho has the most\b", 6), (r"\bfirst\b", 2)],
    "explain": [(r"\bwhy\b", 5), (r"\bhow did you rank\b", 5), (r"\bexplain (the )?(position|ranking|score)\b", 5)],
    "aggregate": [(r"\bhow many\b", 5), (r"\bhow much\b", 5), (r"\btotal\b", 5), (r"\bsum\b", 4), (r"\bexposure\b", 5), (r"\bcount\b", 4), (r"\bvalue of\b", 4)],
    "listing": [(r"\blist\b", 4), (r"\ball\b", 3), (r"\bevery(one|body)?\b", 4), (r"\bshow\b", 2), (r"\bgive me\b", 3), (r"\bwhich customers?\b", 4), (r"\bwhich invoices?\b", 4), (r"\boverdue\b", 3), (r"\bsee\b", 1), (r"\bany\b", 2), (r"\binvoice\b", 1)],
    "definition": [(r"\bwhat is a? ?\b", 6), (r"\bwhat are\b", 5), (r"\bmeaning of\b", 5), (r"\bdefine\b", 5), (r"\bstand for\b", 5), (r"\bexplain\b", 3)],
    "score": [(r"\bscore\b", 4), (r"\bbreakdown\b", 4), (r"\bpoints?\b", 3), (r"\bband\b", 3), (r"\bpriority of\b", 4), (r"\bdetail", 4)],
    "policy": [(r"\bpolicy\b", 5), (r"\brules?\b", 4), (r"\bscoring\b", 5), (r"\bbands?\b", 4), (r"\bhow many points\b", 5)],
    "aging": [(r"\bage?ing\b", 7), (r"\bage analysis\b", 7), (r"\bage profile\b", 7), (r"\bhow old\b", 6), (r"\bbuckets?\b", 4), (r"\bband analysis\b", 5)],
    "concentration": [(r"\bconcentration\b", 8), (r"\blargest accounts?\b", 6), (r"\bbiggest (accounts?|customers?)\b", 6), (r"\bwho (holds|carries|has) the (most|largest|biggest)\b", 7), (r"\bmost exposure\b", 6), (r"\bhow much .* (one|single) customer\b", 6), (r"\bdependen", 5)],
    "board": [(r"\bboard\b", 6), (r"\bbrief\b", 6), (r"\bmonth[\s-]?end\b", 6), (r"\bmanagement summary\b", 6), (r"\bpack\b", 3)],
    "whatif": [(r"\bwhat if\b", 8), (r"\bif nothing\b", 7), (r"\bif we (wait|do nothing|leave)\b", 7), (r"\bdo nothing\b", 6), (r"\bcost of delay\b", 7), (r"\bsimulat", 6), (r"\b(from|in) \d{1,3} (more )?days\b", 4)],
    "dispute": [(r"\bdisput", 7), (r"\bon hold\b", 4), (r"\bcontested\b", 4)],
}

DEFINITION_TOPICS = [
    (r"\b(days? overdue|overdue days|ageing)\b", "days"),
    (r"\b(score|scoring|points?)\b", "score"),
    (r"\b(priority|band|critical|escalat)\b", "priority"),
    (r"\b(exposure)\b", "exposure"),
    (r"\b(promise|promised)\b", "promise"),
    (r"\b(missing data|provisional|blank)\b", "missing"),
    (r"\b(history|payment record)\b", "history"),
    (r"\b(amount band|invoice amount)\b", "amount"),
    (r"\b(audit)\b", "audit"),
    (r"\b(worklist|reminder pack)\b", "exports"),
]

CLOSEST = {
    "listing": "Show all overdue customers",
    "aggregate": "How many are critical?",
    "rank": "Top 3 customers to chase",
    "definition": "What is days overdue?",
    "score": "Score C002",
}


@dataclass
class Query:
    text: str
    intent: str = "unknown"
    scores: dict[str, float] = field(default_factory=dict)
    customers: list[str] = field(default_factory=list)
    priority: str | None = None
    amount_gt: int | None = None
    amount_lt: int | None = None
    days_gt: int | None = None
    days_lt: int | None = None
    due_from: date | None = None
    due_to: date | None = None
    window_label: str | None = None
    mentions_names: bool = False
    top_n: int | None = None
    extra_days: int | None = None
    only_missing: bool = False
    only_not_due: bool = False
    only_disputed: bool = False
    not_contacted_days: int | None = None
    topic: str | None = None
    wants_hindi: bool = False

    @property
    def known(self) -> bool:
        return self.intent != "unknown"

    @property
    def best_guess(self) -> str | None:
        for name, score in sorted(self.scores.items(), key=lambda kv: -kv[1]):
            if score >= 1 and name in CLOSEST:
                return CLOSEST[name]
        return None


def normalise(text: str) -> str:
    low = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    low = re.sub(r"[^a-z0-9\s'./₹+-]", " ", low)
    for pattern, replacement in SYNONYMS:
        low = re.sub(pattern, replacement, low)
    return re.sub(r"\s+", " ", low).strip()


def _number(raw: str) -> int | None:
    """Parse 50000, 50,000, 50k, 1.5 lakh, 2 l."""
    token = raw.replace(",", "").strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(k|l|lakh|lac|crore|cr)?$", token)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit == "k":
        value *= 1_000
    elif unit in ("l", "lakh", "lac"):
        value *= 100_000
    elif unit in ("crore", "cr"):
        value *= 10_000_000
    return int(value)


AMOUNT_GT = re.compile(r"\b(?:over|above|more than|greater than|exceeding|at least|>=?)\s*(?:rs\.?|₹)?\s*([\d,.]+\s*(?:k|l|lakh|lac|crore|cr)?)")
AMOUNT_LT = re.compile(r"\b(?:under|below|less than|smaller than|cheaper than|up to|<=?)\s*(?:rs\.?|₹)?\s*([\d,.]+\s*(?:k|l|lakh|lac|crore|cr)?)")
DAYS_GT = re.compile(r"\b(\d{1,3})\s*\+\s*days?\b|\b(\d{1,3})\s*\+\b")
DAYS_LT = re.compile(r"\b(?:under|below|less than|within|up to)\s*(\d{1,3})\s*days?\b")
PRIORITY_WORDS = [
    (r"\bcritical\b", "Critical"),
    (r"\bhigh\b", "High"),
    (r"\bmedium\b", "Medium"),
    (r"\blow\b", "Low"),
]

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return first, nxt - timedelta(days=1)


def _fmt_window(start: date, end: date) -> str:
    if start == end:
        return f"{start.day} {MONTHS_SHORT[start.month - 1]} {start.year}"
    if start.month == end.month:
        return f"{start.day}–{end.day} {MONTHS_SHORT[start.month - 1]} {start.year}"
    return (
        f"{start.day} {MONTHS_SHORT[start.month - 1]} – "
        f"{end.day} {MONTHS_SHORT[end.month - 1]} {end.year}"
    )


def _window(low: str, q: "Query") -> None:
    """Date windows: "this month", "last month", "past 30 days", "in September"."""
    today = engine.REPORT_DATE

    m = re.search(r"\b(?:last|past|previous|trailing)\s+(\d{1,2})\s*(day|week|month)s?\b", low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        span = n * {"day": 1, "week": 7, "month": 30}[unit]
        q.due_from = today - timedelta(days=span - 1)
        q.due_to = today
        q.window_label = f"overdue for the last {span} days"
        return

    m = re.search(r"\b(more than|over|beyond|longer than)\s+(a|one|1)\s+month\b", low)
    if m:
        q.due_to = today - timedelta(days=31)
        q.window_label = "overdue for more than a month"
        return
    m = re.search(r"\b(more than|over|beyond|longer than)\s+(\d{1,3})\s+days?\b", low)
    if m:
        q.due_to = today - timedelta(days=int(m.group(2)) + 1)
        q.window_label = f"overdue for more than {m.group(2)} days"
        return

    if re.search(r"\b(this|current)\s+month\b", low):
        q.due_from, q.due_to = _month_bounds(today.year, today.month)
        q.window_label = f"due in {today.strftime('%B %Y')}"
        return
    if re.search(r"\b(last|previous)\s+month\b", low):
        month = today.month - 1 or 12
        year = today.year if today.month > 1 else today.year - 1
        q.due_from, q.due_to = _month_bounds(year, month)
        q.window_label = f"due in {date(year, month, 1).strftime('%B %Y')}"
        return

    if re.search(r"\b(this|current)\s+week\b", low):
        q.due_from, q.due_to = today - timedelta(days=6), today
        q.window_label = "overdue in the last 7 days"
        return
    if re.search(r"\b(last|previous)\s+week\b", low):
        q.due_from, q.due_to = today - timedelta(days=13), today - timedelta(days=7)
        q.window_label = "overdue 8–14 days ago"
        return

    for index, name in enumerate(MONTH_NAMES, start=1):
        if re.search(rf"\b{name}\b", low):
            q.due_from, q.due_to = _month_bounds(today.year, index)
            q.window_label = f"due in {date(today.year, index, 1).strftime('%B %Y')}"
            return


def parse(message: str, resolver=None) -> Query:
    """Read a sentence into a Query.

    `resolver` is an optional callable(low) -> list of customer IDs. The app passes
    one that knows the loaded dataset, so any ID scheme works; without it the
    shipped C001-style pattern is used.
    """
    low = normalise(message)
    q = Query(text=message)
    if not low:
        return q

    if resolver is not None:
        q.customers = resolver(low)
    else:
        q.customers = sorted({f"C{int(n):03d}" for n in re.findall(r"\bc\s?-?(\d{1,3})\b", low)})
    q.wants_hindi = bool(re.search(r"\bhindi\b", low))
    q.only_missing = bool(re.search(r"\b(missing|blank|incomplete|provisional)\b", low))
    q.only_not_due = bool(re.search(r"\bnot yet due\b|\bnot due\b", low))

    for pattern, name in PRIORITY_WORDS:
        if re.search(pattern, low):
            q.priority = name
            break

    m = AMOUNT_GT.search(low)
    if m:
        q.amount_gt = _number(m.group(1))
    m = AMOUNT_LT.search(low)
    if m:
        q.amount_lt = _number(m.group(1))

    m = DAYS_GT.search(low)
    if m:
        q.days_gt = int(m.group(1) or m.group(2))
    m = DAYS_LT.search(low)
    if m:
        q.days_lt = int(m.group(1))

    q.mentions_names = bool(re.search(r"\bnames?\b", low))
    _window(low, q)

    m = re.search(r"\b(?:wait|waits|waiting|delay|slip)\s*(\d{1,3})\s*(day|week|month)s?\b", low) or re.search(
        r"\b(?:in|after|for|from)\s*(\d{1,3})\s*(more\s*)?(day|week|month)s?\b", low
    )
    if m:
        unit = m.group(3) if m.lastindex and m.lastindex >= 3 else "day"
        q.extra_days = int(m.group(1)) * {"day": 1, "week": 7, "month": 30}.get(unit or "day", 1)

    q.only_disputed = bool(re.search(r"\bdisput|contested\b|\bon hold\b", low))
    m = re.search(r"\bnot (?:contacted|called|chased)\b(?:\s+(?:in|for))?\s*(\d{1,2})\s*days?\b", low)
    if m:
        q.not_contacted_days = int(m.group(1))

    m = re.search(r"\btop\s*(\d{1,2})\b", low) or re.search(r"\b(\d{1,2})\s*(?:customers|invoices)\b", low)
    if m:
        q.top_n = max(1, min(10, int(m.group(1))))

    for pattern, topic in DEFINITION_TOPICS:
        if re.search(pattern, low):
            q.topic = topic
            break

    for intent, patterns in SPECS.items():
        score = 0.0
        for pattern, weight in patterns:
            if re.search(pattern, low):
                score += weight
        if score:
            q.scores[intent] = score

    q.intent = _decide(q, low)
    return q


def _decide(q: Query, low: str) -> str:
    s = q.scores
    has_cid = bool(q.customers)
    many_cids = len(q.customers) > 1

    # Things that are unambiguous on their own.
    if s.get("thanks", 0) >= 5 and len(low.split()) <= 4:
        return "thanks"
    if s.get("bye", 0) >= 4 and len(low.split()) <= 4:
        return "bye"
    if s.get("meta", 0) >= 4:
        return "meta"
    if s.get("privacy", 0) >= 4 and not has_cid:
        return "privacy"
    if many_cids or s.get("compare", 0) >= 5:
        return "compare" if (many_cids or s.get("compare", 0) >= 5) else "unknown"
    if s.get("followup", 0) >= 5 and not has_cid:
        # "what is a promise to pay" is a definition; "what is due for follow-up" is the log.
        return "definition" if s.get("definition", 0) > s.get("followup", 0) else "followup"
    if s.get("export", 0) >= 5:
        return "export"
    if s.get("board", 0) >= 6:
        return "board"
    if s.get("whatif", 0) >= 6 or (s.get("whatif", 0) >= 4 and q.extra_days and not q.not_contacted_days):
        return "whatif"
    if s.get("aging", 0) >= 6:
        return "aging"
    if s.get("concentration", 0) >= 5:
        return "concentration"
    if s.get("discount", 0) >= 5:
        return "discount"
    if s.get("reminder", 0) >= 4 and has_cid:
        return "reminder"
    if s.get("explain", 0) >= 4 and has_cid:
        return "explain"
    # A definition ("what is exposure") beats a list, unless the sentence also asks
    # for a total ("what is the total overdue amount") — then the total wins.
    if s.get("definition", 0) >= 3 and (q.topic or s.get("aggregate", 0) < 4):
        return "definition"
    if s.get("aggregate", 0) >= 4 and s.get("listing", 0) < 4:
        return "aggregate"
    if s.get("rank", 0) >= 4 and not has_cid:
        return "rank"
    if has_cid and s.get("score", 0) >= 3:
        return "score"
    if s.get("definition", 0) >= 3:
        return "definition"
    if s.get("listing", 0) >= 2:
        return "listing"
    if s.get("definition", 0) >= 2:
        return "definition"
    # A bare filter ("over 60 days", "the low ones", "last week") is a list request.
    if q.priority or q.days_gt is not None or q.days_lt is not None or q.amount_gt is not None or q.amount_lt is not None:
        return "listing"
    if q.only_missing or q.only_not_due:
        return "listing"
    if q.due_from or q.due_to:
        return "listing"
    if q.not_contacted_days or q.only_disputed:
        return "listing"
    if has_cid:
        return "score"
    if s.get("help", 0) >= 3:
        return "help"
    if s.get("greeting", 0) >= 3:
        return "greeting"
    if s.get("policy", 0) >= 4:
        return "policy"
    if s.get("aggregate", 0) >= 3:
        return "aggregate"
    if s.get("rank", 0) >= 3:
        return "rank"
    return "unknown"
