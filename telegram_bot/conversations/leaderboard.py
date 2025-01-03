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
from telegram_bot.image_gen.stat_cards import StatCardData, create_leaderboard_image

from datetime import datetime, timedelta
from io import BytesIO

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

        # Default to showing past week's stats
        await display_leaderboard(update, context, "winrate", "week")
        return ConversationHandler.END

    async def display_leaderboard(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        sort_by: str,
        time_filter: str = "all",
    ):
        chat_id = (
            update.effective_chat.id
            if update.effective_chat
            else update.callback_query.message.chat_id
        )
        pod = game_manager.pods[chat_id]

        # Get all players in the pod
        players_stats = []
        cutoff_date = None
        if time_filter == "week":
            cutoff_date = datetime.now() - timedelta(days=7)

        for user_id in pod.members:
            if stats := game_manager.get_player_stats(
                user_id, chat_id, since_date=cutoff_date
            ):
                players_stats.append(stats)

        # Create stat cards for top players
        stat_cards = []
        if players_stats:
            # Filter out players with no games
            active_players = [p for p in players_stats if p.games_played > 0]

            if active_players:
                # Most wins
                wins_leader = max(active_players, key=lambda s: s.wins)
                stat_cards.append(
                    StatCardData(
                        name=wins_leader.name,
                        avatar_path=game_manager.get_player_avatar(
                            wins_leader.telegram_id, chat_id
                        ),
                        stat_value=wins_leader.wins,
                        stat_name="Wins",
                        subtitle=f"{(wins_leader.wins/wins_leader.games_played*100):.1f}% Win Rate",
                    )
                )

                # Most eliminations
                elim_leader = max(active_players, key=lambda s: s.eliminations)
                stat_cards.append(
                    StatCardData(
                        name=elim_leader.name,
                        avatar_path=game_manager.get_player_avatar(
                            elim_leader.telegram_id, chat_id
                        ),
                        stat_value=elim_leader.eliminations,
                        stat_name="Eliminations",
                        subtitle=f"{(elim_leader.eliminations/elim_leader.games_played):.1f} per game",
                    )
                )

                # Most games
                games_leader = max(active_players, key=lambda s: s.games_played)
                stat_cards.append(
                    StatCardData(
                        name=games_leader.name,
                        avatar_path=game_manager.get_player_avatar(
                            games_leader.telegram_id, chat_id
                        ),
                        stat_value=games_leader.games_played,
                        stat_name="Games",
                        subtitle=f"Most Active Player",
                    )
                )

                # Generate and send the image
                leaderboard_image = create_leaderboard_image(
                    stat_cards, f"{pod.name} Top Players ({TIME_FILTERS[time_filter]})"
                )
                # Convert to bytes for sending
                bio = BytesIO()
                leaderboard_image.save(bio, "PNG")
                bio.seek(0)
                await context.bot.send_photo(chat_id=chat_id, photo=bio)
            else:
                await context.bot.send_message(
                    chat_id=chat_id, text="No games have been played in this pod yet!"
                )
                return

        # Create leaderboard message with HTML formatting
        message = (
            f"<b>{pod.name} Leaderboard</b>\n"
            f"<i>Sorted by {SORT_TITLES[sort_by]} ({TIME_FILTERS[time_filter]})</i>\n\n"
        )

        if not players_stats:
            message += "No players in this pod yet!"
        else:
            active_players = [p for p in players_stats if p.games_played > 0]
            if not active_players:
                message += "No games have been played in this pod yet!"
            else:
                # Sort players based on selected criteria
                sort_func = SORT_METHODS[sort_by]
                active_players.sort(key=sort_func, reverse=True)

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

                # Add inactive players at the bottom if any
                inactive_players = [p for p in players_stats if p.games_played == 0]
                if inactive_players:
                    message += "\n<i>Inactive Players:</i>\n"
                    for player in inactive_players:
                        message += f"• {player.name}\n"

        # Create inline keyboard with sorting and time filter options
        keyboard = [
            # Sorting options
            [
                InlineKeyboardButton(
                    " Sort by Win Rate", callback_data=f"sort_winrate_{time_filter}"
                )
            ],
            [
                InlineKeyboardButton(
                    " Sort by Wins", callback_data=f"sort_wins_{time_filter}"
                )
            ],
            [
                InlineKeyboardButton(
                    " Sort by Eliminations",
                    callback_data=f"sort_eliminations_{time_filter}",
                )
            ],
            [
                InlineKeyboardButton(
                    " Sort by Games", callback_data=f"sort_games_{time_filter}"
                )
            ],
            # Time filter options
            [
                InlineKeyboardButton(" All Time", callback_data=f"sort_{sort_by}_all"),
                InlineKeyboardButton(
                    " Past Week", callback_data=f"sort_{sort_by}_week"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            try:
                # Try to edit the message
                await update.callback_query.message.edit_text(
                    message, reply_markup=reply_markup, parse_mode="HTML"
                )
                await update.callback_query.answer()
            except BadRequest as e:
                # If the message is not modified, ignore the error and continue
                if "Message is not modified" not in str(e):
                    raise
        else:
            await update.message.reply_text(
                message, reply_markup=reply_markup, parse_mode="HTML"
            )

    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        # Format: sort_<method>_<timefilter>
        _, sort_by, time_filter = query.data.split("_")
        await display_leaderboard(update, context, sort_by, time_filter)
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[CommandHandler("leaderboard", show_leaderboard)],
        states={},
        fallbacks=[],
        per_chat=True,
        per_user=False,
    ), CallbackQueryHandler(button_handler, pattern=r"^sort_")
