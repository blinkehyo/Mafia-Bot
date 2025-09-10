import discord
from discord import app_commands
from discord.ext import commands

class EndGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="endgame", description="End the active Mafia game in this channel")
    @app_commands.guilds(discord.Object(id=624414875913027604))
    async def endgame(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        if not hasattr(self.bot, "active_games") or channel_id not in self.bot.active_games:
            await interaction.response.send_message("There is no active game in this channel.", ephemeral=True)
            return

        del self.bot.active_games[channel_id]
        await interaction.response.send_message("The game has been ended. You can now start a new one.")

async def setup(bot):
    await bot.add_cog(EndGame(bot))
