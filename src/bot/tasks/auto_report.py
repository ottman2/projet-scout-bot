import asyncio
import logging
import discord
from discord.ext import tasks, commands
from src.services.faceit_client import FaceitClient
from src.services.faceit import _get_optional_data

logger = logging.getLogger(__name__)

# ID du channel de test/reporting
TARGET_CHANNEL_ID = 1557783363715211394

# Joueur utilisé comme référence pour traquer les matchs de l'équipe
# On prend le pseudo du leader ou d'un joueur régulier
TRACKED_PLAYER = "ottman"

class AutoReportTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_match_id = None
        self.player_id = None
        self.check_new_matches.start()

    def cog_unload(self):
        self.check_new_matches.cancel()

    @tasks.loop(minutes=3.0)
    async def check_new_matches(self):
        await self.bot.wait_until_ready()
        client = getattr(self.bot, "faceit_client", None)
        if not client:
            return

        try:
            # 1. Obtenir l'ID du joueur traqué si pas encore fait
            if not self.player_id:
                player_data = await client.get("/players", params={"nickname": TRACKED_PLAYER})
                self.player_id = player_data.get("player_id")
                if not self.player_id:
                    logger.error(f"Impossible de trouver le joueur {TRACKED_PLAYER} pour l'auto-report.")
                    return

            # 2. Obtenir le dernier match
            history = await _get_optional_data(
                client, 
                f"/players/{self.player_id}/history", 
                params={"game": "cs2", "limit": 1}
            )
            items = history.get("items", [])
            if not items:
                return

            latest_match_id = items[0].get("match_id")

            # 3. Initialisation au démarrage (on ne spam pas le dernier match au reboot)
            if self.last_match_id is None:
                self.last_match_id = latest_match_id
                logger.info(f"AutoReport initialisé. Dernier match suivi : {self.last_match_id}")
                return

            # 4. Nouveau match détecté !
            if latest_match_id != self.last_match_id:
                logger.info(f"Nouveau match détecté : {latest_match_id}")
                self.last_match_id = latest_match_id
                await self.process_and_send_report(client, latest_match_id)

        except Exception as e:
            logger.error(f"Erreur dans la boucle AutoReport : {e}")

    async def process_and_send_report(self, client: FaceitClient, match_id: str):
        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            logger.warning(f"Channel {TARGET_CHANNEL_ID} introuvable pour poster le rapport.")
            return

        # Récupérer les stats détaillées du match
        stats = await _get_optional_data(client, f"/matches/{match_id}/stats")
        rounds = stats.get("rounds", [])
        if not rounds:
            return
            
        round_data = rounds[0]
        round_stats = round_data.get("round_stats", {})
        map_name = round_stats.get("Map", "Unknown")
        score = round_stats.get("Score", "Unknown")
        winner_id = round_stats.get("Winner")

        teams = round_data.get("teams", [])
        
        # Trouver dans quelle équipe est notre joueur traqué pour savoir si c'est une victoire
        our_team = None
        enemy_team = None
        for team in teams:
            is_our_team = any(p.get("player_id") == self.player_id for p in team.get("players", []))
            if is_our_team:
                our_team = team
            else:
                enemy_team = team

        if not our_team:
            return

        is_win = our_team.get("team_id") == winner_id
        
        # Construction de l'Embed
        color = 0x2ECC71 if is_win else 0xE74C3C
        title = f"{'🏆 VICTOIRE' if is_win else '💔 DÉFAITE'} sur {map_name} ({score})"
        
        embed = discord.Embed(title=title, color=color)
        
        # Scoreboard de l'équipe
        scoreboard = []
        best_adr = {"val": -1, "name": ""}
        best_mvp = {"val": -1, "name": ""}
        best_entry = {"val": -1, "name": ""}
        best_sniper = {"val": -1, "name": ""}

        players = our_team.get("players", [])
        # Trier par Kills
        players = sorted(players, key=lambda x: int(x.get("player_stats", {}).get("Kills", 0)), reverse=True)

        for p in players:
            name = p.get("nickname", "Unknown")
            p_stats = p.get("player_stats", {})
            
            kills = p_stats.get("Kills", "0")
            deaths = p_stats.get("Deaths", "0")
            kd = p_stats.get("K/D Ratio", "0")
            
            scoreboard.append(f"**{name}** : {kills}K / {deaths}D  *(K/D: {kd})*")
            
            # Analyse stats
            adr = float(p_stats.get("ADR", 0))
            if adr > best_adr["val"]:
                best_adr = {"val": adr, "name": name}
                
            mvp = int(p_stats.get("MVPs", 0))
            if mvp > best_mvp["val"]:
                best_mvp = {"val": mvp, "name": name}
                
            entry = int(p_stats.get("Entry Wins", 0))
            if entry > best_entry["val"]:
                best_entry = {"val": entry, "name": name}
                
            sniper = int(p_stats.get("Sniper Kills", 0))
            if sniper > best_sniper["val"]:
                best_sniper = {"val": sniper, "name": name}

        embed.add_field(name="📊 Scoreboard", value="\n".join(scoreboard) if scoreboard else "N/A", inline=False)
        
        # Analyse avec Emojis
        analysis = []
        if best_mvp["val"] > 0:
            analysis.append(f"🥇 **MVP** : {best_mvp['name']} ({best_mvp['val']} MVPs)")
        if best_adr["val"] > 0:
            analysis.append(f"💥 **Dégâts** : {best_adr['name']} ({best_adr['val']} ADR)")
        if best_entry["val"] > 0:
            analysis.append(f"🏃 **Open Kills** : {best_entry['name']} ({best_entry['val']} duels d'ouverture gagnés)")
        if best_sniper["val"] > 0:
            analysis.append(f"🎯 **Sniper** : {best_sniper['name']} ({best_sniper['val']} kills à l'AWP)")
            
        embed.add_field(name="🌟 Tops Performances", value="\n".join(analysis) if analysis else "N/A", inline=False)
        
        embed.set_footer(text="Rapport Automatique GandaltF4")
        
        await channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoReportTask(bot))
