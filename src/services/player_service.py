"""Reusable player data retrieval for Discord commands."""

from src.core.analyzer import get_player_map_stats
from src.core.player_analyzer import collect_esea_competitions, normalize_esea_history
from src.services.faceit import get_full_player_profile
from src.services.faceit_client import FaceitClient, FaceitNotFoundError


async def get_player_scouting_data(
    client: FaceitClient, nickname: str, *, deep_history: bool = False
) -> dict | None:
    try:
        data = await get_full_player_profile(client, nickname, deep_history=deep_history)
        data["map_stats"] = get_player_map_stats(data.get("stats"))
        data["esea_seasons"] = normalize_esea_history(
            data.get("history_leagues"), data.get("tournaments"), data.get("organizers")
        )
        data["esea_competitions"] = collect_esea_competitions(
            data.get("history_leagues"), data.get("tournaments"), data.get("organizers")
        )
        return data
    except FaceitNotFoundError:
        return None
