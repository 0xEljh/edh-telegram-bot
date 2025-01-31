from html import escape


# Helper to truncate and escape names
def format_name(name: str, max_len: int = 15) -> str:
    escaped = escape(name)
    return escaped[: max_len - 1] + "…" if len(escaped) > max_len else escaped
