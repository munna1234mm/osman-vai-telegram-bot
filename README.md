# Telegram Task Bot

This is a simple Telegram bot built with Python and `pyTelegramBotAPI`.

## Features
- Custom main menu with buttons: One Task, Daily Task, Invite, Balance, FAQ.
- Basic placeholder responses for each button.
- `/admin` command boilerplate.

## Local Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the bot (make sure to set your `BOT_TOKEN` environment variable if you change the default one):
   ```bash
   python bot.py
   ```

## Deploying to Render.com
Since this bot uses `infinity_polling()`, it should ideally be deployed as a **Background Worker**. If you deploy it as a Web Service, Render expects it to bind to a port, and the deployment might fail or keep restarting if it doesn't.

### Steps to Deploy:
1. Push this code to a GitHub repository.
2. Go to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** and select **Background Worker**.
4. Connect your GitHub repository.
5. Set the following configuration:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
6. Click **Advanced** and add an Environment Variable:
   - Key: `BOT_TOKEN`
   - Value: `8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI` *(or your new token from BotFather)*
7. Click **Create Background Worker**.

The bot will start building and deploying. Once it's running, it will automatically connect to Telegram.
