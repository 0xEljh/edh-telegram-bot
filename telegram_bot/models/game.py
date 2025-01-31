from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
import random
from sqlalchemy.orm import Session
from hashids import Hashids
from telegram_bot.utils import format_name
import os
import dotenv
from .database import (
    Game as DBGame,
    GameResult,
    GameDeletionRequest,
    PodPlayer,
    Elimination,
    Pod as DBPod,
    init_db,
)

dotenv.load_dotenv()


class GameOutcome(str, Enum):
    """Enum representing possible game outcomes."""

    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"


# pick a random word for kill
def get_random_kill_word():
    kill_words = [
        "killed",
        "eliminated",
        "unalived",
        "vanquished",
        "stuck down",
        "slayed",
        "obliterated",
        "snuffed out",
    ]
    return random.choice(kill_words)


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

    def to_dict(self, recursive: bool = False) -> dict:
        """Convert PlayerStats to a dictionary for serialization."""
        return {
            "telegram_id": self.telegram_id,
            "name": self.name,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "eliminations": self.eliminations,
            "games_played": self.games_played,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerStats":
        """Create PlayerStats from a dictionary."""
        return cls(
            telegram_id=data["telegram_id"],
            name=data["name"],
            wins=data.get("wins", 0),
            losses=data.get("losses", 0),
            draws=data.get("draws", 0),
            eliminations=data.get("eliminations", 0),
            games_played=data.get("games_played", 0),
        )

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
class Pod:
    id: int
    name: str
    members: Set[int] = field(default_factory=set)

    def add_member(self, user_id: int):
        self.members.add(user_id)

    def remove_member(self, user_id: int):
        self.members.discard(user_id)

    def to_dict(self) -> dict:
        """Convert Pod to a dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "members": list(self.members),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pod":
        """Create Pod from a dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            members=set(data.get("members", [])),
        )

    @classmethod
    def from_db_pod(cls, db_pod: DBPod) -> "Pod":
        """Create Pod from a database Pod model."""
        return cls(
            id=db_pod.pod_id,
            name=db_pod.name,
            members=set(player.telegram_id for player in db_pod.players),
        )

    def __str__(self) -> str:
        return f"Pod(id={self.id}, name={self.name}, members={len(self.members)})"


