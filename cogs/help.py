import discord
from discord.ext import commands
from discord import app_commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_help_embed(self):
        embed = discord.Embed(
            title="Mafia Bot Commands",
            description="All available commands for the Mafia game bot",
            color=discord.Color.blue()
        )

        # Game Setup Commands
        embed.add_field(
            name="🎮 Game Setup",
            value=(
                "**m!play** [options] - Start a new game\n"
                "`/play` - Start a new game (slash version)\n"
                "**m!endgame** - Force end/cancel current game\n"
                "**m!cancel** - Cancel game with confirmation\n"
                "**m!mafia** `<count>` - Set number of mafia players\n"
                "**m!neutral** `<count>` [teamed] - Set number of neutral players"
            ),
            inline=False
        )

        # Phase Management Commands
        embed.add_field(
            name="⏱️ Phase Management",
            value=(
                "**m!daytime** - Start day phase\n"
                "**m!nighttime** - Start night phase\n"
                "**m!time** - Show current phase and time remaining"
            ),
            inline=False
        )

        # Voting Commands
        embed.add_field(
            name="🗳️ Voting",
            value=(
                "**m!vote** `[@player]` - Vote for a player or show current tally\n"
                "`/vote` - Vote for a player (slash version)\n"
                "**m!unvote** - Remove your current vote\n"
                "`/unvote` - Remove your vote (slash version)"
            ),
            inline=False
        )

        # Debug Commands
        embed.add_field(
            name="🐛 Debug Commands",
            value=(
                "**m!debugmode** `<on|off>` - Toggle debug mode\n"
                "**m!gamestate** - Display current game state\n"
                "**m!dummy** `<action>` - Manage dummy players\n"
                "Use `m!help debug` for detailed information on debug commands."
            ),
            inline=False
        )

        embed.set_footer(text="Tip: Use m!help <category> for more detailed information on specific command categories.")
        return embed

    def get_debug_help_embed(self):
        debug_embed = discord.Embed(
            title="Debug Commands",
            description="Detailed information on debug commands",
            color=discord.Color.blue()
        )
        debug_embed.add_field(
            name="m!debugmode <on|off>",
            value="Toggle debug mode on or off. Only the game host can use this command.",
            inline=False
        )
        debug_embed.add_field(
            name="m!gamestate",
            value="Display current game state, including debug mode status, player counts, game phase, and more.",
            inline=False
        )
        debug_embed.add_field(
            name="m!dummy <action> [parameters]",
            value=(
                "Manage dummy players for testing. Available actions:\n"
                "- add <name> [role]: Add a dummy player\n"
                "- remove <name>: Remove a dummy player\n"
                "- list: List all dummy players\n"
                "- vote <voter> <target>: Make a dummy player vote\n"
                "- unvote <voter>: Remove a dummy player's vote\n"
                "- kill <player>: Kill a player\n"
                "- revive <player>: Revive a player\n"
                "- assign <player> <role>: Assign a role to a player"
            ),
            inline=False
        )
        return debug_embed

    @commands.command(name="help")
    async def help_command(self, ctx, category: str = None):
        """Shows all available Mafia game commands or detailed help for a specific category"""
        print(f"DEBUG: Text-based help command triggered. Category: {category}")
        try:
            if category and category.lower() == "debug":
                await ctx.send(embed=self.get_debug_help_embed())
            else:
                await ctx.send(embed=self.get_help_embed())
            print("DEBUG: Help message sent successfully")
        except Exception as e:
            print(f"DEBUG: Error in text-based help command: {e}")

    @app_commands.command(name="help", description="Shows all available Mafia game commands")
    @app_commands.choices(category=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Debug", value="debug")
    ])
    async def help_slash(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        """Slash command version of help"""
        print(f"DEBUG: Slash help command triggered. Category: {category.value if category else 'None'}")
        try:
            if category and category.value == "debug":
                await interaction.response.send_message(embed=self.get_debug_help_embed())
            else:
                await interaction.response.send_message(embed=self.get_help_embed())
            print("DEBUG: Help message sent successfully")
        except Exception as e:
            print(f"DEBUG: Error in slash help command: {e}")

async def setup(bot):
    await bot.add_cog(HelpCog(bot))