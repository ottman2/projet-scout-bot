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


async def get_full_team_stats(client: FaceitClient, team_name: str) -> dict | None:
    """Return raw and normalized team stats plus each roster member's player stats.

    The returned ``players`` entries contain the original roster member and a
    ``player_data`` object with the player's FACEIT profile, raw CS2 stats,
    normalized map stats, and the other fields supplied by the existing player
    scouting service. Missing player profiles are represented as ``None``.
    ``None`` is returned only when the team itself cannot be found.
    """
    from src.services.player_service import get_player_scouting_data

    team_data = await get_team_scouting_data(client, team_name, include_roster=True)
    if team_data is None:
        return None

    players = []
    for member in team_data.get("members") or []:
        nickname = member.get("nickname") if isinstance(member, dict) else None
        player_data = await get_player_scouting_data(client, nickname) if nickname else None
        players.append({
            "nickname": nickname,
            "roster_member": member,
            "player_data": player_data,
        })

    return {
        "team": team_data["team"],
        "team_stats": team_data["stats"],
        "team_map_stats": team_data["map_stats"],
        "players": players,
    }
