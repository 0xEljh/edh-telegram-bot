"""Scheduled tasks for the bot."""

from datetime import datetime, timedelta, timezone
import asyncio
import logging
from telegram.ext import ContextTypes
from telegram_bot.models.game import GameManager
from telegram_bot.stats.leaderboard import (
    get_player_stats,
    generate_leaderboard_text,
    generate_stat_cards,
    generate_leaderboard_image,
)

logger = logging.getLogger(__name__)


class WeeklyRoundup:
    """Weekly roundup task that sends stats to all pods."""

    def __init__(self, game_manager: GameManager):
        """Initialize with game manager instance."""
        self.game_manager = game_manager

    async def __call__(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send weekly roundup to all pods."""
        try:
            # For each pod
            for pod_id, pod in self.game_manager.pods.items():
                try:
                    # # Create a fake update object with just the chat_id
                    # class FakeUpdate:
                    #     def __init__(self, chat_id):
                    #         self.effective_chat = type(
                    #             "obj", (object,), {"id": chat_id}
                    #         )
                    #         self.callback_query = None
                    #         self.message = None

                    # update = FakeUpdate(pod_id)

                    # Get player stats for the past week
                    active_players, inactive_players = get_player_stats(
                        self.game_manager, pod_id, time_filter="week", sort_by="winrate"
                    )

                    if not active_players:
                        # Skip pods with no active players
                        continue

                    # Send intro message
                    await context.bot.send_message(
                        chat_id=pod_id,
                        text="📊 *Weekly EDH Stats Roundup*\nHere's how everyone performed this past week!\n",
                        parse_mode="Markdown",
                    )

                    # Generate and send stat cards image
                    stat_cards = generate_stat_cards(
                        active_players, self.game_manager, pod_id
                    )
                    if stat_cards:
                        image_bio = generate_leaderboard_image(
                            stat_cards, pod.name, time_filter="week"
                        )
                        if image_bio:
                            await context.bot.send_photo(
                                chat_id=pod_id, photo=image_bio
                            )

                    # Generate and send detailed text stats
                    message = generate_leaderboard_text(
                        pod.name,
                        active_players,
                        inactive_players,
                        sort_by="winrate",
                        time_filter="week",
                    )
                    await context.bot.send_message(
                        chat_id=pod_id, text=message, parse_mode="HTML"
                    )

                except Exception as e:
                    logger.error(f"Error sending weekly roundup to pod {pod_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in weekly roundup: {e}")


def schedule_weekly_roundup(application, game_manager) -> None:
    """Schedule the weekly roundup job."""
    # Schedule for every Sunday at 23:59 UTC
    job_queue = application.job_queue
    weekly_roundup = WeeklyRoundup(game_manager)

    # Calculate the first run
    now = datetime.now(timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7  # 6 is Sunday

    if days_until_sunday == 0 and now.hour >= 23 and now.minute >= 59:
        # If it's Sunday after 23:59, schedule for next Sunday
        days_until_sunday = 7

    first_run = now.replace(hour=23, minute=59, second=0, microsecond=0) + timedelta(
        days=days_until_sunday
    )

    # thirty_seconds_later = now + timedelta(seconds=30)

    # Schedule the job
    job_queue.run_repeating(
        weekly_roundup,
        interval=timedelta(days=7),
        first=first_run,
        name="weekly_roundup",
    )

    logger.info(f"Scheduled weekly roundup for {first_run} UTC")
