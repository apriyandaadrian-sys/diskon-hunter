#!/usr/bin/env python3
"""
PriceHunter Bot - Indonesian Marketplace Price Comparator
Main bot entry point
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from scrapers import search_all_marketplaces
from cache import get_cached_result, set_cached_result
from config import BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Selamat datang di PriceHunter Bot!*\n\n"
        "🔍 Aku bisa mencari harga termurah di:\n"
        "  • Tokopedia\n"
        "  • Shopee\n"
        "  • Lazada\n"
        "  • Bukalapak\n\n"
        "💡 *Cara pakai:*\n"
        "Ketik nama produk yang ingin kamu cari.\n\n"
        "Contoh: `iPhone 15`, `Nike Air Force`, `Sepatu Adidas`\n\n"
        "Ketik /help untuk bantuan lebih lanjut."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /help ────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Panduan PriceHunter Bot*\n\n"
        "*Perintah tersedia:*\n"
        "/start - Mulai bot\n"
        "/help  - Tampilkan bantuan ini\n\n"
        "*Cara mencari harga:*\n"
        "Cukup ketik nama produk, bot akan otomatis mencari di semua marketplace.\n\n"
        "*Tips pencarian terbaik:*\n"
        "✅ Gunakan kata kunci spesifik\n"
        "✅ Sertakan merek jika tahu\n"
        "✅ Tambahkan ukuran/warna jika perlu\n\n"
        "❓ Jika ada pertanyaan, hubungi @admin"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── Handle product search ────────────────────────────────────────────────────
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return

    # Check cache first
    cached = get_cached_result(query)
    if cached:
        await send_results(update, cached, query, from_cache=True)
        return

    # Show searching message
    searching_msg = await update.message.reply_text(
        f"🔍 Mencari *{query}* di semua marketplace...\n"
        "⏳ Mohon tunggu sebentar...",
        parse_mode="Markdown"
    )

    try:
        results = await search_all_marketplaces(query)

        if not results:
            await searching_msg.edit_text(
                "😔 Maaf, produk tidak ditemukan di marketplace manapun.\n"
                "Coba gunakan kata kunci yang berbeda."
            )
            return

        # Cache results
        set_cached_result(query, results)

        # Delete searching message and send results
        await searching_msg.delete()
        await send_results(update, results, query)

    except Exception as e:
        logger.error(f"Search error: {e}")
        await searching_msg.edit_text(
            "❌ Terjadi kesalahan saat mencari. Silakan coba lagi."
        )


# ─── Format and send results ──────────────────────────────────────────────────
async def send_results(update, results, query, from_cache=False):
    sorted_results = sorted(results, key=lambda x: x["price"])
    top = sorted_results[:8]

    cache_note = " _(dari cache)_" if from_cache else ""
    header = f"💰 *Hasil pencarian: {query}*{cache_note}\n"
    header += f"📊 Ditemukan *{len(results)}* produk, menampilkan 8 termurah:\n\n"

    marketplace_emoji = {
        "Tokopedia": "🟢",
        "Shopee":    "🟠",
        "Lazada":    "🔵",
        "Bukalapak": "🔴",
    }

    message = header
    for i, p in enumerate(top, 1):
        emoji = marketplace_emoji.get(p["marketplace"], "🛒")
        price_str = f"Rp {p['price']:,}".replace(",", ".")
        name_short = p["name"][:50] + "..." if len(p["name"]) > 50 else p["name"]

        message += f"*{i}.* {emoji} `{price_str}`\n"
        message += f"   [{name_short}]({p['url']})\n"
        message += f"   🏪 {p['store']} | ⭐ {p.get('rating', 'N/A')}\n\n"

    message += "─────────────────\n"
    message += f"🏆 *Termurah:* {marketplace_emoji.get(top[0]['marketplace'], '🛒')} {top[0]['marketplace']}\n"
    message += f"💵 Harga: Rp {top[0]['price']:,}".replace(",", ".")

    # Add buttons
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{query}"),
            InlineKeyboardButton("📋 Semua Hasil", callback_data=f"all:{query}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )


# ─── Callback for inline buttons ──────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, product = query.data.split(":", 1)

    if action == "refresh":
        await query.message.reply_text(
            f"🔄 Memperbarui hasil untuk *{product}*...",
            parse_mode="Markdown"
        )
        # Clear cache and re-search
        from cache import delete_cached_result
        delete_cached_result(product)
        results = await search_all_marketplaces(product)
        if results:
            set_cached_result(product, results)
            await send_results(query, results, product)

    elif action == "all":
        cached = get_cached_result(product)
        if cached:
            sorted_r = sorted(cached, key=lambda x: x["price"])
            text = f"📋 *Semua hasil untuk: {product}*\n\n"
            for i, p in enumerate(sorted_r[:20], 1):
                price_str = f"Rp {p['price']:,}".replace(",", ".")
                text += f"{i}. [{p['name'][:40]}]({p['url']}) - `{price_str}`\n"
            await query.message.reply_text(
                text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    logger.info("🚀 PriceHunter Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
