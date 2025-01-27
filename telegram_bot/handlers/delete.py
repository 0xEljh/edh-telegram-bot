from telegram import Update
from telegram.ext import CommandHandler
from telegram_bot.strategies import SimpleReplyStrategy
from telegram_bot.models.game import GameManager


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
        result = game_manager.request_game_deletion(game_ref, user_id)
        status_map = {
            "not_found": "❌ Game not found",
            "not_in_game": "❌ You're not part of this game",
            "already_requested": "⏳ You've already requested deletion on this game. It will be deleted if another player uses /delete on the same game.",
            "deleted": "✅ Game deleted successfully",
            "pending": "🗑️ Deletion request recorded! Need 1 more confirmation to delete the game: Another player must also use /delete on the same game.",
            "error": f"❌ Error: {result.get('error', 'Unknown error')}",
        }

        await SimpleReplyStrategy(status_map[result["status"]]).execute(update, context)

    return CommandHandler("delete", handle_delete_game)
