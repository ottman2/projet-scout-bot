import discord
from discord.ext import commands

from src.bot.commands.setmatch_veto_view import SetMatchVetoView
from src.core.veto_analyzer import (
    OFFICIAL_MAP_POOL,
    PICK_MAP_POOL,
    analyze_veto,
    recommend_bans,
    recommend_pick,
)
from src.services.faceit_client import FaceitAPIError
from src.services.team_service import get_full_team_stats, get_team_scouting_data


def _number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bar(value, *, scale: float = 100, width: int = 10) -> str:
    number = _number(value)
    if number is None or scale <= 0:
        return "░" * width
    filled = round(max(0, min(number / scale, 1)) * width)
    return "█" * filled + "░" * (width - filled)


def _display(value) -> str:
    return "N/A" if value is None or value == "" else str(value)


def _percent(value) -> str:
    return f"{value}%" if value is not None and value != "" else "N/A"


def _official_map_name(value) -> str | None:
    normalized = str(value or "").strip().casefold().removeprefix("de_").replace("_", "").replace(" ", "")
    if normalized in {"d2", "dust2"}:
        return "D2"
    return next((name for name in OFFICIAL_MAP_POOL if name.casefold() == normalized), None)


def _flag(country) -> str:
    code = str(country or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🏳️"
    return "".join(chr(127397 + ord(char)) for char in code)


def _team_map_field(team_stats: dict | None) -> str:
    segments = team_stats.get("segments", []) if isinstance(team_stats, dict) else []
    available = {}
    for segment in segments if isinstance(segments, list) else []:
        if not isinstance(segment, dict) or segment.get("mode") != "5v5":
            continue
        name = _official_map_name(segment.get("label"))
        stats = segment.get("stats")
        if name and isinstance(stats, dict):
            available[name] = stats

    lines = []
    for name in OFFICIAL_MAP_POOL:
        stats = available.get(name)
        if stats is None:
            lines.append(f"**{name}**  N/A")
            continue
        wr = stats.get("Win Rate %")
        matches = stats.get("Matches")
        wr_text = f"{wr}%" if wr is not None else "WR N/A"
        matches_text = f"{matches} m" if matches is not None else "matchs N/A"
        lines.append(f"**{name}**  {wr_text} · {matches_text}")
    return "\n".join(lines)


def _player_card(entry: dict) -> tuple[str, str]:
    nickname = str(entry.get("nickname") or "Joueur sans pseudo FACEIT")
    player = entry.get("player_data")
    if not isinstance(player, dict):
        return nickname, "Profil ou statistiques FACEIT indisponibles."

    profile = player.get("profile") if isinstance(player.get("profile"), dict) else {}
    games = profile.get("games") if isinstance(profile.get("games"), dict) else {}
    cs2 = games.get("cs2") if isinstance(games.get("cs2"), dict) else {}
    stats = player.get("stats") if isinstance(player.get("stats"), dict) else {}
    lifetime = stats.get("lifetime") if isinstance(stats.get("lifetime"), dict) else {}

    kd = lifetime.get("Average K/D Ratio")
    wr = lifetime.get("Win Rate %")
    hs = lifetime.get("Average Headshots %")
    adr = lifetime.get("ADR")
    matches = lifetime.get("Matches", lifetime.get("Total Matches"))
    wins = lifetime.get("Wins")

    lines = [
        f"**{_display(cs2.get('faceit_elo'))} Elo** · Niveau **{_display(cs2.get('skill_level'))}**",
        f"K/D **{_display(kd)}**  ·  ADR **{_display(adr)}**",
        f"WR **{_percent(wr)}**  `{_bar(wr)}`",
        f"HS **{_percent(hs)}**  `{_bar(hs)}`",
        f"Matchs **{_display(matches)}**" + (f" · Victoires **{wins}**" if wins is not None else ""),
    ]

    player_maps = player.get("map_stats") if isinstance(player.get("map_stats"), list) else []
    normalized_maps = {}
    for map_stat in player_maps:
        if not isinstance(map_stat, dict):
            continue
        name = _official_map_name(map_stat.get("name"))
        if name:
            normalized_maps[name] = map_stat
    map_lines = []
    for name in OFFICIAL_MAP_POOL:
        map_stat = normalized_maps.get(name)
        if not map_stat:
            continue
        map_wr = map_stat.get("winrate")
        map_lines.append(
            f"{name} {_percent(map_wr)} `{_bar(map_wr)}` · {_display(map_stat.get('matches'))} m"
        )
    if map_lines:
        lines.extend(["", "**Maps**", *map_lines])

    seasons = player.get("esea_seasons") if isinstance(player.get("esea_seasons"), list) else []
    season_numbers = [f"S{item['season']}" for item in seasons if isinstance(item, dict) and item.get("season")]
    if season_numbers:
        lines.append("ESEA : " + ", ".join(season_numbers[:5]))

    title = f"{_flag(profile.get('country'))} {discord.utils.escape_markdown(nickname)}"
    return title, "\n".join(lines)


def _player_elo(entry: dict) -> float:
    player = entry.get("player_data") if isinstance(entry, dict) else None
    profile = player.get("profile") if isinstance(player, dict) else None
    games = profile.get("games") if isinstance(profile, dict) else None
    cs2 = games.get("cs2") if isinstance(games, dict) else None
    elo = _number(cs2.get("faceit_elo")) if isinstance(cs2, dict) else None
    return elo if elo is not None else -1


def _build_team_page(opponent: dict, our_team: dict) -> discord.Embed:
    enemy_name = opponent["team"]["name"]
    embed = discord.Embed(
        title=f"🚨 PROCHAIN MATCH : GandaltF4 vs {enemy_name} 🚨",
        description="Préparation du match · comparaison des statistiques d’équipe",
        color=0xFF0000,
    )
    if opponent["team"].get("avatar"):
        embed.set_thumbnail(url=opponent["team"]["avatar"])
    embed.add_field(
        name=f"🗺️ MAPS {our_team['team']['name']}",
        value=_team_map_field(our_team.get("stats")),
        inline=True,
    )
    embed.add_field(
        name=f"🗺️ MAPS {enemy_name}",
        value=_team_map_field(opponent.get("team_stats")),
        inline=True,
    )
    embed.set_footer(text="Page équipe")
    return embed


def _build_veto_page(opponent: dict, our_team: dict, veto_maps: list[dict]) -> discord.Embed:
    enemy_name = opponent["team"]["name"]
    embed = discord.Embed(
        title=f"🎯 VETO · {our_team['team']['name']} vs {enemy_name}",
        description="Sélectionnez les maps dans l’ordre du veto. Les maps retirées sont désactivées.",
        color=0x5865F2,
    )
    map_icons = {"favorable": "🟢", "neutral": "🟡", "unfavorable": "🔴", "insufficient_data": "⚪"}
    veto_lines = []
    for item in veto_maps:
        map_name = item["map"]
        outside_our_pool = map_name.casefold() not in {name.casefold() for name in PICK_MAP_POOL}
        tag = " · hors pool GandaltF4" if outside_our_pool else ""
        if item["score"] is None:
            detail = "stats N/A"
        else:
            detail = f"{item['score']:+.1f} pts · conf. {item['confidence']}"
        veto_lines.append(f"{map_icons[item['classification']]} **{map_name}**{tag} — {detail}")
    embed.add_field(name="🎯 COMPARAISON VETO", value="\n".join(veto_lines), inline=False)

    pick = recommend_pick(veto_maps)
    pick_text = pick["map"] if pick else "Aucun avantage établi dans notre pool"
    bans = recommend_bans(veto_maps, limit=3)
    ban_lines = []
    for index, item in enumerate(bans, start=1):
        detail = "stats N/A" if item["score"] is None else f"{item['score']:+.1f} pts · {item['confidence']}"
        ban_lines.append(f"{index}. **{item['map']}** — {detail}")
    ban_text = "\n".join(ban_lines) if ban_lines else "Aucune candidate disponible"
    ban_text += "\nRéévaluer après les bans adverses."
    embed.add_field(name="🎯 PICK", value=pick_text, inline=True)
    embed.add_field(name="🚫 BANS PRIORITAIRES", value=ban_text, inline=True)
    embed.set_footer(text="A bannit 1 · B bannit 2 · A bannit 2 · B bannit 1 · la dernière map est jouée")
    return embed


def _build_player_pages(opponent: dict) -> list[discord.Embed]:
    entries = sorted(opponent.get("players") or [], key=_player_elo, reverse=True)
    if not entries:
        embed = discord.Embed(title="👥 ROSTER ADVERSE", description="Aucun membre de roster retourné par FACEIT.", color=0x3498DB)
        return [embed]

    pages = []
    for offset in range(0, len(entries), 2):
        page_entries = entries[offset:offset + 2]
        embed = discord.Embed(
            title="👥 JOUEURS ADVERSES · STATS CLÉS",
            description="K/D moyen, WR, ADR, headshots et performance sur le pool officiel.",
            color=0x3498DB,
        )
        for entry in page_entries:
            title, value = _player_card(entry)
            embed.add_field(name=title[:256], value=value[:1024], inline=False)
        pages.append(embed)
    return pages


def setup(bot: commands.Bot) -> None:
    @bot.command(name="setmatch")
    async def setmatch_command(ctx: commands.Context, *, opponent_name: str):
        wait_msg = await ctx.send(
            f"⏳ Préparation du rapport contre **{opponent_name}**… (équipe, joueurs, veto)"
        )
        try:
            client = bot.faceit_client
            opponent = await get_full_team_stats(client, opponent_name)
            if opponent is None:
                await wait_msg.edit(content=f"❌ Équipe **{opponent_name}** introuvable sur FACEIT.")
                return

            our_team = await get_team_scouting_data(client, "GandaltF4")
            if our_team is None:
                await wait_msg.edit(content="❌ Équipe GandaltF4 introuvable sur FACEIT.")
                return

            veto_maps = analyze_veto(our_team.get("stats"), opponent.get("team_stats"))
            pages = [
                _build_team_page(opponent, our_team),
                _build_veto_page(opponent, our_team, veto_maps),
                *_build_player_pages(opponent),
            ]
            for index, embed in enumerate(pages, start=1):
                embed.set_footer(text=f"Rapport de match · page {index}/{len(pages)}")

            view = SetMatchVetoView(
                pages,
                ctx.author.id,
                veto_page_index=1,
                team_a_name=our_team["team"]["name"],
                team_b_name=opponent["team"]["name"],
            )
            message = await wait_msg.edit(
                content="✅ **Rapport de match prêt**",
                embed=pages[0],
                view=view,
            )
            view.message = message
        except FaceitAPIError as exc:
            await wait_msg.edit(content=f"❌ Erreur FACEIT : {exc}")
