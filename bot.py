#!/usr/bin/env python3
"""PriceHunter Bot — Indonesian Marketplace Price Comparator (Aesthetic Edition ✨)"""

import asyncio
import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)
# Pastikan modul scrapers, cache, dan config sudah sesuai
from scrapers import scrape_tokopedia, scrape_shopee, scrape_bukalapak, search_all_marketplaces
from cache import get_cached_result, set_cached_result, delete_cached_result
from config import BOT_TOKEN

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Emoji yang lebih vibrant dan cerah
MP_EMOJI = {"Tokopedia": "💚", "Shopee": "🧡", "Lazada": "💙", "Bukalapak": "❤️"}
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━"

def fmt_price(p: int) -> str:
    return f"Rp {p:,}".replace(",", ".")

def short(s: str, n=50) -> str:
    return s[:n] + "…" if len(s) > n else s


# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Bestie"
    text = (
        f"✨💎 <b>PRICE HUNTER BOT</b> 💎✨\n"
        f"<i>Temukan harga termurah dalam sekejap!</i>\n"
        f"{DIVIDER}\n\n"
        f"Halo <b>{html.escape(name)}!</b> 👋\n\n"
        f"Aku siap bantu kamu berburu barang termurah dari:\n"
        f"💚 <b>Tokopedia</b>\n"
        f"🧡 <b>Shopee</b>\n"
        f"❤️ <b>Bukalapak</b>\n\n"
        f"💬 <b>Cara Pakai:</b>\n"
        f"Tinggal ketik barang yang mau kamu cari. Contoh:\n"
        f"▸ <code>iPhone 15 Pro Max</code>\n"
        f"▸ <code>Nike Air Force 1</code>\n"
        f"▸ <code>Skintific Mugwort</code>\n\n"
        f"🌟 <i>Yuk, ketik nama produknya sekarang!</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ── /help ──────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 <b>PANDUAN — Price Hunter Bot</b>\n"
        f"{DIVIDER}\n\n"
        f"🛠️ <b>Perintah Spesial:</b>\n"
        f"▸ /start — Mulai lembaran baru ✨\n"
        f"▸ /help  — Buka panduan ini 📖\n"
        f"▸ /debug — Cek status marketplace 🔧\n\n"
        f"💡 <b>Tips Pencarian Jitu:</b>\n"
        f"✅ <i>Lebih detail lebih baik!</i> (Merek + Tipe + Ukuran)\n"
        f"✅ Contoh: <code>Sepatu Nike Air 42</code>\n"
        f"✅ Contoh: <code>Vitamin C 1000mg 100 tablet</code>\n\n"
        f"⚡ <i>Psst... hasil pencarian disimpan dalam cache selama 20 menit agar secepat kilat!</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ── /debug ─────────────────────────────────────────────────────────────────────
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔧 <i>Menguji koneksi ke marketplace, tunggu sebentar ya...</i> ✨", parse_mode="HTML")
    test_query = "Samsung"

    results = {
        "Tokopedia": await scrape_tokopedia(test_query),
        "Shopee":    await scrape_shopee(test_query),
        "Bukalapak": await scrape_bukalapak(test_query),
    }

    text = f"⚙️ <b>HASIL DEBUG MARKETPLACE</b> ⚙️\n{DIVIDER}\n\n"
    for mp, data in results.items():
        emoji = MP_EMOJI.get(mp, "🛍️")
        if data:
            text += f"{emoji} <b>{mp}</b>: ✅ {len(data)} produk\n"
            text += f"   💸 <i>Contoh: {fmt_price(data[0]['price'])}</i>\n\n"
        else:
            text += f"{emoji} <b>{mp}</b>: ❌ <i>Oops, koneksi terputus!</i>\n\n"

    total = sum(len(v) for v in results.values())
    text += f"{DIVIDER}\n📊 <b>Total:</b> {total} produk berhasil ditarik."

    await msg.edit_text(text, parse_mode="HTML")


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
        f"💫 <b>Mencari harga terbaik untukmu...</b>\n\n"
        f"💚 <i>Mengecek Tokopedia...</i>\n"
        f"🧡 <i>Mengecek Shopee...</i>\n"
        f"❤️ <i>Mengecek Bukalapak...</i>\n\n"
        f"⏳ <i>Mohon tunggu sebentar ya!</i>",
        parse_mode="HTML"
    )

    try:
        results = await search_all_marketplaces(query)
        await loading.delete()

        if not results:
            await update.message.reply_text(
                f"🥀 <b>Waduh, tidak ditemukan...</b>\n\n"
                f"Produk <code>{html.escape(query)}</code> tidak ada di jangkauan radar kami.\n\n"
                f"💡 <b>Coba trik ini:</b>\n"
                f"▸ Gunakan kata kunci yang lebih singkat\n"
                f"▸ Sebutkan nama mereknya saja\n"
                f"▸ Ketik /debug untuk cek koneksi",
                parse_mode="HTML"
            )
            return

        set_cached_result(query, results)
        await send_results(update, results, query)

    except Exception as e:
        logger.error(f"Error: {e}")
        await loading.edit_text("💔 <i>Aduh, sistem sedang kewalahan. Coba lagi dalam beberapa saat ya!</i>", parse_mode="HTML")


