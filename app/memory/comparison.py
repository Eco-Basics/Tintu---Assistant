from app.llm.ollama_client import generate
from app.memory.retrieval import retrieve_context

COMPARE_PROMPT = """Compare the new input below against the stored context.

New input:
{new_input}

Stored context:
{context}

Identify:
- What aligns with prior notes or decisions
- What contradicts or differs
- What is new information not previously captured

Be concise and structured."""


async def compare_against_prior(new_input: str, system: str = "") -> str:
    context = await retrieve_context(new_input)
    if not context:
        return "No prior context found to compare against."
    prompt = COMPARE_PROMPT.format(new_input=new_input, context=context)
    return await generate(prompt, system=system)
