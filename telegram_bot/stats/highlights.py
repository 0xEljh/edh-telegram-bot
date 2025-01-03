"""Stat highlighting and calculation module."""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import random
from telegram_bot.models.game import PlayerStats, GameManager


@dataclass
class StatHighlight:
    """A highlighted stat for display."""
    id: str
    title: str
    player: PlayerStats
    stat_value: int
    stat_name: str
    subtitle: str


def safe_division(a: int, b: int, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is 0."""
    try:
        return a / b if b != 0 else default
    except (TypeError, ZeroDivisionError):
        return default


# Pool of available stats to highlight
STAT_POOL = [
    {
        "id": "wins_leader",
        "title": "Wins Leader",
        "stat_name": "Wins",
        "value_func": lambda stats: stats.wins,
        "subtitle_func": lambda stats: f"{safe_division(stats.wins, stats.games_played, 0.0) * 100:.1f}% Win Rate"
    },
    {
        "id": "kills_leader",
        "title": "Most Kills",
        "stat_name": "Kills",
        "value_func": lambda stats: stats.eliminations,
        "subtitle_func": lambda stats: f"{safe_division(stats.eliminations, stats.games_played, 0.0):.1f} per game"
    },
    {
        "id": "games_leader",
        "title": "Most Games",
        "stat_name": "Games",
        "value_func": lambda stats: stats.games_played,
        "subtitle_func": lambda stats: "Most Active Player"
    },
    {
        "id": "winrate_leader",
        "title": "Best Win Rate",
        "stat_name": "Win Rate",
        "value_func": lambda stats: safe_division(stats.wins, stats.games_played, 0.0) * 100,
        "subtitle_func": lambda stats: f"{stats.wins}W-{stats.losses}L"
    },
    {
        "id": "kills_per_game",
        "title": "Most Kills Per Game",
        "stat_name": "K/G",
        "value_func": lambda stats: safe_division(stats.eliminations, stats.games_played, 0.0),
        "subtitle_func": lambda stats: f"{stats.eliminations} Total Kills"
    }
]


def pick_highlight_stats(
    active_players: List[PlayerStats],
    stat_pool: List[Dict[str, Any]] = STAT_POOL,
    num_highlights: int = 3,
    required_stats: Optional[List[str]] = None
) -> List[StatHighlight]:
    """
    Pick interesting stats from the pool to highlight.
    
    Args:
        active_players: List of PlayerStats objects with at least 1 game
        stat_pool: Pool of available stats to choose from
        num_highlights: Number of stats to highlight
        required_stats: List of stat IDs that must be included
        
    Returns:
        List of StatHighlight objects
    """
    if not active_players:
        return []
        
    # Start with required stats if any
    highlights = []
    remaining_pool = list(stat_pool)
    
    if required_stats:
        # Pull out required stats first
        for stat_id in required_stats:
            stat_meta = next((s for s in remaining_pool if s["id"] == stat_id), None)
            if stat_meta:
                remaining_pool.remove(stat_meta)
                value_func = stat_meta["value_func"]
                
                # Find the top player for this stat
                best_player = max(active_players, key=value_func)
                best_value = value_func(best_player)
                
                highlights.append(StatHighlight(
                    id=stat_meta["id"],
                    title=stat_meta["title"],
                    player=best_player,
                    stat_value=best_value,
                    stat_name=stat_meta["stat_name"],
                    subtitle=stat_meta["subtitle_func"](best_player)
                ))
    
    # Randomly pick remaining stats
    random.shuffle(remaining_pool)
    
    # Add random stats until we have enough
    for stat_meta in remaining_pool:
        if len(highlights) >= num_highlights:
            break
            
        value_func = stat_meta["value_func"]
        
        # Find the top player for this stat
        best_player = max(active_players, key=value_func)
        best_value = value_func(best_player)
        
        highlights.append(StatHighlight(
            id=stat_meta["id"],
            title=stat_meta["title"],
            player=best_player,
            stat_value=best_value,
            stat_name=stat_meta["stat_name"],
            subtitle=stat_meta["subtitle_func"](best_player)
        ))
    
    return highlights
