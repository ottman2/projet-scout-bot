"""FACEIT data retrieval for VETO analysis."""

from src.core.veto_analyzer import analyze_veto
from src.services.team_service import get_team_scouting_data


async def get_veto_analysis(client, opponent_name: str) -> dict | None:
    our_data = await get_team_scouting_data(client, "GandaltF4")
    if not our_data:
        return {"error": "Équipe GandaltF4 introuvable sur FACEIT."}
    opponent_data = await get_team_scouting_data(client, opponent_name)
    if not opponent_data:
        return None
    return {
        "our_team": our_data["team"],
        "opponent_team": opponent_data["team"],
        "maps": analyze_veto(our_data.get("stats"), opponent_data.get("stats")),
    }
