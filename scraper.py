import feedparser
import json
import time
import os
import asyncio
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import requests
from bs4 import BeautifulSoup

try:
    from twscrape import API as TwscrapeAPI, gather as twgather
    TWSCRAPE_AVAILABLE = True
except ImportError:
    TWSCRAPE_AVAILABLE = False

# =========================
# CONFIG
# =========================
OUTPUT_FILE = "market_news.json"
seen_news = set()

# =========================
# TWITTER CREDENTIALS (set as environment variables)
# TW_USERNAME, TW_PASSWORD, TW_EMAIL, TW_EMAIL_PASSWORD
# =========================
TW_USERNAME      = os.getenv("TW_USERNAME", "")
TW_PASSWORD      = os.getenv("TW_PASSWORD", "")
TW_EMAIL         = os.getenv("TW_EMAIL", "")
TW_EMAIL_PASSWORD= os.getenv("TW_EMAIL_PASSWORD", "")
TW_DB_PATH       = os.getenv("TW_DB_PATH", "twscrape_accounts.db")

# =========================
# TWITTER OFFICIAL ACCOUNTS TO MONITOR
# =========================
TWITTER_ACCOUNTS_HIGH_PRIORITY = [
    # Indian Regulators & Exchanges
    "RBI", "SEBI_updates", "NSEIndia", "BSEIndia",
    "nsitharaman", "FinMinIndia", "DasShaktikanta",
    "PMOIndia", "narendramodi", "NITI_Aayog",
    # US Market Movers
    "federalreserve", "USTreasury", "realDonaldTrump",
    "SecScottBessent", "POTUS", "SEC_News",
    # Indian Market Experts
    "Nithin0dha", "NithinKamath", "RadhikaGupta29",
    "deepakshenoy", "Ajay_Bagga", "TamalBandyo",
]

TWITTER_ACCOUNTS_MEDIUM_PRIORITY = [
    "nsitharamanoffc", "MEAIndia", "PiyushGoyal", "nitin_gadkari",
    "AmitShah", "MIB_India", "pib_india", "GST_Council",
    "NPCI_NPCI", "UIDAI", "IncomeTaxIndia", "CBIC_India",
    "MinOfPower", "MundaArjun", "HardeepSPuri", "AshwiniVaishnaw",
    "investindia", "SIDBIofficial", "OfficialNAM",
    "ChairmanSBI", "TheOfficialSBI", "LICIndiaForever",
    "IRDAI_India", "PFRDAOfficial", "IDBI_Bank",
    "anandmahindra", "udaykotak", "Iamsamirarora",
    "RNTata2000", "HarshGoenka", "NandanNilekani",
    "kiranshaw", "DeepinderGoyal", "kunalb11", "kunalbshah",
    "vijayshekhar", "AnupamMittal", "FalguniNayar",
    "GhazalAlagh", "vineetasng", "Nikhil0dha",
    "Mitesh_Engr", "dmuthuk", "Arunstockguru",
    "indiacharts", "nakulvibhor", "MashraniVivek",
    "whitehouse", "CMEGroup", "Nasdaq", "NYSE",
    "elonmusk", "GoldmanSachs", "MorganStanley", "BlackRock",
    "EconAtState", "CommerceGov", "BEA_News",
    "stlouisfed", "NewYorkFed", "StateDept",
    # Russia
    "KremlinRussia_E", "mfa_russia_en", "tass_agency",
    "CentralBankRF", "RF_EnergyMin", "RusEmbIndia",
    "ru_minfin", "MedvedevRussiaE", "AmbRus_India",
    "mod_russia", "GovernmentRF", "RusEmbUSA",
    "KremlinRussia", "mfa_russia", "Russia",
    "sundarpichai", "riteshagar",
]

ALL_TWITTER_ACCOUNTS = TWITTER_ACCOUNTS_HIGH_PRIORITY + TWITTER_ACCOUNTS_MEDIUM_PRIORITY

# =========================
# GOOGLE NEWS RSS FALLBACK QUERIES FOR TWITTER TOPICS
# =========================
TWITTER_FALLBACK_RSS = [
    "https://news.google.com/rss/search?q=RBI+policy+repo+rate&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=SEBI+NSE+BSE+India+announcement&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Nifty+Sensex+market+India+today&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Finance+Minister+India+economy&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Federal+Reserve+rate+decision&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Trump+tariff+trade+India&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=India+GDP+inflation+budget&hl=en-IN&gl=IN&ceid=IN:en",
]

