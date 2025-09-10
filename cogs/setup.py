import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import time
from models import GameState, GameConfig, Player, Phase
from views import SignupView, SetupView
from store import GameStore

class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="endgame", description="Force end/cancel the active Mafia game")
    async def endgame_slash(self, interaction: discord.Interaction):
        """Slash command version of endgame"""
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.guild = interaction.guild
        
        ctx = Context(interaction)
        await self.endgame_command(ctx)

    @app_commands.command(name="cancel", description="Cancel the current game (host only)")
    async def cancel_slash(self, interaction: discord.Interaction):
        """Slash command version of cancel"""
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
                self.bot = self.bot
        
        ctx = Context(interaction)
        await self.cancel_command(ctx)

    @app_commands.command(name="mafia", description="Set the number of mafia players")
    @app_commands.describe(count="Number of mafia players (must be at least 1)")
    async def mafia_slash(self, interaction: discord.Interaction, count: int):
        """Slash command version of mafia"""
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
        
        ctx = Context(interaction)
        await self.mafia_command(ctx, count)

    @app_commands.command(name="neutral", description="Set the number of neutral players")
    @app_commands.describe(
        count="Number of neutral players",
        teamed="Whether neutral players are on the same team"
    )
    async def neutral_slash(self, interaction: discord.Interaction, count: int, teamed: bool = False):
        """Slash command version of neutral"""
        class Context:
            def __init__(self, interaction):
                self.channel = interaction.channel
                self.author = interaction.user
                self.send = interaction.response.send_message
        
        ctx = Context(interaction)
        await self.neutral_command(ctx, count, teamed)

    @app_commands.command(name="play", description="Start a new Mafia game in this channel")
    @app_commands.describe(
        min_players="Minimum number of players",
        max_players="Maximum number of players (0 for unlimited)",
        signup_duration="Signup duration (e.g., 1h, 2d, 30m)",
        game_length="Game length",
        role_density="Role density"
    )
    @app_commands.choices(
        game_length=[
            app_commands.Choice(name="Quick (10m-2h)", value="QUICK"),
            app_commands.Choice(name="Long (24-72h)", value="LONG"),
            app_commands.Choice(name="Extended (7-30d)", value="EXTENDED"),
        ],
        role_density=[
            app_commands.Choice(name="Vanilla (no special roles)", value="VANILLA"),
            app_commands.Choice(name="Light (~25% special roles)", value="LIGHT"),
            app_commands.Choice(name="Heavy (≥50% special roles)", value="HEAVY"),
        ]
    )
    async def play_slash(
        self, 
        interaction: discord.Interaction,
        min_players: int = 7,
        max_players: int = 13,
        signup_duration: str = "24h",
        game_length: app_commands.Choice[str] = None,
        role_density: app_commands.Choice[str] = None
    ):
        """Slash command version of play"""
        # Check if there's already a game in this channel
        store = GameStore(self.bot.db)
        existing_game = await store.get_game(interaction.channel.id)
        
        if existing_game and existing_game.phase.name not in ["ENDED", "CANCELLED"]:
            await interaction.response.send_message("There's already an active game in this channel!", ephemeral=True)
            return
        
        # Check permissions
        if not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to start a game.", ephemeral=True)
            return
        
        # Create a new game
        config = GameConfig()
        game = GameState(
            channel_id=interaction.channel.id,
            guild_id=interaction.guild.id,
            host_id=interaction.user.id,
            config=config,
            players=[]
        )
        
        # Set parameters from command options
        game.config.min_players = min_players
        game.config.max_players = max_players if max_players > 0 else None
        
        if game_length:
            game.config.game_length = game_length.value
        if role_density:
            game.config.role_density = role_density.value
        
        # Parse signup duration
        try:
            duration_str = signup_duration
            if duration_str.endswith('m'):
                seconds = int(duration_str[:-1]) * 60
            elif duration_str.endswith('h'):
                seconds = int(duration_str[:-1]) * 3600
            elif duration_str.endswith('d'):
                seconds = int(duration_str[:-1]) * 86400
            else:
                seconds = int(duration_str)
            
            if seconds < 300:  # 5 minutes
                await interaction.response.send_message("Signup duration must be at least 5 minutes.", ephemeral=True)
                return
            if seconds > 1209600:  # 14 days
                await interaction.response.send_message("Signup duration cannot exceed 14 days.", ephemeral=True)
                return
            
            game.config.signup_ends_at = int(time.time()) + seconds
            game.phase = Phase(
                name="SIGNUP",
                number=0,
                ends_at=game.config.signup_ends_at
            )
        except ValueError:
            await interaction.response.send_message("Invalid duration format. Use something like 1h, 2d, 30m, or seconds.", ephemeral=True)
            return
        
        # Save the game
        await store.save_game(game)
        
        # Create the signup message
        view = SignupView(game)
        msg = await interaction.channel.send(
            f"🎭 Mafia Signup (Channel: {interaction.channel.mention})\n"
            f"Players: 0/{game.config.max_players or '∞'} (0 tentative)\n"
            f"Signup ends: <t:{game.config.signup_ends_at}:F> — <t:{game.config.signup_ends_at}:R>",
            view=view
        )
        
        # Save the message ID
        game.messages['signup_message_id'] = msg.id
        await store.save_game(game)
        
        await interaction.response.send_message("Game created successfully! Signup message posted.", ephemeral=True)
    
    @commands.command(name="endgame")
    @commands.guild_only()
    async def endgame_command(self, ctx):
        """
        Prefix command to force-end/cancel the active Mafia game in this channel.
        Usable by the host or anyone with Manage Channels permission.
        """
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)

        if not game or game.phase.name in ["ENDED", "CANCELLED"]:
            await ctx.send("There is no active game in this channel.", ephemeral=False)
            return

        # Authorization: host or Manage Channels
        if game.host_id != ctx.author.id and not ctx.author.guild_permissions.manage_channels:
            await ctx.send("Only the host or a user with Manage Channels can end the game.", ephemeral=True)
            return

        # Mark game cancelled/ended and persist
        game.phase.name = "CANCELLED"
        await store.save_game(game)

        # Remove signup message buttons (safe-guard)
        try:
            if game.messages.get('signup_message_id'):
                msg = await ctx.channel.fetch_message(game.messages['signup_message_id'])
                await msg.edit(view=None)
        except Exception:
            # ignore if message can't be fetched/edited
            pass

        # If you maintain an in-memory active_games map on the bot, remove it as well
        if hasattr(self.bot, "active_games"):
            try:
                if ctx.channel.id in self.bot.active_games:
                    del self.bot.active_games[ctx.channel.id]
            except Exception:
                pass

        await ctx.send("Game has been force-ended and resources cleaned. You can now start a new game.")
    @commands.command(name="play")
    @commands.guild_only()
    async def play_command(self, ctx, *args):
        # Check if there's already a game in this channel
        store = GameStore(self.bot.db)
        existing_game = await store.get_game(ctx.channel.id)
        
        if existing_game and existing_game.phase.name not in ["ENDED", "CANCELLED"]:
            await ctx.send("There's already an active game in this channel!")
            return
        
        # Create a new game
        config = GameConfig()
        game = GameState(
            channel_id=ctx.channel.id,
            guild_id=ctx.guild.id,
            host_id=ctx.author.id,
            config=config,
            players=[]
        )
        
        # Process arguments if provided
        if args:
            # Handle signup duration parameter
            if args[0] == "signup" and len(args) >= 2:
                # Parse duration (e.g., 1h, 2d, 30m)
                duration_str = args[1]
                try:
                    if duration_str.endswith('m'):
                        seconds = int(duration_str[:-1]) * 60
                    elif duration_str.endswith('h'):
                        seconds = int(duration_str[:-1]) * 3600
                    elif duration_str.endswith('d'):
                        seconds = int(duration_str[:-1]) * 86400
                    else:
                        seconds = int(duration_str)
                    
                    if seconds < 300:  # 5 minutes
                        await ctx.send("Signup duration must be at least 5 minutes.")
                        return
                    if seconds > 1209600:  # 14 days
                        await ctx.send("Signup duration cannot exceed 14 days.")
                        return
                    
                    game.config.signup_ends_at = int(time.time()) + seconds
                    game.phase = Phase(
                        name="SIGNUP",
                        number=0,
                        ends_at=game.config.signup_ends_at
                    )
                    
                    # Save the game
                    await store.save_game(game)
                    
                    # Create the signup message
                    view = SignupView(game)
                    msg = await ctx.send(
                        f"🎭 Mafia Signup (Channel: {ctx.channel.mention})\n"
                        f"Players: 0/{game.config.max_players or '∞'} (0 tentative)\n"
                        f"Signup ends: <t:{game.config.signup_ends_at}:F> — <t:{game.config.signup_ends_at}:R>",
                        view=view
                    )
                    
                    # Save the message ID
                    game.messages['signup_message_id'] = msg.id
                    await store.save_game(game)
                    return
                    
                except ValueError:
                    await ctx.send("Invalid duration format. Use something like 1h, 2d, 30m, or seconds.")
                    return
            # Handle custom player count parameter
            elif args[0] == "custom" and len(args) >= 3:
                try:
                    min_players = int(args[1])
                    max_players = int(args[2]) if args[2].lower() != "none" else None
                    
                    if min_players < 5:
                        await ctx.send("Minimum players must be at least 5.")
                        return
                    if max_players and max_players < min_players:
                        await ctx.send("Maximum players must be greater than or equal to minimum players.")
                        return
                    
                    game.config.min_players = min_players
                    game.config.max_players = max_players
                except ValueError:
                    await ctx.send("Invalid number format. Usage: `m!play custom <min> <max|none>`")
                    return
        
        # If no signup duration was set via args, use default (24h)
        if game.config.signup_ends_at == 0:
            game.config.signup_ends_at = int(time.time()) + 86400
            game.phase = Phase(
                name="SIGNUP",
                number=0,
                ends_at=game.config.signup_ends_at
            )
        
        # Save the game
        await store.save_game(game)
        
        # Send setup wizard if no specific parameters were provided
        if not args or args[0] not in ["custom", "signup"]:
            view = SetupView(game)
            await ctx.send(
                f"{ctx.author.mention} is starting a Mafia game! Let's configure it.\n"
                "First, select the player cap:",
                view=view
            )
        else:
            # Directly create the signup message if custom/signup args were provided
            view = SignupView(game)
            msg = await ctx.send(
                f"🎭 Mafia Signup (Channel: {ctx.channel.mention})\n"
                f"Players: 0/{game.config.max_players or '∞'} (0 tentative)\n"
                f"Signup ends: <t:{game.config.signup_ends_at}:F> — <t:{game.config.signup_ends_at}:R>",
                view=view
            )
            
            # Save the message ID
            game.messages['signup_message_id'] = msg.id
            await store.save_game(game)
    
    @commands.command(name="cancel")
    @commands.guild_only()
    async def cancel_command(self, ctx):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game or game.phase.name in ["ENDED", "CANCELLED"]:
            await ctx.send("No active game in this channel.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can cancel the game.")
            return
        
        # Create confirmation view
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
            
            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the host can confirm cancellation.", ephemeral=True)
                    return
                
                game.phase.name = "CANCELLED"
                await store.save_game(game)
                
                # Remove signup message buttons
                if game.messages.get('signup_message_id'):
                    try:
                        msg = await ctx.channel.fetch_message(game.messages['signup_message_id'])
                        await msg.edit(view=None)
                    except:
                        pass
                
                await interaction.response.send_message("Game has been cancelled.")
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the host can cancel.", ephemeral=True)
                    return
                
                await interaction.response.send_message("Cancellation cancelled.")
                self.stop()
            
            async def on_timeout(self):
                await ctx.send("Cancellation timed out.")
        
        view = ConfirmView()
        await ctx.send("Are you sure you want to cancel the game? This action cannot be undone.", view=view)
    
    @commands.command(name="mafia")
    @commands.guild_only()
    async def mafia_command(self, ctx, count: int):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game or game.phase.name != "SIGNUP":
            await ctx.send("No active signup phase in this channel.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can set mafia count.")
            return
        
        total_players = len(game.players)
        if count < 1:
            await ctx.send("Mafia count must be at least 1.")
            return
        
        if count >= total_players:
            await ctx.send("Mafia count must be less than total player count.")
            return
        
        game.mafia_count = count
        await store.save_game(game)
        
        await ctx.send(f"Mafia count set to {count}. Use `m!neutral <count>` to set neutral count.")
    
    @commands.command(name="neutral")
    @commands.guild_only()
    async def neutral_command(self, ctx, count: int, teamed: bool = False):
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game or game.phase.name != "SIGNUP":
            await ctx.send("No active signup phase in this channel.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can set neutral count.")
            return
        
        total_players = len(game.players)
        mafia_count = getattr(game, 'mafia_count', 0)
        
        if count < 0:
            await ctx.send("Neutral count cannot be negative.")
            return
        
        if mafia_count + count >= total_players:
            await ctx.send("Mafia + neutral count must be less than total player count.")
            return
        
        game.neutral_count = count
        game.config.neutrals_teamed = teamed
        await store.save_game(game)
        
        team_status = "on the same team" if teamed else "on individual teams"
        await ctx.send(f"Neutral count set to {count} ({team_status}). Use the confirmation button in DMs to start the game.")

