"""Profile stat calculation utilities."""
from typing import Optional, Tuple
from datetime import datetime, timedelta
from telegram_bot.models.game import GameManager, Game, PlayerStats, GameOutcome


def calculate_decorative_stat(
    player_stats: PlayerStats,
    game_manager: GameManager,
    pod_id: Optional[int] = None,
) -> Tuple[int | float, str]:
    """Calculate the most impressive stat to show on the profile card.
    
    Args:
        player_stats: Player's stats
        game_manager: Game manager instance
        pod_id: Optional pod ID if showing pod-specific stats
        
    Returns:
        Tuple of (stat_value, stat_name). stat_value can be an int (for streaks) 
        or float (for win rates)
    """
    # Get current time for weekly stats
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    # Get player's games from the past week
    weekly_games = game_manager.get_player_games(
        player_stats.telegram_id,
        pod_id=pod_id,
        since_date=week_ago
    )
    weekly_games.sort(key=lambda g: g.created_at)
    
    if not weekly_games:
        return "--%", "W/R (week)"
    
    # Calculate current streak
    current_streak = 0
    streak_type = None  # True for win streak, False for lose streak
    
    for game in reversed(weekly_games):  # Start from most recent
        if player_stats.telegram_id not in game.outcomes:
            continue
            
        won = game.outcomes[player_stats.telegram_id] == GameOutcome.WIN
        
        if streak_type is None:
            streak_type = won
            current_streak = 1
        elif won == streak_type:
            current_streak += 1
        else:
            break
    
    # Calculate weekly win rate
    weekly_wins = sum(
        1 for g in weekly_games 
        if player_stats.telegram_id in g.outcomes 
        and g.outcomes[player_stats.telegram_id] == GameOutcome.WIN
    )
    weekly_winrate = (weekly_wins / len(weekly_games) * 100)
    
    # Check if player has highest win rate in pod
    weekly_top = False
    if pod_id:
        active_players = game_manager.get_pod_members(pod_id)
        weekly_top = True
        for other_id in active_players:
            if other_id == player_stats.telegram_id:
                continue
            other_games = game_manager.get_player_games(
                other_id,
                pod_id=pod_id,
                since_date=week_ago
            )
            if not other_games:
                continue
            other_wins = sum(
                1 for g in other_games 
                if other_id in g.outcomes 
                and g.outcomes[other_id] == GameOutcome.WIN
            )
            other_winrate = (other_wins / len(other_games) * 100)
            if other_winrate > weekly_winrate:
                weekly_top = False
                break
    
    # Determine which stat to show
    if weekly_top:
        return f"{weekly_winrate:.1f}%", "W/R (week)"
    elif current_streak >= 2:
        if streak_type:  # Win streak
            return current_streak, "Win Streak"
        else:  # Lose streak
            return current_streak, "Lose Streak"
    else:
        return f"{weekly_winrate:.1f}%", "W/R (week)"
