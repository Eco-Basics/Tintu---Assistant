import logging
import httpx

logger = logging.getLogger(__name__)

DDGS_URL = "https://api.duckduckgo.com/"


async def web_search(query: str, max_results: int = 3) -> list[dict]:
    """
    Lightweight web search via DuckDuckGo Instant Answer API.
    Returns a list of {title, snippet, url} dicts.
    For V1 this is a best-effort support tool, not core functionality.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                DDGS_URL,
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            data = r.json()

        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", ""),
                "snippet": data["AbstractText"],
                "url": data.get("AbstractURL", ""),
            })
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:60],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })
        return results[:max_results]
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return []
