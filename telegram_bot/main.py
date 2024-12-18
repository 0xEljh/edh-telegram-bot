from telegram_bot.models.game import GameManager
from telegram_bot.conversations import (
    create_profile_conversation,
    create_game_conversation,
    create_history_conversation,
)

from telegram.ext import Application
import dotenv
import os

dotenv.load_dotenv()

game_manager = GameManager("data/data.json")

# Create the handlers
profile_conversation = create_profile_conversation(game_manager)
game_conversation = create_game_conversation(game_manager)
history_command = create_history_conversation(game_manager)

# build and run application
application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
application.add_handler(profile_conversation)
application.add_handler(game_conversation)
application.add_handler(history_command)
application.run_polling()
