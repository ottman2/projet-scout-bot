import re

import discord
from discord.ext import commands

from src.services.faceit_client import FaceitAPIError
from src.services.player_service import get_player_scouting_data
from src.services.team_service import get_team_scouting_data


def setup(bot: commands.Bot) -> None:
    @bot.command(name="setmatch")
    async def setmatch_command(ctx: commands.Context, *, opponent_name: str):
        wait_msg = await ctx.send(
            f"⏳ Création du dossier de match contre **{opponent_name}**... (Scan du roster en cours)"
        )
        try:
            client = bot.faceit_client
            team_data = await get_team_scouting_data(client, opponent_name, include_roster=True)
            if not team_data:
                await wait_msg.edit(content=f"❌ Impossible de trouver l'équipe **{opponent_name}** sur FACEIT.")
                return

            team = team_data["team"]
            real_name = team["name"]
            members = team_data["members"]
            embed = discord.Embed(title=f"🚨 PROCHAIN MATCH : GandaltF4 vs {real_name} 🚨", color=0xFF0000)
            if team.get("avatar"):
                embed.set_thumbnail(url=team["avatar"])

            maps_str = ""
            for data in team_data["map_stats"]:
                if data["matches"] >= 2:
                    maps_str += f"**{data['map']}** : {data['matches']} matchs ({data['winrate']}% WR)\n"
            if not maps_str:
                maps_str = "Données d'équipe insuffisantes en 5v5."
            embed.add_field(name="🗺️ Maps (Équipe)", value=maps_str, inline=False)

            if not members:
                embed.add_field(name="Roster", value="Aucun joueur trouvé dans cette équipe.", inline=False)
            else:
                players = []
                for member in members[:7]:
                    nickname = member.get("nickname")
                    player_data = await get_player_scouting_data(client, nickname)
                    if not player_data:
                        continue
                    leagues = set(player_data.get("history_leagues", []))
                    comps = player_data.get("tournaments", []) + player_data.get("championships", [])
                    leagues.update(
                        f"🏆 {comp.get('name', '')}"
                        for comp in comps
                        if comp.get("name")
                        and any(term in comp["name"].upper() for term in ("ESEA", "SAISON", "SEASON", "S5"))
                    )
                    seasons = [
                        (int(match.group(1)), league)
                        for league in leagues
                        if (match := re.search(r"\bS(\d+)\b", league, re.IGNORECASE))
                    ]
                    profile = player_data.get("profile", {})
                    cs2 = profile.get("games", {}).get("cs2", {})
                    try:
                        elo = int(cs2.get("faceit_elo", 0))
                    except (TypeError, ValueError):
                        elo = 0
                    players.append({"nickname": nickname, "data": player_data, "seasons": seasons, "elo": elo})

                current_season = max(
                    (number for player in players for number, _ in player["seasons"]), default=None
                )
                current_players = [
                    player for player in players
                    if any(number == current_season for number, _ in player["seasons"])
                ]
                current_players.sort(key=lambda player: player["elo"], reverse=True)
                if not current_players:
                    embed.add_field(name="Roster", value="Aucun joueur de la saison actuelle trouvé.", inline=False)
                for player in current_players:
                    data = player["data"]
                    profile = data.get("profile", {})
                    cs2 = profile.get("games", {}).get("cs2", {})
                    country = profile.get("country", "un").lower()
                    flag = f":flag_{country}:" if country != "un" else "🏳️"
                    kd = data.get("stats", {}).get("lifetime", {}).get("Average K/D Ratio", "N/A")
                    season_names = sorted({
                        league for number, league in player["seasons"] if number == current_season
                    })
                    value = (
                        f"**{cs2.get('faceit_elo', 'N/A')} Elo** (Lvl {cs2.get('skill_level', 'N/A')}) "
                        f"• **{kd} K/D**\n{season_names[0]}"
                    )
                    embed.add_field(name=f"{flag} {player['nickname']}", value=value, inline=False)

            await wait_msg.edit(content="✅ **Rapport terminé !**", embed=embed)
        except FaceitAPIError as exc:
            await wait_msg.edit(content=f"❌ Erreur FACEIT : {exc}")
