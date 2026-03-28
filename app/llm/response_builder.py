import logging
from app.llm.ollama_client import generate
from app.llm.prompts import SYSTEM_PROMPT
from app.memory.retrieval import retrieve_context
from app.llm.context_manager import ContextBudgetManager

logger = logging.getLogger(__name__)


async def build_answer(message: str, chat_id: int | None = None) -> str:
    """Answer with rolling history + active task injection."""
    if chat_id is None:
        return await generate(message, system=SYSTEM_PROMPT)
    ctx = ContextBudgetManager(chat_id)
    assembled = await ctx.assemble_context(message)
    prompt = message
    if assembled["history_block"]:
        prompt = f"{assembled['history_block']}Current message: {message}"
    if assembled["tasks_block"]:
        prompt = f"{prompt}\n\n{assembled['tasks_block']}"
    return await generate(prompt, system=SYSTEM_PROMPT)


async def build_retrieval_answer(message: str, chat_id: int | None = None) -> str:
    """Answer with memory retrieval + history + active task injection."""
    context = await retrieve_context(message)
    if context:
        base_prompt = f"Context from memory:\n{context}\n\nUser question: {message}"
    else:
        base_prompt = message
    if chat_id is None:
        return await generate(base_prompt, system=SYSTEM_PROMPT)
    ctx = ContextBudgetManager(chat_id)
    assembled = await ctx.assemble_context(message)
    prompt = base_prompt
    if assembled["history_block"]:
        prompt = f"{assembled['history_block']}Current message: {base_prompt}"
    if assembled["tasks_block"]:
        prompt = f"{prompt}\n\n{assembled['tasks_block']}"
    return await generate(prompt, system=SYSTEM_PROMPT)


async def build_compare_answer(message: str, chat_id: int | None = None) -> str:
    """Compare with prior context. History not injected here (comparison has its own context)."""
    from app.memory.comparison import compare_against_prior
    return await compare_against_prior(message)
