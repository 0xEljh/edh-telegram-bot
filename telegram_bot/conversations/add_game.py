from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import logging

from telegram_bot.models.game import GameManager, GameOutcome
from telegram_bot.models import UnitHandler
from telegram_bot.strategies import (
    SimpleReplyStrategy,
    LoggingErrorStrategy,
    PlayerSelectionReply,
    EliminationSelectionReply,
    GameSummaryReply,
    WinnerSelectionReply,
)

logger = logging.getLogger(__name__)

# Updated conversation states
START_GAME, ADD_PLAYERS, SELECT_WINNER, RECORD_ELIMINATIONS, CONFIRM_GAME = range(5)


def create_game_conversation(game_manager: GameManager) -> ConversationHandler:
    """Create a conversation handler for adding a new game."""

    async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Initialize a new game and show player selection."""
        # Check if in group chat
        if update.effective_chat.type not in ["group", "supergroup"]:
            await update.message.reply_text(
                "❌ Games can only be created in group chats."
            )
            return ConversationHandler.END

        # Check if pod exists for this group
        chat_id = update.effective_chat.id
        if chat_id not in game_manager.pods:
            await update.message.reply_text(
                "❌ No pod exists for this group. Create one first using /pod"
            )
            return ConversationHandler.END

        # Create game with pod_id
        game = game_manager.create_game(pod_id=chat_id)
        context.user_data["current_game"] = game
        context.user_data["added_players"] = []
        context.user_data["eliminated_players"] = []
        return await PlayerSelectionHandler(update, context)

    async def handle_player_selection(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle player selection callback."""
        query = update.callback_query
        await query.answer()

        if query.data == "done_adding_players":
            # if len(context.user_data["added_players"]) < 2:
            #     await SimpleReplyStrategy(
            #         "❌ Sorry, no playing with yourself. At least 2 players are required for a game."
            #     ).execute(update, context)
            #     return await PlayerSelectionHandler(update, context)
            context.user_data["current_player_id"] = context.user_data["added_players"][
                0
            ]
            return await WinnerSelectionHandler(update, context)

        player_id = int(query.data.split(":")[1])
        context.user_data["added_players"].append(player_id)
        game = context.user_data["current_game"]

        player = game_manager.get_pod_player(player_id, game.pod_id)
        game.add_player(player_id, player.name)
        return await PlayerSelectionHandler(update, context)

    async def handle_winner_selection(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Process winner selection and set outcomes"""
        query = update.callback_query
        await query.answer()

        winner_id = int(query.data.split(":")[-1])
        game = context.user_data["current_game"]
        added_players = context.user_data["added_players"]

        # Set outcomes: winner=WIN, others=LOSE
        for player_id in added_players:
            outcome = GameOutcome.WIN if player_id == winner_id else GameOutcome.LOSE
            game.record_outcome(player_id, outcome)

        context.user_data["current_player_id"] = winner_id  # select for winner first
        return await EliminationSelectionHandler(update, context)

    async def handle_elimination_selection(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle elimination selection callback."""
        query = update.callback_query
        await query.answer()

        game = context.user_data["current_game"]
        winners = [
            player_id
            for player_id, outcome in game.outcomes.items()
            if outcome == GameOutcome.WIN
        ]

        if query.data == "done_eliminations":
            # check if there are still players to eliminate
            eliminated_players = context.user_data.get("eliminated_players", [])

            # if eliminated players + winners = total number of players, we are actually done
            if len(eliminated_players) + len(winners) == len(game.players):
                # done
                try:
                    await query.message.delete()
                except Exception as e:
                    # If deletion fails, just continue to summary
                    logger.warning(f"Failed to delete message: {str(e)}")
                return await GameSummaryHandler(update, context)

            # Move to next player
            current_idx = context.user_data["added_players"].index(
                context.user_data["current_player_id"]
            )
            if current_idx + 1 < len(context.user_data["added_players"]):
                context.user_data["current_player_id"] = context.user_data[
                    "added_players"
                ][current_idx + 1]
                return await EliminationSelectionHandler(update, context)
            else:  # all players iterated through; shouldn't hit this anymore
                # Delete the message before showing summary
                try:
                    await query.message.delete()
                except Exception as e:
                    # If deletion fails, just continue to summary
                    logger.warning(f"Failed to delete message: {str(e)}")
                return await GameSummaryHandler(update, context)

        eliminated_id = int(query.data.split(":")[1])
        game = context.user_data["current_game"]
        current_player_id = context.user_data["current_player_id"]

        game.eliminations[eliminated_id] = current_player_id
        context.user_data["eliminated_players"].append(eliminated_id)
        return await EliminationSelectionHandler(update, context)

    async def handle_game_confirmation(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle game confirmation message."""
        text = update.message.text.lower()
        game = context.user_data["current_game"]

        if text == "confirm":
            game_manager.add_game(game)
            await update.message.reply_text("👍 Game has been finalized and saved.")

            # Broadcast the game summary to all players
            for player_id in game.players.keys():
                try:
                    outcome = game.outcomes[player_id]
                    # outcome_emoji = "🏆" if outcome == GameOutcome.WIN else "💀" if outcome == GameOutcome.LOSE else "🤝"
                    outcome_verb = (
                        "VICTORIOUS"
                        if outcome == GameOutcome.WIN
                        else (
                            "DEFEATED"
                            if outcome == GameOutcome.LOSE
                            else "(what happened?)"
                        )
                    )
                    player_personal_message = (
                        f"📢 You were {outcome_verb} in a recent match!"
                    )

                    await context.bot.send_message(
                        chat_id=player_id,
                        parse_mode="HTML",
                        text=f"{player_personal_message}\n\n{str(game)}",
                    )
                except Exception as e:
                    # Log error but continue with other players if one fails
                    print(
                        f"Failed to send game summary to player {player_id}: {str(e)}"
                    )
                    logger.warning(
                        f"Failed to send game summary to player {player_id}: {str(e)}"
                    )

            return ConversationHandler.END
        elif text == "cancel":
            _reset_user_data(context)
            await SimpleReplyStrategy("❌ Game has been discarded.").execute(
                update, context
            )
            return ConversationHandler.END
        else:
            # wait for user to reply with "confirm" or "cancel"
            return CONFIRM_GAME

    # Create handlers with strategies
    PlayerSelectionHandler = UnitHandler(
        reply_strategy=PlayerSelectionReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=ADD_PLAYERS,
    )

    WinnerSelectionHandler = UnitHandler(
        reply_strategy=WinnerSelectionReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=SELECT_WINNER,
    )

    EliminationSelectionHandler = UnitHandler(
        reply_strategy=EliminationSelectionReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=RECORD_ELIMINATIONS,
    )

    GameSummaryHandler = UnitHandler(
        reply_strategy=GameSummaryReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=CONFIRM_GAME,
    )

    async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the current game creation process."""
        _reset_user_data(context)

        await update.message.reply_text(
            "❌ Game creation cancelled. Use /game to start a new game."
        )
        return ConversationHandler.END

    def _reset_user_data(context: ContextTypes.DEFAULT_TYPE) -> None:
        if "current_game" in context.user_data:
            del context.user_data["current_game"]
        if "added_players" in context.user_data:
            del context.user_data["added_players"]
        if "eliminated_players" in context.user_data:
            del context.user_data["eliminated_players"]
        if "current_player_id" in context.user_data:
            del context.user_data["current_player_id"]

    return ConversationHandler(
        entry_points=[CommandHandler("game", start_game)],
        states={
            ADD_PLAYERS: [CallbackQueryHandler(handle_player_selection)],
            SELECT_WINNER: [CallbackQueryHandler(handle_winner_selection)],
            RECORD_ELIMINATIONS: [CallbackQueryHandler(handle_elimination_selection)],
            CONFIRM_GAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_game_confirmation
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
