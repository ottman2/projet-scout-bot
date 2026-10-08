import discord
from discord.ext import commands

from src.services.faceit_client import FaceitAPIError
from src.services.team_service import get_team_scouting_data


def setup(bot: commands.Bot) -> None:
    @bot.command(name="scout")
    async def scout_command(ctx: commands.Context, *, team_name: str):
        await ctx.send(f"🔍 Analyse rapide de **{team_name}** en cours...")
        try:
            team_data = await get_team_scouting_data(bot.faceit_client, team_name)
            if not team_data:
                await ctx.send("❌ Équipe introuvable.")
                return
            real_name = team_data["team"]["name"]
            sorted_stats = team_data["map_stats"]
            if not sorted_stats:
                await ctx.send(f"❌ Aucune statistique pour **{real_name}**.")
                return
            embed = discord.Embed(title=f"Scouting Report : {real_name}", color=0x00FF00)
            for data in sorted_stats:
                if data["matches"] >= 2:
                    embed.add_field(
                        name=data["map"],
                        value=f"Matchs : {data['matches']} \nWinrate : {data['winrate']}%",
                        inline=True,
                    )
            await ctx.send(embed=embed)
        except FaceitAPIError as exc:
            await ctx.send(f"❌ Erreur FACEIT : {exc}")
