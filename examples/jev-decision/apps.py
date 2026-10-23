"""Three toy apps, one per question type, plus the combined router. Pure policy over a Decision."""

from jevkit import Decision, QuestionSet, Uncalibrated


def spam_filter(decision: Decision, question_set: QuestionSet) -> str:  # Noul
    bar = question_set.bar("is_spam", "archive")
    if decision.yes("is_spam", bar):
        return "archive"
    if decision.no("is_spam", bar):
        return "keep"
    return "human"


def department_router(decision: Decision, question_set: QuestionSet) -> str:  # Choice
    match decision.choice("department", question_set.bar("department", "route")):
        case "billing" | "technical" | "sales" as team:
            return f"queue:{team}"
        case _:
            return "human"


def pager(decision: Decision, question_set: QuestionSet) -> bool:  # Score
    bar = question_set.bar("urgency", "page_manager")
    return decision.at_least("urgency", bar["level"], bar["p"])


def route(decision: Decision, question_set: QuestionSet) -> list[str]:
    try:
        if spam_filter(decision, question_set) == "archive":
            return ["archive"]
        actions = [department_router(decision, question_set)]
        if pager(decision, question_set):
            actions.append("page_manager")
        return actions
    except Uncalibrated:
        return ["human"]
