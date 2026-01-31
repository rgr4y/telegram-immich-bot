FROM python:3.14-alpine

LABEL org.opencontainers.image.title="Telegram to Immich bot"
LABEL org.opencontainers.image.description="Telegram bot to upload files directly to your Immich instance"
LABEL org.opencontainers.image.authors="Mario Yanes <mario.yanes@uc3m.es> (@myanesp)"
LABEL org.opencontainers.image.url=https://github.com/myanesp/telegram-immich-bot/blob/main/README.md
LABEL org.opencontainers.image.documentation=https://github.com/myanesp/telegram-immich-bot
LABEL org.opencontainers.image.source="https://github.com/myanesp/telegram-immich-bot"
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"

WORKDIR /app

COPY app/ /app

RUN apk add --no-cache tiff-dev openjpeg-dev \
    && apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libjpeg-turbo-dev \
    zlib-dev \
    libffi-dev \
    openssl-dev \
    libwebp-dev \
    freetype-dev \
    lcms2-dev \
    harfbuzz-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

CMD ["python", "bot.py"]
