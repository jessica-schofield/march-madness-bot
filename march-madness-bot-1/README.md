# March Madness Bot

## Overview
The March Madness Bot is designed to assist users in managing their March Madness bracket pools. It integrates with popular sports data sources and Slack to provide real-time updates, leaderboards, and notifications.

## Features
- **Configuration via Slack or Command Line**: Users can set up the bot using either Slack direct messages or a command-line interface.
- **Real-time Game Updates**: The bot sends notifications when games go final, keeping users informed of the latest results.
- **Daily Summaries**: Users receive a summary of the previous day's games and leaderboard standings.
- **Customizable Settings**: Users can configure various settings, including the number of top players to display and whether to post updates on weekends.

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/jessica-schofield/march-madness-bot.git
   ```
2. Navigate to the project directory:
   ```
   cd march-madness-bot
   ```
3. Install the required dependencies. Ensure you have Python 3 installed, then run:
   ```
   pip install -r requirements.txt
   ```

## Usage
To start the bot, run the following command:
```
python main.py
```
You will be prompted to configure the bot via Slack or command line.

## Configuration
The bot requires configuration settings to function properly. You can set these up during the initial run. The configuration includes:
- Slack credentials
- Bracket pool URLs
- Notification preferences

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.