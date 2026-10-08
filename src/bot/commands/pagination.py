import discord


class EmbedPaginator(discord.ui.View):
    """Owner-only previous/next navigation for a sequence of embeds."""

    def __init__(self, embeds: list[discord.Embed], owner_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.owner_id = owner_id
        self.index = 0
        self.message: discord.Message | None = None
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.previous_button.disabled = self.index == 0
        self.next_button.disabled = self.index >= len(self.embeds) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur de cette fiche peut changer de page.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Précédent", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="Suivant", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.embeds) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    async def on_timeout(self) -> None:
        if self.message:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
