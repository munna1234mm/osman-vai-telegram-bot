# Telegram Task Bot (Web Service Version)

This is a Telegram bot built with `pyTelegramBotAPI` and `FastAPI` to run efficiently on **Render's Free Web Service Tier**.

## Features
- Custom main menu with buttons: One Task, Daily Task, Invite, Balance, FAQ.
- Basic placeholder responses for each button.
- `/admin` command boilerplate.
- **FastAPI Webhook Integration** for serverless-like execution.

## Deployment to Render (FREE TIER)

Since Render's "Background Worker" costs money, we have converted this bot to use a **Web Service** with Webhooks, which is completely free on Render.

### Steps to Deploy:
1. Push this code to a GitHub repository.
2. Go to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** and select **Web Service**.
4. Connect your GitHub repository.
5. Set the following configuration:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn bot:app --host 0.0.0.0 --port $PORT`
6. Click **Advanced** and add an Environment Variable:
   - Key: `BOT_TOKEN`
   - Value: `8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI` *(or your bot token)*
7. Click **Deploy Web Service**.

### ⚠️ IMPORTANT: Set the Webhook!
After Render finishes deploying, you will get a URL (like `https://your-app-name.onrender.com`).
You must tell Telegram to send messages to this URL. 

Open your browser and visit this link (replace with your Bot Token and Render URL):
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_RENDER_URL>/<YOUR_BOT_TOKEN>/
```

Example:
`https://api.telegram.org/bot8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI/setWebhook?url=https://my-telegram-bot.onrender.com/8243932163:AAFRMmbcIJqQgbQCrSpJIiHpKesHS5mH-LI/`

If it responds with `{"ok":true,"result":true,"description":"Webhook was set"}`, your bot is live!
