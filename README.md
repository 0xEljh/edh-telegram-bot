# EDH Telegram Bot

A Telegram bot to track wins, losses, and statistics in your EDH/Commander Magic: The Gathering pods!

## Features

- Create and manage multiple EDH pods
- Track game outcomes (wins, losses, draws)
- Record player eliminations and kill counts
- View player statistics per pod and overall
- Simple and intuitive conversation-based interface
- Persistent data storage (kept simple for now)

## Commands

- `/start` - Get started with the bot
- `/profile` - View your player profile and statistics
- `/game` - Start recording a new game
- `/history` - View game history
- `/pod` - Create or manage pods

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/edh-telegram-bot.git
cd edh-telegram-bot
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Create a `.env` file with your Telegram bot token:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

---

Alternatively, use the dev-container provided in this repository to run the bot locally.

## Running the Bot

1. Activate the Poetry environment:
```bash
poetry shell
```

2. Run the bot:
```bash
python main.py
```

## Project Structure

- `telegram_bot/`
  - `conversations/` - Conversation handlers for interactive commands
  - `handlers/` - Command handlers
  - `models/` - Data models and game logic
  - `strategies/` - Reply and error handling strategies

## Dependencies

- Python 3.11+
- python-telegram-bot 20.7+
- python-dotenv 1.0.0+

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

0xEljh (elijah@0xEljh.com)

## Contribute

Any contributions are welcome!

## Future Plans

- Weekly broadcasts of game results and statistics
- More persistent persistent storage (it's a local JSON file for now)
- Add a leaderboard feature
