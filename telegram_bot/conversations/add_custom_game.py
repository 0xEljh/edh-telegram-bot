from telegram import Update
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
    OutcomeSelectionReply,
    EliminationSelectionReply,
    GameSummaryReply,
)

logger = logging.getLogger(__name__)

# Define conversation states
START_GAME, ADD_PLAYERS, RECORD_OUTCOMES, RECORD_ELIMINATIONS, CONFIRM_GAME = range(5)


def create_custom_game_conversation(game_manager: GameManager) -> ConversationHandler:
    """Create a conversation handler for adding a new (custom) game."""

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

        if context.user_data.get("current_game", None):
            await update.message.reply_text(
                "You were in the process of adding a game. Removing previous game data before continuing"
            )
            _reset_user_data(context)

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

        if query.data == "reset_players":
            context.user_data["added_players"] = []
            return await PlayerSelectionHandler(update, context)

        if query.data == "done_adding_players":
            if len(context.user_data["added_players"]) < 2:
                await SimpleReplyStrategy(
                    "❌ Sorry, no playing with yourself. At least 2 players are required for a game."
                ).execute(update, context)
                return await PlayerSelectionHandler(update, context)

            game = context.user_data["current_game"]
            for player_id in context.user_data["added_players"]:
                player = game_manager.get_pod_player(player_id, game.pod_id)
                game.add_player(player_id, player.name)

            context.user_data["current_player_id"] = context.user_data["added_players"][
                0
            ]

            return await OutcomeSelectionHandler(update, context)

        player_id = int(query.data.split(":")[1])
        context.user_data["added_players"].append(player_id)

        return await PlayerSelectionHandler(update, context)

    async def handle_outcome_selection(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle outcome selection callback."""
        query = update.callback_query
        await query.answer()

        outcome = GameOutcome(query.data.split(":")[2].lower())

        game = context.user_data["current_game"]
        current_player_id = context.user_data["current_player_id"]
        game.record_outcome(current_player_id, outcome)

        # Move to elimination selection for this player
        return await EliminationSelectionHandler(update, context)

    async def handle_elimination_selection(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle elimination selection callback."""
        query = update.callback_query
        await query.answer()

        game = context.user_data["current_game"]

        if query.data == "reset_eliminations":
            # remove all eliminations from current player
            current_player_id = context.user_data["current_player_id"]
            current_eliminations = [
                player
                for player, eliminator in game.eliminations.items()
                if eliminator == current_player_id
            ]
            # 1. Remove from game.eliminations
            # 2. Remove from eliminated players
            for player in current_eliminations:
                game.eliminations.pop(player)
            context.user_data["eliminated_players"] = [
                player
                for player in context.user_data["eliminated_players"]
                if player not in current_eliminations
            ]
            return await EliminationSelectionHandler(update, context)

        if query.data == "done_eliminations":
            # Move to next player or finish
            current_idx = context.user_data["added_players"].index(
                context.user_data["current_player_id"]
            )
            if current_idx + 1 < len(context.user_data["added_players"]):
                context.user_data["current_player_id"] = context.user_data[
                    "added_players"
                ][current_idx + 1]
                return await OutcomeSelectionHandler(update, context)
            else:
                # Delete the message before showing summary
                try:
                    await query.message.delete()
                except Exception as e:
                    # If deletion fails, just continue to summary
                    logger.warning(f"Failed to delete message: {str(e)}")
                return await GameSummaryHandler(update, context)

        eliminated_id = int(query.data.split(":")[1])
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

            # cleanup
            _reset_user_data(context)
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

    # Create handlers with strategies
    PlayerSelectionHandler = UnitHandler(
        reply_strategy=PlayerSelectionReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=ADD_PLAYERS,
    )

    OutcomeSelectionHandler = UnitHandler(
        reply_strategy=OutcomeSelectionReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=RECORD_OUTCOMES,
    )

    EliminationSelectionHandler = UnitHandler(
        reply_strategy=EliminationSelectionReply(
            game_manager, allow_self_elimination=True, allow_winner_elimination=True
        ),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=RECORD_ELIMINATIONS,
    )

    GameSummaryHandler = UnitHandler(
        reply_strategy=GameSummaryReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=CONFIRM_GAME,
    )

    return ConversationHandler(
        entry_points=[CommandHandler("customgame", start_game)],
        states={
            ADD_PLAYERS: [
                CallbackQueryHandler(handle_player_selection),
            ],
            RECORD_OUTCOMES: [
                CallbackQueryHandler(handle_outcome_selection),
            ],
            RECORD_ELIMINATIONS: [
                CallbackQueryHandler(handle_elimination_selection),
            ],
            CONFIRM_GAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_game_confirmation
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        conversation_timeout=300,  # Timeout after 5 minutes of inactivity
        per_user=True,
    )
