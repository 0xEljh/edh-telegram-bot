from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from telegram_bot.models.game import GameManager
from telegram_bot.models import UnitHandler

from telegram_bot.strategies import (
    SimpleReplyStrategy,
    LoggingErrorStrategy,
    GameHistoryReply,
)

NEXT_PAGE = 0


def create_history_conversation(game_manager: GameManager):
    # history conversation needs to support pagination
    # the callback data has the form "page_<page_number>"

    return ConversationHandler(
        entry_points=[
            CommandHandler(
                "history",
                UnitHandler(
                    reply_strategy=GameHistoryReply(game_manager),
                    error_strategy=LoggingErrorStrategy(notify_user=True),
                    return_state=NEXT_PAGE,
                ),
            )
        ],
        states={
            NEXT_PAGE: [
                CallbackQueryHandler(  # callback handler for pagination
                    UnitHandler(
                        reply_strategy=GameHistoryReply(game_manager),
                        error_strategy=LoggingErrorStrategy(notify_user=True),
                        return_state=NEXT_PAGE,
                    )
                )
            ],
        },
        fallbacks=[],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
