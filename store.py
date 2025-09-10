import aiosqlite
import json
from models import GameState
from typing import Optional, List
import time

class GameStore:
    def __init__(self, db):
        self.db = db
    
    async def init_db(self):
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS games (
                channel_id INTEGER PRIMARY KEY,
                game_data TEXT NOT NULL
            )
        ''')
        await self.db.commit()
    
    async def get_game(self, channel_id):
        """Get game with debug output"""
        async with self.db.execute('SELECT game_data FROM games WHERE channel_id = ?', (channel_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                game_data = json.loads(row[0])
                print(f"STORE DEBUG: Raw loaded data - debug_mode = {game_data.get('debug_mode', 'MISSING')}")
                
                game = GameState.from_dict(game_data)
                print(f"STORE DEBUG: Loaded game for channel {channel_id}")
                print(f"STORE DEBUG: debug_mode = {getattr(game, 'debug_mode', 'NOT SET')}")
                return game
        print(f"STORE DEBUG: No game found for channel {channel_id}")
        return None
        
    async def save_game(self, game):
        """Save game with debug output"""
        print(f"STORE DEBUG: Saving game for channel {game.channel_id}")
        print(f"STORE DEBUG: debug_mode = {getattr(game, 'debug_mode', 'NOT SET')}")
        
        # Convert to dict and check what's being serialized
        game_dict = game.to_dict()
        print(f"STORE DEBUG: Serialized debug_mode = {game_dict.get('debug_mode', 'MISSING')}")
        
        game_data = json.dumps(game_dict)
        await self.db.execute(
            'INSERT OR REPLACE INTO games (channel_id, game_data) VALUES (?, ?)',
            (game.channel_id, game_data)
        )
        await self.db.commit()
        print("STORE DEBUG: Game saved successfully")
    
    async def delete_game(self, channel_id: int):
        await self.db.execute('DELETE FROM games WHERE channel_id = ?', (channel_id,))
        await self.db.commit()
    
    async def get_all_games(self) -> List[GameState]:
        async with self.db.execute('SELECT game_data FROM games') as cursor:
            rows = await cursor.fetchall()
            return [GameState.from_dict(json.loads(row[0])) for row in rows]
    
    async def process_phase_transitions(self, bot):
        games = await self.get_all_games()
        current_time = int(time.time())
        
        for game in games:
            if game.phase.ends_at <= current_time:
                if game.phase.name == "SIGNUP":
                    # Process signup ending
                    await self.process_signup_end(bot, game)
                elif game.phase.name == "DAY":
                    # Process day ending
                    await self.process_day_end(bot, game)
                elif game.phase.name == "NIGHT":
                    # Process night ending
                    await self.process_night_end(bot, game)
    
    async def process_signup_end(self, bot, game):
        # Check if we have enough players
        if len(game.players) < game.config.min_players:
            # Auto-extend signup by 10 minutes (once)
            if game.config.signup_ends_at == game.phase.ends_at:
                game.phase.ends_at += 600  # 10 minutes
                await self.save_game(game)
                
                channel = bot.get_channel(game.channel_id)
                if channel:
                    await channel.send(
                        f"Not enough players to start the game. Signup extended by 10 minutes. "
                        f"Current players: {len(game.players)}/{game.config.min_players} required."
                    )
                return
            else:
                # Already extended once, cancel the game
                game.phase.name = "CANCELLED"
                await self.save_game(game)
                
                channel = bot.get_channel(game.channel_id)
                if channel:
                    await channel.send(
                        "Game cancelled due to insufficient players. "
                        f"Required: {game.config.min_players}, got: {len(game.players)}."
                    )
                return
        
        # Proceed with game start
        from views import RoleAssignmentView
        view = RoleAssignmentView(game)
        
        # DM the host for role assignment
        host = await bot.fetch_user(game.host_id)
        if host:
            await host.send(
                "Signup has ended. Please configure the role distribution:",
                view=view
            )
        
        # Update the signup message to remove buttons
        channel = bot.get_channel(game.channel_id)
        if channel and game.messages.get('signup_message_id'):
            try:
                msg = await channel.fetch_message(game.messages['signup_message_id'])
                await msg.edit(view=None)
            except:
                pass
    
    async def process_day_end(self, bot, game):
        # Implement day end logic
        pass
    
    async def process_night_end(self, bot, game):
        # Implement night end logic
        pass