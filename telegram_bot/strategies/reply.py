from typing import Optional, Union, Callable
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime

from telegram_bot.models import GameManager, Game, ReplyStrategy

GAMES_PER_PAGE = 5
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

        player = self.game_manager.get_player(update.effective_user.id)
        if not player:
            await self._send_message(
                update,
                context,
                "You don't have a profile yet. Join a game to create one!",
                None,
            )
            return

        win_rate = (
            (player.wins / player.games_played * 100) if player.games_played > 0 else 0
        )
        avg_eliminations = (
            (player.eliminations / player.games_played)
            if player.games_played > 0
            else 0
        )

        message = (
            f"🎮 <b>Player Profile for {player.name}</b>\n\n"
            f"📊 <b>Statistics:</b>\n"
            f"• Games Played: {player.games_played}\n"
            f"• Wins: {player.wins}\n"
            f"• Losses: {player.losses}\n"
            f"• Draws: {player.draws}\n"
            f"• Total Eliminations: {player.eliminations}\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• Average Eliminations: {avg_eliminations:.1f}\n"
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
        """Format a single game entry."""
        outcome = game.outcomes.get(player_id)
        eliminations = game.eliminations.get(player_id, 0)
        other_players = [name for tid, name in game.players.items() if tid != player_id]

        date = datetime.fromisoformat(game.created_at.isoformat())
        date_str = date.strftime("%Y-%m-%d %H:%M")

        return (
            f"🎲 <b>Game {game.game_id}</b> ({date_str})\n"
            f"• Outcome: {outcome.value.upper() if outcome else 'Unknown'}\n"
            f"• Eliminations: {eliminations}\n"
            f"• Other players: {', '.join(other_players)}\n"
        )

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the player's game history."""
        if not update.effective_user:
            await self._send_message(update, context, "Could not identify user.", None)
            return

        player_id = update.effective_user.id
        player = self.game_manager.get_player(player_id)
        if not player:
            await self._send_message(
                update, context, "You don't have any games yet!", None
            )
            return

        # Get current page from callback data or default to 0
        current_page = 0
        if update.callback_query and update.callback_query.data.startswith(PAGE_PREFIX):
            current_page = int(update.callback_query.data[len(PAGE_PREFIX) :])

        # Get player's games
        player_games = [
            game
            for game in self.game_manager.games.values()
            if player_id in game.players
        ]
        player_games.sort(key=lambda g: g.created_at, reverse=True)

        total_games = len(player_games)
        if total_games == 0:
            await self._send_message(
                update, context, "You haven't played any games yet!", None
            )
            return

        # Paginate games
        start_idx = current_page * GAMES_PER_PAGE
        end_idx = min(start_idx + GAMES_PER_PAGE, total_games)
        current_games = player_games[start_idx:end_idx]

        # Create message
        message = f"🎮 <b>Game History for {player.name}</b>\n"
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
