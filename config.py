"""
config.py - Bot configuration
Edit this file with your actual credentials.
"""

import os

# ─── REQUIRED ─────────────────────────────────────────────────────────────────
# Get your token from @BotFather on Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ─── OPTIONAL SETTINGS ────────────────────────────────────────────────────────
# Max results to show per marketplace
MAX_RESULTS_PER_MARKETPLACE = 10

# Max results shown to user
MAX_DISPLAY_RESULTS = 8

# Cache TTL in seconds
CACHE_TTL_SECONDS = 60 * 20  # 20 minutes

# Request timeout in seconds
REQUEST_TIMEOUT = 15

# Allowed Telegram user IDs (leave empty to allow everyone)
# Example: ALLOWED_USERS = [123456789, 987654321]
ALLOWED_USERS = []

# Bot admin user IDs
ADMIN_USERS = []

# ─── PROXY SETTINGS (Optional) ────────────────────────────────────────────────
# Use proxies to avoid rate limiting (recommended for production)
# Format: "http://user:pass@host:port"
PROXY_LIST = [
    # "http://proxy1:port",
    # "http://proxy2:port",
]
USE_PROXY = False