async def assign_roles(bot, game):
    store = GameStore(bot.db)
    
    # Calculate town count
    total_players = len(game.players)
    town_count = total_players - game.mafia_count - game.neutral_count
    
    # Assign roles
    player_ids = [player.id for player in game.players]
    random.shuffle(player_ids)
    
    # Assign mafia roles
    for i in range(game.mafia_count):
        player_id = player_ids.pop()
        player = game.get_player(player_id)
        player.role = "Mafia"
        game.mafia_ids.append(player_id)
    
    # Assign neutral roles
    neutral_roles = ["Jester", "Executioner", "Serial Killer", "Arsonist"]
    for i in range(game.neutral_count):
        player_id = player_ids.pop()
        player = game.get_player(player_id)
        player.role = random.choice(neutral_roles) if game.config.role_density != "VANILLA" else "Neutral"
        game.neutral_ids.append(player_id)
    
    # Assign town roles
    town_roles = ["Vanilla Townie"]
    if game.config.role_density != "VANILLA":
        town_roles.extend(["Cop", "Doctor", "Vigilante", "Investigator"])
    
    for i in range(town_count):
        player_id = player_ids.pop()
        player = game.get_player(player_id)
        if game.config.role_density == "VANILLA" or i == 0:
            player.role = "Vanilla Townie"
        else:
            # Assign special roles based on density
            if game.config.role_density == "LIGHT" and i % 4 == 0:
                player.role = random.choice(town_roles[1:])
            elif game.config.role_density == "HEAVY" and i % 2 == 0:
                player.role = random.choice(town_roles[1:])
            else:
                player.role = "Vanilla Townie"
        game.town_ids.append(player_id)
    
    # DM roles to players
    for player in game.players:
        try:
            user = await bot.fetch_user(player.id)
            if user:
                await user.send(f"Your role for the Mafia game in <#{game.channel_id}> is: **{player.role}**")
        except:
            print(f"Could not DM user {player.id}")
    
    # Create mafia channel if needed
    if game.mafia_count >= 2:
        guild = bot.get_guild(game.guild_id)
        if guild:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            
            # Add mafia players
            for player_id in game.mafia_ids:
                member = guild.get_member(player_id)
                if member:
                    overwrites[member] = discord.PermissionOverwrite(read_messages=True)
            
            try:
                mafia_channel = await guild.create_text_channel(
                    "mafia-chat",
                    overwrites=overwrites,
                    reason="Mafia game private channel"
                )
                game.mafia_channel_id = mafia_channel.id
            except discord.Forbidden:
                print("Could not create mafia channel - insufficient permissions")
    
    # Start the first day
    game.phase = Phase(
        name="DAY",
        number=1,
        ends_at=int(time.time()) + game.config.day_duration_sec
    )
    
    await store.save_game(game)
    
    # Announce game start
    channel = bot.get_channel(game.channel_id)
    if channel:
        await channel.send(
            f"🌞 Day 1 has begun!\n"
            f"Ends: <t:{game.phase.ends_at}:F> — <t:{game.phase.ends_at}:R>\n"
            f"Use `m!vote @player` to vote. `m!time` to see remaining time.\n"
            f"Check your DMs for your role!"
        )

async def setup(bot):
    cog = SetupCog(bot)
    await bot.add_cog(cog)
    
    # Remove existing slash commands to avoid duplicates
    bot.tree.remove_command("play", type=discord.AppCommandType.chat_input)
    bot.tree.remove_command("endgame", type=discord.AppCommandType.chat_input)
    bot.tree.remove_command("cancel", type=discord.AppCommandType.chat_input)
    bot.tree.remove_command("mafia", type=discord.AppCommandType.chat_input)
    bot.tree.remove_command("neutral", type=discord.AppCommandType.chat_input)
    
    # Add all slash commands
    bot.tree.add_command(cog.play_slash)
    bot.tree.add_command(cog.endgame_slash)
    bot.tree.add_command(cog.cancel_slash)
    bot.tree.add_command(cog.mafia_slash)
    bot.tree.add_command(cog.neutral_slash)