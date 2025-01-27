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
        "   • Add me to your group chat, then use this command to create a pod.\n"
        "   • Pod names are final. At least for now.\n\n"
        "📝 /profile - Create or view your player profile\n"
        "   • To include a player in a game, that player must already have a profile.\n"
        "   • You'll need to do this for each pod you're in. Your profile is unique to each pod.\n"
        "   • Your name and profile picture are also final for now.\n"
        "   • After your profile is created, use this to see your accumulated game statistics\n\n"
        "🎮 /game - Record a new game\n"
        "   • If your game is atypical (e.g. multiple winners, draws, a player won through dying), use /customgame instead\n\n"
        "📊 /history - View past recorded games\n\n"
        "❌ /delete <reference> - Delete a game\n"
        "   • Game reference IDs can be found at the bottom of game summaries in /history\n"
        "   • 2 players must attempt to delete the same game before it gets deleted. This is to prevent griefing.\n\n"
        "Ready to begin? Start by inviting me to your pod's group chat and then using /pod\n\n"
        "<i>Stuck? Use /cancel to exit any conversation and then try again. If the issue still persists, contact me on telegram via /help</i>\n"
        "<i>Wish to record your games with different play groups? You can add me into the chat with each of your different play groups and create a pod. You will need to create a player profile for each new pod you are in. </i>\n"
        "Tip: using /profile and /history in a private chat with me will show your stats/recorded games across all pods\n"
    )

    async def start(update: Update, context):
        await SimpleReplyStrategy(
            message_template=welcome_message, parse_mode="HTML"
        ).execute(update, context)

    return CommandHandler("start", start)
