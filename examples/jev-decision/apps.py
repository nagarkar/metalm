"""Three toy apps, one per question type, plus the combined router. Pure policy over a Decision."""
from jevkit import Decision, QuestionSet, Uncalibrated

def spam_filter(d: Decision, qs: QuestionSet) -> str:          # Noul
    bar = qs.bar("is_spam", "archive")
    if d.yes("is_spam", bar): return "archive"
    if d.no("is_spam", bar):  return "keep"
    return "human"

def department_router(d: Decision, qs: QuestionSet) -> str:    # Choice
    match d.choice("department", qs.bar("department", "route")):
        case "billing" | "technical" | "sales" as team: return f"queue:{team}"
        case _:                                       return "human"

def pager(d: Decision, qs: QuestionSet) -> bool:               # Score
    b = qs.bar("urgency", "page_manager")
    return d.at_least("urgency", b["level"], b["p"])

def route(d: Decision, qs: QuestionSet) -> list[str]:
    try:
        if spam_filter(d, qs) == "archive": return ["archive"]
        out = [department_router(d, qs)]
        if pager(d, qs): out.append("page_manager")
        return out
    except Uncalibrated:
        return ["human"]
