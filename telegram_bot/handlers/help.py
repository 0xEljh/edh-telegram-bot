from telegram import Update
from telegram.ext import CommandHandler
from telegram_bot.strategies import SimpleReplyStrategy


def create_help_handler() -> CommandHandler:
    # direct people to my telegram and github
    telegram = "@elijahngsy"
    github = "https://github.com/0xEljh/edh-telegram-bot"
    message = (
        "Here are the available commands:\n\n"
        "/start - Get started with the bot\n"
        "/profile - View your player profile and statistics\n"
        "/game - Start recording a new game\n"
        "/history - View your personal game history\n"
        "/podhistory - View this pod's game history\n"
        "/pod - Create or manage pods\n"
        "/leaderboard - View pod leaderboard with stats and rankings\n"
    )
    help_message = (
        f"👋 Encountered a bug? Contact me on telegram via {telegram}. I'd like to know about it, and am more than happy to help.\n\n"
        f"{message}\n\n"
        f"🔍 Want to see how this bot works? Or want to fix the issue directly? Check out the source code on github: {github}"
    )

    async def help(update: Update, context):
        await SimpleReplyStrategy(
            message_template=help_message, parse_mode="HTML"
        ).execute(update, context)

    return CommandHandler("help", help)
