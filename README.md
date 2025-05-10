# VybeScope Telegram Bot

### Visit here: [t.me/vybescope_bot](https://t.me/vybescope_bot)

>  Note: The Bot Code is deployed on DigitalOcean.

VybeScope is a feature-rich Python Telegram bot for Solana users, offering real-time wallet tracking, token stats, and whale alerts. Users can connect and monitor multiple wallets, view live balances and 24h changes, and receive instant notifications for large transactions (whale alerts) with customizable thresholds. The bot provides detailed token statistics, top holders, and market data for any Solana token, plus a personal dashboard to manage tracked wallets and alert settings. All data is stored in-memory or lightweight JSON, ensuring privacy and fast setup.

The intuitive button-based interface makes it easy to add/remove wallets, set whale alert thresholds, and explore token analytics and even Deep Research on Tokens & Protocols using an LLM.

VybeScope is ideal for traders, investors, and enthusiasts who want actionable Solana insights directly in Telegram.


## User Interface

<table style="border-collapse: collapse; border: none; text-align: center; width: 100%;">
   <tr style="border: none; font-weight: bold;">
      <td style="border: none;">Token Information</td>
      <td style="border: none;">Wallet Tracking</td>
      <td style="border: none;">Whale Alerts</td>
      <!-- <td style="border: none;">Research Mini App</td> -->
   </tr>
   <tr style="border: none;">
      <td style="border: none;"><img src="https://gcdnb.pbrd.co/images/BfKwMnzydfSI.gif" alt="Token Information Example" width="250"/></td>
      <td style="border: none;"><img src="https://gcdnb.pbrd.co/images/ThS1Oc8EBjFG.gif" alt="Wallet Tracking Example" width="250"/></td>
      <td style="border: none;"><img src="https://gcdnb.pbrd.co/images/Ex0lkuqCEHz3.gif" alt="Whale Alerts Sample" width="250"/></td>
      <!-- <td style="border: none;"><img src="https://gcdnb.pbrd.co/images/OVFVpoaVefRb.gif?o=1" alt="Research Mini App" width="250"/></td> -->
   </tr>
</table>


## Key Features
- 🔗 Connect and track multiple Solana wallets
- 🐋 Customizable whale alerts for large transactions
- 📊 Token stats, price, and top holders lookup
- 💼 Personal dashboard for wallet and alert management
- 🔔 Real-time notifications for whale alerts and Tracked Wallet Transactions
- 🤖 Research Agent Telegram Mini App (For advanced AI analytics and research.) 

# Notification System
I have also tested and validated the scheduled notification system for both whale alerts and wallet tracking.


## Alert & Notification System

VybeScope offers a comprehensive notification system to keep you updated on wallet activities and significant market movements:

<table style="border-collapse: collapse; border: none; text-align: center; width: 100%;">
   <tr style="border: none; font-weight: bold;">
      <td style="border: none;">Feature</td>
      <td style="border: none;">Description</td>
      <td style="border: none;">Demo</td>
   </tr>
   <tr style="border: none;">
      <td style="border: none;">Wallet Transfer Alerts</td>
      <td style="border: none;">Receive instant notifications whenever your tracked wallets send or receive funds. The system monitors transactions in real-time and delivers detailed alerts showing transaction amount, token type, and wallet addresses involved. Customize tracking for multiple wallets simultaneously.</td>
      <td style="border: none;"><img src="https://i.postimg.cc/HkQ8V3BY/wallet-tracking-demo.jpg" alt="Wallet Alert Example" width="250"/></td>
   </tr>
   <tr style="border: none;">
      <td style="border: none;">Whale Transaction Alerts</td>
      <td style="border: none;">Stay ahead of the market with customizable whale alerts. Set your own thresholds for transaction sizes to monitor large trades that could impact token prices. Each alert provides detailed information including transaction value, percentage of total supply moved, and links to explore the transaction further.</td>
      <td style="border: none;"><img src="https://i.postimg.cc/0NPMmmBp/whale-alert-demo.jpg" alt="Whale Alert Example" width="250"/></td>
   </tr>
</table>

Both notification types operate on configurable intervals (default: 2 minutes), which you can adjust in the environment settings for your specific monitoring needs.

## Quick Start
1. Clone the repo and install requirements:
   ```
   git clone https://github.com/eskayML/vybeScope
   cd vybescope
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following required variables:
   ```
   BOT_TOKEN=your_telegram_bot_token_here
   VYBE_API_KEY=your_vybe_api_key_here
   ```

   Some optional env parameters you could also include are

   ```
   WHALE_ALERT_INTERVAL_SECONDS = 120 
   # not adding this env variable leaves the default value in the code at 120 (2 minutes)

   WALLET_TRACKING_INTERVAL_SECONDS = 120
   # likewise not adding this env variable leaves the default value as 120 (2 minutes)
   ```

4. Start the bot:
   ```
   python bot.py
   ```



## Notable Details

This bot is designed to be lightweight and portable:

- Uses in-memory storage for user data, wallets, and transactions
- Communicates with the Vybe API for blockchain data
- Simple to deploy and run

### Bonus
I added available quick commands to augment the already rich User Interface for quick and easy access to different features


## Hackathon Submission

This project is a submission for the Vybe Telegram Bot Challenge. The goal is to create an intuitive and feature-rich Telegram bot that integrates with cryptocurrency wallets/tokens and provides a seamless user experience.

## License

MIT License