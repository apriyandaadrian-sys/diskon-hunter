"""
scrapers.py - Marketplace scrapers for Tokopedia, Shopee, Lazada, Bukalapak
Uses httpx for async requests + BeautifulSoup for parsing
"""

import asyncio
import random
import logging
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict

logger = logging.getLogger(__name__)

# ─── Rotating User Agents ─────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
    }


# ─── Price Parser ─────────────────────────────────────────────────────────────
def parse_price(price_str: str) -> int:
    """Convert price string like 'Rp 150.000' to integer 150000"""
    try:
        cleaned = "".join(c for c in price_str if c.isdigit())
        return int(cleaned) if cleaned else 0
    except Exception:
        return 0


# ─── Tokopedia Scraper ────────────────────────────────────────────────────────
async def scrape_tokopedia(query: str) -> List[Dict]:
    results = []
    url = f"https://www.tokopedia.com/search?st=product&q={query.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(
            headers=get_headers(),
            timeout=15,
            follow_redirects=True,
        ) as client:
            # Tokopedia needs the Apollo/GraphQL API for reliable results
            graphql_url = "https://gql.tokopedia.com/"
            payload = {
                "operationName": "SearchProductQueryV4",
                "variables": {
                    "params": f"q={query}&st=product&source=universe&page=1&rows=10"
                },
                "query": """
                query SearchProductQueryV4($params: String) {
                  ace_search_product_v4(params: $params) {
                    data {
                      products {
                        id name price imageUrl url
                        shop { name }
                        rating
                      }
                    }
                  }
                }
                """
            }

            headers = get_headers()
            headers.update({
                "Content-Type": "application/json",
                "X-Source": "tokopedia-lite",
                "X-Device": "desktop-0.0",
                "Origin": "https://www.tokopedia.com",
                "Referer": url,
            })

            resp = await client.post(graphql_url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                products = (
                    data.get("data", {})
                        .get("ace_search_product_v4", {})
                        .get("data", {})
                        .get("products", [])
                )
                for p in products[:10]:
                    price = parse_price(str(p.get("price", "0")))
                    if price > 0:
                        results.append({
                            "marketplace": "Tokopedia",
                            "name": p.get("name", ""),
                            "price": price,
                            "url": p.get("url", ""),
                            "store": p.get("shop", {}).get("name", ""),
                            "rating": str(p.get("rating", "N/A")),
                            "image": p.get("imageUrl", ""),
                        })

    except Exception as e:
        logger.warning(f"Tokopedia scrape failed: {e}")

    return results


# ─── Shopee Scraper ───────────────────────────────────────────────────────────
async def scrape_shopee(query: str) -> List[Dict]:
    results = []
    search_url = (
        f"https://shopee.co.id/api/v4/search/search_items"
        f"?by=relevancy&keyword={query.replace(' ', '%20')}"
        f"&limit=10&newest=0&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH"
        f"&version=2"
    )

    try:
        async with httpx.AsyncClient(
            headers={
                **get_headers(),
                "Referer": "https://shopee.co.id/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=15,
            follow_redirects=True,
        ) as client:
            resp = await client.get(search_url)

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])

                for item in items[:10]:
                    item_data = item.get("item_basic", {})
                    price_raw = item_data.get("price", 0)
                    # Shopee prices are in 100000ths of IDR
                    price = int(price_raw / 100000) if price_raw else 0

                    if price > 0:
                        shopid = item_data.get("shopid", "")
                        itemid = item_data.get("itemid", "")
                        name = item_data.get("name", "")
                        url = f"https://shopee.co.id/{name.replace(' ', '-')}-i.{shopid}.{itemid}"

                        results.append({
                            "marketplace": "Shopee",
                            "name": name,
                            "price": price,
                            "url": url,
                            "store": item_data.get("shop_name", ""),
                            "rating": str(round(item_data.get("item_rating", {}).get("rating_star", 0), 1)),
                            "image": f"https://cf.shopee.co.id/file/{item_data.get('image', '')}",
                        })

    except Exception as e:
        logger.warning(f"Shopee scrape failed: {e}")

    return results


# ─── Lazada Scraper ───────────────────────────────────────────────────────────
async def scrape_lazada(query: str) -> List[Dict]:
    results = []
    url = f"https://www.lazada.co.id/catalog/?q={query.replace(' ', '+')}&_keyori=ss&from=input&spm=a2o4l"

    try:
        async with httpx.AsyncClient(
            headers={**get_headers(), "Referer": "https://www.lazada.co.id/"},
            timeout=15,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Extract JSON data from script tag
                import re, json
                script_tags = soup.find_all("script")
                for script in script_tags:
                    if script.string and "window.__moduleData__" in script.string:
                        match = re.search(r'"listItems"\s*:\s*(\[.*?\])', script.string, re.DOTALL)
                        if match:
                            try:
                                items_json = match.group(1)
                                items = json.loads(items_json)
                                for item in items[:10]:
                                    price = parse_price(str(item.get("price", "0")))
                                    if price > 0:
                                        results.append({
                                            "marketplace": "Lazada",
                                            "name": item.get("name", ""),
                                            "price": price,
                                            "url": "https:" + item.get("productUrl", ""),
                                            "store": item.get("sellerName", ""),
                                            "rating": str(item.get("ratingScore", "N/A")),
                                            "image": item.get("image", ""),
                                        })
                            except Exception:
                                pass
                        break

    except Exception as e:
        logger.warning(f"Lazada scrape failed: {e}")

    return results


# ─── Bukalapak Scraper ────────────────────────────────────────────────────────
async def scrape_bukalapak(query: str) -> List[Dict]:
    results = []
    api_url = (
        f"https://api.bukalapak.com/multisearch/products"
        f"?keywords={query.replace(' ', '%20')}&limit=10&offset=0"
    )

    try:
        async with httpx.AsyncClient(
            headers={
                **get_headers(),
                "Referer": "https://www.bukalapak.com/",
                "Accept": "application/json",
            },
            timeout=15,
            follow_redirects=True,
        ) as client:
            resp = await client.get(api_url)

            if resp.status_code == 200:
                data = resp.json()
                products = data.get("data", [])

                for p in products[:10]:
                    price = parse_price(str(p.get("price", "0")))
                    if price > 0:
                        results.append({
                            "marketplace": "Bukalapak",
                            "name": p.get("name", ""),
                            "price": price,
                            "url": p.get("url", ""),
                            "store": p.get("store", {}).get("name", ""),
                            "rating": str(p.get("rating", {}).get("average_rate", "N/A")),
                            "image": p.get("images", {}).get("small_urls", [""])[0],
                        })

    except Exception as e:
        logger.warning(f"Bukalapak scrape failed: {e}")

    return results


# ─── Aggregate All ────────────────────────────────────────────────────────────
async def search_all_marketplaces(query: str) -> List[Dict]:
    """Run all scrapers in parallel and combine results"""
    tasks = [
        scrape_tokopedia(query),
        scrape_shopee(query),
        scrape_lazada(query),
        scrape_bukalapak(query),
    ]

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    combined = []
    for r in all_results:
        if isinstance(r, list):
            combined.extend(r)
        else:
            logger.warning(f"Scraper returned exception: {r}")

    # Filter out invalid prices
    combined = [p for p in combined if p.get("price", 0) > 0]

    logger.info(f"Found {len(combined)} results for '{query}'")
    return combined
