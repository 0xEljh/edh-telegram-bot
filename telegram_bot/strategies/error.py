from telegram import Update
from telegram.ext import ContextTypes
import logging
from typing import Optional

from ..models.strategies import ErrorStrategy

logger = logging.getLogger(__name__)


class LoggingErrorStrategy(ErrorStrategy):
    """An error strategy that logs errors and notifies the user."""

    def __init__(
        self,
        notify_user: bool = True,
        default_message: str = "An error occurred while processing your request. Please try again later.",
        error_messages: Optional[dict[type[Exception], str]] = None,
    ):
        super().__init__(error_messages=error_messages, default_message=default_message)
        self.notify_user = notify_user

    async def handle_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
        error_messages: Optional[dict[type[Exception], str]] = None,
    ) -> None:
        """Log the error and optionally notify the user."""
        logger.error(f"Error occurred while handling update {update}: {error}")

        if self.notify_user and update.effective_chat:
            # Find the most specific error message that matches the error type
            message = self.default_message
            if error_messages:
                for error_type, custom_message in error_messages.items():
                    if isinstance(error, error_type):
                        message = custom_message
                        break

            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=message
            )
