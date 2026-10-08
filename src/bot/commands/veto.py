import discord
from discord.ext import commands

from src.services.faceit_client import FaceitAPIError
from src.services.veto_service import get_veto_analysis
from src.core.veto_analyzer import PICK_MAP_POOL, recommend_bans, recommend_pick


def _side_line(label: str, side: dict | None) -> str:
    if not side or side.get("winrate") is None:
        return f"{label} : N/A"
    matches = f"{side['matches']} matchs" if side.get("matches") is not None else "N/A matchs"
    kd = f"K/D {side['kd']:.2f}" if side.get("kd") is not None else "K/D N/A"
    return f"{label} : {side['winrate']:g}% — {matches} — {kd}"


def setup(bot: commands.Bot) -> None:
    @bot.command(name="veto")
    async def veto_command(ctx: commands.Context, *, team_name: str):
        wait_msg = await ctx.send(f"Analyse VETO contre **{team_name}** en cours…")
        try:
            data = await get_veto_analysis(bot.faceit_client, team_name)
            if data is None:
                await wait_msg.edit(content=f"Équipe **{team_name}** introuvable sur FACEIT.")
                return
            if "error" in data:
                await wait_msg.edit(content=data["error"])
                return
            maps = data["maps"]
            embed = discord.Embed(
                title=f"🎯 VETO ANALYSIS — {data['our_team']['name']} vs {data['opponent_team']['name']}",
                color=0x5865F2,
            )
            sections = (
                ("🟢 Maps favorables", "favorable"), ("🟡 Maps neutres", "neutral"),
                ("🔴 Maps défavorables", "unfavorable"), ("⚪ Données insuffisantes", "insufficient_data"),
            )
            for title, category in sections:
                selected = [item for item in maps if item["classification"] == category]
                if not selected:
                    continue
                lines = []
                for item in selected:
                    pool_note = "" if item["map"].casefold() in {name.casefold() for name in PICK_MAP_POOL} else " — hors pool jouable GandaltF4"
                    lines.extend([
                        f"**{item['map']}**{pool_note}",
                        _side_line(data["our_team"]["name"], item["our"]),
                        _side_line(data["opponent_team"]["name"], item["opponent"]),
                    ])
                    if item["score"] is not None:
                        lines.append(f"Avantage : {item['score']:+.1f} pts • Confiance : {item['confidence']}")
                    else:
                        lines.append("Données insuffisantes pour comparer.")
                # Discord field values are limited to 1024 characters.
                chunks, current = [], []
                for line in lines:
                    if sum(map(len, current)) + len(current) + len(line) > 950 and current:
                        chunks.append("\n".join(current)); current = []
                    current.append(line)
                if current:
                    chunks.append("\n".join(current))
                for index, chunk in enumerate(chunks):
                    embed.add_field(name=title if index == 0 else f"{title} (suite)", value=chunk, inline=False)
            pick, bans = recommend_pick(maps), recommend_bans(maps, limit=3)
            embed.add_field(name="🎯 PICK conseillé", value=pick["map"] if pick else "Aucun avantage favorable établi", inline=True)
            if bans:
                ban_lines = []
                for index, item in enumerate(bans, start=1):
                    if item["score"] is None:
                        detail = "stats insuffisantes — option hors de notre pool jouable"
                    else:
                        detail = f"{item['score']:+.1f} pts, confiance {item['confidence']}"
                        if item["map"].casefold() not in {name.casefold() for name in PICK_MAP_POOL}:
                            detail += " — hors de notre pool jouable"
                        else:
                            detail += " — map de notre pool (repli)"
                    ban_lines.append(f"{index}. **{item['map']}** — {detail}")
                ban_value = "\n".join(ban_lines) + "\nChoisir le premier ban, puis réévaluer les deux suivants après les bans adverses."
            else:
                ban_value = "Aucune comparaison statistique disponible."
            embed.add_field(name="🚫 Bans possibles pour GandaltF4", value=ban_value, inline=False)
            await wait_msg.edit(content=None, embed=embed)
        except FaceitAPIError as exc:
            await wait_msg.edit(content=f"Erreur FACEIT : {exc}")
