"""
scrapers.py - Enhanced marketplace scrapers with Anti-Bot Evasion
Requires: pip install curl_cffi bs4
"""

import asyncio
import random
import logging
import re
import json
from bs4 import BeautifulSoup
from typing import List, Dict

# Ganti httpx dengan curl_cffi untuk memalsukan TLS Fingerprint browser asli
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

# Gunakan Residential Proxy jika ada (SANGAT DIREKOMENDASIKAN)
# Contoh: "http://user:pass@pr.oxylabs.io:7777"
PROXY_URL = None 

# Impersonate target (Pilih versi browser terbaru yang didukung curl_cffi)
BROWSER_IMPERSONATE = "chrome120"

def get_headers(referer=""):
    """
    Header dasar. curl_cffi akan mengurus header spesifik browser (seperti sec-ch-ua)
    berdasarkan impersonate yang dipilih, jadi kita tidak perlu hardcode User-Agent.
    """
    return {
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or "https://www.google.com/",
        "DNT": "1",
    }

def get_proxy_dict():
    return {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

def parse_price(val) -> int:
    try:
        return int("".join(c for c in str(val) if c.isdigit()))
    except:
        return 0

async def human_delay():
    """Simulasi jeda manusia (jitter) antara 1 sampai 3 detik"""
    await asyncio.sleep(random.uniform(1.0, 3.0))


# ── TOKOPEDIA (GraphQL) ───────────────────────────────────────────────────────
async def scrape_tokopedia(query: str) -> List[Dict]:
    results = []
    try:
        await human_delay()
        
        # AsyncSession dengan impersonate akan memanipulasi TLS fingerprint
        async with AsyncSession(impersonate=BROWSER_IMPERSONATE, proxies=get_proxy_dict(), timeout=20) as client:
            headers = get_headers("https://www.tokopedia.com/")
            headers.update({
                "Content-Type": "application/json",
                "X-Source": "tokopedia-lite",
                "X-Device": "desktop-0.0",
                "Origin": "https://www.tokopedia.com",
                "X-Tkpd-Lite-Service": "zeus" # Header tambahan yang sering dicek
            })

            payload = [{
                "operationName": "SearchProductQueryV4",
                "variables": {
                    "params": f"q={query}&st=product&source=universe&page=1&rows=10&ob=23"
                },
                "query": """query SearchProductQueryV4($params: String) {
                    ace_search_product_v4(params: $params) {
                        data { products {
                            id name price imageUrl url
                            shop { name }
                            rating ratingAverage
                        }}
                    }
                }"""
            }]

            r = await client.post("https://gql.tokopedia.com/", json=payload, headers=headers)
            
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    data = data[0]
                products = (data.get("data", {})
                               .get("ace_search_product_v4", {})
                               .get("data", {})
                               .get("products", []))
                for p in products[:10]:
                    price = parse_price(p.get("price", 0))
                    if price > 0:
                        results.append({
                            "marketplace": "Tokopedia",
                            "name": p.get("name", ""),
                            "price": price,
                            "url": p.get("url", ""),
                            "store": p.get("shop", {}).get("name", ""),
                            "rating": str(p.get("ratingAverage", "N/A")),
                        })
    except Exception as e:
        logger.warning(f"Tokopedia error: {e}")
    return results


# ── SHOPEE ────────────────────────────────────────────────────────────────────
async def scrape_shopee(query: str) -> List[Dict]:
    results = []
    try:
        await human_delay()
        encoded = query.replace(" ", "%20")
        url = (
            f"https://shopee.co.id/api/v4/search/search_items"
            f"?by=relevancy&keyword={encoded}&limit=10&newest=0"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2"
        )
        
        async with AsyncSession(impersonate=BROWSER_IMPERSONATE, proxies=get_proxy_dict(), timeout=20) as client:
            # Shopee sangat ketat. Kita perlu mengunjungi halaman utama dulu untuk mendapatkan cookie awalan
            await client.get("https://shopee.co.id/", headers=get_headers())
            await human_delay()

            headers = get_headers("https://shopee.co.id/")
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Accept"] = "application/json"

            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                for item in data.get("items", [])[:10]:
                    ib = item.get("item_basic", {})
                    raw_price = ib.get("price", 0)
                    price = int(raw_price / 100000) if raw_price else 0
                    if price > 0:
                        shopid = ib.get("shopid", "")
                        itemid = ib.get("itemid", "")
                        name = ib.get("name", "")
                        slug = name.lower().replace(" ", "-")[:60]
                        results.append({
                            "marketplace": "Shopee",
                            "name": name,
                            "price": price,
                            "url": f"https://shopee.co.id/{slug}-i.{shopid}.{itemid}",
                            "store": ib.get("shop_name", ""),
                            "rating": str(round(ib.get("item_rating", {}).get("rating_star", 0), 1)),
                        })
    except Exception as e:
        logger.warning(f"Shopee error: {e}")
    return results


# ── BUKALAPAK ─────────────────────────────────────────────────────────────────
async def scrape_bukalapak(query: str) -> List[Dict]:
    results = []
    try:
        await human_delay()
        encoded = query.replace(" ", "%20")
        url = f"https://api.bukalapak.com/products?keywords={encoded}&limit=10&offset=0"
        
        async with AsyncSession(impersonate=BROWSER_IMPERSONATE, proxies=get_proxy_dict(), timeout=20) as client:
            headers = get_headers("https://www.bukalapak.com/")
            headers["Accept"] = "application/json, text/plain, */*"

            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                for p in data.get("data", [])[:10]:
                    price = parse_price(p.get("price", 0))
                    if price > 0:
                        results.append({
                            "marketplace": "Bukalapak",
                            "name": p.get("name", ""),
                            "price": price,
                            "url": p.get("url", ""),
                            "store": p.get("store", {}).get("name", ""),
                            "rating": str(p.get("rating", {}).get("average_rate", "N/A")),
                        })
    except Exception as e:
        logger.warning(f"Bukalapak error: {e}")
    return results


# ── LAZADA ────────────────────────────────────────────────────────────────────
async def scrape_lazada(query: str) -> List[Dict]:
    results = []
    try:
        await human_delay()
        encoded = query.replace(" ", "+")
        url = f"https://www.lazada.co.id/catalog/?q={encoded}&_keyori=ss&from=input"
        
        async with AsyncSession(impersonate=BROWSER_IMPERSONATE, proxies=get_proxy_dict(), timeout=20) as client:
            headers = get_headers("https://www.lazada.co.id/")
            
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for script in soup.find_all("script"):
                    if script.string and "window.pageData" in script.string:
                        match = re.search(r'"items"\s*:\s*(\[.*?\])\s*,\s*"[a-z]', script.string, re.DOTALL)
                        if match:
                            try:
                                items = json.loads(match.group(1))
                                for item in items[:10]:
                                    price = parse_price(item.get("price", "0"))
                                    if price > 0:
                                        results.append({
                                            "marketplace": "Lazada",
                                            "name": item.get("name", ""),
                                            "price": price,
                                            "url": "https:" + item.get("itemUrl", ""),
                                            "store": item.get("sellerName", ""),
                                            "rating": str(item.get("ratingScore", "N/A")),
                                        })
                            except:
                                pass
                        break
    except Exception as e:
        logger.warning(f"Lazada error: {e}")
    return results


# ── AGGREGATE ─────────────────────────────────────────────────────────────────
async def search_all_marketplaces(query: str) -> List[Dict]:
    tasks = [
        scrape_tokopedia(query),
        scrape_shopee(query),
        scrape_bukalapak(query),
        scrape_lazada(query),
    ]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    combined = []
    for r in all_results:
        if isinstance(r, list):
            combined.extend(r)
            
    combined = [p for p in combined if p.get("price", 0) > 0]
    logger.info(f"Total results for '{query}': {len(combined)}")
    return combined
async def scrape_tokopedia(query: str) -> List[Dict]:
    results = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            headers = get_headers("https://www.tokopedia.com/")
            headers["Content-Type"] = "application/json"
            headers["X-Source"] = "tokopedia-lite"
            headers["X-Device"] = "desktop-0.0"
            headers["Origin"] = "https://www.tokopedia.com"

            payload = [{
                "operationName": "SearchProductQueryV4",
                "variables": {
                    "params": f"q={query}&st=product&source=universe&page=1&rows=10&ob=23"
                },
                "query": """query SearchProductQueryV4($params: String) {
                    ace_search_product_v4(params: $params) {
                        data { products {
                            id name price imageUrl url
                            shop { name }
                            rating ratingAverage
                        }}
                    }
                }"""
            }]

            r = await client.post(
                "https://gql.tokopedia.com/",
                json=payload,
                headers=headers
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    data = data[0]
                products = (data.get("data", {})
                               .get("ace_search_product_v4", {})
                               .get("data", {})
                               .get("products", []))
                for p in products[:10]:
                    price = parse_price(p.get("price", 0))
                    if price > 0:
                        results.append({
                            "marketplace": "Tokopedia",
                            "name": p.get("name", ""),
                            "price": price,
                            "url": p.get("url", ""),
                            "store": p.get("shop", {}).get("name", ""),
                            "rating": str(p.get("ratingAverage", "N/A")),
                        })
    except Exception as e:
        logger.warning(f"Tokopedia error: {e}")
    return results


# ── SHOPEE ────────────────────────────────────────────────────────────────────
async def scrape_shopee(query: str) -> List[Dict]:
    results = []
    try:
        encoded = query.replace(" ", "%20")
        url = (
            f"https://shopee.co.id/api/v4/search/search_items"
            f"?by=relevancy&keyword={encoded}&limit=10&newest=0"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2"
        )
        headers = get_headers("https://shopee.co.id/")
        headers["X-Requested-With"] = "XMLHttpRequest"

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                for item in data.get("items", [])[:10]:
                    ib = item.get("item_basic", {})
                    raw_price = ib.get("price", 0)
                    price = int(raw_price / 100000) if raw_price else 0
                    if price > 0:
                        shopid = ib.get("shopid", "")
                        itemid = ib.get("itemid", "")
                        name = ib.get("name", "")
                        slug = name.lower().replace(" ", "-")[:60]
                        results.append({
                            "marketplace": "Shopee",
                            "name": name,
                            "price": price,
                            "url": f"https://shopee.co.id/{slug}-i.{shopid}.{itemid}",
                            "store": ib.get("shop_name", ""),
                            "rating": str(round(
                                ib.get("item_rating", {}).get("rating_star", 0), 1
                            )),
                        })
    except Exception as e:
        logger.warning(f"Shopee error: {e}")
    return results


# ── BUKALAPAK ─────────────────────────────────────────────────────────────────
async def scrape_bukalapak(query: str) -> List[Dict]:
    results = []
    try:
        encoded = query.replace(" ", "%20")
        url = f"https://api.bukalapak.com/products?keywords={encoded}&limit=10&offset=0"
        headers = get_headers("https://www.bukalapak.com/")
        headers["Accept"] = "application/json"

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                for p in data.get("data", [])[:10]:
                    price = parse_price(p.get("price", 0))
                    if price > 0:
                        results.append({
                            "marketplace": "Bukalapak",
                            "name": p.get("name", ""),
                            "price": price,
                            "url": p.get("url", ""),
                            "store": p.get("store", {}).get("name", ""),
                            "rating": str(p.get("rating", {}).get("average_rate", "N/A")),
                        })
    except Exception as e:
        logger.warning(f"Bukalapak error: {e}")
    return results


# ── LAZADA ────────────────────────────────────────────────────────────────────
async def scrape_lazada(query: str) -> List[Dict]:
    results = []
    try:
        import re, json
        from bs4 import BeautifulSoup
        encoded = query.replace(" ", "+")
        url = f"https://www.lazada.co.id/catalog/?q={encoded}&_keyori=ss&from=input"
        headers = get_headers("https://www.lazada.co.id/")

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for script in soup.find_all("script"):
                    if script.string and "window.pageData" in script.string:
                        match = re.search(r'"items"\s*:\s*(\[.*?\])\s*,\s*"[a-z]', script.string, re.DOTALL)
                        if match:
                            try:
                                items = json.loads(match.group(1))
                                for item in items[:10]:
                                    price = parse_price(item.get("price", "0"))
                                    if price > 0:
                                        results.append({
                                            "marketplace": "Lazada",
                                            "name": item.get("name", ""),
                                            "price": price,
                                            "url": "https:" + item.get("itemUrl", ""),
                                            "store": item.get("sellerName", ""),
                                            "rating": str(item.get("ratingScore", "N/A")),
                                        })
                            except:
                                pass
                        break
    except Exception as e:
        logger.warning(f"Lazada error: {e}")
    return results


# ── AGGREGATE ─────────────────────────────────────────────────────────────────
async def search_all_marketplaces(query: str) -> List[Dict]:
    tasks = [
        scrape_tokopedia(query),
        scrape_shopee(query),
        scrape_bukalapak(query),
        scrape_lazada(query),
    ]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    combined = []
    for r in all_results:
        if isinstance(r, list):
            combined.extend(r)
    combined = [p for p in combined if p.get("price", 0) > 0]
    logger.info(f"Total results for '{query}': {len(combined)}")
    return combined
