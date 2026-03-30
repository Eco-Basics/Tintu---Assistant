import re
import logging
from app.llm.ollama_client import generate
from app.llm.prompts import CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

VALID_TYPES = {
    "answer",
    "capture_note",
    "create_task",
    "set_reminder",
    "create_routine",
    "project_update",
    "retrieval_query",
    "compare_context",
    "draft_reply",
    "daily_summary",
    "end_of_day_review",
    "update_preference",
    "list_tasks",
    "complete_task",
    "list_reminders",
    "search",
}

KEYWORD_MAP = {
    "create_task": [
        r"\badd.*task\b", r"\bcreate.*task\b", r"\bnew task\b",
        r"\bput.*on my list\b", r"\bto.do\b", r"\bneed to\b",
        r"\bi have to\b", r"\bremember to\b", r"\bdon't let me forget to\b",
    ],
    "set_reminder": [
        r"\bremind me\b", r"\bset.*reminder\b", r"\balert me\b",
        r"\bnotify me\b", r"\bping me\b",
        r"\bat \d+\s*(am|pm)\b", r"\bin \d+ (hour|minute|day)\b",
    ],
    "capture_note": [
        r"\bsave (this|that)\b", r"\bnote (this|that|down)\b",
        r"\bkeep (this|that)\b", r"\bcapture\b", r"\bjot\b",
        r"\bwrite (this|that) down\b", r"\bput (this|that) in.*inbox\b",
        r"\bstore (this|that)\b",
    ],
    "retrieval_query": [
        r"\bwhat did (i|we)\b", r"\bdo you remember\b",
        r"\bwhat was (the|my)\b", r"\bpull up\b",
        r"\bfind.*note\b", r"\blook up\b", r"\blast time\b",
        r"\bwhat('s| is) (the status|happening with)\b",
    ],
    "compare_context": [
        r"\bcompare\b", r"\bhas.*changed\b", r"\bdifference\b",
        r"\bconflict\b", r"\bvs\b", r"\bchanged since\b",
    ],
    "update_preference": [
        r"\bi prefer\b", r"\bi (always|usually|like to)\b",
        r"\bby default\b", r"\bset my preference\b",
        r"\bmy timezone\b", r"\bmy (morning|evening|daily) (time|routine)\b",
    ],
    "daily_summary": [
        r"\bdaily (summary|plan|brief|overview)\b",
        r"\bwhat('s| is| are) (my|the) plan(s)? (for today|today)\b",
        r"\bgive me.*today\b", r"\bsummarise.*today\b",
    ],
    "end_of_day_review": [
        r"\bend of day\b", r"\beod\b", r"\bwrap up\b",
        r"\bhow did (i|the day)\b", r"\bend.*day review\b",
        r"\bwhat did i (get done|accomplish|complete)\b",
    ],
    "list_tasks": [
        r"\bshow.*tasks\b", r"\blist.*tasks\b", r"\bmy tasks\b",
        r"\bwhat.*tasks\b", r"\bopen tasks\b", r"\bdue today\b",
        r"\bwhat('s| is) on my list\b",
    ],
    "complete_task": [
        r"\bdone (with|on)\b", r"\bfinished\b", r"\bcompleted\b",
        r"\bmark.*done\b", r"\btick.*off\b", r"\bcross.*off\b",
        r"\bi('ve| have) done\b", r"\bjust (did|finished|completed)\b",
    ],
    "search": [
        r"\bsearch\b", r"\bfind\b", r"\blook for\b",
    ],
    "draft_reply": [
        r"\bdraft\b", r"\bwrite.*message\b", r"\bcompose\b",
        r"\bhelp me.*write\b", r"\bprepare.*message\b",
    ],
    "create_routine": [
        r"\brecurring\b", r"\bevery (day|week|monday|morning|evening)\b",
        r"\bdaily routine\b", r"\bweekly routine\b", r"\bschedule.*routine\b",
    ],
}


def keyword_classify(text: str) -> str | None:
    text_lower = text.lower()
    for intent, patterns in KEYWORD_MAP.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return intent
    return None


async def classify(message: str) -> str:
    intent = keyword_classify(message)
    if intent:
        logger.debug(f"Keyword classified: {intent}")
        return intent

    prompt = CLASSIFICATION_PROMPT.format(message=message)
    response = await generate(prompt, timeout=120, num_predict=20)
    result = response.strip().lower()

    if result in VALID_TYPES:
        logger.debug(f"LLM classified: {result}")
        return result

    logger.warning(f"Classification fallback for: {message[:60]!r}")
    return "answer"
