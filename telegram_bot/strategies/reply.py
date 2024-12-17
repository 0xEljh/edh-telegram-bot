from typing import Optional, Union, Callable
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..models.strategies import ReplyStrategy

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
