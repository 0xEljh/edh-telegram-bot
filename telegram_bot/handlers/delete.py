from telegram import Update
from telegram.ext import CommandHandler
from telegram_bot.strategies import SimpleReplyStrategy
from telegram_bot.models.game import GameManager
import logging

logger = logging.getLogger(__name__)


def create_deletegame_handler(game_manager: GameManager) -> CommandHandler:
    async def handle_delete_game(update: Update, context):
        user_id = update.effective_user.id
        args = context.args

        if not args:
            await SimpleReplyStrategy(
                "Please provide a game reference\n" "Usage: /delete <game_reference>"
            ).execute(update, context)
            return

        game_ref = args[0]
        game = game_manager.get_game_by_reference(game_ref)

        if game is None:
            return await SimpleReplyStrategy(
                "❌ Game not found. Copy a game reference by tapping on it in the history message and try again."
            )

        result = game_manager.request_game_deletion(game_ref, user_id)
        status_map = {
            "not_found": "❌ Game not found",
            "not_in_game": "❌ You're not part of this game",
            "already_requested": "⏳ You've already requested deletion on this game. It will be deleted if another player uses /delete on the same game.",
            "deleted": "✅ Game deleted successfully",
            "pending": "🗑️ Deletion request recorded! Need 1 more confirmation to delete the game: Another player must also use /delete on the same game.",
            "error": f"❌ Error: {result.get('error', 'Unknown error')}",
        }

        # if pending, let all involved players know a request was made via DM, and that they can attempt to delete it too
        if result["status"] == "pending":
            for player_id in game.players.keys():
                if player_id == user_id:
                    # skip the user themselves for this
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=player_id,
                        parse_mode="HTML",
                        text=f"A player has requested that the following game be deleted. If this is correct, please use /delete {game_ref} to confirm their deletion request.\n\n{str(game)}",
                    )
                except Exception as e:
                    # Log error but continue with other players if one fails
                    print(
                        f"Failed to send game summary to player {player_id}: {str(e)}"
                    )
                    logger.warning(
                        f"Failed to send game summary to player {player_id}: {str(e)}"
                    )

        # if deleted, let all involved players know their games has been deleted via DM
        if result["status"] == "deleted":
            for player_id in game.players.keys():
                try:
                    await context.bot.send_message(
                        chat_id=player_id,
                        parse_mode="HTML",
                        text=f"A game you were a part of has been deleted.\n\n{str(game)}",
                    )
                except Exception as e:
                    # Log error but continue with other players if one fails
                    print(
                        f"Failed to send game summary to player {player_id}: {str(e)}"
                    )
                    logger.warning(
                        f"Failed to send game summary to player {player_id}: {str(e)}"
                    )

        await SimpleReplyStrategy(status_map[result["status"]]).execute(update, context)

    return CommandHandler("delete", handle_delete_game)
