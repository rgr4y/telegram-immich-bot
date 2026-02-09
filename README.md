# Telegram to Immich Bot

[![GitHub](https://badgen.net/badge/icon/github?icon=github&label)](https://github.com/myanesp/telegram-immich-bot)
[![Docker](https://badgen.net/badge/icon/docker?icon=docker&label)](https://hub.docker.com/r/myanesp/telegram-immich-bot)
[![Docker Pulls](https://badgen.net/docker/pulls/myanesp/telegram-immich-bot?icon=docker&label=pulls)](https://hub.docker.com/r/myanesp/telegram-immich-bot)
[![Last Commit](https://img.shields.io/github/last-commit/myanesp/telegram-immich-bot)](https://github.com/myanesp/telegram-immich-bot)
[![License](https://badgen.net/github/license/myanesp/telegram-immich-bot)](LICENSE)
[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)

## Why?

This Docker container provides a simple way to automatically upload files from Telegram to your Immich photo management system. It's perfect for:

- Images and photos sent without compression that your relatives send you via Telegram
- Automatically backing up photos/videos sent to a Telegram bot
- Creating a simple upload pipeline for your personal media

## Features

- ✅ Automatic file uploads from Telegram to Immich
- ✅ Preserves original file metadata (for images sent as Documents)
- ✅ User restriction control (only allow specific Telegram user IDs)
- ✅ Simple configuration via environment variables

## How to Run

1. **Set up your Telegram bot**:
   - Create a new bot using [@BotFather](https://t.me/BotFather)
   - Note down your bot token
   - Start a chat with your new bot

2. **Configure your Immich instance**:
   - Ensure your Immich API is accessible from the host
   - Generate an API key from your Immich settings

3. **Run the container and send a file!**
This image is available both on [Docker Hub](https://hub.docker.com/r/myanesp/telegram-immich-bot) and [GitHub Container Registry](https://github.com/myanesp/telegram-immich-bot), so you're free to choose from which one you're going to download the image. Edit the following docker compose/docker run command to match your needs and you are ready to go! Remember to send the image(s) as File/Documents and not as Picture to preserve all metadata.

### Run with Docker Compose (Using .env file - Recommended)

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your configuration:
   ```bash
   nano .env  # or use your favorite editor
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

The `docker-compose.yml` file is already configured to use the `.env` file. If you want to enable support for files larger than 20MB, you'll need to:
- Get your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from https://my.telegram.org/apps
- Set `TELEGRAM_API_URL=http://telegram-bot-api:8081` in your `.env` file
- The `telegram-bot-api` service will automatically start and handle large files

### Run with Docker Compose (Inline Configuration)

```yaml
services:
  telegram-immich-bot:
    image: ghcr.io/myanesp/telegram-immich-bot:latest # or myanesp/telegram-immich-bot
    container_name: telegram-immich-bot
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=your_telegram_bot_token
      - IMMICH_API_URL=https://your-immich-instance.tld/api
      - IMMICH_API_KEY=your_immich_api_key
      - ALLOWED_USER_IDS=user1_id,user2_id
      - TZ=Europe/Madrid
```
### Run with Docker run

```yaml
docker run -d \
  --name telegram-immich-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_telegram_bot_token \
  -e IMMICH_API_URL=http://your-immich-instance/api \
  -e IMMICH_API_KEY=your_immich_api_key \
  -e ALLOWED_USER_IDS=user1_id,user2_id \ 
  ghcr.io/myanesp/telegram-immich-bot:latest # or myanesp/telegram-immich-bot
```

## Environment Variables

| VARIABLE | MANDATORY | DESCRIPTION | DEFAULT |
|----------|:---------:|-------------------------------------------------------------|---------|
| TELEGRAM_BOT_TOKEN | ✅ | Your Telegram bot token obtained from @BotFather | - |
| IMMICH_API_URL | ✅ | Full URL to your Immich API endpoint (can be local or public) (e.g., `http://your-immich-instance:2283/api`) | - |
| IMMICH_API_KEY | ✅ | API key for authenticating with your Immich instance | - |
| ALLOWED_USER_IDS | ✅ | Comma-separated list of Telegram user IDs allowed to use the bot (e.g., `123456789,987654321`) | - |
| TELEGRAM_API_ID | ❌ | Your Telegram API ID from https://my.telegram.org/apps (required for files >20MB) | - |
| TELEGRAM_API_HASH | ❌ | Your Telegram API Hash from https://my.telegram.org/apps (required for files >20MB) | - |
| TELEGRAM_API_URL | ❌ | URL to local Telegram Bot API server (e.g., `http://telegram-bot-api:8081`) | - |
| LOG_LEVEL | ❌ | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| BOT_NAME | ❌ | Custom name for your bot | Telegram to Immich Bot |

## Handling Large Files (>20MB)

By default, Telegram's Bot API has a 20MB file size limit. To handle larger files (up to 2GB), you need to use a local Telegram Bot API server:

1. Get your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from https://my.telegram.org/apps
2. Add them to your `.env` file
3. Set `TELEGRAM_API_URL=http://telegram-bot-api:8081` in your `.env` file
4. The included `docker-compose.yml` already includes the `telegram-bot-api` service
5. Start your services with `docker-compose up -d`

The bot will automatically detect the local API server and increase the file size limit to 2GB.

## Planned features

- [ ] Upload videos
- [ ] Multiarch support
- [ ] Multilingual support
- [ ] Reduce Docker image size
