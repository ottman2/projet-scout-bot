import re

import discord

from src.core.player_analyzer import chunk_lines


def _display(value) -> str:
    return "N/A" if value is None or value == "" else str(value)


def _safe(value) -> str:
    return re.sub(r"([\\*_~|`>])", r"\\\1", _display(value))


def build_player_embeds(requested_nickname: str, data: dict) -> list[discord.Embed]:
    """Render all available player data into complete, Discord-safe pages."""
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    games = profile.get("games") if isinstance(profile.get("games"), dict) else {}
    cs2 = games.get("cs2") if isinstance(games.get("cs2"), dict) else {}
    stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
    lifetime = stats.get("lifetime") if isinstance(stats.get("lifetime"), dict) else {}
    nickname = profile.get("nickname") or requested_nickname
    country = profile.get("country") or "N/A"
    flag = f":flag_{str(country).lower()}:" if country != "N/A" else "🏳️"

    embeds: list[discord.Embed] = []
    description = (
        f"**Nationality:** {_safe(country)} {flag}\n"
        f"**FACEIT Level:** {_safe(cs2.get('skill_level'))}\n"
        f"**Elo:** {_safe(cs2.get('faceit_elo'))}"
    )

    recent_results = lifetime.get("Recent Results")
    if isinstance(recent_results, list):
        form_str = " ".join("🟢" if str(r) == "1" else "🔴" for r in recent_results)
        if form_str:
            description += f"\n**Forme:** {form_str}"

    current_streak = lifetime.get("Current Win Streak")
    if current_streak and str(current_streak) != "0":
        description += f"\n**Série en cours:** {_safe(current_streak)} victoire(s)"

    overview = discord.Embed(
        title=f"👤 PLAYER — {nickname}",
        description=description,
        color=0x3498DB,
    )
    if profile.get("avatar"):
        overview.set_thumbnail(url=profile["avatar"])
    embeds.append(overview)

    known_stats = {
        "Matches": "Matches",
        "Win Rate %": "Win Rate",
        "Average K/D Ratio": "K/D",
        "Average Headshots %": "Headshot %",
        "Recent Results": None,
        "Current Win Streak": None,
    }
    
    stats_lines = []
    for key, label in known_stats.items():
        if label is not None:
            stats_lines.append(f"**{label}:** {_safe(lifetime.get(key))}")
            
    for key, value in lifetime.items():
        if key not in known_stats and value is not None:
            stats_lines.append(f"**{_safe(key)}:** {_safe(value)}")
            
    _append_section(embeds, "📊 GLOBAL STATS", stats_lines, "Statistiques indisponibles.")

    team_lines = []
    teams = data.get("teams")
    for team in teams if isinstance(teams, list) else []:
        if isinstance(team, dict):
            team_lines.append(f"• {_safe(team.get('name'))}")
    _append_section(embeds, "🏢 KNOWN TEAMS", team_lines, "Aucune équipe connue dans les données FACEIT.")

    map_lines = []
    map_stats = data.get("map_stats")
    for map_stat in map_stats if isinstance(map_stats, list) else []:
        if not isinstance(map_stat, dict):
            continue
        winrate = map_stat.get("winrate")
        line = (
            f"**{_safe(map_stat.get('name'))}** — Matches: {_safe(map_stat.get('matches'))}"
            f" • Winrate: {_safe(winrate)}{'%' if winrate is not None and winrate != 'N/A' else ''}"
        )
        if map_stat.get("kd") is not None:
            line += f" • K/D: {_safe(map_stat['kd'])}"
        map_lines.append(line)
    _append_section(embeds, "🗺️ MAPS", map_lines, "Aucune statistique de map disponible.")

    history_lines = []
    seasons = data.get("esea_seasons")
    for season in seasons if isinstance(seasons, list) else []:
        if not isinstance(season, dict):
            continue
        number = season.get("season")
        history_lines.append(f"**ESEA Season {number}**")
        sources = season.get("sources")
        history_lines.extend(
            f"  • {_safe(source)}" for source in (sources if isinstance(sources, list) else [])
        )
    if not history_lines:
        competitions = data.get("esea_competitions")
        history_lines.extend(
            f"• {_safe(name)}" for name in (competitions if isinstance(competitions, list) else [])
        )
    _append_section(
        embeds,
        "🏆 ESEA HISTORY",
        history_lines,
        "Aucune saison ou compétition ESEA identifiée dans l’historique accessible.",
    )

    total = len(embeds)
    for index, embed in enumerate(embeds, start=1):
        embed.set_footer(text=f"Page {index}/{total} • Navigation avec les boutons")
    return embeds


def _append_section(embeds: list[discord.Embed], title: str, lines: list[str], empty_message: str) -> None:
    pages = chunk_lines(lines or [empty_message], max_chars=3500)
    total = len(pages)
    for index, page in enumerate(pages, start=1):
        page_title = f"{title} — PAGE {index}/{total}" if total > 1 else title
        embeds.append(discord.Embed(title=page_title, description=page, color=0x3498DB))
