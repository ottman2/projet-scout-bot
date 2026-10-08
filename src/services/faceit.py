"""Thin FACEIT Data API v4 accessors used by scouting services."""

import logging
import re

from src.services.faceit_client import (
    FaceitAPIError,
    FaceitAuthenticationError,
    FaceitClient,
    FaceitRateLimitError,
)


logger = logging.getLogger(__name__)


async def _get_optional_data(client: FaceitClient, endpoint: str, *, params: dict | None = None) -> dict:
    try:
        return await client.get(endpoint, params=params, allow_not_found=True)
    except (FaceitAuthenticationError, FaceitRateLimitError):
        raise
    except FaceitAPIError as exc:
        logger.warning("Optional FACEIT data unavailable for %s (HTTP %s)", endpoint, exc.status)
        return {}


async def search_team(client: FaceitClient, team_name: str) -> dict:
    return await client.get("/search/teams", params={"nickname": team_name, "game": "cs2", "limit": 1})


async def get_team_stats(client: FaceitClient, team_id: str) -> dict:
    return await client.get(f"/teams/{team_id}/stats/cs2", allow_not_found=True)


async def get_team_details(client: FaceitClient, team_id: str) -> dict:
    return await client.get(f"/teams/{team_id}", allow_not_found=True)


async def _get_all_items(
    client: FaceitClient,
    endpoint: str,
    *,
    base_params: dict | None = None,
    page_size: int = 100,
) -> list[dict]:
    """Read all available pages from a FACEIT list endpoint."""
    result: list[dict] = []
    offset = 0
    seen_pages: set[tuple[str, ...]] = set()
    while True:
        params = {**(base_params or {}), "offset": offset, "limit": page_size}
        page = await _get_optional_data(client, endpoint, params=params)
        items = page.get("items", [])
        if not isinstance(items, list) or not items:
            break
        signature = tuple(
            str(item.get("tournament_id") or item.get("team_id") or item.get("id") or repr(item))
            for item in items
        )
        if signature in seen_pages:
            break
        seen_pages.add(signature)
        result.extend(item for item in items if isinstance(item, dict))
        next_offset = offset + len(items)
        if next_offset <= offset or len(items) < page_size:
            break
        offset = next_offset
    return result


async def get_full_player_profile(
    client: FaceitClient, nickname: str, *, deep_history: bool = False
) -> dict:
    player_data = await client.get("/players", params={"nickname": nickname})
    player_id = player_data.get("player_id")
    if not player_id:
        return {"profile": player_data, "stats": {}, "teams": [], "tournaments": [], "championships": [], "history_leagues": []}

    stats_data = await _get_optional_data(client, f"/players/{player_id}/stats/cs2")
    if deep_history:
        teams = await _get_all_items(client, f"/players/{player_id}/teams")
        tournaments = await _get_all_items(client, f"/players/{player_id}/tournaments")
    else:
        teams_data = await _get_optional_data(client, f"/players/{player_id}/teams")
        tournament_data = await _get_optional_data(
            client, f"/players/{player_id}/tournaments", params={"limit": 50}
        )
        teams = teams_data.get("items", [])
        tournaments = tournament_data.get("items", [])

    history_leagues: set[str] = set()
    for game in ("cs2", "csgo"):
        max_offset = 1000 if deep_history else 300
        for offset in range(0, max_offset + 1, 100):
            params = {"game": game, "offset": offset, "limit": 100}
            if deep_history:
                # FACEIT defaults this query's lower bound to one month ago.
                params["from"] = 0
            history = await _get_optional_data(
                client,
                f"/players/{player_id}/history",
                params=params,
            )
            items = history.get("items", [])
            if not items:
                break
            for match in items:
                competition = match.get("competition_name", "")
                upper = competition.upper()
                if competition and any(term in upper for term in ("ESEA", "SAISON", "SEASON", "S5")):
                    history_leagues.add(f"🏆 {competition}")
            if len(items) < 100:
                break

    # Tournament names may omit the league brand; resolve the organizer only
    # for season-like titles rather than issuing requests for every event.
    organizers: dict[str, str] = {}
    organizer_ids = {
        str(tournament.get("organizer_id"))
        for tournament in tournaments
        if tournament.get("organizer_id")
        and re.search(r"\b(?:ESEA|SEASON\s*\d{1,3}|S\d{1,3})\b", tournament.get("name") or "", re.I)
    }
    for organizer_id in organizer_ids:
        organizer = await _get_optional_data(client, f"/organizers/{organizer_id}")
        if organizer.get("name"):
            organizers[organizer_id] = organizer["name"]

    return {
        "profile": player_data,
        "stats": stats_data,
        "teams": teams,
        "tournaments": tournaments,
        "championships": [],
        "organizers": organizers,
        "history_leagues": list(history_leagues),
    }
