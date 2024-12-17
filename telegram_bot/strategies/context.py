from telegram import Update
from telegram.ext import ContextTypes

from ..models.strategies import ContextStrategy

from typing import Optional, Dict, Any, Union, Callable

class SimpleContextStrategy(ContextStrategy):
    """A simple context strategy that updates user_data with provided values."""
    
    def __init__(self, data_updates: Dict[str, Union[Any, Callable[[ContextTypes.DEFAULT_TYPE], Any]]]):
        self.data_updates = data_updates

    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Update user_data with the provided values."""
        for key, value in self.data_updates.items():
            if callable(value):
                context.user_data[key] = value(context)
            else:
                context.user_data[key] = value
