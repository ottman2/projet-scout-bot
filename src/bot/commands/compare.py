import discord
from discord.ext import commands

from src.bot.commands.pagination import EmbedPaginator
from src.services.faceit_client import (
    FaceitAPIError,
    FaceitAuthenticationError,
    FaceitNotFoundError,
    FaceitRateLimitError,
)
from src.services.player_service import get_player_scouting_data


def _safe(value) -> str:
    return "N/A" if value is None or value == "" else str(value)


def build_compare_embeds(name1: str, data1: dict, name2: str, data2: dict) -> list[discord.Embed]:
    embeds = []
    
    # --- 1. Global Embed ---
    p1_profile = data1.get("profile", {})
    p1_cs2 = p1_profile.get("games", {}).get("cs2", {})
    p1_stats = data1.get("stats", {}).get("lifetime", {})

    p2_profile = data2.get("profile", {})
    p2_cs2 = p2_profile.get("games", {}).get("cs2", {})
    p2_stats = data2.get("stats", {}).get("lifetime", {})

    p1_name = p1_profile.get("nickname") or name1
    p2_name = p2_profile.get("nickname") or name2

    global_embed = discord.Embed(
        title=f"⚔️ COMPARATIF GLOBAL : {p1_name} vs {p2_name}",
        color=0xE74C3C
    )

    global_embed.add_field(
        name=f"🔵 {p1_name}",
        value=(
            f"**Lvl:** {_safe(p1_cs2.get('skill_level'))} ({_safe(p1_cs2.get('faceit_elo'))} Elo)\n"
            f"**Matches:** {_safe(p1_stats.get('Matches'))}\n"
            f"**Win Rate:** {_safe(p1_stats.get('Win Rate %'))}%\n"
            f"**K/D:** {_safe(p1_stats.get('Average K/D Ratio'))}\n"
            f"**HS %:** {_safe(p1_stats.get('Average Headshots %'))}%"
        ),
        inline=True
    )

    global_embed.add_field(
        name=f"🔴 {p2_name}",
        value=(
            f"**Lvl:** {_safe(p2_cs2.get('skill_level'))} ({_safe(p2_cs2.get('faceit_elo'))} Elo)\n"
            f"**Matches:** {_safe(p2_stats.get('Matches'))}\n"
            f"**Win Rate:** {_safe(p2_stats.get('Win Rate %'))}%\n"
            f"**K/D:** {_safe(p2_stats.get('Average K/D Ratio'))}\n"
            f"**HS %:** {_safe(p2_stats.get('Average Headshots %'))}%"
        ),
        inline=True
    )

    if p1_profile.get("avatar"):
        global_embed.set_thumbnail(url=p1_profile["avatar"])

    embeds.append(global_embed)

    # --- 2. Map Embeds ---
    p1_maps = {m.get("name"): m for m in data1.get("map_stats", []) if isinstance(m, dict)}
    p2_maps = {m.get("name"): m for m in data2.get("map_stats", []) if isinstance(m, dict)}

    all_maps = set(p1_maps.keys()).union(set(p2_maps.keys()))
    
    def total_matches(m_name):
        return int(p1_maps.get(m_name, {}).get("matches", 0)) + int(p2_maps.get(m_name, {}).get("matches", 0))
    
    # Sort maps by total matches descending
    sorted_maps = sorted(list(all_maps), key=total_matches, reverse=True)

    # Limit to top 10 most played maps to avoid too many pages
    for m_name in sorted_maps[:10]:
        m1 = p1_maps.get(m_name, {})
        m2 = p2_maps.get(m_name, {})
        
        map_embed = discord.Embed(
            title=f"🗺️ COMPARATIF MAP : {m_name}",
            description=f"**{p1_name}** vs **{p2_name}** sur **{m_name}**",
            color=0x2ECC71
        )
        
        wr1 = m1.get("winrate")
        wr1_str = f"{wr1}%" if wr1 is not None and wr1 != "N/A" else "N/A"
        wr2 = m2.get("winrate")
        wr2_str = f"{wr2}%" if wr2 is not None and wr2 != "N/A" else "N/A"
        
        hs1 = m1.get("hs_percent")
        hs1_str = f"{hs1}%" if hs1 is not None and hs1 != "N/A" else "N/A"
        hs2 = m2.get("hs_percent")
        hs2_str = f"{hs2}%" if hs2 is not None and hs2 != "N/A" else "N/A"

        map_embed.add_field(
            name=f"🔵 {p1_name}",
            value=(
                f"**Matches:** {_safe(m1.get('matches', 0))}\n"
                f"**Win Rate:** {wr1_str}\n"
                f"**K/D:** {_safe(m1.get('kd'))}\n"
                f"**HS %:** {hs1_str}\n"
                f"**Kills/Match:** {_safe(m1.get('avg_kills'))}\n"
                f"**Total MVPs:** {_safe(m1.get('mvps'))}"
            ),
            inline=True
        )

        map_embed.add_field(
            name=f"🔴 {p2_name}",
            value=(
                f"**Matches:** {_safe(m2.get('matches', 0))}\n"
                f"**Win Rate:** {wr2_str}\n"
                f"**K/D:** {_safe(m2.get('kd'))}\n"
                f"**HS %:** {hs2_str}\n"
                f"**Kills/Match:** {_safe(m2.get('avg_kills'))}\n"
                f"**Total MVPs:** {_safe(m2.get('mvps'))}"
            ),
            inline=True
        )
        
        if p1_profile.get("avatar"):
            map_embed.set_thumbnail(url=p1_profile["avatar"])

        embeds.append(map_embed)

    # --- Footer for pagination ---
    total = len(embeds)
    for index, e in enumerate(embeds, start=1):
        e.set_footer(text=f"Page {index}/{total} • Navigation avec les boutons")

    return embeds


def setup(bot: commands.Bot) -> None:
    @bot.command(name="compare")
    async def compare_command(ctx: commands.Context, player1: str, player2: str):
        wait_msg = await ctx.send(f"⚔️ Comparaison de **{player1}** et **{player2}** en cours...")
        try:
            data1 = await get_player_scouting_data(bot.faceit_client, player1)
            data2 = await get_player_scouting_data(bot.faceit_client, player2)

            if not data1 and not data2:
                await wait_msg.edit(content=f"❌ Les joueurs **{player1}** et **{player2}** sont introuvables.")
                return
            if not data1:
                await wait_msg.edit(content=f"❌ Joueur **{player1}** introuvable.")
                return
            if not data2:
                await wait_msg.edit(content=f"❌ Joueur **{player2}** introuvable.")
                return

            embeds = build_compare_embeds(player1, data1, player2, data2)
            view = EmbedPaginator(embeds, ctx.author.id) if len(embeds) > 1 else None
            
            await wait_msg.edit(content=None, embed=embeds[0], view=view)
            if view:
                view.message = wait_msg

        except FaceitNotFoundError:
            await wait_msg.edit(content="❌ Un des joueurs est introuvable ou inaccessible.")
        except FaceitRateLimitError:
            await wait_msg.edit(content="⏳ FACEIT limite temporairement les requêtes. Réessaie dans quelques instants.")
        except FaceitAuthenticationError:
            await wait_msg.edit(content="❌ FACEIT a refusé l’accès aux données. Vérifie la clé API configurée.")
        except FaceitAPIError as exc:
            await wait_msg.edit(
                content=f"❌ Erreur réseau lors de la récupération (HTTP {exc.status or 'inconnu'})."
            )
