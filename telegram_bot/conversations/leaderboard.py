from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from telegram_bot.models.game import GameManager
from telegram_bot.strategies import SimpleReplyStrategy

SORT_METHODS = {
    "winrate": lambda stats: (
        stats.wins / stats.games_played if stats.games_played > 0 else 0
    ),
    "wins": lambda stats: stats.wins,
    "eliminations": lambda stats: stats.eliminations,
}

SORT_TITLES = {
    "winrate": "🎯 Win Rate",
    "wins": "🏆 Total Wins",
    "eliminations": "⚔️ Total Eliminations",
}


def create_leaderboard_conversation(game_manager: GameManager) -> ConversationHandler:
    async def show_leaderboard(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        chat_id = update.effective_chat.id
        if update.effective_chat.type not in ["group", "supergroup"]:
            await update.message.reply_text(
                "This command can only be used in group chats."
            )
            return ConversationHandler.END

        if chat_id not in game_manager.pods:
            await update.message.reply_text(
                "No pod exists for this group chat. Create one using /pod first!"
            )
            return ConversationHandler.END

        # Default sort by winrate
        await display_leaderboard(update, context, "winrate")
        return ConversationHandler.END

    async def display_leaderboard(
        update: Update, context: ContextTypes.DEFAULT_TYPE, sort_by: str
    ):
        chat_id = (
            update.effective_chat.id
            if update.effective_chat
            else update.callback_query.message.chat_id
        )
        pod = game_manager.pods[chat_id]

        # Get all players in the pod
        players_stats = []
        for user_id in pod.members:
            if stats := game_manager.get_player_stats(user_id, chat_id):
                players_stats.append(stats)

        # Sort players based on selected criteria
        sort_func = SORT_METHODS[sort_by]
        players_stats.sort(key=sort_func, reverse=True)

        # Create leaderboard message with HTML formatting
        message = (
            f"<b>🏆 {pod.name} Leaderboard</b>\n"
            f"<i>Sorted by {SORT_TITLES[sort_by]}</i>\n\n"
        )

        for i, stats in enumerate(players_stats, 1):
            winrate = (
                stats.wins / stats.games_played * 100 if stats.games_played > 0 else 0
            )
            medals = ["🥇", "🥈", "🥉"]
            rank = medals[i - 1] if i <= 3 else f"{i}."

            message += (
                f"{rank} <b>{stats.name}</b>\n"
                f"   • Win Rate: <code>{winrate:.1f}%</code>\n"
                f"   • Record: <code>{stats.wins}W-{stats.losses}L</code>\n"
                f"   • Eliminations: <code>{stats.eliminations}</code>\n"
                f"   • Games: <code>{stats.games_played}</code>\n\n"
            )

        # Create inline keyboard with one button per row and emojis
        keyboard = [
            [InlineKeyboardButton("🎯 Sort by Win Rate", callback_data="sort_winrate")],
            [InlineKeyboardButton("🏆 Sort by Wins", callback_data="sort_wins")],
            [
                InlineKeyboardButton(
                    "⚔️ Sort by Eliminations", callback_data="sort_eliminations"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.message.edit_text(
                message, reply_markup=reply_markup, parse_mode="HTML"
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                message, reply_markup=reply_markup, parse_mode="HTML"
            )

    async def button_callback(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        sort_by = query.data.replace("sort_", "")
        await display_leaderboard(update, context, sort_by)
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[CommandHandler("leaderboard", show_leaderboard)],
        states={},
        fallbacks=[],
        name="leaderboard_conversation",
        persistent=False,
        allow_reentry=True,
        per_chat=True,
        per_user=False,
    ), CallbackQueryHandler(button_callback, pattern=r"^sort_")
