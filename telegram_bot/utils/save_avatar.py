import os
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

AVATAR_DIR = Path("data/avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)


async def save_avatar(bot, photo, user_id: int, pod_id: int) -> str:
    """Save the user's avatar photo to disk.

    Args:
        bot: The telegram bot instance
        photo: The PhotoSize object from telegram
        user_id: The user's telegram ID
        pod_id: The pod ID; i.e. the group chat ID

    Returns:
        The relative path to the saved avatar file
    """
    # Get the file from Telegram
    logger.info(f"saving avatar for {user_id} from {pod_id}")
    file = await bot.get_file(photo.file_id)

    # Create filename using user_id
    filename = f"{user_id}_{pod_id}.jpg"
    filepath = AVATAR_DIR / filename

    # Download and save the file
    await file.download_to_drive(custom_path=str(filepath))
    logger.info(f"Avatar saved at {filepath}")

    return str(filepath)
