# VybeScope Telegram Bot

VybeScope is a feature-rich Python Telegram bot for Solana users, offering real-time wallet tracking, token stats, and whale alerts—all with zero database setup. Users can connect and monitor multiple wallets, view live balances and 24h changes, and receive instant notifications for large transactions (whale alerts) with customizable thresholds. The bot provides detailed token statistics, top holders, and market data for any Solana token, plus a personal dashboard to manage tracked wallets and alert settings. All data is stored in-memory or lightweight JSON, ensuring privacy and fast setup.

    The intuitive button-based interface makes it easy to add/remove wallets, set whale alert thresholds, and explore token analytics and even Token Research using LLMs.
 VybeScope is ideal for traders, investors, and enthusiasts who want actionable Solana insights directly in Telegram.

## Key Features
- 🔗 Connect and track multiple Solana wallets
- 🐋 Customizable whale alerts for large transactions
- 📊 Token stats, price, and top holders lookup
- 💼 Personal dashboard for wallet and alert management
- 🔔 Real-time notifications and analytics
- ⚡ No database required—lightweight and portable

## Quick Start
1. Clone the repo and install requirements:
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
   python bot.py
   ```

## Bot Commands


## User Interface

The bot features an intuitive button-based interface that allows users to:

- Connect their cryptocurrency wallets
- View and manage transactions
- Enable Whale Alerts.
- Set custom thresholds for whale alerts
- Check token prices and statistics
- View Highest Holders (Whale Wallets).
- Monitor wallet activity.
- Adjust settings and preferences
- Get help and support.

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