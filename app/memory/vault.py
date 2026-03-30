import logging
from pathlib import Path
from app.config import VAULT_PATH

logger = logging.getLogger(__name__)

VAULT_DIRS = [
    "inbox", "daily", "projects", "decisions",
    "snippets", "routines", "references", "archive",
]


async def ensure_vault_structure():
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    for d in VAULT_DIRS:
        (VAULT_PATH / d).mkdir(exist_ok=True)
    logger.info(f"Vault ready at {VAULT_PATH}")


def write_inbox(content: str, timestamp: str) -> Path:
    slug = timestamp.replace(":", "-").replace(" ", "_")
    path = VAULT_PATH / "inbox" / f"{slug}.md"
    path.write_text(
        f"---\ncaptured: {timestamp}\n---\n\n{content}\n",
        encoding="utf-8",
    )
    return path


def read_inbox_recent(n: int = 10) -> list[dict]:
    inbox = VAULT_PATH / "inbox"
    files = sorted(inbox.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:n]
    return [{"path": str(f), "content": f.read_text(encoding="utf-8")} for f in files]


def read_daily(date_str: str) -> str | None:
    path = VAULT_PATH / "daily" / f"{date_str}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None


def write_daily(date_str: str, content: str) -> Path:
    path = VAULT_PATH / "daily" / f"{date_str}.md"
    path.write_text(content, encoding="utf-8")
    return path


def append_daily(date_str: str, content: str) -> Path:
    path = VAULT_PATH / "daily" / f"{date_str}.md"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing.rstrip() + "\n\n" + content + "\n", encoding="utf-8")
    else:
        path.write_text(f"# {date_str}\n\n{content}\n", encoding="utf-8")
    return path


def write_decision(date_str: str, title: str, content: str) -> Path:
    slug = title.lower().replace(" ", "-")[:50]
    path = VAULT_PATH / "decisions" / f"{date_str}-{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


def ensure_project_vault(slug: str) -> Path:
    path = VAULT_PATH / "projects" / slug
    path.mkdir(parents=True, exist_ok=True)
    for filename in ["overview.md", "tasks.md", "notes.md", "decisions.md", "phase.md"]:
        p = path / filename
        if not p.exists():
            section = filename.replace(".md", "").title()
            p.write_text(f"# {section}\n\n", encoding="utf-8")
    return path


def search_vault(query: str, max_results: int = 10) -> list[dict]:
    query_lower = query.lower()
    results = []
    for f in VAULT_PATH.rglob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
            if query_lower in text.lower():
                for line in text.splitlines():
                    if query_lower in line.lower():
                        results.append({
                            "path": str(f.relative_to(VAULT_PATH)),
                            "snippet": line.strip()[:150],
                        })
                        break
        except Exception:
            continue
        if len(results) >= max_results:
            break
    return results
