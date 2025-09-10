import discord
from discord.ext import commands
import aiosqlite
import asyncio
import json
import os
from store import GameStore

# Load configuration
with open('config.json') as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MafiaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=config.get('prefix', 'm!'),
            intents=intents,
            help_command=None
        )
        self.db = None
        self.store = None
        
    async def setup_hook(self):
        # Initialize database
        self.db = await aiosqlite.connect('mafia.db')
        self.store = GameStore(self.db)
        await self.store.init_db()
        
        # Load cogs
        cogs_to_load = ['cogs.setup', 'cogs.phase', 'cogs.vote', 'cogs.time', 'cogs.endgame', 'cogs.debug', 'cogs.help']
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                print(f"Successfully loaded extension: {cog}")
            except discord.ClientException as e:
                if "already loaded" in str(e):
                    print(f"Extension {cog} is already loaded. Skipping.")
                else:
                    print(f"Failed to load extension {cog}: {e}")
            except Exception as e:
                print(f"Failed to load extension {cog}: {e}")
        
        print("All extensions loaded. If you don't see any error messages above, all cogs should be working.")
        
        # Sync application commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
        
        # Start background task for phase transitions
        self.phase_task = self.loop.create_task(self.check_phase_transitions())
        
    async def check_phase_transitions(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                # Check for phase transitions every 5 seconds
                await asyncio.sleep(5)
                await self.store.process_phase_transitions(self)
            except Exception as e:
                print(f"Error in phase transition task: {e}")
                
    async def close(self):
        if self.db:
            await self.db.close()
        await super().close()

bot = MafiaBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game(name="Mafia | m!help or /help"))

if __name__ == "__main__":
    bot.run(config['token'])