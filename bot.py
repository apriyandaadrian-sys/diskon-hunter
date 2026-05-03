#!/usr/bin/env python3
"""PriceHunter Bot — Indonesian Marketplace Price Comparator"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)
from scrapers import scrape_tokopedia, scrape_shopee, scrape_bukalapak, search_all_marketplaces
from cache import get_cached_result, set_cached_result, delete_cached_result
from config import BOT_TOKEN

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

MP_EMOJI = {"Tokopedia": "🟢", "Shopee": "🟠", "Lazada": "🔵", "Bukalapak": "🔴"}

def fmt_price(p: int) -> str:
    return f"Rp {p:,}".replace(",", ".")

def short(s: str, n=52) -> str:
    return s[:n] + "…" if len(s) > n else s


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Kamu"
    await update.message.reply_text(
        f"╔═══════════════════════╗\n"
        f"║  🛒 *PRICE HUNTER BOT*   ║\n"
        f"╚═══════════════════════╝\n\n"
        f"Halo *{name}!* 👋\n\n"
        f"Aku carikan harga termurah di:\n\n"
        f"🟢 *Tokopedia*\n"
        f"🟠 *Shopee*\n"
        f"🔴 *Bukalapak*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Ketik nama produk, contoh:\n\n"
        f"  ▸ `iPhone 15 Pro Max`\n"
        f"  ▸ `Nike Air Force 1`\n"
        f"  ▸ `Samsung Galaxy A55`\n\n"
        f"🔍 *Ketik nama produk sekarang\\!*",
        parse_mode="Markdown"
    )


# ── /help ──────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *BANTUAN — Price Hunter Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Perintah:*\n"
        "▸ /start — Mulai bot\n"
        "▸ /help  — Panduan ini\n"
        "▸ /debug — Cek koneksi marketplace\n\n"
        "*Tips pencarian:*\n"
        "✅ Spesifik: merek + tipe + ukuran\n"
        "✅ Contoh: `Sepatu Nike Air 42`\n"
        "✅ Contoh: `Vitamin C 1000mg 100tablet`\n\n"
        "💡 Hasil di\\-cache 20 menit",
        parse_mode="Markdown"
    )


# ── /debug ─────────────────────────────────────────────────────────────────────
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔧 *Menguji koneksi ke marketplace...*", parse_mode="Markdown")
    test_query = "Samsung"

    results = {
        "Tokopedia": await scrape_tokopedia(test_query),
        "Shopee":    await scrape_shopee(test_query),
        "Bukalapak": await scrape_bukalapak(test_query),
    }

    text = "🔧 *HASIL DEBUG*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for mp, data in results.items():
        emoji = MP_EMOJI.get(mp, "🛒")
        if data:
            text += f"{emoji} *{mp}*: ✅ {len(data)} produk ditemukan\n"
            text += f"   Contoh: {fmt_price(data[0]['price'])}\n\n"
        else:
            text += f"{emoji} *{mp}*: ❌ Tidak dapat diakses\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━━\n"
    total = sum(len(v) for v in results.values())
    text += f"📊 Total: *{total} produk* dari test query `{test_query}`"

    await msg.edit_text(text, parse_mode="Markdown")


# ── Search ─────────────────────────────────────────────────────────────────────
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query or query.startswith("/"):
        return

    cached = get_cached_result(query)
    if cached:
        await send_results(update, cached, query, from_cache=True)
        return

    loading = await update.message.reply_text(
        f"🔍 Mencari *{query}*\n\n"
        f"🟢 Tokopedia...\n"
        f"🟠 Shopee...\n"
        f"🔴 Bukalapak...",
        parse_mode="Markdown"
    )

    try:
        results = await search_all_marketplaces(query)
        await loading.delete()

        if not results:
            await update.message.reply_text(
                f"😔 *Tidak ditemukan*\n\n"
                f"Produk `{query}` tidak ada di marketplace.\n\n"
                f"💡 Coba:\n"
                f"▸ Kata kunci lebih singkat\n"
                f"▸ Nama merek saja\n"
                f"▸ Ketik /debug untuk cek koneksi",
                parse_mode="Markdown"
            )
            return

        set_cached_result(query, results)
        await send_results(update, results, query)

    except Exception as e:
        logger.error(f"Error: {e}")
        await loading.edit_text("❌ Terjadi kesalahan. Coba lagi.")


# ── Send results ───────────────────────────────────────────────────────────────
async def send_results(update, results, query, from_cache=False):
    sorted_r = sorted(results, key=lambda x: x["price"])
    top = sorted_r[:8]
    best = top[0]
    cache_tag = " _(cache)_" if from_cache else ""
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣"]

    msg = (
        f"╔═══════════════════════╗\n"
        f"║    💰 *HASIL PENCARIAN*     ║\n"
        f"╚═══════════════════════╝\n\n"
        f"🔍 *{query}*{cache_tag}\n"
        f"📦 *{len(results)}* produk ditemukan\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 TERMURAH: {MP_EMOJI.get(best['marketplace'],'🛒')} *{fmt_price(best['price'])}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, p in enumerate(top):
        e = MP_EMOJI.get(p["marketplace"], "🛒")
        m = medals[i]
        store = p.get("store","")[:28]
        rating = p.get("rating","")
        rating_txt = f"  ⭐{rating}" if rating and rating not in ("N/A","0.0","0") else ""

        msg += f"{m} {e} *{fmt_price(p['price'])}*\n"
        msg += f"   [{short(p['name'])}]({p['url']})\n"
        msg += f"   🏪 {store}{rating_txt}\n\n"

    # marketplace summary
    mp_counts = {}
    for r in results:
        mp_counts[r["marketplace"]] = mp_counts.get(r["marketplace"], 0) + 1
    msg += "━━━━━━━━━━━━━━━━━━━━━━━\n"
    for mp, cnt in mp_counts.items():
        msg += f"{MP_EMOJI.get(mp,'🛒')} {mp}: {cnt} produk\n"

    if len(msg) > 4000:
        msg = msg[:3990] + "\n_...dst_"

    keyboard = [[
        InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{query}"),
        InlineKeyboardButton("📋 Semua", callback_data=f"all:{query}"),
    ]]

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── Callbacks ──────────────────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action, product = q.data.split(":", 1)

    if action == "refresh":
        delete_cached_result(product)
        await q.message.reply_text(f"🔄 Memperbarui `{product}`...", parse_mode="Markdown")
        results = await search_all_marketplaces(product)
        if results:
            set_cached_result(product, results)
            await send_results(q, results, product)
        else:
            await q.message.reply_text("😔 Tidak ada hasil.")

    elif action == "all":
        cached = get_cached_result(product)
        if not cached:
            await q.message.reply_text("⏰ Cache expired. Cari ulang ya!")
            return
        sorted_r = sorted(cached, key=lambda x: x["price"])
        text = f"📋 *SEMUA HASIL — {product}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, p in enumerate(sorted_r[:20], 1):
            e = MP_EMOJI.get(p["marketplace"],"🛒")
            text += f"{i}\\. {e} *{fmt_price(p['price'])}*\n"
            text += f"   [{short(p['name'],45)}]({p['url']})\n\n"
            if len(text) > 3800:
                text += "_\\.\\.\\. dan lainnya_"
                break
        await q.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    logger.info("🚀 PriceHunter Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
