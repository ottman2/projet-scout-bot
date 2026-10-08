from src.bot.commands.player import setup as setup_player
from src.bot.commands.scout import setup as setup_scout
from src.bot.commands.setmatch import setup as setup_setmatch
from src.bot.commands.veto import setup as setup_veto


def setup_commands(bot) -> None:
    setup_setmatch(bot)
    setup_scout(bot)
    setup_player(bot)
    setup_veto(bot)
