from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Union
import json
from datetime import datetime, timedelta
import time

@dataclass
class GameConfig:
    min_players: int = 5
    max_players: Optional[int] = 13
    signup_ends_at: int = 0
    day_duration_sec: int = 86400
    night_duration_sec: int = 28800
    twilight_enabled: bool = True
    neutrals_teamed: bool = False
    role_density: str = "LIGHT"  # VANILLA, LIGHT, HEAVY
    game_length: str = "LONG"    # QUICK, LONG, EXTENDED
    
    def to_dict(self):
        return {
            "min_players": self.min_players,
            "max_players": self.max_players,
            "signup_ends_at": self.signup_ends_at,
            "day_duration_sec": self.day_duration_sec,
            "night_duration_sec": self.night_duration_sec,
            "twilight_enabled": self.twilight_enabled,
            "neutrals_teamed": self.neutrals_teamed,
            "role_density": self.role_density,
            "game_length": getattr(self, 'game_length', 'LONG')
        }

@dataclass
class Player:
    id: int
    status: str = "alive"  # alive, dead
    tentative: bool = False
    role: Optional[str] = None
    name: Optional[str] = None  # Add this missing attribute
    
    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "tentative": self.tentative,
            "role": self.role,
            "name": getattr(self, 'name', None)  # Handle the name attribute if it exists
        }
    
    def get_display_name(self):
        if self.name:
            return self.name
        return f"<@{self.id}>"

@dataclass
class Phase:
    name: str = "SIGNUP"  # SIGNUP, DAY, NIGHT, ENDED, CANCELLED
    number: int = 0
    ends_at: int = 0
    
    def to_dict(self):
        return {
            "name": self.name,
            "number": self.number,
            "ends_at": self.ends_at
        }

@dataclass
class GameState:
    channel_id: int
    guild_id: int
    host_id: int
    config: GameConfig
    players: List[Player]
    mafia_ids: List[int] = None
    neutral_ids: List[int] = None
    town_ids: List[int] = None
    phase: Phase = None
    votes: Dict[int, int] = None
    messages: Dict[str, int] = None
    debug_mode: bool = False
    dummy_players: List[Player] = None
    
    def __post_init__(self):
        if self.mafia_ids is None:
            self.mafia_ids = []
        if self.neutral_ids is None:
            self.neutral_ids = []
        if self.town_ids is None:
            self.town_ids = []
        if self.phase is None:
            self.phase = Phase()
        if self.votes is None:
            self.votes = {}
        if self.messages is None:
            self.messages = {}
        if self.dummy_players is None:
            self.dummy_players = []
        self.debug_mode = bool(self.debug_mode)
            
    def to_dict(self):
        """Convert GameState object to dictionary for serialization"""
        return {
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "host_id": self.host_id,
            "config": self.config.to_dict() if hasattr(self.config, 'to_dict') else vars(self.config),
            "players": [player.to_dict() if hasattr(player, 'to_dict') else vars(player) for player in self.players],
            "mafia_ids": self.mafia_ids,
            "neutral_ids": self.neutral_ids,
            "town_ids": self.town_ids,
            "phase": self.phase.to_dict() if hasattr(self.phase, 'to_dict') else vars(self.phase),
            "votes": self.votes,
            "messages": self.messages,
            "debug_mode": getattr(self, 'debug_mode', False),
            "dummy_players": [player.to_dict() if hasattr(player, 'to_dict') else vars(player) 
                            for player in getattr(self, 'dummy_players', [])]
        }
    
    def get_all_players(self):
        """Get both real and dummy players"""
        return self.players + self.dummy_players
    
    def get_player(self, player_id: int) -> Optional[Player]:
        """Get a player by ID (checks both real and dummy players)"""
        for player in self.get_all_players():
            if player.id == player_id:
                return player
        return None
    
    @classmethod
    def from_dict(cls, data):
        # Only print debug info when debug_mode is changing or there's an issue
        debug_mode_value = data.get('debug_mode', False)
        
        # Optional: only print when debug_mode is True or when it's missing but should be True
        if debug_mode_value == True or ('debug_mode' not in data and debug_mode_value == True):
            print(f"FROM_DICT: Raw data debug_mode = {data.get('debug_mode', 'MISSING')}")
            print(f"FROM_DICT: Extracted debug_mode = {debug_mode_value}")
        
        config = GameConfig(**data['config'])
        players = [Player(**p) for p in data['players']]
        phase = Phase(**data['phase'])
        
        # Extract dummy_players with proper default handling
        dummy_players_data = data.get('dummy_players', [])
        dummy_players = [Player(**p) for p in dummy_players_data]
        
        # Create the GameState instance with ALL parameters
        game = cls(
            channel_id=data['channel_id'],
            guild_id=data['guild_id'],
            host_id=data['host_id'],
            config=config,
            players=players,
            mafia_ids=data.get('mafia_ids', []),
            neutral_ids=data.get('neutral_ids', []),
            town_ids=data.get('town_ids', []),
            phase=phase,
            votes=data.get('votes', {}),
            messages=data.get('messages', {}),
            debug_mode=debug_mode_value,  # Use the extracted value
            dummy_players=dummy_players
        )
        
        # Only print final debug mode when it's True
        if game.debug_mode == True:
            print(f"FROM_DICT: Final game.debug_mode = {game.debug_mode}")
        
        return game

    def get_alive_players(self):
        return [p for p in self.get_all_players() if p.status == "alive"]
    
    def add_player(self, player_id: int, tentative: bool = False):
        if not any(p.id == player_id for p in self.get_all_players()):
            self.players.append(Player(id=player_id, tentative=tentative))
    
    def remove_player(self, player_id: int):
        self.players = [p for p in self.players if p.id != player_id]
        self.dummy_players = [p for p in self.dummy_players if p.id != player_id]
    
    def get_vote_count(self, target_id: int) -> int:
        return sum(1 for voter_id, voted_id in self.votes.items() if voted_id == target_id)
    
    def get_majority_threshold(self) -> int:
        alive_count = len(self.get_alive_players())
        return (alive_count // 2) + 1