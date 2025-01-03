"""Leaderboard generation and display utilities."""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from io import BytesIO

from telegram_bot.models.game import PlayerStats, GameManager
from telegram_bot.image_gen.stat_cards import StatCardData, create_leaderboard_image
from telegram_bot.stats.highlights import pick_highlight_stats

# Sorting methods for leaderboard
SORT_METHODS = {
    "winrate": lambda stats: (
        stats.wins / stats.games_played if stats.games_played > 0 else 0
    ),
    "wins": lambda stats: stats.wins,
    "eliminations": lambda stats: stats.eliminations,
    "games": lambda stats: stats.games_played,
}

SORT_TITLES = {
    "winrate": " Win Rate",
    "wins": " Total Wins",
    "eliminations": " Total Kills",
    "games": " Games Played",
}

TIME_FILTERS = {
    "all": "All Time",
    "week": "Past Week",
}

# Stats that should always be included in highlights
REQUIRED_STATS = ["winrate_leader"]


def get_player_stats(
    game_manager: GameManager,
    pod_id: int,
    time_filter: str = "week",
    sort_by: str = "winrate"
) -> Tuple[List[PlayerStats], List[PlayerStats]]:
    """Get sorted lists of active and inactive players for a pod.
    
    Args:
        game_manager: The game manager instance
        pod_id: ID of the pod to get stats for
        time_filter: 'all' or 'week'
        sort_by: Sorting method from SORT_METHODS
        
    Returns:
        Tuple of (active_players, inactive_players)
    """
    players_stats = []
    cutoff_date = None
    
    if time_filter == "week":
        cutoff_date = datetime.now() - timedelta(days=7)

    # Get stats for all players
    for user_id in game_manager.pods[pod_id].members:
        if stats := game_manager.get_player_stats(user_id, pod_id, since_date=cutoff_date):
            players_stats.append(stats)

    # Split into active and inactive
    active_players = [p for p in players_stats if p.games_played > 0]
    inactive_players = [p for p in players_stats if p.games_played == 0]
    
    # Sort active players
    sort_func = SORT_METHODS[sort_by]
    active_players.sort(key=sort_func, reverse=True)
    
    return active_players, inactive_players


def generate_leaderboard_text(
    pod_name: str,
    active_players: List[PlayerStats],
    inactive_players: Optional[List[PlayerStats]] = None,
    sort_by: str = "winrate",
    time_filter: str = "week"
) -> str:
    """Generate formatted leaderboard text.
    
    Args:
        pod_name: Name of the pod
        active_players: List of players with games played
        inactive_players: Optional list of players with no games
        sort_by: Sorting method used
        time_filter: Time period filter used
        
    Returns:
        Formatted leaderboard text
    """
    message = (
        f"<b>{pod_name} Leaderboard</b>\n"
        f"<i>Sorted by {SORT_TITLES[sort_by]} ({TIME_FILTERS[time_filter]})</i>\n\n"
    )

    if not active_players and not inactive_players:
        message += "No players in this pod yet!"
    elif not active_players:
        message += "No games have been played in this pod yet!"
    else:
        for i, stats in enumerate(active_players, 1):
            winrate = stats.wins / stats.games_played * 100
            medals = ["", "", ""]
            rank = medals[i - 1] if i <= 3 else f"{i}."

            message += (
                f"{rank} <b>{stats.name}</b>\n"
                f"   • Win Rate: <code>{winrate:.1f}%</code>\n"
                f"   • Record: <code>{stats.wins}W-{stats.losses}L</code>\n"
                f"   • Eliminations: <code>{stats.eliminations}</code>\n"
                f"   • Games: <code>{stats.games_played}</code>\n\n"
            )

        if inactive_players:
            message += "\n<i>Inactive Players:</i>\n"
            for player in inactive_players:
                message += f"• {player.name}\n"
                
    return message


def generate_stat_cards(
    active_players: List[PlayerStats],
    game_manager: GameManager,
    pod_id: int,
    num_highlights: int = 3
) -> List[StatCardData]:
    """Generate stat cards for the leaderboard.
    
    Args:
        active_players: List of players with games played
        game_manager: GameManager instance for getting avatars
        pod_id: ID of the pod
        num_highlights: Number of stat cards to generate
        
    Returns:
        List of StatCardData objects
    """
    if not active_players:
        return []
        
    # Get highlighted stats
    highlights = pick_highlight_stats(
        active_players,
        num_highlights=num_highlights,
        required_stats=REQUIRED_STATS
    )
    
    # Create stat cards from highlights
    stat_cards = []
    for highlight in highlights:
        stat_cards.append(
            StatCardData(
                name=highlight.player.name,
                avatar_path=game_manager.get_player_avatar(
                    highlight.player.telegram_id, pod_id
                ),
                stat_value=highlight.stat_value,
                stat_name=highlight.stat_name,
                subtitle=highlight.subtitle,
            )
        )
        
    return stat_cards


def generate_leaderboard_image(
    stat_cards: List[StatCardData],
    pod_name: str,
    time_filter: str = "week"
) -> BytesIO:
    """Generate a leaderboard image with stat cards.
    
    Args:
        stat_cards: List of stat cards to include
        pod_name: Name of the pod
        time_filter: Time period filter used
        
    Returns:
        BytesIO object containing the PNG image
    """
    if not stat_cards:
        return None
        
    image = create_leaderboard_image(
        stat_cards,
        f"{pod_name} Top Players ({TIME_FILTERS[time_filter]})"
    )
    
    # Convert to bytes for sending
    bio = BytesIO()
    image.save(bio, "PNG")
    bio.seek(0)
    
    return bio
