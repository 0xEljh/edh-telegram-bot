from abc import ABC, abstractmethod
from os import error
from typing import Optional, Union, Callable, Dict, Type
from telegram import Update, InlineKeyboardMarkup
from telegram.error import BadRequest, NetworkError
from telegram.ext import ContextTypes
from telegram_bot.utils import safe_edit_message
from dataclasses import dataclass
import time


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
                return await safe_edit_message(
                    message=update.callback_query.message,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode=self.parse_mode
                )
            except BadRequest as e:
                # Message content didn't change, ignore error
                pass
            except NetworkError as e:
                # retry after short delay in event of transient network error
                time.sleep(0.5)
                return await safe_edit_message(
                    message=update.callback_query.message,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode=self.parse_mode
                )

        try:        
            return await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                parse_mode=self.parse_mode,
                reply_markup=keyboard,
            )
        except NetworkError as e:
            # retry after short delay in event of transient network error
            time.sleep(0.5)
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
