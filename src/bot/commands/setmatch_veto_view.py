import copy

import discord

from src.core.veto_analyzer import OFFICIAL_MAP_POOL


class SetMatchVetoView(discord.ui.View):
    """Interactive A/B map veto embedded in the paginated setmatch report."""

    TURNS = (("A", 1), ("B", 2), ("A", 2), ("B", 1))

    def __init__(
        self,
        pages: list[discord.Embed],
        owner_id: int,
        *,
        veto_page_index: int = 1,
        team_a_name: str = "GandaltF4",
        team_b_name: str = "Adversaire",
        timeout: float = 900,
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.owner_id = owner_id
        self.veto_page_index = veto_page_index
        self._initial_veto_embed = copy.deepcopy(pages[veto_page_index])
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        self.page_index = 0
        self.actions: list[dict[str, str]] = []
        self.remaining: list[str] = []
        self.stage = 0
        self.stage_count = 0
        self.bans = {"A": [], "B": []}
        self.played_map: str | None = None
        self.map_buttons: dict[str, discord.ui.Button] = {}

        for index, map_name in enumerate(OFFICIAL_MAP_POOL):
            button = discord.ui.Button(label=map_name, style=discord.ButtonStyle.secondary, row=index // 4)

            async def select_map(interaction: discord.Interaction, chosen_map: str = map_name):
                await self._select_map(interaction, chosen_map)

            button.callback = select_map
            self.map_buttons[map_name] = button
            self.add_item(button)

        self.previous_button = discord.ui.Button(label="Précédent", emoji="◀️", style=discord.ButtonStyle.secondary, row=4)
        self.next_button = discord.ui.Button(label="Suivant", emoji="▶️", style=discord.ButtonStyle.secondary, row=4)
        self.undo_button = discord.ui.Button(label="Annuler dernier", style=discord.ButtonStyle.secondary, row=4)
        self.reset_button = discord.ui.Button(label="Réinitialiser", style=discord.ButtonStyle.danger, row=4)
        self.previous_button.callback = self._previous
        self.next_button.callback = self._next
        self.undo_button.callback = self._undo
        self.reset_button.callback = self._reset
        for button in (self.previous_button, self.next_button, self.undo_button, self.reset_button):
            self.add_item(button)

        self._rebuild_state()
        self._refresh_veto_embed()
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l’auteur de `!setmatch` peut saisir les bans et naviguer dans ce rapport.",
                ephemeral=True,
            )
            return False
        return True

    def _rebuild_state(self) -> None:
        self.remaining = list(OFFICIAL_MAP_POOL)
        self.stage = 0
        self.stage_count = 0
        self.bans = {"A": [], "B": []}
        self.played_map = None

        for action in self.actions:
            map_name = action["map"]
            if map_name not in self.remaining:
                continue
            self.remaining.remove(map_name)
            self.bans[action["team"]].append(map_name)
            self.stage_count += 1
            if self.stage < len(self.TURNS) and self.stage_count == self.TURNS[self.stage][1]:
                self.stage += 1
                self.stage_count = 0
        if self.stage == len(self.TURNS) and len(self.remaining) == 1:
            self.played_map = self.remaining[0]

    def _instruction(self) -> str:
        if self.played_map:
            last_ban = self.actions[-1]["map"]
            return f"✅ Équipe B a banni **{last_ban}**. Map jouée : **{self.played_map}**. Veto terminé."
        if self.stage < len(self.TURNS):
            team, count = self.TURNS[self.stage]
            left = count - self.stage_count
            return f"Étape {self.stage + 1}/4 — équipe **{team}** : bannir encore **{left}** map(s)."
        return "Veto terminé. Une seule map reste à jouer."

    def _status_text(self) -> str:
        parts = [
            f"A = {self.team_a_name} · B = {self.team_b_name}",
            "L’auteur de la commande saisit les choix annoncés par les deux équipes.",
            self._instruction(),
        ]
        if self.bans["A"]:
            parts.append("Bans A : " + ", ".join(self.bans["A"]))
        if self.bans["B"]:
            parts.append("Bans B : " + ", ".join(self.bans["B"]))
        parts.append("Maps restantes : " + (", ".join(self.remaining) if self.remaining else "aucune"))
        return "\n".join(parts)

    def _refresh_veto_embed(self) -> None:
        # Always rebuild from an untouched base embed. Mutating a derived embed
        # on each page visit caused duplicate status fields in Discord.
        embed = copy.deepcopy(self._initial_veto_embed)
        if self.actions:
            for index in reversed(range(len(embed.fields))):
                if embed.fields[index].name in {"🎯 PICK", "🚫 BANS PRIORITAIRES"}:
                    embed.remove_field(index)
        embed.add_field(name="🔄 VETO EN COURS", value=self._status_text(), inline=False)
        self.pages[self.veto_page_index] = embed

    def _current_embed(self) -> discord.Embed:
        return self.pages[self.page_index]

    def _sync_buttons(self) -> None:
        self.previous_button.disabled = self.page_index == 0
        self.next_button.disabled = self.page_index >= len(self.pages) - 1
        self.undo_button.disabled = not self.actions
        self.reset_button.disabled = not self.actions

        for map_name, button in self.map_buttons.items():
            button.disabled = (
                self.page_index != self.veto_page_index
                or self.played_map is not None
                or map_name not in self.remaining
            )

    async def _select_map(self, interaction: discord.Interaction, map_name: str) -> None:
        if self.page_index != self.veto_page_index or map_name not in self.remaining or self.played_map:
            await interaction.response.send_message("Cette map n’est plus disponible pour cette étape.", ephemeral=True)
            return
        if self.stage < len(self.TURNS):
            team, _ = self.TURNS[self.stage]
            self.actions.append({"type": "BAN", "team": team, "map": map_name})
        else:
            await interaction.response.send_message("Le veto est terminé.", ephemeral=True)
            return
        self._rebuild_state()
        self._refresh_veto_embed()
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _previous(self, interaction: discord.Interaction) -> None:
        self.page_index = max(0, self.page_index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.page_index = min(len(self.pages) - 1, self.page_index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _undo(self, interaction: discord.Interaction) -> None:
        if self.actions:
            self.actions.pop()
            self._rebuild_state()
            self._refresh_veto_embed()
            self._sync_buttons()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _reset(self, interaction: discord.Interaction) -> None:
        self.actions.clear()
        self._rebuild_state()
        self._refresh_veto_embed()
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if getattr(self, "message", None):
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
