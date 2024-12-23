from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from telegram_bot.models.game import GameManager

from telegram_bot.strategies import SimpleReplyStrategy, LoggingErrorStrategy

NAMING_POD = 0


def create_pod_conversation(game_manager: GameManager) -> ConversationHandler:
    async def start_pod_creation(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        if update.effective_chat.type not in ["group", "supergroup"]:
            await update.message.reply_text(
                "This command can only be used in group chats."
            )
            return ConversationHandler.END

        chat_id = update.effective_chat.id

        if chat_id in game_manager.pods:
            pod = game_manager.pods[chat_id]

            # Get all members in the pod
            member_stats = []
            for user_id in pod.members:
                if stats := game_manager.get_player_stats(user_id, chat_id):
                    member_stats.append(stats)

            # Sort members by win rate
            member_stats.sort(
                key=lambda x: x.wins / x.games_played if x.games_played > 0 else 0,
                reverse=True,
            )

            # Get all chat members who haven't signed up
            try:
                chat_members = await update.effective_chat.get_member_count()
                signed_up = len(pod.members)
                not_signed_up = chat_members - signed_up - 1  # -1 for the bot itself

                message = (
                    f"<b>📊 Pod Status: {pod.name}</b>\n\n"
                    f"<b>👥 Members ({signed_up}/{chat_members - 1})</b>\n"
                )

                for i, stats in enumerate(member_stats, 1):
                    winrate = (
                        stats.wins / stats.games_played * 100
                        if stats.games_played > 0
                        else 0
                    )
                    message += (
                        f"{i}. <b>{stats.name}</b>\n"
                        f"   • Win Rate: <code>{winrate:.1f}%</code>\n"
                        f"   • Record: <code>{stats.wins}W-{stats.losses}L</code>\n"
                        f"   • Games: <code>{stats.games_played}</code>\n\n"
                    )

                if not_signed_up > 0:
                    message += (
                        f"\n<i>😴 {not_signed_up} members haven't signed up yet.</i>\n"
                        "<i>They can join using /profile</i>"
                    )

                await update.message.reply_text(message, parse_mode="HTML")
            except Exception as e:
                # Fallback to basic message if we can't get member count
                await update.message.reply_text(
                    f"This group chat's pod, {pod.name}, has already been created. Use /profile to add yourself to this pod."
                )
            return ConversationHandler.END

        chat_id = update.effective_chat.id

        if chat_id in game_manager.pods:
            pod = game_manager.pods[chat_id]
            await update.message.reply_text(
                f"This group chat's pod, {pod.name}, has already been created. Use /profile to add yourself to this pod."
            )
            return ConversationHandler.END

        await SimpleReplyStrategy(
            message_template=(
                "Please enter a name for your new pod\n---\n"
                "<i>Reply to this by tapping this message and clicking 'Reply'. I can't see messages that aren't replies to me!</i>"
            ),
            parse_mode="HTML",
        ).execute(update, context)
        return NAMING_POD

    async def name_pod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        pod_name = update.message.text.strip()
        chat_id = update.effective_chat.id

        try:
            pod = game_manager.create_pod(chat_id, pod_name)
            await update.message.reply_text(
                f"Pod '{pod_name}' has been created successfully!"
            )
            await update.message.reply_text(
                "After pod members have created their profiles with /profile use /game to start recording games for this pod."
            )
        except ValueError as e:
            if "Pod with ID" in str(e) and "already exists" in str(e):
                pod = game_manager.pods[chat_id]
                await update.message.reply_text(
                    f"Your pod, {pod.name}, already exists."
                )
            else:
                await update.message.reply_text(f"Error creating pod: {str(e)}")

        return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Pod creation cancelled.")
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[CommandHandler("pod", start_pod_creation)],
        states={
            NAMING_POD: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_pod)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="pod_conversation",
        persistent=False,
        allow_reentry=True,
        per_chat=True,
        per_user=False,
    )
