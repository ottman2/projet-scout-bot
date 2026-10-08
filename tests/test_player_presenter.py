from src.bot.commands.player_presenter import build_player_embeds
from src.bot.commands.pagination import EmbedPaginator
import discord


def _section_embeds(embeds, prefix):
    return [embed for embed in embeds if embed.title.startswith(prefix)]


def test_all_maps_fit_on_one_maps_embed_when_under_discord_page_size():
    data = {
        "profile": {"nickname": "Player", "games": {"cs2": {"faceit_elo": 2000, "skill_level": 10}}},
        "map_stats": [{"name": f"Map{i}", "matches": 10 - i, "winrate": 60} for i in range(6)],
    }
    maps = _section_embeds(build_player_embeds("Player", data), "🗺️ MAPS")
    assert len(maps) == 1
    assert all(f"Map{i}" in maps[0].description for i in range(6))


def test_map_list_overflow_creates_pages_without_dropping_maps():
    data = {
        "profile": {"nickname": "Player"},
        "map_stats": [{"name": f"Map{i:03}", "matches": 1, "winrate": 50} for i in range(130)],
    }
    maps = _section_embeds(build_player_embeds("Player", data), "🗺️ MAPS")
    assert len(maps) > 1
    rendered = "\n".join(embed.description for embed in maps)
    assert all(f"Map{i:03}" in rendered for i in range(130))


def test_missing_stats_maps_teams_and_history_render_safely():
    embeds = build_player_embeds("Player", {"profile": {"nickname": "Player"}})
    stats = _section_embeds(embeds, "📊 GLOBAL STATS")[0].description
    assert "N/A" in stats
    assert "Aucune statistique de map" in _section_embeds(embeds, "🗺️ MAPS")[0].description
    assert "Aucune équipe connue" in _section_embeds(embeds, "🏢 KNOWN TEAMS")[0].description
    assert "Aucune saison" in _section_embeds(embeds, "🏆 ESEA HISTORY")[0].description


def test_discord_paginator_starts_on_first_page_and_exposes_next_button():
    paginator = EmbedPaginator([discord.Embed(title="one"), discord.Embed(title="two")], owner_id=123)
    assert paginator.previous_button.disabled
    assert not paginator.next_button.disabled
