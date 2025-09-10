import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from models import GameState, Player
from store import GameStore

class DebugCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dummy_user_counter = -1  # Negative IDs for dummy users
    
    @commands.command(name="debugmode")
    @commands.guild_only()
    async def debug_command(self, ctx, mode: str):
        """Enable or disable debug mode"""
        print(f"DEBUG: debugmode command called with mode: {mode}")

        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        print(f"DEBUG: Game found: {game is not None}")
        if game:
            print(f"DEBUG: Current debug_mode: {getattr(game, 'debug_mode', 'NOT SET')}")
            print(f"DEBUG: Host ID: {game.host_id}, Author ID: {ctx.author.id}")

        if not game:
            await ctx.send("No active game in this channel.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can enable debug mode.")
            return
        
        if mode.lower() == "on":
            game.debug_mode = True
            print(f"DEBUG: Set debug_mode to True")
            await ctx.send("Debug mode enabled. Use `m!dummy` commands to add test players.")
        elif mode.lower() == "off":
            game.debug_mode = False
            # Clear dummy players when disabling debug
            game.dummy_players = []
            print(f"DEBUG: Set debug_mode to False")
            await ctx.send("Debug mode disabled. All dummy players removed.")
        else:
            await ctx.send("Usage: `m!debugmode on|off`")
        
        # Add debug output before and after saving
        print(f"DEBUG: About to save game with debug_mode: {game.debug_mode}")
        await store.save_game(game)
        
        # Verify the save worked by immediately retrieving the game
        saved_game = await store.get_game(ctx.channel.id)
        print(f"DEBUG: After save, retrieved debug_mode: {getattr(saved_game, 'debug_mode', 'NOT SET')}")

    @debug_command.error
    async def debug_error(self, ctx, error):
        """Error handler for debug command"""
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `m!debugmode on|off`")
        else:
            print(f"Unexpected error in debug command: {error}")
    
    @commands.command(name="dummy")
    @commands.guild_only()
    async def dummy_command(self, ctx, action: str, *args):
        """Manage dummy players for testing"""
        print(f"DEBUG: dummy command called with action: {action}, args: {args}")
        
        store = GameStore(self.bot.db)
        game = await store.get_game(ctx.channel.id)
        
        if not game:
            await ctx.send("No active game in this channel.")
            return
        
        current_debug_mode = getattr(game, 'debug_mode', False)
        if not current_debug_mode:
            await ctx.send("Debug mode is not enabled. Use `m!debugmode on` first.")
            return
        
        if game.host_id != ctx.author.id:
            await ctx.send("Only the host can manage dummy players.")
            return
        
        # Handle different actions
        if action.lower() == "add":
            if len(args) < 1:
                await ctx.send("Usage: `m!dummy add <name> [role]`")
                return
            
            name = args[0]
            role = args[1] if len(args) > 1 else "Villager"
            
            # Generate a unique negative ID for the dummy player
            self.dummy_user_counter -= 1
            dummy_id = self.dummy_user_counter
            
            # Create and add the dummy player
            dummy_player = Player(id=dummy_id, name=name, role=role)
            game.dummy_players.append(dummy_player)
            
            await store.save_game(game)
            await ctx.send(f"Added dummy player '{name}' with role '{role}' (ID: {dummy_id})")
        
        elif action.lower() == "remove":
            if len(args) < 1:
                await ctx.send("Usage: `m!dummy remove <name>`")
                return
            
            name = args[0]
            removed = False
            
            for i, player in enumerate(game.dummy_players):
                if player.name and player.name.lower() == name.lower():
                    del game.dummy_players[i]
                    removed = True
                    break
            
            if removed:
                await store.save_game(game)
                await ctx.send(f"Removed dummy player '{name}'")
            else:
                await ctx.send(f"No dummy player named '{name}' found")
        
        elif action.lower() == "list":
            if not game.dummy_players:
                await ctx.send("No dummy players added.")
                return
            
            player_list = []
            for player in game.dummy_players:
                status = f"{player.name} (ID: {player.id}, Role: {player.role}, Status: {player.status})"
                player_list.append(status)
            
            await ctx.send("Dummy players:\n" + "\n".join(player_list))
        
        elif action.lower() == "vote":
            if len(args) < 2:
                await ctx.send("Usage: `m!dummy vote <voter> <target>`")
                return
            
            voter_name, target_name = args[0], args[1]
            
            # Find voter and target players
            voter = None
            target = None
            
            for player in game.get_all_players():
                if player.name and player.name.lower() == voter_name.lower():
                    voter = player
                if player.name and player.name.lower() == target_name.lower():
                    target = player
            
            if not voter:
                await ctx.send(f"Voter '{voter_name}' not found")
                return
            
            if not target:
                await ctx.send(f"Target '{target_name}' not found")
                return
            
            # Record the vote
            game.votes[voter.id] = target.id
            await store.save_game(game)
            await ctx.send(f"{voter.name} voted for {target.name}")
        
        elif action.lower() == "unvote":
            if len(args) < 1:
                await ctx.send("Usage: `m!dummy unvote <voter>`")
                return
            
            voter_name = args[0]
            voter = None
            
            for player in game.get_all_players():
                if player.name and player.name.lower() == voter_name.lower():
                    voter = player
                    break
            
            if not voter:
                await ctx.send(f"Voter '{voter_name}' not found")
                return
            
            if voter.id in game.votes:
                del game.votes[voter.id]
                await store.save_game(game)
                await ctx.send(f"Removed vote from {voter.name}")
            else:
                await ctx.send(f"{voter.name} doesn't have a vote to remove")
        
        elif action.lower() == "kill":
            if len(args) < 1:
                await ctx.send("Usage: `m!dummy kill <player>`")
                return
            
            player_name = args[0]
            player = None
            
            for p in game.get_all_players():
                if p.name and p.name.lower() == player_name.lower():
                    player = p
                    break
            
            if not player:
                await ctx.send(f"Player '{player_name}' not found")
                return
            
            player.status = "dead"
            await store.save_game(game)
            await ctx.send(f"{player.name} has been killed")
        
        elif action.lower() == "revive":
            if len(args) < 1:
                await ctx.send("Usage: `m!dummy revive <player>`")
                return
            
            player_name = args[0]
            player = None
            
            for p in game.get_all_players():
                if p.name and p.name.lower() == player_name.lower():
                    player = p
                    break
            
            if not player:
                await ctx.send(f"Player '{player_name}' not found")
                return
            
            player.status = "alive"
            await store.save_game(game)
            await ctx.send(f"{player.name} has been revived")
        
        elif action.lower() == "assign":
            if len(args) < 2:
                await ctx.send("Usage: `m!dummy assign <player> <role>`")
                return
            
            player_name, role = args[0], args[1]
            player = None
            
            for p in game.get_all_players():
                if p.name and p.name.lower() == player_name.lower():
                    player = p
                    break
            
            if not player:
                await ctx.send(f"Player '{player_name}' not found")
                return
            
            player.role = role
            await store.save_game(game)
            await ctx.send(f"Assigned role '{role}' to {player.name}")
        
        else:
            await ctx.send("""
            Invalid action. Available actions:
            
            add <name> [role] - Add a dummy player
            remove <name> - Remove a dummy player
            list - List all dummy players
            vote <voter> <target> - Make a dummy player vote
            unvote <voter> - Remove a dummy player's vote
            kill <player> - Kill a player
            revive <player> - Revive a player
            assign <player> <role> - Assign a role to a player
            """)
    
    @dummy_command.error
    async def dummy_error(self, ctx, error):
        """Error handler for dummy command"""
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("""
            Usage: `m!dummy <action> [parameters]`
        
            Available actions:
            - `add <name> [role]` - Add a dummy player
            - `remove <name>` - Remove a dummy player
            - `list` - List all dummy players
            - `vote <voter> <target>` - Make a dummy player vote
            - `unvote <voter>` - Remove a dummy player's vote
            - `kill <player>` - Kill a player
            - `revive <player>` - Revive a player
            - `assign <player> <role>` - Assign a role to a player
            """)
        else:
            await ctx.send(f"An error occurred: {str(error)}")
            print(f"Unexpected error in dummy command: {error}")

    @commands.command(name="gamestate")
    @commands.guild_only()
    async def gamestate_command(self, ctx):
        """Display current game state"""
        try:
            store = GameStore(self.bot.db)
            game = await store.get_game(ctx.channel.id)
            
            if not game:
                await ctx.send("No active game in this channel.")
                return
            
            debug_mode = getattr(game, 'debug_mode', False)
            regular_players = len(game.players)
            dummy_players = len(getattr(game, 'dummy_players', []))
            
            status_message = (
                f"Debug Mode: **{'Enabled' if debug_mode else 'Disabled'}**\n"
                f"Regular Players: **{regular_players}**\n"
                f"Dummy Players: **{dummy_players}**\n"
                f"Total Players: **{regular_players + dummy_players}**\n"
                f"Game Phase: **{getattr(game.phase, 'name', 'UNKNOWN')}**\n"
                f"Game State: **{getattr(game, 'state', 'UNKNOWN')}**"
            )
            
            await ctx.send(status_message)
        except Exception as e:
            await ctx.send(f"An error occurred while fetching game state: {str(e)}")
            print(f"Unexpected error in gamestate command: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            if ctx.invoked_with.startswith('debug'):
                await ctx.send(f"Debug command '{ctx.invoked_with}' not found. Use 'm!help' to see available debug commands.")
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Bad argument: {str(error)}")
        else:
            await ctx.send(f"An error occurred: {str(error)}")
        print(f"Command '{ctx.command}' raised an error: {error}")

async def setup(bot):
    print("DEBUG: Setting up DebugCo