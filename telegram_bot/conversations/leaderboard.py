"""Leaderboard conversation handlers."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import BadRequest

from telegram_bot.models.game import GameManager
from telegram_bot.strategies import SimpleReplyStrategy
from telegram_bot.stats.leaderboard import (
    get_player_stats,
    generate_leaderboard_text,
    generate_stat_cards,
    generate_leaderboard_image,
    TIME_FILTERS,
    SORT_TITLES
)

import logging

logger = logging.getLogger(__name__)


def create_leaderboard_conversation(game_manager: GameManager) -> ConversationHandler:
    async def show_leaderboard(
        update: Update, context: ContextTypes.DEFAULT_TYPE, sort_by="winrate", time_filter="week"
    ) -> None:
        """Show the leaderboard for a pod."""
        chat_id = update.effective_chat.id

        # Get the pod
        pod = game_manager.pods.get(chat_id)
        if not pod:
            await update.effective_message.reply_text(
                "This chat is not registered as a pod! Use /newpod to create one."
            )
            return

        # Get player stats
        active_players, inactive_players = get_player_stats(
            game_manager, chat_id, time_filter, sort_by
        )

        # Generate and send text leaderboard
        message = generate_leaderboard_text(
            pod.name, active_players, inactive_players, sort_by, time_filter
        )
        
        # Create buttons for time filter and sorting
        keyboard = []
        # Time filter row
        time_buttons = []
        for tf in TIME_FILTERS:
            text = f"{TIME_FILTERS[tf]}" + (" ✓" if tf == time_filter else "")
            time_buttons.append(
                InlineKeyboardButton(
                    text=text, callback_data=f"leaderboard_time_{tf}_{sort_by}"
                )
            )
        keyboard.append(time_buttons)

        # Sort method row
        sort_buttons = []
        for sm in SORT_TITLES:
            text = f"{SORT_TITLES[sm]}" + (" ✓" if sm == sort_by else "")
            sort_buttons.append(
                InlineKeyboardButton(
                    text=text, callback_data=f"leaderboard_sort_{sm}_{time_filter}"
                )
            )
        keyboard.append(sort_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Generate stat cards and image
            stat_cards = generate_stat_cards(active_players, game_manager, chat_id)
            if stat_cards:
                image_bio = generate_leaderboard_image(stat_cards, pod.name, time_filter)
                if image_bio:
                    await context.bot.send_photo(chat_id=chat_id, photo=image_bio)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )

        except BadRequest as e:
            logger.error(f"Error sending leaderboard: {e}")
            await SimpleReplyStrategy().handle_error(update, context, e)

    async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await show_leaderboard(update, context)

    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button presses."""
        query = update.callback_query
        await query.answer()

        # Parse the callback data
        _, action, value, other = query.data.split("_")
        if action == "time":
            time_filter, sort_by = value, other
        else:  # action == "sort"
            sort_by, time_filter = value, other

        # Show the updated leaderboard
        await show_leaderboard(update, context, sort_by, time_filter)

        # Delete the old message to avoid clutter
        try:
            await query.message.delete()
        except BadRequest:
            pass

    return ConversationHandler(
        entry_points=[CommandHandler("leaderboard", leaderboard_command)],
        states={},
        fallbacks=[],
        per_message=False,
    ), CallbackQueryHandler(button_callback, pattern=r"^leaderboard_")