# ── Send results ───────────────────────────────────────────────────────────────
async def send_results(update, results, query, from_cache=False):
    sorted_r = sorted(results, key=lambda x: x["price"])
    top = sorted_r[:8]
    best = top[0]
    
    cache_tag = " <i>(kilat ⚡)</i>" if from_cache else ""
    medals = ["🥇","🥈","🥉","🎀","🎀","🎀","🎀","🎀"]

    msg = (
        f"💎 <b>HASIL BERBURU HARGA</b> 💎\n"
        f"{DIVIDER}\n"
        f"🔍 <b>Produk:</b> {html.escape(query)}{cache_tag}\n"
        f"📦 <b>Total:</b> {len(results)} penawaran ditemukan\n\n"
        f"🏆 <b>TERMURAH:</b> {MP_EMOJI.get(best['marketplace'],'🛍️')} <b>{fmt_price(best['price'])}</b>\n"
        f"{DIVIDER}\n\n"
    )

    for i, p in enumerate(top):
        e = MP_EMOJI.get(p["marketplace"], "🛍️")
        m = medals[i]
        
        safe_name = html.escape(short(p['name']))
        safe_store = html.escape(p.get("store","")[:28])
        rating = p.get("rating","")
        rating_txt = f" ⭐ {rating}" if rating and rating not in ("N/A","0.0","0") else ""

        msg += f"{m} {e} <b>{fmt_price(p['price'])}</b>\n"
        msg += f"   📎 <a href='{p['url']}'>{safe_name}</a>\n"
        msg += f"   🏪 <i>{safe_store}</i>{rating_txt}\n\n"

    # Marketplace summary
    mp_counts = {}
    for r in results:
        mp_counts[r["marketplace"]] = mp_counts.get(r["marketplace"], 0) + 1
        
    msg += f"{DIVIDER}\n"
    for mp, cnt in mp_counts.items():
        msg += f"{MP_EMOJI.get(mp,'🛍️')} <b>{mp}:</b> {cnt} hasil\n"

    if len(msg) > 4000:
        msg = msg[:3990] + "\n<i>...dan masih banyak lagi!</i>"

    keyboard = [[
        InlineKeyboardButton("🔄 Segarkan Data", callback_data=f"refresh:{query}"),
        InlineKeyboardButton("📋 Tampilkan Semua", callback_data=f"all:{query}"),
    ]]

    await update.message.reply_text(
        msg,
        parse_mode="HTML",
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
        await q.message.reply_text(f"🔄 <i>Menyegarkan data untuk</i> <b>{html.escape(product)}</b>...", parse_mode="HTML")
        results = await search_all_marketplaces(product)
        if results:
            set_cached_result(product, results)
            await send_results(q, results, product)
        else:
            await q.message.reply_text("🥀 <i>Maaf, saat ini tidak ada hasil terbaru.</i>", parse_mode="HTML")

    elif action == "all":
        cached = get_cached_result(product)
        if not cached:
            await q.message.reply_text("⏰ <i>Sesi berakhir! Silakan ketik ulang nama produk ya.</i>", parse_mode="HTML")
            return
            
        sorted_r = sorted(cached, key=lambda x: x["price"])
        text = f"📋 <b>DAFTAR LENGKAP — {html.escape(product)}</b>\n{DIVIDER}\n\n"
        
        for i, p in enumerate(sorted_r[:20], 1):
            e = MP_EMOJI.get(p["marketplace"],"🛍️")
            safe_name = html.escape(short(p['name'], 45))
            text += f"<b>{i}.</b> {e} <b>{fmt_price(p['price'])}</b>\n"
            text += f"   📎 <a href='{p['url']}'>{safe_name}</a>\n\n"
            if len(text) > 3800:
                text += "✨ <i>...dan penawaran lainnya!</i>"
                break
                
        await q.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    
    logger.info("✨ PriceHunter Bot is shining bright and running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
    
