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
from telegram_bot.utils import save_avatar
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ENTER_NAME = 0
ENTER_PHOTO = 1


def create_profile_conversation(game_manager: GameManager) -> ConversationHandler:
    # profile handler has 2 routes:
    # if user doesn't have a profile, move to creating one
    # if user has a profile, show their stats

    def create_profile_message_template(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        user_name = (
            update.effective_user.first_name if update.effective_user else "User"
        )
        pod = game_manager.pods.get(update.effective_chat.id)
        return (
            f"👋 Let's create your player profile! What shall others in {pod.name} know you as, {user_name}?"
            "\n---\n"
            "<i>Reply to this by tapping this message and clicking 'Reply'. I can't see messages that aren't replies to me!</i>"
        )

    CreateProfileHandler = UnitHandler(
        reply_strategy=SimpleReplyStrategy(
            message_template=create_profile_message_template,
            parse_mode="HTML",
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

        # check if in a group chat
        if update.effective_chat.type not in ["group", "supergroup"]:
            # if not in a group chat, check if player already exists:
            if player:
                return await StatsHandler(update, context)
            else:
                # if player doesn't exist, tell them to create a profile via a pod
                await SimpleReplyStrategy(
                    message_template="❌ You don't have a profile yet. Join a pod via a group chat to create one!",
                ).execute(update, context)
                return ConversationHandler.END

        chat_id = update.effective_chat.id

        if chat_id not in game_manager.pods:
            await SimpleReplyStrategy(
                message_template="❌ No pod exists for this group. Create one first using /pod"
            ).execute(update, context)
            return ConversationHandler.END

        # attempt to retrieve the player's stats from the pod
        player_stats = game_manager.get_player_stats(
            telegram_id=update.effective_user.id, pod_id=chat_id
        )
        # chain subsequent handlers based on whether the player exists or not
        if player_stats:
            return await StatsHandler(update, context)
        else:
            return await CreateProfileHandler(update, context)

    async def receive_name_and_prompt_photo(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        # Store the name in context for later use
        profile_name = update.message.text.strip()
        context.user_data["profile_name"] = profile_name

        await update.message.reply_text(
            f"Great name, {profile_name}! 📸 Now, you can optionally send me a photo for your profile, or send /skip to continue without one."
        )
        return ENTER_PHOTO

    async def receive_photo_and_create_profile(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        chat_id = update.effective_chat.id
        name = context.user_data["profile_name"]

        if not name:
            logger.error(
                "No name stored in user_data when expecting to create a profile."
            )
            await update.message.reply_text(
                "❌ Something went wrong. Please start over with /profile."
            )
            return ConversationHandler.END

        # Get the smallest usable photo (we don't need high resolution)
        # Telegram sends multiple sizes, first is smallest
        photo = update.message.photo[0]

        # Save the avatar
        # note that since avatars are unique to each (user, pod) pair, we can't just use the user_id
        avatar_path = await save_avatar(
            context.bot, photo, update.effective_user.id, chat_id
        )

        logger.info(
            f"Attempting to create profile for {update.effective_user.id} with name='{name}'"
        )

        game_manager.create_player(
            name=name,
            telegram_id=update.effective_user.id,
            pod_id=chat_id,
            avatar_url=avatar_path,
        )

        await update.message.reply_text(
            f"✨ Welcome, {name}! Your profile has been created with your photo. You can now participate in games!"
        )
        return ConversationHandler.END

    async def skip_photo_and_create_profile(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> str:
        chat_id = update.effective_chat.id
        name = context.user_data["profile_name"]

        if not name:
            logger.error(
                "No name stored in user_data when expecting to create a profile."
            )
            await update.message.reply_text(
                "❌ Something went wrong. Please start over with /profile."
            )
            return ConversationHandler.END

        logger.info(
            f"Attempting to create profile for {update.effective_user.id} with name='{name}'"
        )

        # Try to get user's Telegram profile photo
        user_profile_photos = await context.bot.get_user_profile_photos(
            user_id=update.effective_user.id, limit=1
        )

        avatar_path = None
        if user_profile_photos.total_count > 0:
            # Get the smallest usable size of their profile photo
            photo = user_profile_photos.photos[0][0]  # First photo, smallest size
            avatar_path = await save_avatar(
                context.bot, photo, update.effective_user.id, chat_id
            )
        try:
            game_manager.create_player(
                name=name,
                telegram_id=update.effective_user.id,
                pod_id=chat_id,
                avatar_url=avatar_path,
            )
        except Exception as e:
            logger.exception("Failed to create player profile without a custom photo.")
            await update.message.reply_text(
                "❌ Something went wrong while creating your profile. Please try again."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            f"✨ Welcome, {name}! Your profile has been created. You can now participate in games!"
        )
        return ConversationHandler.END

    async def handle_unexpected_file(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle unexpected file types in the ENTER_PHOTO state."""
        logger.warning("User sent an unexpected file type instead of a photo.")
        await update.message.reply_text(
            "❌ I only accept photos here! Please either send a photo or use /skip."
        )
        return ENTER_PHOTO

    def _reset_user_data(context):
        # remove name and photo
        if "profile_name" in context.user_data:
            del context.user_data["profile_name"]

    async def cancel_profile_creation(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel profile creation process."""
        logger.info("Profile creation conversation canceled by user.")
        _reset_user_data(context)
        await update.message.reply_text(
            "❌ Profile creation cancelled. Use /profile to try again."
        )
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[CommandHandler("profile", load_profile_and_route_user)],
        states={
            ENTER_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_name_and_prompt_photo
                ),
                CommandHandler(
                    "profile", cancel_profile_creation
                ),  # Cancel if user hits /profile again
            ],
            ENTER_PHOTO: [
                MessageHandler(filters.PHOTO, receive_photo_and_create_profile),
                CommandHandler("skip", skip_photo_and_create_profile),
                MessageHandler(
                    ~filters.COMMAND & ~filters.PHOTO, handle_unexpected_file
                ),
                CommandHandler(
                    "profile", cancel_profile_creation
                ),  # Cancel if user hits /profile again
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_profile_creation)],
        per_chat=True,
        per_user=True,
    )
