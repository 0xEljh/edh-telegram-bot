"""Pod history conversation handler."""

from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from telegram_bot.models.game import GameManager
from telegram_bot.models import UnitHandler
from telegram_bot.strategies import LoggingErrorStrategy
from telegram_bot.strategies.reply import PodHistoryReply

NEXT_PAGE = 0


def create_pod_history_conversation(game_manager: GameManager) -> ConversationHandler:
    """Create the pod history conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler(
                "podhistory",
                UnitHandler(
                    reply_strategy=PodHistoryReply(game_manager),
                    error_strategy=LoggingErrorStrategy(notify_user=True),
                    return_state=NEXT_PAGE,
                ),
            )
        ],
        states={
            NEXT_PAGE: [
                CallbackQueryHandler(  # callback handler for pagination
                    UnitHandler(
                        reply_strategy=PodHistoryReply(game_manager),
                        error_strategy=LoggingErrorStrategy(notify_user=True),
                        return_state=NEXT_PAGE,
                    )
                )
            ],
        },
        fallbacks=[],
        per_message=False,
    )
