import logging
import httpx
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def generate(
    prompt: str,
    system: str = "",
    model: str = OLLAMA_MODEL,
    timeout: int = 300,
) -> str:
    payload: dict = {"model": model, "prompt": f"/no_think {prompt}", "stream": False}
    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "").strip()
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
