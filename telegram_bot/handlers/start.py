"""
/start should nest other conversations like /profile and /game
everything should be accessible from /start
But for now, we'll keep it super simple
"""

from telegram import Update
from telegram.ext import CommandHandler
from telegram_bot.strategies import SimpleReplyStrategy


def create_start_handler() -> CommandHandler:
    """Send a welcome message when the command /start is issued."""
    welcome_message = (
        "👋 Welcome to the EDH Game Tracker Bot!\n\n"
        "Here's what you can do:\n\n"
        "🏠 /pod - Create a new pod (play group)\n"
        "   ↳ Use this in a group chat to set up your play group\n"
        "   ↳ The bot must be added to the group chat first\n\n"
        "📝 /profile - Create or view your player profile\n"
        "   ↳ You'll need to do this for each pod you're in. Your profile is unique to each pod.\n"
        "   ↳ After your profile is created, use this to see your accumulated game statistics\n\n"
        "🎮 /game - Record a new game\n\n"
        "📊 /history - View past recorded games\n\n"
        "Ready to begin? Start by inviting me to your pod's group chat and then using /pod\n\n"
        "Tip: using /profile and /history in a private chat with me will show your stats/recorded games across all pods\n"
        "<i>Stuck? Use /cancel to exit any conversation and then try again.</i>"
    )

    async def start(update: Update, context):
        await SimpleReplyStrategy(
            message_template=welcome_message, parse_mode="HTML"
        ).execute(update, context)

    return CommandHandler("start", start)
