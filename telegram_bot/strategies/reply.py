from typing import Optional, Union, Callable
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime

from telegram_bot.models import GameManager, Game, ReplyStrategy

GAMES_PER_PAGE = 3
PAGE_PREFIX = "page_"


class SimpleReplyStrategy(ReplyStrategy):
    """A simple reply strategy that sends a message with an optional keyboard."""

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Execute the reply strategy by sending a message with optional keyboard.

        Args:
            update: The update from Telegram
            context: The context object from the handler
        """
        if not update.effective_chat:
            return

        # Get the message text
        if callable(self.message_template):
            message = self.message_template(update, context)
        else:
            message = self.message_template or ""

        # Get the keyboard
        keyboard = None
        if self.keyboard:
            if callable(self.keyboard):
                keyboard = self.keyboard(update, context)
            else:
                keyboard = self.keyboard

        # Send the message
        await self._send_message(update, context, message, keyboard)


class PlayerProfileReply(ReplyStrategy):
    """Strategy for displaying a player's profile and stats."""

    def __init__(self, game_manager: GameManager):
        super().__init__(parse_mode="HTML")
        self.game_manager = game_manager

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the player's profile."""
        if not update.effective_user:
            await self._send_message(update, context, "Could not identify user.", None)
            return
        user_name = update.effective_user.first_name
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None

        # Get player stats based on context
        # for the specific pod if in a group chat; else the aggregated player stats
        if chat_id and chat_id in self.game_manager.pods:
            # In a pod's group chat - show pod-specific stats
            player_stats = self.game_manager.get_pod_player(user_id, chat_id)
            if not player_stats:
                await self._send_message(
                    update,
                    context,
                    "You don't have a profile in this pod yet. Use the /profile command to create one!",
                    None,
                )
                return
        else:
            # In private chat - show aggregated stats across all pods
            player_stats = self.game_manager.get_aggregated_player_stats(user_id)
            if not player_stats:
                await self._send_message(
                    update,
                    context,
                    "You don't have a profile yet. Join a pod via a group chat to create one!",
                    None,
                )
                return


        win_rate = (
            (player_stats.wins / player_stats.games_played * 100) if player_stats.games_played > 0 else 0
        )
        avg_eliminations = (
            (player_stats.eliminations / player_stats.games_played)
            if player_stats.games_played > 0
            else 0
        )

        message = (
            f"🎮 <b>Player Profile for {user_name} aka {player_stats.name}"
            if not chat_id or chat_id not in self.game_manager.pods else
            f"🎮 <b>Player Profile for {user_name} aka {player_stats.name} in {self.game_manager.pods[chat_id].name}"
        )
        message += "</b>\n\n"
        message += (
            f"📊 <b>Statistics:</b>\n"
            f"• Games Played: {player_stats.games_played}\n"
            f"• Wins: {player_stats.wins}\n"
            f"• Losses: {player_stats.losses}\n"
            f"• Draws: {player_stats.draws}\n"
            f"• Total Kills: {player_stats.eliminations}\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• Average Kills: {avg_eliminations:.1f}\n"
        )

        await self._send_message(update, context, message, None)


class GameHistoryReply(ReplyStrategy):
    """Strategy for displaying a player's game history with pagination."""

    def __init__(self, game_manager: GameManager):
        super().__init__(parse_mode="HTML")
        self.game_manager = game_manager

    def _create_pagination_keyboard(
        self, total_games: int, current_page: int
    ) -> Optional[InlineKeyboardMarkup]:
        """Create pagination keyboard."""
        total_pages = (total_games + GAMES_PER_PAGE - 1) // GAMES_PER_PAGE
        if total_pages <= 1:
            return None

        buttons = []
        if current_page > 0:
            buttons.append(
                InlineKeyboardButton(
                    "◀️ Previous", callback_data=f"{PAGE_PREFIX}{current_page-1}"
                )
            )
        if current_page < total_pages - 1:
            buttons.append(
                InlineKeyboardButton(
                    "Next ▶️", callback_data=f"{PAGE_PREFIX}{current_page+1}"
                )
            )

        return InlineKeyboardMarkup([buttons]) if buttons else None

    def _format_game_entry(self, game: Game, player_id: int) -> str:
        return f"---\n\n{str(game)}\n\n"

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the player's game history."""
        if not update.effective_user:
            await self._send_message(update, context, "Could not identify user.", None)
            return

        player_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None
        
        # Get current page from callback data or default to 0
        current_page = 0
        if update.callback_query and update.callback_query.data.startswith(PAGE_PREFIX):
            current_page = int(update.callback_query.data[len(PAGE_PREFIX) :])

        # Get player's games, filtered by pod if in a group chat
        player_games = []
        for game in self.game_manager.games.values():
            if player_id in game.players:
                # If in group chat, only show games from this pod
                if chat_id and chat_id in self.game_manager.pods:
                    if game.pod_id == chat_id:
                        player_games.append(game)
                # If in private chat, show all games
                else:
                    player_games.append(game)

        player_games.sort(key=lambda g: g.created_at, reverse=True)

        total_games = len(player_games)
        if total_games == 0:
            message = "You haven't played any games"
            if chat_id and chat_id in self.game_manager.pods:
                message += f" in {self.game_manager.pods[chat_id].name}"
            message += " yet!"
            await self._send_message(update, context, message, None)
            return

        # Paginate games
        start_idx = current_page * GAMES_PER_PAGE
        end_idx = min(start_idx + GAMES_PER_PAGE, total_games)
        current_games = player_games[start_idx:end_idx]

        # Create message
        message = f"🎮 <b>Game History"
        if chat_id and chat_id in self.game_manager.pods:
            message += f" for {self.game_manager.pods[chat_id].name}"
        message += "</b>\n"
        message += f"Showing games {start_idx + 1}-{end_idx} of {total_games}\n\n"

        for game in current_games:
            message += self._format_game_entry(game, player_id) + "\n"

        keyboard = self._create_pagination_keyboard(total_games, current_page)

        # If this is a callback query, edit the message
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message, parse_mode=self.parse_mode, reply_markup=keyboard
            )
        else:
            await self._send_message(update, context, message, keyboard)