RSS_FEEDS = {
    "Moneycontrol": "https://www.moneycontrol.com/stocksmarketsindia/",
    "EconomicTimes": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Reuters": "https://www.reuters.com/markets/",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "AlJazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "NYTimes": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "Reddit": "https://www.reddit.com/r/stocks/.rss"
}

analyzer = SentimentIntensityAnalyzer()

# =========================
# ADVANCED KEYWORDS
# =========================
BULLISH_KEYWORDS = {
    "bullish", "bull", "rally", "surge", "moon", "rocket",
    "breakout", "strong", "buy", "accumulate",
    "long", "golden cross"
}

BEARISH_KEYWORDS = {
    "bearish", "bear", "crash", "dump", "plunge",
    "sell-off", "downtrend", "weak", "sell",
    "short", "death cross"
}

FINANCIAL_KEYWORDS = {
    "support", "resistance", "breakout", "breakdown",
    "nifty", "banknifty", "sensex", "bse", "nse",
    "rsi", "macd", "bollinger", "volume"
}

GEOPOLITICAL_KEYWORDS = {
    "war", "conflict", "sanction", "fed", "rbi",
    "rate hike", "inflation", "recession"
}

# =========================
# BASE KEYWORDS
# =========================
KEYWORDS = [
    "nifty", "bank nifty", "sensex", "market crash", "inflation",
    "interest rate", "rbi", "fii", "dii", "expiry", "pcr",
    "stocks", "market", "shares", "trading",
    "breakout", "support", "resistance", "rally", "selloff"
]

HIGH_IMPACT = [
    "rbi policy", "repo rate", "rate hike", "market crash",
    "recession", "budget", "war", "fii selling", "fed", "interest cut"
]

# =========================
# SCORING
# =========================
def get_news_score(text):
    score = 0
    text = text.lower()
    for word in HIGH_IMPACT:
        if word in text:
            score += 5
    for word in KEYWORDS:
        if word in text:
            score += 1
    for word in BULLISH_KEYWORDS:
        if word in text:
            score += 2
    for word in BEARISH_KEYWORDS:
        if word in text:
            score += 2
    for word in FINANCIAL_KEYWORDS:
        if word in text:
            score += 1
    for word in GEOPOLITICAL_KEYWORDS:
        if word in text:
            score += 2
    return score


def get_impact(score):
    if score >= 6:
        return "HIGH"
    elif score >= 3:
        return "MEDIUM"
    return "LOW"


# =========================
# BUILD ITEM
# =========================
def build_news_item(source, title, link, summary="", published=""):
    sentiment = analyzer.polarity_scores(title)
    score = get_news_score((title + summary).lower())
    return {
        "source": source,
        "title": title,
        "summary": summary,
        "link": link,
        "published": published,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "score": score,
        "impact": get_impact(score),
        "sentiment": sentiment["compound"],
        "sentiment_label": (
            "bullish" if sentiment["compound"] > 0.05
            else "bearish" if sentiment["compound"] < -0.05
            else "neutral"
        )
    }


