from typing import List, Dict
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from telegram_bot.models import ReplyStrategy
from telegram_bot.models.game import GameManager, GameOutcome
from telegram_bot.utils import format_name


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

        for member_id in self.game_manager.get_pod_members(chat_id):
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
        if added_players:
            keyboard.append(
                [
                    InlineKeyboardButton("🔄 Reset", callback_data="reset_players"),
                    InlineKeyboardButton(
                        "✅ Done", callback_data="done_adding_players"
                    ),
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
            current_player_names = [
                self.game_manager.get_pod_player(pid, chat_id).name
                for pid in added_players
            ]
            message = (
                "👥 Current players:\n\n"
                + "\n".join(
                    f"👤 {format_name(name, max_len=20)}"
                    for name in current_player_names
                )
                + "\n\n"
                + "Select more players or press Done:"
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

        await self._send_message(
            update,
            context,
            message,
            keyboard,
            update_message=True if update.callback_query else False,
        )


class EliminationSelectionReply(ReplyStrategy):
    """Strategy for displaying elimination selection interface."""

    def __init__(
        self,
        game_manager: GameManager,
        allow_self_elimination: bool = False,
        allow_winner_elimination=False,
    ):
        super().__init__()
        self.game_manager = game_manager
        self.allow_self_elimination = allow_self_elimination
        self.allow_winner_elimination = allow_winner_elimination

    def _create_keyboard(
        self,
        available_players: List[int],
        current_player_id: int,
        pod_id: int,
        eliminated_list: list,
    ) -> InlineKeyboardMarkup:
        """Create keyboard with available players for elimination."""
        keyboard = []
        for pid in available_players:
            if not self.allow_self_elimination and pid == current_player_id:
                continue
            player = self.game_manager.get_pod_player(pid, pod_id)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        player.name,
                        callback_data=f"eliminate:{pid}",
                    )
                ]
            )

        actions = []
        if eliminated_list:
            actions.append(
                InlineKeyboardButton("🔄 Reset", callback_data="reset_eliminations")
            )
        actions.append(
            InlineKeyboardButton("✅ Done", callback_data="done_eliminations")
        )

        keyboard.append(actions)
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

        if not self.allow_winner_elimination:
            winners = [
                player_id
                for player_id, outcome in game.outcomes.items()
                if outcome == GameOutcome.WIN
            ]
            available_players = [p for p in available_players if p not in winners]

        eliminated_by_current = [
            format_name(game.players[eid], max_len=20)
            for eid, eliminator_id in game.eliminations.items()
            if eliminator_id == current_player_id
        ]

        eliminated_list = (
            ""
            if not eliminated_by_current
            else "\n☠️ " + "\n☠️ ".join(eliminated_by_current)
        )

        keyboard = self._create_keyboard(
            available_players, current_player_id, pod_id, eliminated_list
        )

        message = (
            f"Select players eliminated by {game.players[current_player_id]}:"
            f"{eliminated_list}"
        )

        await self._send_message(
            update,
            context,
            message,
            keyboard,
            update_message=True if update.callback_query else False,
        )


class GameSummaryReply(ReplyStrategy):
    """Strategy for displaying game summary."""

    def __init__(self, game_manager: GameManager):
        super().__init__(parse_mode="HTML")
        self.game_manager = game_manager

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display game summary."""
        game = context.user_data["current_game"]
        game_summary = str(game)
        message = (
            f"Game summary:\n\n{game_summary}\n\n"
            "<b>Reply 'confirm' to finalize the game or 'cancel' to discard.</b>"
            "\n---\n"
            "<i>Reply to this by tapping this message and clicking 'Reply'. I can't see messages that aren't replies to me!</i>"
        )

        await self._send_message(
            update=update, context=context, message=message, keyboard=None
        )


class WinnerSelectionReply(ReplyStrategy):
    """Strategy for displaying winner selection interface."""

    def __init__(self, game_manager: GameManager):
        super().__init__(parse_mode="HTML")
        self.game_manager = game_manager

    def _create_keyboard(
        self, available_players: List[int], pod_id: int
    ) -> InlineKeyboardMarkup:
        """Create keyboard with available players for winner selection."""
        keyboard = []
        for pid in available_players:
            player = self.game_manager.get_pod_player(pid, pod_id)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        player.name,
                        callback_data=f"winner:{pid}",
                    )
                ]
            )
        return InlineKeyboardMarkup(keyboard)

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display winner selection interface."""
        game = context.user_data["current_game"]
        pod_id = update.effective_chat.id

        # Get all players in the game
        available_players = context.user_data["added_players"]
        keyboard = self._create_keyboard(available_players, pod_id)

        message = (
            "🏆 Select the winner of the game:\n"
            "<i>Are there multiple winners in your game? Use /cancel to abort. Then use /customgame instead.</i>"
        )

        await self._send_message(
            update,
            context,
            message,
            keyboard,
            update_message=True if update.callback_query else False,
        )
