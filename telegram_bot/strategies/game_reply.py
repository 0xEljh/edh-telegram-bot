from typing import List, Dict
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from telegram_bot.models import ReplyStrategy
from telegram_bot.models.game import GameManager, GameOutcome


class PlayerSelectionReply(ReplyStrategy):
    """Strategy for displaying player selection interface."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager
        self.update = None

    def _create_keyboard(self, added_players: List[int]) -> InlineKeyboardMarkup:
        """Create keyboard with available players."""
        keyboard = []
        chat_id = (
            self.update.effective_chat.id
            if self.update and self.update.effective_chat
            else None
        )

        if not chat_id or chat_id not in self.game_manager.pods:
            raise ValueError("Player selection should only be done in group chats.")

        # Get players from the current pod if in a group chat
        available_players = []

        pod = self.game_manager.pods[chat_id]
        for member_id in pod.members:
            if member_id not in added_players:
                player = self.game_manager.get_pod_player(member_id, chat_id)
                if player:
                    available_players.append(player)

        for player in available_players:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{player.name}",
                        callback_data=f"add_player:{player.telegram_id}",
                    )
                ]
            )
        keyboard.append(
            [
                InlineKeyboardButton(
                    "✅ Done Adding Players", callback_data="done_adding_players"
                )
            ]
        )
        return InlineKeyboardMarkup(keyboard)

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display player selection interface."""
        self.update = update
        added_players = context.user_data.get("added_players", [])
        keyboard = self._create_keyboard(added_players)
        chat_id = update.effective_chat.id

        message = "Select players to add to the game:"
        if added_players:
            current_players = [
                self.game_manager.get_pod_player(pid, chat_id).name
                for pid in added_players
            ]
            message = (
                f"👥 Current players: {', '.join(current_players)}\n\n"
                "Select more players or press Done:"
            )

        await self._send_message(
            update,
            context,
            message,
            keyboard,
            update_message=True if update.callback_query else False,
        )


class OutcomeSelectionReply(ReplyStrategy):
    """Strategy for displaying outcome selection interface."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager

    def _create_keyboard(self, player_id: int) -> InlineKeyboardMarkup:
        """Create keyboard with outcome options for a player."""
        keyboard = [
            [InlineKeyboardButton(f"🏆 Win", callback_data=f"outcome:{player_id}:win")],
            [
                InlineKeyboardButton(
                    f"💀 Lose", callback_data=f"outcome:{player_id}:lose"
                )
            ],
            [
                InlineKeyboardButton(
                    f"🤝 Draw", callback_data=f"outcome:{player_id}:draw"
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display outcome selection interface."""
        game = context.user_data["current_game"]
        current_player_id = context.user_data["current_player_id"]
        player_name = game.players[current_player_id]

        keyboard = self._create_keyboard(current_player_id)
        message = f"Select outcome for {player_name}:"

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message, reply_markup=keyboard
            )
        else:
            await update.message.reply_text(text=message, reply_markup=keyboard)


class EliminationSelectionReply(ReplyStrategy):
    """Strategy for displaying elimination selection interface."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager

    def _create_keyboard(
        self, available_players: List[int], current_player_id: int, pod_id: int
    ) -> InlineKeyboardMarkup:
        """Create keyboard with available players for elimination."""
        keyboard = []
        for pid in available_players:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        self.game_manager.get_pod_player(pid, pod_id),
                        callback_data=f"eliminate:{pid}",
                    )
                ]
            )
        keyboard.append(
            [InlineKeyboardButton("✅ Done", callback_data="done_eliminations")]
        )
        return InlineKeyboardMarkup(keyboard)

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display elimination selection interface."""
        game = context.user_data["current_game"]
        current_player_id = context.user_data["current_player_id"]
        eliminated_players = context.user_data.get("eliminated_players", [])
        pod_id = update.effective_chat.id

        available_players = [
            p for p in context.user_data["added_players"] if p not in eliminated_players
        ]

        keyboard = self._create_keyboard(available_players, current_player_id, pod_id)
        eliminated_by_current = [
            game.players[eid]
            for eid, eliminator_id in game.eliminations.items()
            if eliminator_id == current_player_id
        ]

        eliminated_list = (
            ""
            if not eliminated_by_current
            else "\n☠️ " + "\n☠️ ".join(eliminated_by_current)
        )

        message = (
            f"Select players eliminated by {game.players[current_player_id]}:"
            f"{eliminated_list}"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message, reply_markup=keyboard
            )
        else:
            await update.message.reply_text(text=message, reply_markup=keyboard)


class GameSummaryReply(ReplyStrategy):
    """Strategy for displaying game summary."""

    def __init__(self, game_manager: GameManager):
        super().__init__()
        self.game_manager = game_manager

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display game summary."""
        game = context.user_data["current_game"]
        game_summary = str(game)
        message = (
            f"Game summary:\n\n{game_summary}\n\n"
            "Type 'confirm' to finalize the game or 'cancel' to discard."
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(text=message)
        else:
            await update.message.reply_text(text=message)
