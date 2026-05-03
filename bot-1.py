#!/usr/bin/env python3
"""
PriceHunter Bot — Cari harga termurah di marketplace Indonesia
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)
from scrapers import search_all_marketplaces
from cache import get_cached_result, set_cached_result, delete_cached_result
from config import BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Emoji map ──────────────────────────────────────────────────────────────────
MP_EMOJI = {
    "Tokopedia": "🟢",
    "Shopee":    "🟠",
    "Lazada":    "🔵",
    "Bukalapak": "🔴",
}

def fmt_price(price: int) -> str:
    return f"Rp {price:,}".replace(",", ".")

def short_name(name: str, limit=55) -> str:
    return name[:limit] + "…" if len(name) > limit else name

def stars(rating) -> str:
    try:
        r = float(str(rating))
        filled = round(r)
        return "⭐" * filled + "☆" * (5 - filled) + f" {r:.1f}"
    except:
        return "☆☆☆☆☆"


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Kamu"
    text = (
        f"╔══════════════════════╗\n"
        f"║  🛒 *PRICE HUNTER BOT*  ║\n"
        f"╚══════════════════════╝\n\n"
        f"Halo, *{name}!* 👋\n\n"
        f"Aku akan carikan harga termurah\n"
        f"di semua marketplace Indonesia! 🇮🇩\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Tokopedia   🟠 Shopee\n"
        f"🔵 Lazada       🔴 Bukalapak\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 *Cara pakai:*\n"
        f"Ketik nama produk yang ingin\n"
        f"kamu cari, contoh:\n\n"
        f"   ▸ `iPhone 15 Pro Max`\n"
        f"   ▸ `Nike Air Force 1`\n"
        f"   ▸ `Laptop Asus Vivobook`\n\n"
        f"🔍 Ketik nama produk sekarang!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /help ──────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *BANTUAN — Price Hunter Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Perintah:*\n"
        "▸ /start — Mulai bot\n"
        "▸ /help  — Bantuan ini\n\n"
        "*Tips pencarian terbaik:*\n"
        "✅ Gunakan kata kunci spesifik\n"
        "✅ Sertakan merek & tipe produk\n"
        "✅ Tambahkan ukuran/warna/kapasitas\n\n"
        "*Contoh pencarian bagus:*\n"
        "▸ `Samsung Galaxy A55 8/256`\n"
        "▸ `Sepatu Adidas Stan Smith 42`\n"
        "▸ `Vitamin C 1000mg 100 tablet`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Hasil di-*cache* 20 menit\n"
        "untuk pencarian yang lebih cepat!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Search handler ─────────────────────────────────────────────────────────────
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query or query.startswith("/"):
        return

    # Cache hit
    cached = get_cached_result(query)
    if cached:
        await send_results(update, cached, query, from_cache=True)
        return

    # Loading message
    loading = await update.message.reply_text(
        f"🔍 *Mencari:* `{query}`\n\n"
        f"⏳ Sedang mengecek harga di:\n"
        f"🟢 Tokopedia \\.\\.\\.\n"
        f"🟠 Shopee \\.\\.\\.\n"
        f"🔵 Lazada \\.\\.\\.\n"
        f"🔴 Bukalapak \\.\\.\\.",
        parse_mode="MarkdownV2"
    )

    try:
        results = await search_all_marketplaces(query)
        await loading.delete()

        if not results:
            await update.message.reply_text(
                "╔══════════════════════╗\n"
                "║    😔 *Tidak Ditemukan*   ║\n"
                "╚══════════════════════╝\n\n"
                f"Produk *{query}* tidak ditemukan\n"
                "di marketplace manapun.\n\n"
                "💡 *Saran:*\n"
                "▸ Coba kata kunci lebih singkat\n"
                "▸ Cek ejaan nama produk\n"
                "▸ Gunakan nama merek saja",
                parse_mode="Markdown"
            )
            return

        set_cached_result(query, results)
        await send_results(update, results, query)

    except Exception as e:
        logger.error(f"Search error: {e}")
        await loading.edit_text(
            "❌ *Terjadi kesalahan*\n"
            "Silakan coba beberapa saat lagi.",
            parse_mode="Markdown"
        )


# ── Format & send results ──────────────────────────────────────────────────────
async def send_results(update, results, query, from_cache=False):
    sorted_r = sorted(results, key=lambda x: x["price"])
    top = sorted_r[:8]
    cheapest = top[0]

    # Count per marketplace
    mp_counts = {}
    for r in results:
        mp = r["marketplace"]
        mp_counts[mp] = mp_counts.get(mp, 0) + 1

    cache_tag = " _(cache)_" if from_cache else ""

    # Header
    header = (
        f"╔══════════════════════╗\n"
        f"║    💰 *HASIL PENCARIAN*    ║\n"
        f"╚══════════════════════╝\n\n"
        f"🔍 *{query}*{cache_tag}\n"
        f"📦 {len(results)} produk ditemukan\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *TERMURAH:* {MP_EMOJI.get(cheapest['marketplace'], '🛒')} "
        f"*{fmt_price(cheapest['price'])}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    body = ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    for i, p in enumerate(top):
        emoji = MP_EMOJI.get(p["marketplace"], "🛒")
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = short_name(p["name"])
        price = fmt_price(p["price"])
        store = p.get("store", "")[:25]
        rating = p.get("rating", "")

        body += f"{medal} {emoji} *{price}*\n"
        body += f"   [{name}]({p['url']})\n"
        if store:
            body += f"   🏪 {store}"
        if rating and rating != "N/A" and rating != "0.0":
            body += f"  ⭐ {rating}"
        body += "\n\n"

    # Footer marketplace summary
    footer = "━━━━━━━━━━━━━━━━━━━━━━\n"
    for mp, count in mp_counts.items():
        footer += f"{MP_EMOJI.get(mp, '🛒')} {mp}: {count} produk\n"

    full_msg = header + body + footer

    # Buttons
    keyboard = [[
        InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{query}"),
        InlineKeyboardButton("📋 Tampilkan Semua", callback_data=f"all:{query}"),
    ]]
    markup = InlineKeyboardMarkup(keyboard)

    # Telegram message limit = 4096 chars
    if len(full_msg) > 4000:
        full_msg = full_msg[:3990] + "\n…"

    await update.message.reply_text(
        full_msg,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=markup,
    )


# ── Inline button callbacks ────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, product = q.data.split(":", 1)

    if action == "refresh":
        delete_cached_result(product)
        await q.message.reply_text(
            f"🔄 *Memperbarui harga untuk:*\n`{product}`\n\n⏳ Mohon tunggu...",
            parse_mode="Markdown"
        )
        results = await search_all_marketplaces(product)
        if results:
            set_cached_result(product, results)
            await send_results(q, results, product)
        else:
            await q.message.reply_text("😔 Tidak ada hasil ditemukan.")

    elif action == "all":
        cached = get_cached_result(product)
        if not cached:
            await q.message.reply_text("⏰ Cache sudah expired. Cari ulang produknya ya!")
            return
        sorted_r = sorted(cached, key=lambda x: x["price"])
        text = (
            f"📋 *SEMUA HASIL — {product}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for i, p in enumerate(sorted_r[:20], 1):
            emoji = MP_EMOJI.get(p["marketplace"], "🛒")
            text += f"{i}\\. {emoji} *{fmt_price(p['price'])}*\n"
            text += f"   [{short_name(p['name'], 45)}]({p['url']})\n\n"
            if len(text) > 3800:
                text += "_\\.\\.\\. dan lainnya_"
                break
        await q.message.reply_text(
            text, parse_mode="Markdown", disable_web_page_preview=True
        )


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    logger.info("🚀 PriceHunter Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
