from typing import Optional
from telegram import Update
from .strategies import ContextStrategy, ReplyStrategy, ErrorStrategy

class UnitHandler:
    """A handler that executes a sequence of strategies to process a Telegram update."""

    def __init__(
        self,
        context_strategy: Optional[ContextStrategy] = None,
        reply_strategy: Optional[ReplyStrategy] = None,
        error_strategy: Optional[ErrorStrategy] = None,
        next_handler: Optional['UnitHandler'] = None,
        return_state: Optional[str] = None
    ):
        self.context_strategy = context_strategy
        self.reply_strategy = reply_strategy
        self.error_strategy = error_strategy
        self.next_handler = next_handler
        self.return_state = return_state


    async def __call__(self, update: Update, context) -> None:
        """Execute the handler's strategies in sequence.
        
        Args:
            update: The update from Telegram
            context: The context object from the handler; make no assumptions about its type at this level
        """
        try:
            # Execute context strategy if provided
            if self.context_strategy:
                await self.context_strategy.execute(update, context)

            # Execute reply strategy if provided
            if self.reply_strategy:
                await self.reply_strategy.execute(update, context)

            # Execute next handler if provided; 
            return_state = None
            if self.next_handler:
                return_state = await self.next_handler(update, context)
            
            # prioritize next handler's return
            if self.return_state is not None:
                return self.return_state
            return return_state

        except Exception as e:
            # Execute error strategy if provided
            if self.error_strategy:
                await self.error_strategy.handle_error(update, context, e)
            else:
                raise
