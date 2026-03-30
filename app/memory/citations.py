def fmt_vault_citation(relative_path: str) -> str:
    return f"Source: vault/{relative_path}"


def fmt_db_citation(table: str, row_id: int) -> str:
    return f"Source: {table} #{row_id}"


def fmt_summary_citation(date_str: str) -> str:
    return f"Source: conversation summary ({date_str})"


def fmt_citations(sources: list[str]) -> str:
    if not sources:
        return ""
    return "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)
