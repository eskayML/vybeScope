# VybeScope Telegram Bot

A Python-based Telegram bot for the Vybe hackathon challenge. This bot allows users to connect their crypto wallets, view transactions, manage settings, and receive whale alerts for large transactions through an intuitive interface.

## Features

- 💰 **Wallet Connection**: Connect Phantom, Solflare, or Backpack wallets
- 📊 **Transaction Management**: View and manage your crypto transactions
- 🐋 **Whale Alerts**: Get notified of large cryptocurrency transactions
- 🪙 **Balance Checking**: Check your cryptocurrency balances
- 📈 **Token Statistics**: Look up token prices and market data
- 🔍 **Wallet Tracking**: Monitor activity for any Solana address
- ⚙️ **User Settings**: Customize notifications, language, and privacy settings
- 🔄 **In-Memory Storage**: Lightweight implementation with no database dependencies

## Project Structure

```
vybescope/
├── main.py               # Main bot entry point
├── bot_handler.py        # Bot functionality handler
├── wallet.py             # Wallet connection and transaction handling
├── utils.py              # Utility functions
├── requirements.txt      # Python dependencies
├── .env-example          # Example environment variables
└── README.md             # Project documentation
```

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/your-username/vybescope.git
   cd vybescope
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following content:
   ```
   BOT_TOKEN=your_telegram_bot_token_here
   VYBE_API_KEY=your_vybe_api_key_here
   ```

4. Start the bot:
   ```
   python main.py
   ```

## Getting a Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Follow the instructions to create a new bot
4. Copy the token provided by BotFather and add it to your `.env` file

## Bot Commands


## User Interface

The bot features an intuitive button-based interface that allows users to:

- Connect their cryptocurrency wallets
- View and manage transactions
- Set custom thresholds for whale alerts
- Check token prices and statistics
- Monitor wallet activity
- Adjust settings and preferences
- Get help and support

## Whale Alert Feature

The whale alert feature monitors large cryptocurrency transactions on the Solana blockchain. Users can:

- Set custom thresholds to define what constitutes a "whale" transaction
- Receive alerts when transactions above their threshold occur
- View detailed information about each large transaction
- Track specific wallets for significant activity

## Implementation Details

This bot is designed to be lightweight and portable:

- Uses in-memory storage for user data, wallets, and transactions
- No database dependencies required
- Communicates with the Vybe API for blockchain data
- Simple to deploy and run

## Hackathon Submission

This project is a submission for the Vybe Telegram Bot Challenge. The goal is to create an intuitive and feature-rich Telegram bot that integrates with cryptocurrency wallets and provides a seamless user experience.

## License

MIT License 