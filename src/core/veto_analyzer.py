"""Deterministic map comparison for the first version of the VETO command."""

from __future__ import annotations

from typing import Any

FAVORABLE_THRESHOLD = 10.0
UNFAVORABLE_THRESHOLD = -10.0
KD_WEIGHT = 5.0  # A 0.10 K/D edge contributes only 0.5 score points.
# Current official pool supplied by the user; FACEIT calls D2 "Dust2".
OFFICIAL_MAP_POOL = ("D2", "Nuke", "Inferno", "Cache", "Anubis", "Ancient", "Mirage")
# GandaltF4's own playable/pick pool, kept separate from the official veto pool.
PICK_MAP_POOL = ("D2", "Nuke", "Cache", "Inferno")
_OFFICIAL_MAP_RANK = {name.casefold(): rank for rank, name in enumerate(OFFICIAL_MAP_POOL)}
_PICK_MAP_RANK = {name.casefold(): rank for rank, name in enumerate(PICK_MAP_POOL)}


def _display_map_name(label: str) -> str:
    normalized = label.strip().casefold().removeprefix("de_").replace("_", "").replace(" ", "")
    if normalized in {"d2", "dust2"}:
        return "D2"
    # Canonicalize common FACEIT labels while retaining maps outside our pool.
    known_maps = ("Nuke", "Cache", "Inferno", "Mirage", "Ancient", "Anubis", "Overpass", "Train", "Vertigo")
    return next((name for name in known_maps if normalized == name.casefold()), label.strip())


def _number(value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None and result < minimum or maximum is not None and result > maximum:
        return None
    return result


def _team_maps(payload: dict | None) -> dict[str, dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
        return {}
    maps: dict[str, dict] = {}
    for segment in payload["segments"]:
        if not isinstance(segment, dict) or segment.get("mode") != "5v5":
            continue
        label = segment.get("label")
        stats = segment.get("stats")
        if not isinstance(label, str) or not label.strip() or not isinstance(stats, dict):
            continue
        winrate = _number(stats.get("Win Rate %"), minimum=0, maximum=100)
        matches = _number(stats.get("Matches"), minimum=0)
        kd = next((_number(stats[k], minimum=0) for k in ("Average K/D Ratio", "K/D Ratio") if k in stats), None)
        map_name = _display_map_name(label)
        if map_name.casefold() not in _OFFICIAL_MAP_RANK:
            continue
        maps[map_name] = {
            "map": map_name, "winrate": winrate,
            "matches": int(matches) if matches is not None else None, "kd": kd,
        }
    return maps


def confidence_for(matches: int | None) -> tuple[str, float]:
    """Use the smaller team's sample: <10 low (0.5), 10-29 medium (0.75), 30+ high (1)."""
    if matches is None or matches < 10:
        return "faible", 0.5
    if matches < 30:
        return "moyenne", 0.75
    return "élevée", 1.0


def analyze_veto(our_stats: dict | None, opponent_stats: dict | None) -> list[dict]:
    ours, opponents = _team_maps(our_stats), _team_maps(opponent_stats)
    result = []
    # Keep every official map in the report, even when neither team has stats for it.
    for name in OFFICIAL_MAP_POOL:
        our, opponent = ours.get(name), opponents.get(name)
        base = {"map": name, "our": our, "opponent": opponent, "score": None, "confidence": "faible"}
        if not our or not opponent or our["winrate"] is None or opponent["winrate"] is None:
            base["classification"] = "insufficient_data"
            result.append(base)
            continue
        volume = min(x for x in (our["matches"], opponent["matches"]) if x is not None) if any(
            x is not None for x in (our["matches"], opponent["matches"])
        ) else None
        confidence, factor = confidence_for(volume)
        # WR is the primary signal. K/D is a small secondary signal only when both exist.
        kd_delta = our["kd"] - opponent["kd"] if our["kd"] is not None and opponent["kd"] is not None else 0.0
        score = ((our["winrate"] - opponent["winrate"]) + KD_WEIGHT * kd_delta) * factor
        base.update(score=score, confidence=confidence)
        base["classification"] = (
            "favorable" if score >= FAVORABLE_THRESHOLD else
            "unfavorable" if score <= UNFAVORABLE_THRESHOLD else "neutral"
        )
        result.append(base)
    return result


def recommend_pick(analysis: list[dict]) -> dict | None:
    candidates = [
        item for item in analysis
        if item["classification"] == "favorable" and item["map"].casefold() in _PICK_MAP_RANK
    ]
    return max(candidates, key=lambda x: (x["score"], _volume(x), -_PICK_MAP_RANK[x["map"].casefold()]), default=None)


def recommend_bans(analysis: list[dict], limit: int = 3) -> list[dict]:
    """Rank available ban candidates from most dangerous to least dangerous for us.

    Maps without comparable winrate data are omitted rather than assigned a made-up score.
    This is a shortlist for GandaltF4's three bans, not a BO veto simulation.
    """
    candidates = list(analysis)
    ordered = sorted(
        candidates,
        key=lambda x: (
            x["map"].casefold() in _PICK_MAP_RANK,  # maps outside our pool are first choice bans
            x["score"] is None,
            x["score"] if x["score"] is not None else float("inf"),
            -_volume(x),
            _OFFICIAL_MAP_RANK[x["map"].casefold()],
        ),
    )
    return ordered[:max(0, limit)]


def recommend_ban(analysis: list[dict]) -> dict | None:
    """Return the most statistically dangerous map when comparable data exists."""
    candidates = [item for item in analysis if item["score"] is not None]
    return min(candidates, key=lambda x: (x["score"], -_volume(x), _OFFICIAL_MAP_RANK[x["map"].casefold()]), default=None)


def _volume(item: dict) -> int:
    values = [side["matches"] for side in (item.get("our"), item.get("opponent")) if side and side.get("matches") is not None]
    return min(values) if values else 0
