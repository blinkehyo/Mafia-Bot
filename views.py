import discord
from discord.ui import View, Button, Select
from models import GameState, GameConfig
from typing import Optional

class SignupView(View):
    def __init__(self, game: GameState):
        super().__init__(timeout=None)
        self.game = game
    
    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="join_button")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        # Check if user is already in the game
        user_id = interaction.user.id
        player = self.game.get_player(user_id)
        
        if player and not player.tentative:
            await interaction.response.send_message("You're already in the game!", ephemeral=True)
            return
        
        # Check if game is full
        max_players = self.game.config.max_players
        if max_players and len([p for p in self.game.players if not p.tentative]) >= max_players:
            # Check if there are tentatives to remove
            tentatives = [p for p in self.game.players if p.tentative]
            if tentatives:
                # Remove the most recent tentative
                self.game.remove_player(tentatives[-1].id)
                self.game.add_player(user_id, tentative=False)
                await interaction.response.send_message("You've joined the game! A tentative player was removed to make space.", ephemeral=True)
            else:
                await interaction.response.send_message("The game is full!", ephemeral=True)
                return
        else:
            if player and player.tentative:
                # Promote from tentative to full
                player.tentative = False
                await interaction.response.send_message("You've been promoted from tentative to full player!", ephemeral=True)
            else:
                # Add new player
                self.game.add_player(user_id, tentative=False)
                await interaction.response.send_message("You've joined the game!", ephemeral=True)
        
        # Update the signup message
        from store import GameStore
        store = GameStore(interaction.client.db)
        await store.save_game(self.game)
        
        # Update the signup message count
        channel = interaction.channel
        try:
            msg = await channel.fetch_message(self.game.messages['signup_message_id'])
            tentative_count = len([p for p in self.game.players if p.tentative])
            full_count = len([p for p in self.game.players if not p.tentative])
            max_str = f"/{self.game.config.max_players}" if self.game.config.max_players else ""
            
            await msg.edit(
                content=f"🎭 Mafia Signup (Channel: {channel.mention})\n"
                       f"Players: {full_count}{max_str} ({tentative_count} tentative)\n"
                       f"Signup ends: <t:{self.game.config.signup_ends_at}:F> — <t:{self.game.config.signup_ends_at}:R>",
                view=self
            )
        except:
            pass

    @discord.ui.button(label="Tentative", style=discord.ButtonStyle.secondary, custom_id="tentative_button")
    async def tentative_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        
        # Check if user is already in the game
        player = self.game.get_player(user_id)
        if player:
            if player.tentative:
                await interaction.response.send_message("You're already tentative!", ephemeral=True)
            else:
                await interaction.response.send_message("You're already a full player! Use the Join button if you want to confirm your spot.", ephemeral=True)
            return
        
        # Add as tentative
        self.game.add_player(user_id, tentative=True)
        await interaction.response.send_message("You've been added as a tentative player.", ephemeral=True)
        
        # Update the signup message
        from store import GameStore
        store = GameStore(interaction.client.db)
        await store.save_game(self.game)
        
        # Update the signup message count
        channel = interaction.channel
        try:
            msg = await channel.fetch_message(self.game.messages['signup_message_id'])
            tentative_count = len([p for p in self.game.players if p.tentative])
            full_count = len([p for p in self.game.players if not p.tentative])
            max_str = f"/{self.game.config.max_players}" if self.game.config.max_players else ""
            
            await msg.edit(
                content=f"🎭 Mafia Signup (Channel: {channel.mention})\n"
                       f"Players: {full_count}{max_str} ({tentative_count} tentative)\n"
                       f"Signup ends: <t:{self.game.config.signup_ends_at}:F> — <t:{self.game.config.signup_ends_at}:R>",
                view=self
            )
        except:
            pass

    @discord.ui.button(label="Withdraw", style=discord.ButtonStyle.danger, custom_id="withdraw_button")
    async def withdraw_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        
        # Check if user is in the game
        player = self.game.get_player(user_id)
        if not player:
            await interaction.response.send_message("You're not in the game!", ephemeral=True)
            return
        
        # Remove the player
        self.game.remove_player(user_id)
        await interaction.response.send_message("You've been removed from the game.", ephemeral=True)
        
        # Update the signup message
        from store import GameStore
        store = GameStore(interaction.client.db)
        await store.save_game(self.game)
        
        # Update the signup message count
        channel = interaction.channel
        try:
            msg = await channel.fetch_message(self.game.messages['signup_message_id'])
            tentative_count = len([p for p in self.game.players if p.tentative])
            full_count = len([p for p in self.game.players if not p.tentative])
            max_str = f"/{self.game.config.max_players}" if self.game.config.max_players else ""
            
            await msg.edit(
                content=f"🎭 Mafia Signup (Channel: {channel.mention})\n"
                       f"Players: {full_count}{max_str} ({tentative_count} tentative)\n"
                       f"Signup ends: <t:{self.game.config.signup_ends_at}:F> — <t:{self.game.config.signup_ends_at}:R>",
                view=self
            )
        except:
            pass

