# March Madness Bot

## Version
**v1.1.1**

## Description
The March Madness Bot is designed to assist users in tracking and managing their March Madness brackets. It integrates with Slack to provide updates, summaries, and leaderboard information.

## Features
- Fetches game data from ESPN and CBS.
- Posts daily summaries of game results and leaderboard standings to Slack.
- Sends direct messages for important notifications and reminders.
- Handles user authentication and configuration setup.

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/jessica-schofield/march-madness-bot.git
   ```
2. Navigate to the project directory:
   ```
   cd march-madness-bot
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration
Before running the bot, ensure that you have a configuration file set up. You can create a `config.json` file based on the provided template in the `bot_setup` directory.

## Usage
To start the bot, run the following command:
```
python src/main.py
```

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.