import discord
from discord.ext import commands
from store import GameStore

class TimeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
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
    await bot.add_cog(TimeCog(bot))