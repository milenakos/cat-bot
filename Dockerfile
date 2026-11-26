FROM python:3.15-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runtime state lives in the /data volume. cursor.txt keeps the top.gg vote replay position,
# so a redeploy does not credit old votes twice.
RUN mkdir -p /data \
    && ln -sf /data/cursor.txt cursor.txt \
    && ln -sf /data/emojis_cache.json config/emojis_cache.json

# The bot serves its web routes on port 8069. Tokens and DB settings come from the environment.
CMD ["python", "bot.py"]
