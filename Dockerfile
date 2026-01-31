FROM python:3.13-slim
WORKDIR /app

# runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
  zlib1g libjpeg62-turbo libwebp7 libtiff6 libopenjp2-7 \
  && rm -rf /var/lib/apt/lists/*

# build deps (temporary)
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential python3-dev \
  zlib1g-dev libjpeg62-turbo-dev libwebp-dev libtiff-dev libopenjp2-7-dev \
  && rm -rf /var/lib/apt/lists/*

COPY app/ /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# remove build deps
RUN apt-get purge -y --auto-remove \
  build-essential python3-dev \
  zlib1g-dev libjpeg62-turbo-dev libwebp-dev libtiff-dev libopenjp2-7-dev

CMD ["python", "bot.py"]