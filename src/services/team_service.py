"""Reusable team data retrieval for Discord scouting commands."""

from src.services.faceit import get_team_details, get_team_stats, search_team
from src.services.faceit_client import FaceitClient
from src.core.analyzer import get_sorted_map_stats


async def get_team_scouting_data(
    client: FaceitClient, team_name: str, *, include_roster: bool = False
) -> dict | None:
    result = await search_team(client, team_name)
    items = result.get("items", [])
    if not items:
        return None
    team = items[0]
    team_id = team["team_id"]
    stats = await get_team_stats(client, team_id)
    details = await get_team_details(client, team_id) if include_roster else {}
    return {
        "team": team,
        "stats": stats,
        "map_stats": get_sorted_map_stats(stats),
        "members": details.get("members", []),
    }
