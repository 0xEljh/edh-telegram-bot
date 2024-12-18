from abc import ABC, abstractmethod
from os import error
from typing import Optional, Union, Callable, Dict, Type
from telegram import Update, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from dataclasses import dataclass


class ContextStrategy(ABC):
    """Abstract base class for context manipulation strategies."""

    @abstractmethod
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Execute the context strategy.

        Args:
            update: The update from Telegram
            context: The context object from the handler
        """
        pass


class ReplyStrategy(ABC):
    """Abstract base class for reply strategies."""

    def __init__(
        self,
        message_template: Optional[
            Union[str, Callable[[Update, ContextTypes.DEFAULT_TYPE], str]]
        ] = None,
        parse_mode: Optional[str] = None,
        keyboard: Optional[
            Union[
                InlineKeyboardMarkup,
                Callable[[Update, ContextTypes.DEFAULT_TYPE], InlineKeyboardMarkup],
            ]
        ] = None,
    ):
        self.message_template = message_template
        self.parse_mode = parse_mode
        self.keyboard = keyboard

    async def _send_message(
        self, update, context, message, keyboard, update_message=False
    ):
        """Helper to abstract away complexity of sending a message to the user."""

        if update.callback_query and update_message:
            try:
                return await update.callback_query.edit_message_text(
                    text=message, parse_mode=self.parse_mode, reply_markup=keyboard
                )
            except BadRequest as e:
                pass

        return await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode=self.parse_mode,
            reply_markup=keyboard,
        )

    @abstractmethod
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Execute the reply strategy.

        Args:
            update: The update from Telegram
            context: The context object from the handler
        """
        pass


@dataclass
class ErrorStrategy(ABC):
    """Abstract base class for error handling strategies."""

    error_messages: Optional[Dict[Type[Exception], str]]
    default_message: str

    @abstractmethod
    async def handle_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
    ) -> None:
        """Handle an error that occurred during handler execution.

        Args:
            update: The update from Telegram
            context: The context object from the handler
            error: The exception that was raised
        """
        pass
