import discord
from discord.ext import commands
from discord import app_commands
from store import GameStore
import time

class VoteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="vote", description="Vote for a player during the day phase")
    @app_commands.describe(player="The player to vote for")
    async def vote_slash(self, interaction: discord.Interaction, player: discord.Member):
        """Slash command version of vote"""
        # Convert interaction to context-like object
        class Context:
            def __init__(self, interaction, bot):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        ctx = Context(interaction, self.bot)
        await self.vote_command(ctx, player)
        
    @app_commands.command(name="unvote", description="Remove your current vote")
    async def unvote_slash(self, interaction: discord.Interaction):
        """Slash command version of unvote"""
        # Convert interaction to context-like object
        class Context:
            def __init__(self, interaction, bot):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = bot
        
        ctx = Context(interaction, self.bot)
        await self.unvote_command(ctx)
    
    @commands.command(name="vote")
    @commands.guild_only()
    async def vote_command(self, ctx, target: discord.Member = None):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game or game.phase.name != "DAY":
            await ctx.send("Voting is only allowed during day phases.")
            return
        
        # Check if voter is alive
        voter = game.get_player(ctx.author.id)
        if not voter or voter.status != "alive":
            await ctx.send("Only alive players can vote.")
            return
        
        if target is None:
            # Show current tally
            await self.show_tally(ctx, game)
            return
        
        # Check if target is valid
        target_player = game.get_player(target.id)
        if not target_player or target_player.status != "alive":
            await ctx.send("You can only vote for alive players.")
            return
        
        # Record vote
        game.votes[ctx.author.id] = target.id
        await store.save_game(game)
        
        await ctx.send(f"{ctx.author.mention} has voted for {target.mention}.", allowed_mentions=discord.AllowedMentions.none())
        
        # Update tally
        await self.update_tally(ctx, game)
        
        # Check for hammer
        vote_count = game.get_vote_count(target.id)
        majority = game.get_majority_threshold()
        
        if vote_count >= majority:
            # Hammer reached
            await ctx.send(f"🔨 Hammer on {target.mention}! Twilight begins. (60s)")
            
            # Notify host
            host = await self.bot.fetch_user(game.host_id)
            if host:
                await host.send(f"Hammer reached on {target.mention} in <#{game.channel_id}>. Please record the flip.")
            
            # End day phase
            game.phase.name = "TWILIGHT"
            game.phase.ends_at = int(time.time()) + 60  # 60 second twilight
            await store.save_game(game)
    
    @commands.command(name="unvote")
    @commands.guild_only()
    async def unvote_command(self, ctx):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game or game.phase.name != "DAY":
            await ctx.send("Voting is only allowed during day phases.")
            return
        
        # Check if voter has a vote
        if ctx.author.id not in game.votes:
            await ctx.send("You don't have an active vote to remove.")
            return
        
        # Remove vote
        del game.votes[ctx.author.id]
        await store.save_game(game)
        
        await ctx.send(f"{ctx.author.mention} has removed their vote.")
        
        # Update tally
        await self.update_tally(ctx, game)
    
    async def show_tally(self, ctx, game):
        alive_players = game.get_alive_players()
        alive_count = len(alive_players)
        majority = game.get_majority_threshold()
        
        # Count votes per player
        vote_counts = {}
        for target_id in game.votes.values():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        
        # Create tally message
        lines = []
        for player in alive_players:
            count = vote_counts.get(player.id, 0)
            to_hammer = majority - count
            hammer_text = f" **[{to_hammer} to hammer]**" if to_hammer > 0 and to_hammer <= 3 else ""
            lines.append(f"# <@{player.id}> ({count}){hammer_text}")
        
        # Find not voting players
        voting_players = set(game.votes.keys())
        not_voting = [f"<@{p.id}>" for p in alive_players if p.id not in voting_players]
        
        tally_msg = (
            f"📊 Vote Tally (Day {game.phase.number}) — {alive_count} alive, majority is {majority}\n"
            + "\n".join(lines) +
            f"\nNot voting ({len(not_voting)}): {', '.join(not_voting) if not_voting else 'None'}"
        )
        
        await ctx.send(tally_msg, allowed_mentions=discord.AllowedMentions.none())
    
    async def update_tally(self, ctx, game):
        # Check if we have a tally message to update
        if not game.messages.get('tally_message_id'):
            return
        
        try:
            tally_msg = await ctx.channel.fetch_message(game.messages['tally_message_id'])
            await self.show_tally(ctx, game)  # This will edit the message content
        except:
            pass

async def setup(bot):
    cog = VoteCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.vote_slash)
    bot.tree.add_command(cog.unvote_slash)