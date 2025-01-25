"""Rate limiting utilities for Telegram API calls."""
import asyncio
import logging
from typing import Optional, Any, Callable
from datetime import datetime, timedelta
from telegram.error import RetryAfter, TimedOut
from telegram import Message

logger = logging.getLogger(__name__)

# Global rate limiting state
_last_edit = datetime.now()
MIN_EDIT_INTERVAL = 0.2  # seconds between edits

async def safe_edit_message(
    message: Message,
    text: str,
    reply_markup: Optional[Any] = None,
    parse_mode: Optional[str] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Optional[Message]:
    """
    Safely edit a message with rate limiting and retries.
    
    Args:
        message: Message to edit
        text: New text content
        reply_markup: Optional reply markup (keyboard)
        parse_mode: Optional parse mode for text formatting
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (will be exponentially increased)
        
    Returns:
        Updated message if successful, None if failed after retries
    """
    global _last_edit
    
    # Ensure minimum time between edits
    now = datetime.now()
    time_since_last = (now - _last_edit).total_seconds()
    if time_since_last < MIN_EDIT_INTERVAL:
        await asyncio.sleep(MIN_EDIT_INTERVAL - time_since_last)
    
    for attempt in range(max_retries):
        try:
            # Update last edit time before attempting
            _last_edit = datetime.now()
            
            return await message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            
        except RetryAfter as e:
            if attempt == max_retries - 1:
                raise
            
            # Wait the required time plus a small buffer
            wait_time = e.retry_after + 0.1
            logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
            await asyncio.sleep(wait_time)
            
        except TimedOut:
            if attempt == max_retries - 1:
                raise
                
            # Exponential backoff for timeouts
            wait_time = base_delay * (2 ** attempt)
            logger.warning(f"Request timed out, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"Failed to edit message: {str(e)}")
            raise

    return None
