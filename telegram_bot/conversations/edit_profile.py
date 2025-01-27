from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

# Add these states at the top with other state definitions
EDIT_PROFILE = "edit_profile"
SELECT_POD = "select_pod"
CHOOSE_ACTION = "choose_action"
ENTER_NEW_NAME = "enter_new_name"
ENTER_NEW_PHOTO = "enter_new_photo"


def create_edit_profile_conversation(game_manager: GameManager) -> ConversationHandler:
    async def start_edit_profile(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Entry point for profile editing conversation."""
        chat_type = update.effective_chat.type
        user_id = update.effective_user.id

        # Reset any previous data
        context.user_data.clear()

        if chat_type in ["group", "supergroup"]:
            # Handle group chat context
            pod_id = update.effective_chat.id
            player = game_manager.get_pod_player(user_id, pod_id)

            if not player:
                await SimpleReplyStrategy(
                    "❌ You don't have a profile in this pod yet!"
                ).execute(update, context)
                return ConversationHandler.END

            context.user_data["pod_id"] = pod_id
            await SimpleReplyStrategy(
                "🔧 Please continue profile editing in our private chat!"
            ).execute(update, context, reply_markup=ReplyKeyboardRemove())

            # Send private message with edit options
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✏️ Editing profile for {game_manager.pods[pod_id].name}...",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Change Name", callback_data="name")],
                        [InlineKeyboardButton("Change Avatar", callback_data="avatar")],
                        [InlineKeyboardButton("Cancel", callback_data="cancel")],
                    ]
                ),
            )
            return CHOOSE_ACTION

        else:  # Private chat
            pods = game_manager.get_user_pods(user_id)
            if not pods:
                await SimpleReplyStrategy("❌ You're not in any pods yet!").execute(
                    update, context
                )
                return ConversationHandler.END

            if len(pods) == 1:
                context.user_data["pod_id"] = pods[0].pod_id
                return await present_edit_options(update, context)

            buttons = [
                [InlineKeyboardButton(pod.name, callback_data=f"pod_{pod.pod_id}")]
                for pod in pods
            ]
            await SimpleReplyStrategy(
                "📂 Which pod's profile would you like to edit?"
            ).execute(update, context, reply_markup=InlineKeyboardMarkup(buttons))
            return SELECT_POD

    async def select_pod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle pod selection in private chat."""
        query = update.callback_query
        await query.answer()

        pod_id = int(query.data.split("_")[1])
        context.user_data["pod_id"] = pod_id
        return await present_edit_options(query, context)

    async def present_edit_options(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Present edit options after pod selection."""
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Change Name", callback_data="name")],
                [InlineKeyboardButton("Change Avatar", callback_data="avatar")],
                [InlineKeyboardButton("Both", callback_data="both")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")],
            ]
        )

        if isinstance(update, CallbackQuery):
            await update.edit_message_text("📝 What would you like to update?")
            await SimpleReplyStrategy("Choose an option:").execute(
                update.message, context, reply_markup=keyboard
            )
        else:
            await SimpleReplyStrategy("Choose an option:").execute(
                update, context, reply_markup=keyboard
            )
        return CHOOSE_ACTION

    async def handle_edit_choice(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle user's choice of what to edit."""
        query = update.callback_query
        await query.answer()

        choice = query.data
        if choice == "cancel":
            await query.edit_message_text("❌ Edit cancelled.")
            return ConversationHandler.END

        context.user_data["edit_mode"] = choice

        if choice in ["name", "both"]:
            await query.edit_message_text("🖊️ Please send your new name:")
            return ENTER_NEW_NAME

        if choice == "avatar":
            await query.edit_message_text("📸 Please send your new profile photo:")
            return ENTER_NEW_PHOTO

    async def handle_new_name(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Process new name input."""
        new_name = update.message.text.strip()
        context.user_data["new_name"] = new_name

        if context.user_data.get("edit_mode") == "both":
            await SimpleReplyStrategy(
                "✅ Name saved! Now send your new photo:"
            ).execute(update, context)
            return ENTER_NEW_PHOTO

        return await finalize_update(update, context)

    async def handle_new_photo(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Process new photo upload."""
        photo = update.message.photo[-1]  # Get highest quality photo
        pod_id = context.user_data["pod_id"]
        user_id = update.effective_user.id

        try:
            avatar_path = await save_avatar(context.bot, photo, user_id, pod_id)
            context.user_data["new_avatar"] = avatar_path
        except Exception as e:
            logger.error(f"Failed to save avatar: {str(e)}")
            await SimpleReplyStrategy(
                "❌ Failed to save photo. Please try again."
            ).execute(update, context)
            return ENTER_NEW_PHOTO

        return await finalize_update(update, context)

    async def finalize_update(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Commit changes to database."""
        pod_id = context.user_data["pod_id"]
        user_id = update.effective_user.id
        new_name = context.user_data.get("new_name")
        new_avatar = context.user_data.get("new_avatar")

        try:
            # Update database
            session = game_manager.Session()
            player = (
                session.query(PodPlayer)
                .filter_by(telegram_id=user_id, pod_id=pod_id)
                .first()
            )

            if new_name:
                player.name = new_name
            if new_avatar:
                player.avatar_url = new_avatar

            session.commit()
            await SimpleReplyStrategy("✅ Profile updated successfully!").execute(
                update, context
            )
        except Exception as e:
            logger.error(f"Update failed: {str(e)}")
            await SimpleReplyStrategy(
                "❌ Failed to update profile. Please try again."
            ).execute(update, context)
        finally:
            session.close()
            context.user_data.clear()

        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[CommandHandler("editprofile", start_edit_profile)],
        states={
            SELECT_POD: [CallbackQueryHandler(select_pod)],
            CHOOSE_ACTION: [CallbackQueryHandler(handle_edit_choice)],
            ENTER_NEW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_name)
            ],
            ENTER_NEW_PHOTO: [MessageHandler(filters.PHOTO, handle_new_photo)],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            MessageHandler(filters.ALL, lambda u, c: None),  # Ignore invalid inputs
        ],
        per_user=True,
        per_chat=True,
    )
