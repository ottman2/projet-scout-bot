import discord
from discord.ext import commands

from src.bot.commands.pagination import EmbedPaginator
from src.bot.commands.player_presenter import build_player_embeds
from src.services.faceit_client import (
    FaceitAPIError,
    FaceitAuthenticationError,
    FaceitNotFoundError,
    FaceitRateLimitError,
)
from src.services.player_service import get_player_scouting_data


def setup(bot: commands.Bot) -> None:
    @bot.command(name="player")
    async def player_command(ctx: commands.Context, nickname: str):
        wait_msg = await ctx.send(f"👤 Analyse complète de **{nickname}** en cours...")
        try:
            data = await get_player_scouting_data(bot.faceit_client, nickname, deep_history=True)
            if not data:
                await wait_msg.edit(content=f"❌ Joueur **{nickname}** introuvable ou inaccessible.", embed=None)
                return

            embeds = build_player_embeds(nickname, data)
            view = EmbedPaginator(embeds, ctx.author.id) if len(embeds) > 1 else None
            await wait_msg.edit(content=None, embed=embeds[0], view=view)
            if view:
                view.message = wait_msg
        except FaceitNotFoundError:
            await wait_msg.edit(content=f"❌ Joueur **{nickname}** introuvable ou inaccessible.", embed=None)
        except FaceitRateLimitError:
            await wait_msg.edit(content="⏳ FACEIT limite temporairement les requêtes. Réessaie dans quelques instants.", embed=None)
        except FaceitAuthenticationError:
            await wait_msg.edit(content="❌ FACEIT a refusé l’accès aux données. Vérifie la clé API configurée.", embed=None)
        except FaceitAPIError as exc:
            await wait_msg.edit(
                content=f"❌ Impossible de récupérer la fiche FACEIT (HTTP {exc.status or 'réseau'}).",
                embed=None,
            )
