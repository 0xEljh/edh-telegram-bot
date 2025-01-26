from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Pod(Base):
    __tablename__ = "pods"

    pod_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    # Relationships
    players = relationship("PodPlayer", back_populates="pod")
    games = relationship("Game", back_populates="pod")


class PodPlayer(Base):
    # TODO: consider adding more indexes to this
    __tablename__ = "pods_players"

    pods_player_id = Column(Integer, primary_key=True, autoincrement=True)
    pod_id = Column(Integer, ForeignKey("pods.pod_id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False)
    name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint("pod_id", "telegram_id", name="uq_pod_player"),)

    # Relationships
    pod = relationship("Pod", back_populates="players")
    game_results = relationship("GameResult", back_populates="player")


class Game(Base):
    __tablename__ = "games"

    game_id = Column(Integer, primary_key=True, autoincrement=True)
    pod_id = Column(
        Integer, ForeignKey("pods.pod_id"), nullable=False, index=True
    )  # commonly used
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,  # commonly used
    )

    deletion_reference = Column(String, unique=True)
    deletion_requests = relationship("GameDeletionRequest", back_populates="game")

    # Relationships
    pod = relationship("Pod", back_populates="games")
    results = relationship("GameResult", back_populates="game")
    eliminations = relationship("Elimination", back_populates="game")


class GameResult(Base):
    __tablename__ = "game_results"

    game_id = Column(Integer, ForeignKey("games.game_id"), primary_key=True)
    player_id = Column(
        Integer, ForeignKey("pods_players.pods_player_id"), primary_key=True
    )
    outcome = Column(String, nullable=False)  # 'win', 'lose', or 'draw'
    # TODO: consider migrating to this:
    # outcome = Column(Enum('win', 'lose', 'draw', name='outcome_enum'), nullable=False)

    # Relationships
    game = relationship("Game", back_populates="results")
    player = relationship("PodPlayer", back_populates="game_results")


class Elimination(Base):
    __tablename__ = "eliminations"

    elimination_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    eliminator_id = Column(
        Integer, ForeignKey("pods_players.pods_player_id"), nullable=False
    )
    eliminated_id = Column(
        Integer, ForeignKey("pods_players.pods_player_id"), nullable=False
    )

    # Relationships
    game = relationship("Game", back_populates="eliminations")
    eliminator = relationship("PodPlayer", foreign_keys=[eliminator_id])
    eliminated = relationship("PodPlayer", foreign_keys=[eliminated_id])


class GameDeletionRequest(Base):
    __tablename__ = "game_deletion_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(
        Integer,
        ForeignKey("games.game_id", ondelete="CASCADE"),  # Direct column-level FK
        nullable=False,
    )
    requester_id = Column(
        Integer,
        ForeignKey("pods_players.pods_player_id", ondelete="CASCADE"),  # Direct FK
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    game = relationship("Game", back_populates="deletion_requests")
    requester = relationship("PodPlayer", foreign_keys=[requester_id])


# Database connection setup
def init_db(db_url: str = "sqlite:///edh_games.db"):
    """Initialize the database connection and create tables."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
