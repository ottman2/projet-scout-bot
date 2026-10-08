from typing import Any


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


def get_sorted_map_stats(stats_data: dict | None) -> list[dict[str, Any]]:
    """Return valid 5v5 map segments ordered by match count, descending.

    Segments with invalid/missing counts are ignored; low-volume maps are kept
    for backwards compatibility so callers can apply their own threshold.
    """
    if not isinstance(stats_data, dict):
        return []
    segments = stats_data.get("segments")
    if not isinstance(segments, list):
        return []

    clean_stats = []
    for segment in segments:
        if not isinstance(segment, dict) or segment.get("mode") != "5v5":
            continue
        stats = segment.get("stats", {})
        if not isinstance(stats, dict):
            continue
        try:
            matches = int(stats.get("Matches", 0))
        except (TypeError, ValueError):
            continue
        try:
            winrate = int(float(stats.get("Win Rate %", 0)))
        except (TypeError, ValueError):
            winrate = 0
        clean_stats.append({
            "map": segment.get("label"),
            "matches": matches,
            "winrate": winrate,
        })
    return sorted(clean_stats, key=lambda item: item["matches"], reverse=True)


def get_player_map_stats(stats_data: dict | None) -> list[dict[str, Any]]:
    """Normalize a player's 5v5 map segments in match-count order."""
    if not isinstance(stats_data, dict) or not isinstance(stats_data.get("segments"), list):
        return []
    maps = []
    for segment in stats_data["segments"]:
        if not isinstance(segment, dict) or segment.get("mode") != "5v5" or segment.get("type") != "Map":
            continue
        map_stats = segment.get("stats", {})
        if not isinstance(map_stats, dict):
            continue
        try:
            matches = int(map_stats.get("Matches", "0"))
        except (TypeError, ValueError):
            continue
        if matches > 0:
            label = str(segment.get("label") or "Inconnu")
            map_record = {
                "name": label.replace("de_", "").capitalize(),
                "matches": matches,
                "winrate": map_stats.get("Win Rate %", "N/A"),
            }
            for kd_key in ("Average K/D Ratio", "K/D Ratio"):
                if kd_key in map_stats:
                    map_record["kd"] = map_stats[kd_key]
                    break
            maps.append(map_record)
    return sorted(maps, key=lambda item: (item["matches"], _numeric(item["winrate"])), reverse=True)