class SetupView(View):
    def __init__(self, game: GameState):
        super().__init__(timeout=300)  # 5 minute timeout
        self.game = game
    
    @discord.ui.select(
        placeholder="Select player cap",
        options=[
            discord.SelectOption(label="Micro (5-7 players)", value="micro"),
            discord.SelectOption(label="Normal (7-13 players)", value="normal"),
            discord.SelectOption(label="Large (14-25 players)", value="large"),
            discord.SelectOption(label="Unlimited (5+ players)", value="unlimited"),
            discord.SelectOption(label="Custom", value="custom"),
        ]
    )
    async def player_cap_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.game.host_id:
            await interaction.response.send_message("Only the host can configure the game.", ephemeral=True)
            return
        
        value = select.values[0]
        if value == "micro":
            self.game.config.min_players = 5
            self.game.config.max_players = 7
        elif value == "normal":
            self.game.config.min_players = 7
            self.game.config.max_players = 13
        elif value == "large":
            self.game.config.min_players = 14
            self.game.config.max_players = 25
        elif value == "unlimited":
            self.game.config.min_players = 5
            self.game.config.max_players = None
        else:  # custom
            # Would need to implement a modal for custom input
            await interaction.response.send_message("Please use the command again with custom parameters: `m!play custom <min> <max>`", ephemeral=True)
            return
        
        await interaction.response.send_message(f"Player cap set to: {self.game.config.min_players}-{self.game.config.max_players or '∞'}", ephemeral=True)
        
        # Proceed to next configuration step
        await self.ask_game_length(interaction)
    
    async def ask_game_length(self, interaction: discord.Interaction):
        # Create a new view for game length selection
        view = GameLengthView(self.game)
        await interaction.followup.send(
            "Select game length:",
            view=view,
            ephemeral=True
        )

class GameLengthView(View):
    def __init__(self, game: GameState):
        super().__init__(timeout=300)
        self.game = game
    
    @discord.ui.select(
        placeholder="Select game length",
        options=[
            discord.SelectOption(label="Quick (10m-2h)", value="quick"),
            discord.SelectOption(label="Long (24-72h)", value="long"),
            discord.SelectOption(label="Extended (7-30d)", value="extended"),
        ]
    )
    async def game_length_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.game.host_id:
            await interaction.response.send_message("Only the host can configure the game.", ephemeral=True)
            return
        
        self.game.config.game_length = select.values[0].upper()
        await interaction.response.send_message(f"Game length set to: {self.game.config.game_length}", ephemeral=True)
        
        # Proceed to next configuration step
        await self.ask_role_density(interaction)
    
    async def ask_role_density(self, interaction: discord.Interaction):
        view = RoleDensityView(self.game)
        await interaction.followup.send(
            "Select role density:",
            view=view,
            ephemeral=True
        )

class RoleDensityView(View):
    def __init__(self, game: GameState):
        super().__init__(timeout=300)
        self.game = game
    
    @discord.ui.select(
        placeholder="Select role density",
        options=[
            discord.SelectOption(label="Vanilla (no special roles)", value="vanilla"),
            discord.SelectOption(label="Light (~25% special roles)", value="light"),
            discord.SelectOption(label="Heavy (≥50% special roles)", value="heavy"),
        ]
    )
    async def role_density_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.game.host_id:
            await interaction.response.send_message("Only the host can configure the game.", ephemeral=True)
            return
        
        self.game.config.role_density = select.values[0].upper()
        await interaction.response.send_message(f"Role density set to: {self.game.config.role_density}", ephemeral=True)
        
        # Proceed to next configuration step
        await self.ask_signup_duration(interaction)
    
    async def ask_signup_duration(self, interaction: discord.Interaction):
        # Would need to implement a modal for duration input
        await interaction.followup.send(
            "Please set the signup duration using: `m!play signup <duration>` where duration is like 1h, 2d, etc.",
            ephemeral=True
        )

class RoleAssignmentView(View):
    def __init__(self, game: GameState):
        super().__init__(timeout=None)
        self.game = game
    
    @discord.ui.button(label="Set Mafia Count", style=discord.ButtonStyle.primary)
    async def set_mafia_count(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.game.host_id:
            await interaction.response.send_message("Only the host can configure roles.", ephemeral=True)
            return
        
        # Calculate suggested mafia count based on role density
        total_players = len(self.game.players)
        if self.game.config.role_density == "VANILLA":
            suggested = max(1, total_players // 4)
        elif self.game.config.role_density == "LIGHT":
            suggested = max(1, total_players // 3)
        else:  # HEAVY
            suggested = max(1, total_players // 2)
        
        await interaction.response.send_message(
            f"Suggested mafia count: {suggested}. Use `m!mafia <count>` to set the exact number.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Set Neutral Count", style=discord.ButtonStyle.secondary)
    async def set_neutral_count(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.game.host_id:
            await interaction.response.send_message("Only the host can configure roles.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Use `m!neutral <count> [teamed]` to set the number of neutral players and whether they're on the same team.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Confirm and Start", style=discord.ButtonStyle.success)
    async def confirm_start(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.game.host_id:
            await interaction.response.send_message("Only the host can start the game.", ephemeral=True)
            return
        
        # Validate that we have mafia and neutral counts set
        if not hasattr(self.game, 'mafia_count') or not hasattr(self.game, 'neutral_count'):
            await interaction.response.send_message("Please set both mafia and neutral counts first.", ephemeral=True)
            return
        
        # Assign roles and start the game
        from cogs.setup import assign_roles
        await assign_roles(interaction.client, self.game)
        
        await interaction.response.send_message("Game is starting! Roles are being assigned and DMed to players.", ephemeral=True)