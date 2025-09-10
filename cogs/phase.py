import discord
from discord.ext import commands
from discord import app_commands
from store import GameStore
import time

class PhaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="daytime", description="Start the day phase (host only)")
    async def daytime_slash(self, interaction: discord.Interaction):
        """Slash command version of daytime"""
        # Convert interaction to context-like object for reuse
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
        
        ctx = Context(interaction)
        await self.daytime_command(ctx)

    @commands.command(name="daytime")
    @commands.guild_only()
    async def daytime_command(self, ctx):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game:
            await ctx.send("No active game in this channel.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can change phases.")
            return
        
        if game.phase.name != "NIGHT":
            await ctx.send("Can only start day from night phase.")
            return
        
        # End night and start day
        game.phase.name = "DAY"
        game.phase.number += 1
        game.phase.ends_at = int(time.time()) + game.config.day_duration_sec
        
        # Clear votes
        game.votes = {}
        
        await store.save_game(game)
        
        await ctx.send(
            f"🌞 Day {game.phase.number} has begun!\n"
            f"Ends: <t:{game.phase.ends_at}:F> — <t:{game.phase.ends_at}:R>\n"
            f"Use `m!vote @player` to vote. `m!time` to see remaining time."
        )
    
    @app_commands.command(name="nighttime", description="Start the night phase (host only)")
    async def nighttime_slash(self, interaction: discord.Interaction):
        """Slash command version of nighttime"""
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
        
        ctx = Context(interaction)
        await self.nighttime_command(ctx)

    @commands.command(name="nighttime")
    @commands.guild_only()
    async def nighttime_command(self, ctx):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game:
            await ctx.send("No active game in this channel.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can change phases.")
            return
        
        if game.phase.name != "DAY":
            await ctx.send("Can only start night from day phase.")
            return
        
        # End day and start night
        game.phase.name = "NIGHT"
        game.phase.ends_at = int(time.time()) + game.config.night_duration_sec
        
        # Clear votes
        game.votes = {}
        
        await store.save_game(game)
        
        await ctx.send(
            f"🌙 Night {game.phase.number} has begun. Ends: <t:{game.phase.ends_at}:F> — <t:{game.phase.ends_at}:R>\n"
            f"No talking if your server rules disallow it. Host: actions via DM."
        )

    @app_commands.command(name="time", description="Show current phase and time remaining")
    async def time_slash(self, interaction: discord.Interaction):
        """Slash command version of time"""
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.send = interaction.response.send_message
        
        ctx = Context(interaction)
        await self.time_command(ctx)

    @commands.command(name="time")
    @commands.guild_only()
    async def time_command(self, ctx):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game or game.phase.name in ["ENDED", "CANCELLED"]:
            await ctx.send("No active game in this channel.")
            return
        
        await ctx.send(
            f"Current phase: {game.phase.name} {game.phase.number if game.phase.number > 0 else ''}\n"
            f"Ends: <t:{game.phase.ends_at}:F> — <t:{game.phase.ends_at}:R>"
        )

async def setup(bot):
    cog = PhaseCog(bot)
    await bot.add_cog(cog)
    
    # Remove any existing slash commands to avoid duplicates
    bot.tree.remove_command("daytime", type=discord.AppCommandType.chat_input)
    bot.tree.remove_command("nighttime", type=discord.AppCommandType.chat_input)
    bot.tree.remove_command("time", type=discord.AppCommandType.chat_input)
    
    # Add the slash commands
    bot.tree.add_command(cog.daytime_slash)
    bot.tree.add_command(cog.nighttime_slash)
    bot.tree.add_command(cog.time_slash)