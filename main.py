from telegram_bot.models.game import GameManager
from telegram_bot.conversations import (
    create_profile_conversation,
    create_game_conversation,
    create_history_conversation,
    create_pod_conversation,
    create_leaderboard_conversation,
)
from telegram_bot.handlers import create_start_handler, create_help_handler
from telegram_bot.scheduled_tasks import schedule_weekly_roundup

from telegram.ext import Application
import dotenv
import os
import logging

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

dotenv.load_dotenv()

game_manager = GameManager(db_url="sqlite:///data/games.db")

# Create the handlers
start_command = create_start_handler()
help_command = create_help_handler()
profile_conversation = create_profile_conversation(game_manager)
game_conversation = create_game_conversation(game_manager)
history_command = create_history_conversation(game_manager)
pod_conversation = create_pod_conversation(game_manager)
leaderboard_conversation, leaderboard_callback = create_leaderboard_conversation(
    game_manager
)

# build application
application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()


# Add handlers
application.add_handler(start_command)
application.add_handler(help_command)
application.add_handler(profile_conversation)
application.add_handler(game_conversation)
application.add_handler(history_command)
application.add_handler(pod_conversation)
application.add_handler(leaderboard_conversation)
application.add_handler(leaderboard_callback)

# Schedule weekly roundup
schedule_weekly_roundup(application, game_manager)

# Start the bot
application.run_polling()
