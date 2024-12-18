from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
import json
import os
from pathlib import Path


class GameOutcome(str, Enum):
    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"


@dataclass
class PlayerStats:
    """Statistics for a player across all games."""

    telegram_id: int
    name: str
    wins: int = 0
    losses: int = 0
    draws: int = 0
    eliminations: int = 0
    games_played: int = 0

    def update_from_game(self, outcome: GameOutcome, eliminations: int = 0):
        """Update stats based on a game outcome."""
        self.games_played += 1
        self.eliminations += eliminations
        if outcome == GameOutcome.WIN:
            self.wins += 1
        elif outcome == GameOutcome.LOSE:
            self.losses += 1
        else:  # DRAW
            self.draws += 1

    def __str__(self) -> str:
        """Return a string representation of player stats."""
        return (
            f"📊 Stats for {self.name}:\n"
            f"🎮 Games Played: {self.games_played}\n"
            f"🏆 Wins: {self.wins}\n"
            f"💀 Losses: {self.losses}\n"
            f"🤝 Draws: {self.draws}\n"
            f"⚔️ Eliminations: {self.eliminations}"
        )


@dataclass
class Game:
    """Represents a single EDH game.

    dev note: may want to represent telegram_id as a string instead of an int
    """

    game_id: int
    created_at: datetime
    players: Dict[int, str] = field(default_factory=dict)  # telegram_id -> name mapping
    outcomes: Dict[int, GameOutcome] = field(default_factory=dict)
    eliminations: Dict[int, int] = field(
        default_factory=dict
    )  # eliminated_id -> eliminator_id
    finalized: bool = False

    def add_player(self, telegram_id: int, name: str) -> None:
        """Add a player to the game."""
        if self.finalized:
            raise ValueError("Cannot add players to a finalized game")
        self.players[telegram_id] = name

    def record_outcome(
        self, telegram_id: int, outcome: GameOutcome, eliminations: Dict[int, int] = {}
    ) -> None:
        """Record a player's outcome and eliminations."""
        if telegram_id not in self.players:
            raise ValueError(f"Player {telegram_id} is not in this game")
        if self.finalized:
            raise ValueError("Cannot modify a finalized game")
        self.outcomes[telegram_id] = outcome
        for eliminated_id, eliminator_id in eliminations.items():
            if eliminator_id == telegram_id:
                self.eliminations[eliminated_id] = eliminator_id

    def finalize(self) -> None:
        """Mark the game as finalized."""
        missing_players = set(self.players.keys()) - set(self.outcomes.keys())
        if missing_players:
            raise ValueError(f"Missing outcomes for players: {missing_players}")
        self.finalized = True

    def to_dict(self) -> dict:
        """Convert the game to a dictionary for serialization."""
        return {
            "game_id": self.game_id,
            "created_at": self.created_at.isoformat(),
            "players": {str(tid): name for tid, name in self.players.items()},
            "outcomes": {
                str(tid): outcome.value for tid, outcome in self.outcomes.items()
            },
            "eliminations": {
                str(tid): str(eid) for tid, eid in self.eliminations.items()
            },
            "finalized": self.finalized,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        """Create a Game instance from a dictionary."""
        return cls(
            game_id=int(data["game_id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            players={int(tid): name for tid, name in data["players"].items()},
            outcomes={
                int(tid): GameOutcome(outcome)
                for tid, outcome in data["outcomes"].items()
            },
            eliminations={
                int(tid): int(eid) for tid, eid in data["eliminations"].items()
            },
            finalized=data["finalized"],
        )

    def __str__(self) -> str:
        """Return a string representation of the game."""
        summary = []

        summary.append(f"💥 {' vs '.join(self.players.values())}")
        summary.append("\n")
        for player_id, player_name in self.players.items():
            outcome = self.outcomes.get(player_id, "Unknown")
            eliminations = sum(
                1 for eid in self.eliminations.values() if eid == player_id
            )
            outcome_emoji = (
                "🏆"
                if outcome.value == "win"
                else "💀" if outcome.value == "lose" else "🤝"
            )
            summary.append(
                f"  {outcome_emoji} {player_name} — {outcome.value.capitalize()} | ⚔️ Eliminations: {eliminations}"
            )

        summary.append("\n")
        summary.append("Eliminations:")
        summary.append("\n")
        for eliminated_id, eliminator_id in self.eliminations.items():
            eliminated_name = self.players[eliminated_id]
            eliminator_name = self.players[eliminator_id]
            summary.append(f"  ☠️ {eliminated_name} was eliminated by {eliminator_name}")

        summary.append("\n")
        summary.append(f"Created at: {self.created_at.strftime('%Y-%m-%d %H:%M')}")
        # summary.append(f"Finalized: {'Yes' if self.finalized else 'No'}")
        return "\n".join(summary)


class GameManager:
    """Manages games and player statistics."""

    def __init__(self, data_file: str = "edh_games.json"):
        self.data_file = data_file
        self.games: Dict[int, Game] = {}
        self.players: Dict[int, PlayerStats] = {}
        self.load_from_file()

    def create_game(self, game_id: Optional[int] = None) -> Game:
        """Create a new game with an optional ID."""
        if game_id is None:
            # Find the next available game ID
            game_id = 0
            while game_id in self.games:
                game_id += 1
                
        if game_id in self.games:
            raise ValueError(f"Game with ID {game_id} already exists")

        game = Game(game_id=game_id, created_at=datetime.now())
        self.games[game_id] = game
        return game

    def add_game(self, game: Game) -> None:
        """Add a completed game and update player statistics."""
        if not game.finalized:
            raise ValueError("Cannot add an unfinalized game")

        # Update player statistics
        for telegram_id in game.players:
            if telegram_id not in self.players:
                self.players[telegram_id] = PlayerStats(
                    telegram_id=telegram_id, name=game.players[telegram_id]
                )

            eliminations = sum(
                1 for eid in game.eliminations.values() if eid == telegram_id
            )
            self.players[telegram_id].update_from_game(
                game.outcomes[telegram_id], eliminations
            )

        self.games[game.game_id] = game
        self.save_to_file()

    def get_player(self, telegram_id: int) -> Optional[PlayerStats]:
        """Get a player's statistics by telegram_id."""
        return self.players.get(telegram_id)

    def create_player(self, telegram_id: int, name: str) -> PlayerStats:
        """Create a new player."""
        if telegram_id in self.players:
            raise ValueError(f"Player {telegram_id} already exists")
        player = PlayerStats(telegram_id=telegram_id, name=name)
        self.players[telegram_id] = player
        self.save_to_file()
        return player

    def save_to_file(self) -> None:
        """Save all games and player statistics to file."""
        data = {
            "games": {gid: game.to_dict() for gid, game in self.games.items()},
            "players": {
                tid: {
                    "telegram_id": p.telegram_id,
                    "name": p.name,
                    "wins": p.wins,
                    "losses": p.losses,
                    "draws": p.draws,
                    "eliminations": p.eliminations,
                    "games_played": p.games_played,
                }
                for tid, p in self.players.items()
            },
        }

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.data_file)), exist_ok=True)

        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self) -> None:
        """Load games and player statistics from file."""
        if not os.path.exists(self.data_file):
            return

        with open(self.data_file, "r") as f:
            data = json.load(f)

        # TODO may want to drop all unfinalized games here

        self.games = {
            int(gid): Game.from_dict(game_data)
            for gid, game_data in data.get("games", {}).items()
        }

        self.players = {
            int(tid): PlayerStats(**player_data)
            for tid, player_data in data.get("players", {}).items()
        }
