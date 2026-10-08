"""Player-specific normalization and Discord-sized pagination helpers."""

import re


_ESEA_SEASON_PATTERNS = (
    re.compile(r"\bESEA\s+(?:(?:LEAGUE|ADVANCED)\s+)?(?:SEASON\s*|S\s*)(\d{1,3})\b", re.IGNORECASE),
    # FACEIT ESEA divisions often use names such as "S59 EU Open10 A - Regular Season".
    re.compile(r"\bS(\d{1,3})\s+EU\s+OPEN10\b", re.IGNORECASE),
)


def extract_esea_season(name: str | None, organizer_name: str | None = None) -> int | None:
    """Extract an ESEA season number only from explicit ESEA or known FACEIT ESEA naming.

    The organizer name may qualify a generic competition title (for example,
    organizer "ESEA" plus tournament "Season 59"). Other bare season numbers
    and unrelated organizers are deliberately ignored.
    """
    title = str(name or "").strip()
    organizer = str(organizer_name or "").strip()
    combined = f"{organizer} {title}".strip()
    for pattern in _ESEA_SEASON_PATTERNS:
        match = pattern.search(combined)
        if match and (pattern is _ESEA_SEASON_PATTERNS[1] or re.search(r"\bESEA\b", combined, re.I)):
            return int(match.group(1))
    return None


def normalize_esea_history(
    history_names: list[str] | None,
    tournaments: list[dict] | None = None,
    organizers: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """Deduplicate recognized seasons and retain useful source competition names."""
    seasons: dict[int, set[str]] = {}
    for name in history_names or []:
        source_name = str(name or "").strip()
        number = extract_esea_season(source_name)
        if number is not None:
            seasons.setdefault(number, set()).add(source_name)

    organizer_names = organizers or {}
    for tournament in tournaments or []:
        if not isinstance(tournament, dict):
            continue
        name = str(tournament.get("name") or "").strip()
        organizer_id = str(tournament.get("organizer_id") or "")
        organizer = organizer_names.get(organizer_id, "")
        number = extract_esea_season(name, organizer)
        if number is not None:
            source = f"{organizer}: {name}" if organizer else name
            seasons.setdefault(number, set()).add(source)

    return [
        {"season": number, "sources": sorted(sources, key=str.casefold)}
        for number, sources in sorted(seasons.items(), reverse=True)
    ]


def collect_esea_competitions(
    history_names: list[str] | None,
    tournaments: list[dict] | None = None,
    organizers: dict[str, str] | None = None,
) -> list[str]:
    """Return only competition names explicitly tied to ESEA or its known division format."""
    entries: set[str] = set()
    organizer_names = organizers or {}
    for raw_name in history_names or []:
        name = str(raw_name or "").strip()
        if re.search(r"\bESEA\b", name, re.I) or _ESEA_SEASON_PATTERNS[1].search(name):
            entries.add(name)
    for tournament in tournaments or []:
        if not isinstance(tournament, dict):
            continue
        name = str(tournament.get("name") or "").strip()
        organizer = organizer_names.get(str(tournament.get("organizer_id") or ""), "")
        if re.search(r"\bESEA\b", f"{organizer} {name}", re.I) or _ESEA_SEASON_PATTERNS[1].search(name):
            entries.add(f"{organizer}: {name}" if organizer else name)
    return sorted(entries, key=str.casefold)


def chunk_lines(lines: list[str], max_chars: int = 3500) -> list[str]:
    """Pack every line into Discord-safe text pages without dropping content."""
    if max_chars < 1:
        raise ValueError("max_chars doit être supérieur à zéro")
    pages: list[str] = []
    current: list[str] = []
    current_size = 0
    for original in lines:
        line = str(original)
        pieces = [line[i:i + max_chars] for i in range(0, len(line), max_chars)] or [""]
        for piece in pieces:
            added_size = len(piece) + (1 if current else 0)
            if current and current_size + added_size > max_chars:
                pages.append("\n".join(current))
                current = []
                current_size = 0
                added_size = len(piece)
            current.append(piece)
            current_size += added_size
    if current:
        pages.append("\n".join(current))
    return pages
