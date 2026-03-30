import re
import logging
import httpx
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    # Strip <think>...</think> blocks
    text = _THINK_RE.sub("", text)
    # Also handle bare thinking before </think> (Ollama chat API omits opening tag)
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    return text.strip()


async def generate(
    prompt: str,
    system: str = "",
    model: str = OLLAMA_MODEL,
    timeout: int = 300,
) -> str:
    # Use /api/chat — think:false works correctly here (unlike /api/generate, see Ollama #14793)
    messages = []
    effective_system = f"/no_think\n{system}" if system else "/no_think"
    messages.append({"role": "system", "content": effective_system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "num_predict": 512,
            "presence_penalty": 1.5,
        },
    }

    try:
        logger.info(f"Ollama request start: model={model} prompt_len={len(prompt)}")
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            response.raise_for_status()
            raw = response.json().get("message", {}).get("content", "").strip()
            logger.info(f"Ollama response received: {len(raw)} chars")
            return _strip_thinking(raw)
    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        return "The model took too long to respond. Please try again."
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama")
        return "Cannot reach the language model. Is Ollama running?"
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return "Something went wrong with the language model."


async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
