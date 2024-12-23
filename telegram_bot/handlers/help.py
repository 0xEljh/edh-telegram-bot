from telegram import Update
from telegram.ext import CommandHandler
from telegram_bot.strategies import SimpleReplyStrategy


def create_help_handler() -> CommandHandler:
    # direct people to my telegram and github
    telegram = "https://t.me/elijahngsy"
    github = "https://github.com/0xEljh/edh-telegram-bot"
    help_message = (
        f"👋 Encountered a bug? Contact me on telegram via {telegram}. I'd like to know about it, and am more than happy to help.\n\n"
        f"🔍 Want to see how this bot works? Or want to fix the issue directly? Check out the source code on github: {github}"
    )

    async def help(update: Update, context):
        await SimpleReplyStrategy(
            message_template=help_message, parse_mode="HTML"
        ).execute(update, context)

    return CommandHandler("help", help)
