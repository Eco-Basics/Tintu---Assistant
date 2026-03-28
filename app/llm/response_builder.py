from app.llm.ollama_client import generate
from app.llm.prompt_builder import build_system_prompt
from app.memory.retrieval import retrieve_context


async def build_answer(message: str) -> str:
    system = await build_system_prompt()
    return await generate(message, system=system)


async def build_retrieval_answer(message: str) -> str:
    context = await retrieve_context(message)
    if context:
        prompt = f"Context from memory:\n{context}\n\nUser question: {message}"
    else:
        prompt = message
    system = await build_system_prompt()
    return await generate(prompt, system=system)


async def build_compare_answer(message: str) -> str:
    from app.memory.comparison import compare_against_prior
    system = await build_system_prompt()
    return await compare_against_prior(message, system=system)
