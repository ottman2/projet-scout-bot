import asyncio
import logging

import aiohttp
import discord
from discord.ext import commands

from src.bot.commands import setup_commands
from src.config import ConfigurationError, load_config
from src.services.faceit_client import FaceitClient


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Réservé aux futurs rapports automatiques ; les commandes actuelles ne l'utilisent pas.
TARGET_CHANNEL_ID = 1557425631996936315


class ScoutingBot(commands.Bot):
    faceit_client: FaceitClient | None = None


intents = discord.Intents.default()
intents.message_content = True
bot = ScoutingBot(command_prefix="!", intents=intents)
setup_commands(bot)


@bot.event
async def on_ready():
    logger.info("Bot connecté en tant que %s", bot.user)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error("Erreur de commande Discord : %s", type(error).__name__)
    await ctx.send("❌ Une erreur est survenue pendant le traitement de la commande.")


import os
from aiohttp import web

async def handle_web(request):
    return web.Response(text="Scout Bot is awake!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Serveur web de maintien en vie démarré sur le port {port}")


async def run_bot() -> None:
    config = load_config()
    
    # Démarrage du serveur web pour satisfaire Render.com
    await start_web_server()

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        bot.faceit_client = FaceitClient(session, config.faceit_api_key, timeout_seconds=15)
        
        # Charger la tâche d'auto-report
        await bot.load_extension("src.bot.tasks.auto_report")
        
        await bot.start(config.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration invalide : {exc}") from None