@dataclass
class Game:
    """Represents a single EDH game."""

    pod_id: int
    created_at: datetime
    players: Dict[int, str] = field(default_factory=dict)  # telegram_id -> name mapping
    outcomes: Dict[int, GameOutcome] = field(default_factory=dict)
    eliminations: Dict[int, int] = field(
        default_factory=dict
    )  # eliminated_id -> eliminator_id
    finalized: bool = False
    game_id: Optional[int] = None  # Default to None for auto-assignment
    deletion_reference: Optional[str] = None  # Reference for game deletion
    _db_game: Optional[DBGame] = None

    def add_player(self, telegram_id: int, name: str):
        """Add a player to the game."""
        self.players[telegram_id] = name

    def record_outcome(
        self, telegram_id: int, outcome: GameOutcome, eliminations: Dict[int, int] = {}
    ):
        """Record a player's outcome and eliminations."""
        if telegram_id not in self.players:
            raise ValueError(f"Player {telegram_id} is not in this game")
        self.outcomes[telegram_id] = outcome
        for eliminated_id, count in eliminations.items():
            if eliminated_id not in self.players:
                raise ValueError(
                    f"Eliminated player {eliminated_id} is not in this game"
                )
            self.eliminations[eliminated_id] = telegram_id

    def finalize(self, session: Session):
        """Save the game to database."""
        if self.finalized:
            return  # Already finalized, no need to do it again

        if not self.outcomes:
            raise ValueError("Cannot finalize game with no outcomes recorded")

        # All database operations should be in the same transaction
        try:
            # Create or get the game record
            if not self._db_game:
                self._db_game = DBGame(pod_id=self.pod_id, created_at=self.created_at)
                session.add(self._db_game)
                session.flush()  # Get the game_id

                if not self._db_game.game_id:
                    raise ValueError("Failed to generate game_id")

                self.game_id = self._db_game.game_id

            # Add all game results at once
            results = []
            for telegram_id, outcome in self.outcomes.items():
                player = (
                    session.query(PodPlayer)
                    .filter_by(pod_id=self.pod_id, telegram_id=telegram_id)
                    .first()
                )
                if not player:
                    raise ValueError(
                        f"Player {telegram_id} not found in pod {self.pod_id}"
                    )

                results.append(
                    GameResult(
                        game_id=self.game_id,
                        player_id=player.pods_player_id,
                        outcome=outcome.value,
                    )
                )

            # Bulk insert results
            if results:
                session.bulk_save_objects(results)

            # Add all eliminations at once
            eliminations = []
            for eliminated_id, eliminator_id in self.eliminations.items():
                eliminated = (
                    session.query(PodPlayer)
                    .filter_by(pod_id=self.pod_id, telegram_id=eliminated_id)
                    .first()
                )
                eliminator = (
                    session.query(PodPlayer)
                    .filter_by(pod_id=self.pod_id, telegram_id=eliminator_id)
                    .first()
                )

                if not eliminated or not eliminator:
                    raise ValueError(
                        f"Players not found - Eliminated: {eliminated_id}, Eliminator: {eliminator_id}"
                    )

                eliminations.append(
                    Elimination(
                        game_id=self.game_id,
                        eliminator_id=eliminator.pods_player_id,
                        eliminated_id=eliminated.pods_player_id,
                    )
                )

            # Bulk insert eliminations
            if eliminations:
                session.bulk_save_objects(eliminations)

            # Generate deletion reference
            hashids = Hashids(salt=os.getenv("DATABASE_SALT"), min_length=6)
            deletion_ref = hashids.encode(self.game_id)
            self.deletion_reference = deletion_ref

            self._db_game.deletion_reference = deletion_ref

            session.flush()  # Ensure all changes are valid
            self.finalized = True

        except Exception as e:
            # session.rollback() # currently redundant (rollback in game manager level)
            raise RuntimeError(f"Failed to finalize game: {str(e)}") from e

    @classmethod
    def from_db_game(cls, db_game: DBGame) -> "Game":
        """Create a Game instance from a database Game model."""
        game = cls(
            pod_id=db_game.pod_id,
            created_at=db_game.created_at,
            game_id=db_game.game_id,
            deletion_reference=db_game.deletion_reference,
            finalized=True,
            _db_game=db_game,
        )

        # Load players and outcomes
        for result in db_game.results:
            telegram_id = result.player.telegram_id
            game.players[telegram_id] = result.player.name
            game.outcomes[telegram_id] = GameOutcome(result.outcome)

        # Load eliminations
        for elimination in db_game.eliminations:
            eliminated_id = elimination.eliminated.telegram_id
            eliminator_id = elimination.eliminator.telegram_id
            game.eliminations[eliminated_id] = eliminator_id

        return game

    def to_dict(self) -> dict:
        """Convert the game to a dictionary for serialization."""
        return {
            "game_id": self.game_id,
            "pod_id": self.pod_id,
            "created_at": self.created_at.isoformat(),
            "players": {str(tid): name for tid, name in self.players.items()},
            "outcomes": {
                str(tid): outcome.value for tid, outcome in self.outcomes.items()
            },
            "eliminations": {
                str(tid): str(eid) for tid, eid in self.eliminations.items()
            },
            "finalized": self.finalized,
            "deletion_reference": self.deletion_reference,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        """Create a Game instance from a dictionary."""
        return cls(
            game_id=int(data["game_id"]),
            pod_id=int(data["pod_id"]),
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
            deletion_reference=data.get("deletion_reference"),
        )

    def _get_outcome_emoji(self, outcome: GameOutcome) -> str:
        return {
            GameOutcome.WIN: "🟢",
            GameOutcome.LOSE: "🔴",
            GameOutcome.DRAW: "🟡",
        }.get(outcome, "⚪")

    def __str__(self) -> str:
        """Return a string representation of the game."""

        winners = [
            self.players[telegram_id]
            for telegram_id, outcome in self.outcomes.items()
            if outcome == GameOutcome.WIN
        ]

        summary = [
            f"<b>{' vs '.join(self.players.values())}</b>:  <b>🏆{', '.join(winners)} </b>"
        ]
        if hasattr(self, "description") and self.description:
            summary.append(f"\n📜 {self.description}")
        summary.append("\n")

        # sort by outcome; show the winner
        outcome_order = {GameOutcome.WIN: 0, GameOutcome.LOSE: 1, GameOutcome.DRAW: 2}
        sorted_players = sorted(
            self.players.items(),
            key=lambda item: outcome_order.get(
                self.outcomes.get(item[0], GameOutcome.DRAW), 3
            ),
        )

        for telegram_id, player_name in sorted_players:
            outcome = self.outcomes.get(telegram_id)
            kills = sum(1 for eid in self.eliminations.values() if eid == telegram_id)
            # Build achievement badges
            badges = []
            if outcome == GameOutcome.WIN:
                badges.append("🏆 Victor")
            if outcome == GameOutcome.LOSE:
                badges.append("💀 Defeat")
            if kills > 0:
                badges.append(f"⚔️x{kills}")

            summary.append(
                f"┃ {self._get_outcome_emoji(outcome)} {format_name(player_name)}"
                + (f" │ {', '.join(badges)}" if badges else "")
            )

        if self.eliminations:
            summary.append("\n\n<b>Takedowns:</b>")
            for eliminated_id, eliminator_id in self.eliminations.items():
                summary.append(
                    f"┃ ☠️ {self.players[eliminated_id]} "
                    + f"was {get_random_kill_word()} by "
                    + f"<i>{self.players[eliminator_id]}</i>"
                )

        summary.append("\n\n" + self.created_at.strftime("%a %b %d, %H:%M"))
        if self.deletion_reference:
            summary.append(f"Ref: <code>{self.deletion_reference}</code>")

        return "\n".join(summary)


class GameManager:
    """Manages games and player statistics."""

    def __init__(
        self, db_url: str = "sqlite:///data/games.db", db_salt: str = "SECRET_SALT"
    ):
        """Initialize the game manager with a database connection."""
        self.Session = init_db(db_url)
        self._session = self.Session()
        self.hashids = Hashids(salt=db_salt, min_length=6)

    def _reset_session(self):
        """Reset the session if it's in an invalid state."""
        if self._session is not None:
            try:
                self._session.close()
            except:
                pass
        self._session = self.Session()

    def _safe_commit(self):
        """Safely commit changes and handle any errors."""
        try:
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            self._reset_session()
            raise e

    def _safe_query(self, query_func):
        """Execute a query function with automatic session recovery."""
        try:
            return query_func(self._session)
        except Exception as e:
            self._session.rollback()
            self._reset_session()
            # Try one more time with fresh session
            try:
                return query_func(self._session)
            except Exception as e2:
                self._session.rollback()
                raise RuntimeError(
                    f"Query failed after session reset: {str(e2)}"
                ) from e2

    @property
    def pods(self) -> Dict[int, Pod]:
        """Get all pods."""

        def query_func(session):
            return {
                pod.pod_id: Pod.from_db_pod(pod) for pod in session.query(DBPod).all()
            }

        return self._safe_query(query_func)

    def add_game(self, game: Game):
        """Add a completed game and update player statistics."""
        try:
            with self._session.begin_nested():  # Create a savepoint
                # First validate that all players exist
                for telegram_id in game.players:
                    player = (
                        self._session.query(PodPlayer)
                        .filter_by(pod_id=game.pod_id, telegram_id=telegram_id)
                        .first()
                    )
                    if not player:
                        raise ValueError(
                            f"Player {telegram_id} not found in pod {game.pod_id}"
                        )

                # Then validate all eliminations reference valid players
                for eliminated_id, eliminator_id in game.eliminations.items():
                    if eliminated_id not in game.players:
                        raise ValueError(
                            f"Eliminated player {eliminated_id} is not in this game"
                        )
                    if eliminator_id not in game.players:
                        raise ValueError(
                            f"Eliminator {eliminator_id} is not in this game"
                        )

                # Now try to finalize the game
                game.finalize(self._session)
                self._session.flush()  # Ensure all changes are valid

            # If we get here, commit the transaction
            self._safe_commit()

        except Exception as e:
            self._session.rollback()
            self._reset_session()
            raise RuntimeError(f"Failed to add game: {str(e)}") from e

    def create_game(self, pod_id: int) -> Game:
        """Create a new game."""
        if not self._session.query(DBPod).filter_by(pod_id=pod_id).first():
            raise ValueError(f"Pod with ID {pod_id} does not exist")

        return Game(pod_id=pod_id, created_at=datetime.now())

    def create_pod(self, pod_id: int, name: str) -> Pod:
        """Create a new pod."""
        if self._session.query(DBPod).filter_by(pod_id=pod_id).first():
            raise ValueError(f"Pod with ID {pod_id} already exists")

        db_pod = DBPod(pod_id=pod_id, name=name)
        self._session.add(db_pod)
        self._safe_commit()

        pod = Pod(id=pod_id, name=name)
        # self.pods[pod_id] = pod
        return pod

    def get_pod_members(self, pod_id: int) -> Set[int]:
        """Get all member IDs in a pod."""
        pod = self._session.query(DBPod).filter_by(pod_id=pod_id).first()
        if pod:
            return set(player.telegram_id for player in pod.players)
        return set()

    def create_player(
        self, telegram_id: int, name: str, pod_id: int, avatar_url: Optional[str] = None
    ) -> PlayerStats:
        """Create a new player and add them to a pod.

        Args:
            telegram_id: The player's Telegram ID
            name: The player's chosen display name
            pod_id: The ID of the pod to add the player to
            avatar_url: Optional URL to the player's avatar image
        """
        if pod_id not in self.pods:
            raise ValueError(f"Pod with ID {pod_id} does not exist")

        # Check if player already exists in this pod
        existing_player = (
            self._session.query(PodPlayer)
            .filter_by(telegram_id=telegram_id, pod_id=pod_id)
            .first()
        )
        if existing_player:
            raise ValueError(f"Player {telegram_id} already exists in pod {pod_id}")

        # Create new PodPlayer in database
        pod_player = PodPlayer(
            telegram_id=telegram_id, name=name, pod_id=pod_id, avatar_url=avatar_url
        )
        self._session.add(pod_player)
        self._safe_commit()

        player_stats = PlayerStats(telegram_id=telegram_id, name=name)

        return player_stats

    def get_player_avatar(self, telegram_id: int, pod_id: int) -> Optional[str]:
        """Get the avatar path for a player in a pod."""
        player = (
            self._session.query(PodPlayer)
            .filter_by(telegram_id=telegram_id, pod_id=pod_id)
            .first()
        )
        return player.avatar_url if player else None

    def get_player_stats(
        self, telegram_id: int, pod_id: int, since_date: Optional[datetime] = None
    ) -> Optional[PlayerStats]:
        """Get a player's statistics by telegram_id and pod_id."""

        def query_func(session):
            player = (
                session.query(PodPlayer)
                .filter_by(telegram_id=telegram_id, pod_id=pod_id)
                .first()
            )
            if not player:
                return None

            stats = PlayerStats(telegram_id=telegram_id, name=player.name)

            query = (
                session.query(GameResult)
                .join(GameResult.player)
                .filter(
                    PodPlayer.pod_id == pod_id,
                    PodPlayer.pods_player_id == GameResult.player_id,
                    PodPlayer.telegram_id == telegram_id,
                )
            )

            if since_date:
                query = query.join(GameResult.game).filter(
                    DBGame.created_at >= since_date
                )

            for result in query.all():
                eliminations = session.query(Elimination).filter(
                    Elimination.game_id == result.game_id,
                    Elimination.eliminator_id == player.pods_player_id,
                )
                if since_date:
                    eliminations = eliminations.join(Elimination.game).filter(
                        DBGame.created_at >= since_date
                    )
                elim_count = eliminations.count()

                stats.update_from_game(
                    GameOutcome(result.outcome), eliminations=elim_count
                )

            return stats

        return self._safe_query(query_func)

    def get_player_games(
        self,
        telegram_id: int,
        pod_id: Optional[int] = None,
        since_date: Optional[datetime] = None,
    ) -> List[Game]:
        """Get all games for a player, optionally filtered by pod and date.

        Args:
            telegram_id: The player's Telegram ID
            pod_id: Optional pod ID to filter games by
            since_date: Optional date to only return games after this date

        Returns:
            List of Game objects, sorted by creation date (newest first)
        """

        def query_func(session: Session) -> List[Game]:
            query = (
                session.query(DBGame)
                .join(GameResult)
                .join(PodPlayer)
                .filter(PodPlayer.telegram_id == telegram_id)
            )

            if pod_id is not None:
                query = query.filter(DBGame.pod_id == pod_id)

            if since_date is not None:
                query = query.filter(DBGame.created_at >= since_date)

            return [Game.from_db_game(g) for g in query.all()]

        return self._safe_query(query_func)

    def get_pod_player(self, telegram_id: int, pod_id: int) -> Optional[PlayerStats]:
        """Get a player by telegram_id and pod_id."""
        return self.get_player_stats(telegram_id, pod_id)

    def get_player(self, telegram_id: int) -> Optional[Dict[int, PlayerStats]]:
        """Get all pod stats for a player by telegram_id."""
        players = (
            self._session.query(PodPlayer).filter_by(telegram_id=telegram_id).all()
        )
        return {
            player.pod_id: self.get_player_stats(telegram_id, player.pod_id)
            for player in players
        }

    def get_aggregated_player_stats(self, telegram_id: int) -> Optional[PlayerStats]:
        """Get aggregated stats for a player across all pods."""
        player_stats = self.get_player(telegram_id)
        if not player_stats:
            return None

        # Take name from any pod (this would be ignored later anyway)
        aggregated = PlayerStats(
            telegram_id=telegram_id, name=next(iter(player_stats.values())).name
        )

        # Aggregate stats across all pods
        for stats in player_stats.values():
            aggregated.wins += stats.wins
            aggregated.losses += stats.losses
            aggregated.draws += stats.draws
            aggregated.eliminations += stats.eliminations
            aggregated.games_played += stats.games_played

        return aggregated

    def get_pod_games(
        self, pod_id: int, since_date: Optional[datetime] = None
    ) -> List[Game]:
        """Get all games from a specific pod, optionally filtered by date.

        Args:
            pod_id: The ID of the pod to get games for
            since_date: Optional date to filter games from

        Returns:
            List of Game objects, sorted by creation date (newest first)
        """
        query = self._session.query(DBGame).filter(DBGame.pod_id == pod_id)

        if since_date:
            query = query.filter(DBGame.created_at >= since_date)

        query = query.order_by(DBGame.created_at.desc())

        return [Game.from_db_game(db_game) for db_game in query.all()]

    def get_game_by_reference(self, deletion_reference: str) -> Optional[Game]:
        """Get game by its deletion reference."""

        def query_func(session):
            db_game = (
                session.query(DBGame)
                .filter_by(deletion_reference=deletion_reference)
                .first()
            )
            return Game.from_db_game(db_game) if db_game else None

        return self._safe_query(query_func)

    def request_game_deletion(self, deletion_ref: str, requester_id: int) -> dict:
        """Process game deletion request. Returns status object with result and details."""
        try:
            game = self.get_game_by_reference(deletion_ref)
            if not game:
                return {"status": "not_found"}

            # Get pod player ID
            pod_player = (
                self._session.query(PodPlayer)
                .filter_by(pod_id=game.pod_id, telegram_id=requester_id)
                .first()
            )
            if not pod_player:
                return {"status": "not_in_game"}

            # Check existing requests
            existing = (
                self._session.query(GameDeletionRequest)
                .filter_by(game_id=game.game_id, requester_id=pod_player.pods_player_id)
                .first()
            )
            if existing:
                return {"status": "already_requested"}

            # Create new request
            self._session.add(
                GameDeletionRequest(
                    game_id=game.game_id, requester_id=pod_player.pods_player_id
                )
            )

            # Check if we have 2 unique requesters
            requesters = (
                self._session.query(GameDeletionRequest.requester_id)
                .filter_by(game_id=game.game_id)
                .distinct()
                .count()
            )

            if requesters >= 2:
                # Delete game and related data
                db_game = game._db_game
                self._session.delete(db_game)
                self._safe_commit()
                return {"status": "deleted"}

            self._safe_commit()
            return {"status": "pending"}

        except Exception as e:
            self._session.rollback()
            return {"status": "error", "error": str(e)}
