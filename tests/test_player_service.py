from unittest.mock import AsyncMock

import pytest

from src.services.faceit import get_full_player_profile


@pytest.mark.asyncio
async def test_deep_profile_scans_history_from_epoch_and_resolves_organizer():
    history_calls = []

    async def get(endpoint, *, params=None, allow_not_found=False):
        if endpoint == "/players":
            return {"player_id": "p1", "nickname": "Player"}
        if endpoint.endswith("/stats/cs2"):
            return {"lifetime": {"Matches": "10"}, "segments": []}
        if endpoint.endswith("/teams"):
            return {"items": [{"team_id": "t1", "name": "Team"}]}
        if endpoint.endswith("/tournaments"):
            return {"items": [{"tournament_id": "e1", "name": "Season 59", "organizer_id": "org1"}]}
        if endpoint.endswith("/history"):
            history_calls.append(params)
            if params["game"] == "cs2":
                return {"items": [{"competition_name": "S59 EU Open10 A - Regular Season"}]}
            return {"items": []}
        if endpoint == "/organizers/org1":
            return {"name": "ESEA"}
        raise AssertionError(f"Unexpected FACEIT endpoint: {endpoint}")

    client = type("Client", (), {})()
    client.get = AsyncMock(side_effect=get)
    profile = await get_full_player_profile(client, "Player", deep_history=True)
    assert profile["teams"][0]["name"] == "Team"
    assert profile["organizers"] == {"org1": "ESEA"}
    assert history_calls[0]["from"] == 0
    assert history_calls[0]["offset"] == 0
    assert history_calls[0]["limit"] == 100
    assert len(history_calls) == 2
