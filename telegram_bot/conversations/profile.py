"""
/start should prompt user to create a profile; i.e. choose a name at this stage.
Adding a photo will come later.
/profile will also have the same flow (i.e. create a profile if they don't already have one).
/start would also have other flows attached to it.
"""

from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from telegram_bot.models.game import GameManager
from telegram_bot.models import UnitHandler

from telegram_bot.strategies import (
    SimpleReplyStrategy,
    LoggingErrorStrategy,
    PlayerProfileReply,
)

ENTER_NAME = 0


def create_profile_conversation(game_manager: GameManager) -> ConversationHandler:
    # profile handler has 2 routes:
    # if user doesn't have a profile, move to creating one
    # if user has a profile, show their stats
    # game_manager = GameManager("data/data.json")

    def create_profile_message_template(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        user_name = (
            update.effective_user.first_name if update.effective_user else "User"
        )
        return f"👋 Let's create your player profile! What shall others know you as, {user_name}?"

    CreateProfileHandler = UnitHandler(
        reply_strategy=SimpleReplyStrategy(
            message_template=create_profile_message_template
        ),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=ENTER_NAME,
    )

    StatsHandler = UnitHandler(
        reply_strategy=PlayerProfileReply(game_manager),
        error_strategy=LoggingErrorStrategy(notify_user=True),
        return_state=ConversationHandler.END,  # for now, conversation simply ends here.
    )

    async def load_profile_and_route_user(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        # retrieve the player profile from the game manager via their telegram id:
        player = game_manager.get_player(telegram_id=update.effective_user.id)

        # chain subsequent handlers based on whether the player exists or not
        if player:
            return await StatsHandler(update, context)
        else:
            return await CreateProfileHandler(update, context)

    async def recieve_name_and_create_profile(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        game_manager.create_player(
            name=update.message.text.strip(), telegram_id=update.effective_user.id
        )
        await update.message.reply_text(
            f"✨ Welcome, {update.message.text.strip()}! Your profile has been created. You can now participate in games!"
        )
        return await StatsHandler(update, context)

    return ConversationHandler(
        entry_points=[CommandHandler("profile", load_profile_and_route_user)],
        states={
            ENTER_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, recieve_name_and_create_profile
                )
            ]
        },
        fallbacks=[],
    )