# =========================
# MONEYCONTROL
# =========================
def fetch_moneycontrol_html():
    news_list = []
    try:
        res = requests.get(
            "https://www.moneycontrol.com/stocksmarketsindia/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.find_all("a"):
            title = a.get_text(strip=True)
            link = a.get("href")
            if not title or not link or "moneycontrol.com" not in link:
                continue
            if link in seen_news:
                continue
            news_list.append(build_news_item("Moneycontrol", title, link))
            seen_news.add(link)
    except Exception as e:
        print("Moneycontrol Error:", e)
    return news_list


# =========================
# REUTERS  (Reuters killed their public RSS in 2020; reuters.com is JS-rendered
#  so BeautifulSoup gets nothing.  Fix: use Google News RSS scoped to reuters.com
#  which reliably returns 80-100 articles, then fall back to direct RSS if any
#  instance ever starts working again.)
# =========================
REUTERS_GOOGLE_RSS = [
    "https://news.google.com/rss/search?q=site:reuters.com+india+market+economy&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=site:reuters.com+nifty+sensex+rbi+sebi&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=site:reuters.com+india+finance+trade&hl=en-IN&gl=IN&ceid=IN:en",
]
REUTERS_DIRECT_RSS = [
    "https://feeds.reuters.com/reuters/INbusinessNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/topNews",
]

def fetch_reuters_news(limit=20):
    news_list = []

    # ── Primary: Google News RSS scoped to reuters.com ──────────────────────
    for rss_url in REUTERS_GOOGLE_RSS:
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue
            for entry in feed.entries:
                link  = entry.get("link", "")
                title = entry.get("title", "")
                if not title or not link or link in seen_news:
                    continue
                news_list.append(build_news_item(
                    "Reuters", title, link,
                    entry.get("summary", ""),
                    entry.get("published", "")
                ))
                seen_news.add(link)
                if len(news_list) >= limit:
                    break
            if news_list:
                print(f"Reuters (Google News RSS): {len(news_list)} articles")
                return news_list
        except Exception as e:
            print(f"Reuters Google RSS Error [{rss_url[:55]}]: {e}")

    # ── Fallback: Direct Reuters RSS (works in some regions / future) ────────
    for rss_url in REUTERS_DIRECT_RSS:
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue
            for entry in feed.entries:
                link  = entry.get("link", "")
                title = entry.get("title", "")
                if not title or not link or link in seen_news:
                    continue
                news_list.append(build_news_item(
                    "Reuters", title, link,
                    entry.get("summary", ""),
                    entry.get("published", "")
                ))
                seen_news.add(link)
                if len(news_list) >= limit:
                    break
            if news_list:
                print(f"Reuters (Direct RSS): {len(news_list)} articles")
                return news_list
        except Exception as e:
            print(f"Reuters Direct RSS Error [{rss_url[:50]}]: {e}")

    print(f"Reuters total fetched: {len(news_list)}")
    return news_list


# =========================
# TWITTER  — All Nitter instances are dead (403 / empty / DNS-gone).
#  Strategy:
#    1. twscrape  (async, uses internal Twitter API — needs ONE real Twitter
#       account stored as env vars TW_USERNAME / TW_PASSWORD / TW_EMAIL /
#       TW_EMAIL_PASSWORD).  Fetches the real timelines of every official
#       account in TWITTER_ACCOUNTS_HIGH_PRIORITY first, then MEDIUM.
#    2. Google News RSS fallback — topical queries covering the same accounts'
#       subject areas, so market-relevant tweets that make news still appear.
# =========================

_tw_api_instance = None  # module-level cache so login happens only once

async def _twscrape_init_api():
    """Create/reuse twscrape API and login if credentials are provided."""
    global _tw_api_instance
    if _tw_api_instance is not None:
        return _tw_api_instance
    api = TwscrapeAPI(TW_DB_PATH)
    if TW_USERNAME and TW_PASSWORD and TW_EMAIL:
        try:
            await api.pool.add_account(
                TW_USERNAME, TW_PASSWORD,
                TW_EMAIL, TW_EMAIL_PASSWORD
            )
            await api.pool.login_all()
        except Exception as e:
            print(f"Twitter login warning (may already be logged in): {e}")
    _tw_api_instance = api
    return api


async def _twscrape_fetch_async(accounts, limit_per_account=3):
    """Fetch recent tweets from a list of @handles concurrently via twscrape."""
    news_list = []
    try:
        api = await _twscrape_init_api()

        async def fetch_one(username):
            items = []
            try:
                user = await api.user_by_login(username)
                if not user:
                    return items
                tweets = await twgather(api.user_tweets(user.id, limit=limit_per_account))
                for tw in tweets:
                    text = tw.rawContent or ""
                    link = f"https://x.com/{username}/status/{tw.id}"
                    if not text or link in seen_news:
                        continue
                    items.append(build_news_item(
                        f"Twitter @{username}",
                        text[:150],
                        link,
                        text,
                        str(tw.date) if tw.date else ""
                    ))
                    seen_news.add(link)
            except Exception as e:
                print(f"  twscrape @{username}: {e}")
            return items

        # Process in batches of 10 to be rate-limit friendly
        BATCH = 10
        for i in range(0, len(accounts), BATCH):
            batch = accounts[i:i + BATCH]
            results = await asyncio.gather(*[fetch_one(u) for u in batch])
            for r in results:
                news_list.extend(r)
            if i + BATCH < len(accounts):
                await asyncio.sleep(1.5)   # gentle pause between batches

    except Exception as e:
        print(f"twscrape async error: {e}")
    return news_list


def _fetch_twitter_via_twscrape(limit_per_account=3):
    """Sync wrapper — runs the async twscrape fetcher in its own event loop."""
    # High-priority accounts every call; add medium-priority accounts too
    accounts = ALL_TWITTER_ACCOUNTS
    try:
        # asyncio.run() works fine inside a background thread
        news = asyncio.run(_twscrape_fetch_async(accounts, limit_per_account))
        print(f"Twitter (twscrape): {len(news)} tweets from {len(accounts)} accounts")
        return news
    except RuntimeError:
        # Fallback if an event loop is already running (e.g. some async servers)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _twscrape_fetch_async(accounts, limit_per_account))
            return future.result(timeout=120)


def _fetch_twitter_via_googlenews(limit=30):
    """
    Google News RSS fallback — topical queries that surface tweets and
    statements from the same official accounts when twscrape is unavailable
    or not yet configured.
    """
    news_list = []
    for rss_url in TWITTER_FALLBACK_RSS:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                link  = entry.get("link", "")
                title = entry.get("title", "")
                if not title or not link or link in seen_news:
                    continue
                news_list.append(build_news_item(
                    "Twitter/News",
                    title, link,
                    entry.get("summary", ""),
                    entry.get("published", "")
                ))
                seen_news.add(link)
                if len(news_list) >= limit:
                    break
        except Exception as e:
            print(f"Twitter Google-News fallback error: {e}")
        if len(news_list) >= limit:
            break
    print(f"Twitter (Google News fallback): {len(news_list)} items")
    return news_list


def fetch_twitter_news(accounts=None, limit_per_account=3):
    """
    Main entry-point for Twitter data.

    Priority order:
      1. twscrape  — set TW_USERNAME / TW_PASSWORD / TW_EMAIL env vars to enable.
         Monitors ALL accounts in ALL_TWITTER_ACCOUNTS (high + medium priority).
      2. Google News RSS fallback — topical queries covering the same subjects.
    """
    # ── 1. twscrape (real Twitter timelines) ────────────────────────────────
    if TWSCRAPE_AVAILABLE:
        if TW_USERNAME and TW_PASSWORD:
            try:
                result = _fetch_twitter_via_twscrape(limit_per_account)
                if result:
                    return result
                print("twscrape returned 0 tweets — falling back to Google News RSS")
            except Exception as e:
                print(f"twscrape failed, falling back: {e}")
        else:
            print(
                "Twitter: twscrape installed but NO credentials found.\n"
                "  Set TW_USERNAME, TW_PASSWORD, TW_EMAIL env vars to enable real-time\n"
                "  official account monitoring.  Using Google News fallback for now."
            )

    # ── 2. Google News RSS fallback ─────────────────────────────────────────
    return _fetch_twitter_via_googlenews(limit=30)


# =========================
# FETCH NEWS
# =========================
def fetch_news():
    new_items = []
    new_items += fetch_moneycontrol_html()
    new_items += fetch_reuters_news()
    new_items += fetch_twitter_news()

    for source, url in RSS_FEEDS.items():
        if source in ["Moneycontrol", "Reuters"]:
            continue
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if entry.link in seen_news:
                    continue
                news_item = build_news_item(
                    source,
                    entry.title,
                    entry.link,
                    entry.get("summary", "")
                )
                new_items.append(news_item)
                seen_news.add(entry.link)
        except Exception as e:
            print(f"{source} RSS Error:", e)

    print("Total news fetched:", len(new_items))
    return new_items


# =========================
# SAVE
# =========================
def save_news(news):
    try:
        with open(OUTPUT_FILE, "r") as f:
            existing = json.load(f)
    except Exception:
        existing = []
    existing.extend(news)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(existing, f, indent=4)


# =========================
# BACKGROUND SCRAPER
# =========================
def background_scraper(socketio):
    print("Real-Time Scraper Started...")
    while True:
        try:
            news = fetch_news()
            if news:
                save_news(news)
                socketio.emit("news_update", {"news": news})
            else:
                print("No news found")
        except Exception as e:
            print("Scraper Error:", e)
        time.sleep(60)
