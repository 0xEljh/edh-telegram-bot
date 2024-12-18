"""
/start should nest other conversations like /profile and /game
everything should be accessible from /start
But for now, we'll keep it super simple
"""

from telegram import Update
from telegram.ext import CommandHandler


def create_start_handler() -> CommandHandler:
    """Send a welcome message when the command /start is issued."""
    welcome_message = (
        "👋 Welcome to the EDH Game Tracker Bot!\n\n"
        "Here's what you can do:\n\n"
        "📝 /profile - Create or view your player profile\n"
        "   ↳ New players should start here!\n\n"
        "   ↳ See your accumulated game statistics\n\n"
        "🎮 /game - Record a new game\n"
        "   ↳ Track wins, losses, and eliminations\n\n"
        "📊 /history - View your game history\n"
        "   ↳ Bask in previous glory or remember grievances\n\n"
        "Ready to begin? Start by setting up your /profile!"
    )

    async def start(update: Update, context):
        await update.message.reply_text(welcome_message)

    return CommandHandler("start", start)
