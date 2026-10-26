"""
title: NewsWeaver
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/openwebui-stuff/tree/main/tools/newsweaver
funding_url: https://github.com/sponsors/PureGrain
version: 1.0.0
license: MIT
required_open_webui_version: 0.10.0
description: Real headlines, not homepages. Top, US, world, business, tech, science, health, sports and local news from Google News and outlet RSS feeds, news search on any subject, and the Hacker News front page. Short lists with source, age and link. SearXNG news as an optional fallback. No API keys, no extra packages.
"""

import asyncio
import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import quote_plus

import httpx
from pydantic import BaseModel, Field

Emitter = Optional[Callable[[dict], Awaitable[Any]]]

GOOGLE_NEWS = "https://news.google.com/rss"
HN_URL = "https://hn.algolia.com/api/v1/search"
USER_AGENT = "Mozilla/5.0 (compatible; NewsWeaver/1.0; +https://github.com/PureGrain/openwebui-stuff)"
MAX_FEED_BYTES = 4_000_000

# Topic name -> Google News section (None = the main top stories page)
GOOGLE_TOPICS = {
    "top": None,
    "us": "NATION",
    "world": "WORLD",
    "business": "BUSINESS",
    "tech": "TECHNOLOGY",
    "science": "SCIENCE",
    "health": "HEALTH",
    "sports": "SPORTS",
    "entertainment": "ENTERTAINMENT",
}

TOPIC_ALIASES = {
    "": "top", "top": "top", "headlines": "top", "top stories": "top", "general": "top", "latest": "top", "breaking": "top",
    "us": "us", "u.s.": "us", "usa": "us", "nation": "us", "national": "us", "america": "us", "united states": "us",
    "world": "world", "international": "world", "global": "world",
    "business": "business", "finance": "business", "economy": "business", "markets": "business", "money": "business",
    "tech": "tech", "technology": "tech", "computers": "tech", "ai": "tech", "gadgets": "tech",
    "science": "science", "space": "science",
    "health": "health", "medicine": "health",
    "sports": "sports", "sport": "sports",
    "entertainment": "entertainment", "movies": "entertainment", "tv": "entertainment", "music": "entertainment",
    "local": "local", "my city": "local", "near me": "local", "nearby": "local", "hometown": "local", "here": "local",
}

# Friendly outlet names for feeds whose own titles are vague ("News", "Top Stories")
SOURCE_NAMES = {
    "arstechnica.com": "Ars Technica",
    "theverge.com": "The Verge",
    "techcrunch.com": "TechCrunch",
    "wlky.com": "WLKY",
    "whas11.com": "WHAS11",
    "lpm.org": "Louisville Public Media",
    "wave3.com": "WAVE 3",
    "wdrbwave.com": "WDRB+WAVE",
}
GENERIC_FEED_TITLE = re.compile(r"^(news|top stories|latest|home|headlines|local|all)$|\brss\b|\bfeed\b", re.I)

TOPIC_LABELS = {
    "top": "Top stories", "us": "U.S.", "world": "World", "business": "Business", "tech": "Technology",
    "science": "Science", "health": "Health", "sports": "Sports", "entertainment": "Entertainment",
}


class WeaverError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


async def _emit(emitter: Emitter, text: str, done: bool = False) -> None:
    if emitter:
        try:
            await emitter({"type": "status", "data": {"description": text, "done": done}})
        except Exception:
            pass


def _local(tag: str) -> str:
    """'{http://www.w3.org/2005/Atom}entry' -> 'entry'."""
    return tag.rsplit("}", 1)[-1].lower()


def _child(node: ET.Element, *names: str) -> Optional[ET.Element]:
    for child in node:
        if _local(child.tag) in names:
            return child
    return None


def _text(node: Optional[ET.Element]) -> str:
    return (node.text or "").strip() if node is not None else ""


def _clean(text: str) -> str:
    """Strip HTML tags and entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _parse_date(text: str) -> Optional[datetime]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _age(moment: Optional[datetime], now: datetime) -> Optional[str]:
    if not moment:
        return None
    minutes = int((now - moment).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    if minutes < 48 * 60:
        return f"{minutes // 60}h ago"
    return f"{minutes // 1440}d ago"


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:60]


def _host(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/:]+)", url or "")
    return m.group(1) if m else ""


def _feed_name(feed_title: str, host: str) -> str:
    if host in SOURCE_NAMES:
        return SOURCE_NAMES[host]
    title = re.sub(r"\s+[-:|]\s+(all content|all stories|home|latest( news)?|news)$", "", feed_title, flags=re.I).strip()
    return host if not title or GENERIC_FEED_TITLE.search(title) else title


def _parse_feed(content: bytes, host: str) -> list:
    """RSS 2.0 or Atom -> [{title, source, published, link, summary}] in feed order."""
    root = ET.fromstring(content)
    channel = _child(root, "channel")
    if channel is not None:
        feed_title = _clean(_text(_child(channel, "title")))
        entries = [n for n in channel if _local(n.tag) == "item"]
    else:
        feed_title = _clean(_text(_child(root, "title")))
        entries = [n for n in root if _local(n.tag) in ("entry", "item")]
    feed_source = _feed_name(feed_title, host)
    items = []
    for node in entries:
        title = _clean(_text(_child(node, "title")))
        if not title:
            continue
        link_node = _child(node, "link")
        link = ""
        if link_node is not None:
            link = (link_node.get("href") or link_node.text or "").strip()
        source_node = _child(node, "source")
        source = _clean(_text(source_node)) if source_node is not None else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()  # Google News appends " - Outlet"
        published = _parse_date(_text(_child(node, "pubdate", "published", "updated", "date")))
        summary = _clean(_text(_child(node, "description", "summary")))
        items.append({
            "title": title,
            "source": source or feed_source,
            "published": published,
            "link": link,
            "summary": summary if not source else "",  # Google News descriptions are just a list of links
        })
    return items


class Tools:
    class Valves(BaseModel):
        default_location: str = Field(default="Louisville, KY", description="City for local news when the user has not set one")
        local_feeds: str = Field(
            default="https://www.wlky.com/topstories-rss, https://www.whas11.com/feeds/syndication/rss/news/local, https://www.lpm.org/news.rss, https://www.wave3.com/arc/outboundfeeds/rss/?outputType=xml",
            description="RSS feeds of local outlets for the default location, comma separated. Used only when the local city is the default location",
        )
        tech_feeds: str = Field(
            default="https://feeds.arstechnica.com/arstechnica/index, https://www.theverge.com/rss/index.xml, https://techcrunch.com/feed/",
            description="RSS feeds mixed in with Google News for the tech topic, comma separated",
        )
        google_news_region: str = Field(default="US:en", description="Google News edition as COUNTRY:language, for example US:en, GB:en, CA:fr")
        searxng_url: str = Field(default="", description="SearXNG base URL for the news search fallback, for example http://searxng:8080. Leave empty to turn the fallback off")
        max_items: int = Field(default=8, description="Headlines returned when the model does not ask for a number (1 to 25)")
        max_age_hours: int = Field(default=48, description="Skip stories older than this many hours (0 = no limit)")
        include_summaries: bool = Field(default=False, description="Add a one-line summary when the feed has one. Costs context")
        include_links: bool = Field(default=True, description="Include the article link for each headline")
        cache_minutes: int = Field(default=10, description="Reuse a fetched feed for this many minutes")

    class UserValves(BaseModel):
        user_location: Optional[str] = Field(default=None, description="Your city for local news, for example 'Louisville, KY'")

    def __init__(self):
        self.valves = self.Valves()
        self._cache: dict = {}

    # ============= HELPERS =============

    def _user_valve(self, user: Optional[dict], name: str) -> Optional[str]:
        valves = (user or {}).get("valves")
        value = valves.get(name) if isinstance(valves, dict) else getattr(valves, name, None)
        return str(value).strip() if value else None

    def _limit(self, limit: Any) -> int:
        try:
            n = int(limit) if limit not in (None, "", 0) else int(self.valves.max_items)
        except (TypeError, ValueError):
            n = int(self.valves.max_items)
        return max(1, min(25, n))

    def _region(self) -> str:
        country, _, lang = (self.valves.google_news_region or "US:en").partition(":")
        country, lang = (country or "US").upper(), (lang or "en").lower()
        return f"hl={lang}-{country}&gl={country}&ceid={country}:{lang}"

    def _google_topic_url(self, section: Optional[str]) -> str:
        if section is None:
            return f"{GOOGLE_NEWS}?{self._region()}"
        return f"{GOOGLE_NEWS}/headlines/section/topic/{section}?{self._region()}"

    def _google_search_url(self, query: str, days: int) -> str:
        return f"{GOOGLE_NEWS}/search?q={quote_plus(f'{query} when:{days}d')}&{self._region()}"

    @staticmethod
    def _split(text: str) -> list:
        return [u.strip() for u in re.split(r"[,\s]+", text or "") if u.strip().startswith("http")]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(12, connect=5),
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
            follow_redirects=True,
        )

    async def _run(self, emitter: Emitter, label: str, work: Callable[[httpx.AsyncClient], Awaitable[Any]]) -> Any:
        await _emit(emitter, f"{label}...")
        try:
            async with self._client() as client:
                result = await work(client)
            await _emit(emitter, label, done=True)
            return result
        except WeaverError as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": str(e), "hint": e.hint} if e.hint else {"error": str(e)}
        except httpx.HTTPError as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": f"The news source did not answer: {type(e).__name__}", "hint": "Try again in a moment."}
        except Exception as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": f"{type(e).__name__}: {e}"}

    async def _fetch_feed(self, client: httpx.AsyncClient, url: str) -> list:
        ttl = max(0, int(self.valves.cache_minutes)) * 60
        hit = self._cache.get(url)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        r = await client.get(url)
        r.raise_for_status()
        if len(r.content) > MAX_FEED_BYTES:
            raise WeaverError(f"Feed too large: {_host(url)}")
        items = _parse_feed(r.content, _host(url))
        if len(items) == 1 and items[0]["title"].lower().startswith("this feed is not available"):
            raise WeaverError(f"Feed not available: {_host(url)}")  # Google News answers 200 with a placeholder item
        self._cache[url] = (time.monotonic(), items)
        if len(self._cache) > 64:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            self._cache.pop(oldest, None)
        return items

    async def _gather_feeds(self, client: httpx.AsyncClient, urls: list) -> tuple:
        """Fetch feeds in parallel. Returns ([items per feed], [hosts that failed])."""
        results = await asyncio.gather(*(self._fetch_feed(client, u) for u in urls), return_exceptions=True)
        feeds, failed = [], []
        for url, result in zip(urls, results):
            if isinstance(result, BaseException):
                failed.append(_host(url))
            else:
                feeds.append(result)
        return feeds, failed

    def _merge(self, feeds: list, limit: int, now: datetime) -> list:
        """Take stories from each feed in turn, so one outlet cannot fill the list. Drops repeats and stale stories."""
        max_age = int(self.valves.max_age_hours or 0) * 3600
        queues = []
        for items in feeds:
            fresh = [i for i in items if not (max_age and i["published"] and (now - i["published"]).total_seconds() > max_age)]
            queues.append(fresh)
        seen, picked = set(), []
        while len(picked) < limit and any(queues):
            for queue in queues:
                while queue:
                    item = queue.pop(0)
                    key = _title_key(item["title"])
                    if key and key not in seen:
                        seen.add(key)
                        picked.append(item)
                        break
                if len(picked) >= limit:
                    break
        return picked

    def _format(self, items: list, now: datetime) -> list:
        rows = []
        for item in items:
            row = {"title": item["title"], "source": item["source"], "age": _age(item.get("published"), now)}
            if self.valves.include_summaries and item.get("summary"):
                summary = item["summary"]
                row["summary"] = summary if len(summary) <= 160 else summary[:157].rsplit(" ", 1)[0] + "..."
            if self.valves.include_links and item.get("link"):
                row["link"] = item["link"]
            rows.append({k: v for k, v in row.items() if v})
        return rows

    async def _searxng_news(self, client: httpx.AsyncClient, query: str, days: int, limit: int) -> list:
        base = (self.valves.searxng_url or "").strip().rstrip("/")
        if not base:
            return []
        base = re.sub(r"/search$", "", base)
        time_range = "day" if days <= 1 else "week" if days <= 7 else "month" if days <= 31 else "year"
        r = await client.get(f"{base}/search", params={"q": query, "format": "json", "categories": "news", "time_range": time_range})
        r.raise_for_status()
        items = []
        for hit in (r.json().get("results") or [])[: limit * 2]:
            title = _clean(hit.get("title") or "")
            if not title:
                continue
            items.append({
                "title": title,
                "source": _host(hit.get("url") or ""),
                "published": _parse_date(hit.get("publishedDate") or ""),
                "link": hit.get("url") or "",
                "summary": _clean(hit.get("content") or ""),
            })
        return items

    # ============= TOOLS =============

    async def get_headlines(
        self, topic: str = "top", limit: int = 0, __user__: Optional[dict] = None, __event_emitter__: Emitter = None
    ) -> dict:
        """
        Current news headlines by topic: real stories with source, age and link. Use this for "what's in the news", "biggest tech stories right now", "local news", "business headlines".
        :param topic: One of top, us, world, business, tech, science, health, sports, entertainment, local. Local means the user's own city. Any other subject is searched instead.
        :param limit: How many headlines, 1 to 25. Leave 0 for the default.
        """
        key = TOPIC_ALIASES.get(str(topic or "").strip().lower())
        if key is None:
            return await self.search_news(query=str(topic), limit=limit, __user__=__user__, __event_emitter__=__event_emitter__)
        if key == "local":
            return await self._local_news(limit, __user__, __event_emitter__)

        async def work(client: httpx.AsyncClient) -> dict:
            n = self._limit(limit)
            urls = [self._google_topic_url(GOOGLE_TOPICS[key])]
            if key == "tech":
                urls += self._split(self.valves.tech_feeds)
            feeds, failed = await self._gather_feeds(client, urls)
            if not feeds:
                raise WeaverError("No news source answered.", "Check that Open WebUI can reach news.google.com, then try again.")
            now = datetime.now(timezone.utc)
            out = {"topic": TOPIC_LABELS[key], "headlines": self._format(self._merge(feeds, n, now), now)}
            if failed:
                out["sources_not_answering"] = failed
            return out

        return await self._run(__event_emitter__, f"Getting {TOPIC_LABELS[key].lower()} headlines", work)

    async def _local_news(self, limit: Any, user: Optional[dict], emitter: Emitter) -> dict:
        async def work(client: httpx.AsyncClient) -> dict:
            n = self._limit(limit)
            default_city = (self.valves.default_location or "").strip()
            city = self._user_valve(user, "user_location") or default_city
            if not city:
                raise WeaverError("No city is set for local news.", "Set your city in Chat Controls > Valves > user_location.")
            urls = [self._google_search_url(f"{city} -obituary -obituaries", 2)]
            if city.lower() == default_city.lower():
                urls += self._split(self.valves.local_feeds)
            feeds, failed = await self._gather_feeds(client, urls)
            if not feeds:
                raise WeaverError("No news source answered.", "Try again in a moment.")
            now = datetime.now(timezone.utc)
            out = {"topic": f"Local news: {city}", "headlines": self._format(self._merge(feeds, n, now), now)}
            if failed:
                out["sources_not_answering"] = failed
            return out

        return await self._run(emitter, "Getting local news", work)

    async def search_news(
        self, query: str, days: int = 3, limit: int = 0, __user__: Optional[dict] = None, __event_emitter__: Emitter = None
    ) -> dict:
        """
        Search recent news articles on any subject, person, company or place. Returns real articles with source, age and link, newest coverage first.
        :param query: What to search for, for example "Ford layoffs", "SpaceX launch", "Kentucky Derby".
        :param days: How far back to look, 1 to 30 days.
        :param limit: How many articles, 1 to 25. Leave 0 for the default.
        """
        query = re.sub(r"\s+", " ", str(query or "")).strip()
        if not query:
            return {"error": "Nothing to search for.", "hint": "Give a subject, or use get_headlines for top stories."}

        async def work(client: httpx.AsyncClient) -> dict:
            n = self._limit(limit)
            try:
                span = max(1, min(30, int(days or 3)))
            except (TypeError, ValueError):
                span = 3
            now = datetime.now(timezone.utc)
            items, source_used, google_failed = [], "Google News", False
            try:
                items = await self._fetch_feed(client, self._google_search_url(query, span))
            except Exception:
                items, google_failed = [], True
            if not items:
                try:
                    items = await self._searxng_news(client, query, span, n)
                    source_used = "SearXNG news"
                except Exception:
                    items = []
            if not items and google_failed:
                raise WeaverError("Google News did not answer and there is no other news source.", "Try again in a moment.")
            if not items:
                return {"query": query, "days": span, "headlines": [], "note": f"No news articles found in the last {span} days."}
            picked = self._merge([items], n, now) if source_used == "Google News" else items[:n]
            return {"query": query, "days": span, "found_with": source_used, "headlines": self._format(picked, now)}

        return await self._run(__event_emitter__, f"Searching news for {query}", work)

    async def get_hacker_news(self, limit: int = 10, __event_emitter__: Emitter = None) -> dict:
        """
        The Hacker News front page right now: the stories programmers and tech people are reading and discussing, with points and comment counts.
        :param limit: How many stories, 1 to 30.
        """

        async def work(client: httpx.AsyncClient) -> dict:
            try:
                n = max(1, min(30, int(limit or 10)))
            except (TypeError, ValueError):
                n = 10
            r = await client.get(HN_URL, params={"tags": "front_page", "hitsPerPage": n})
            r.raise_for_status()
            now = datetime.now(timezone.utc)
            hits = sorted(r.json().get("hits") or [], key=lambda h: h.get("points") or 0, reverse=True)
            rows = []
            for hit in hits[:n]:
                posted = datetime.fromtimestamp(hit["created_at_i"], timezone.utc) if hit.get("created_at_i") else None
                discussion = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                row = {
                    "title": hit.get("title"),
                    "site": _host(hit.get("url") or "") or "news.ycombinator.com",
                    "points": hit.get("points"),
                    "comments": hit.get("num_comments"),
                    "age": _age(posted, now),
                }
                if self.valves.include_links:
                    row["link"] = hit.get("url") or discussion
                    row["discussion"] = discussion
                rows.append({k: v for k, v in row.items() if v is not None})
            return {"source": "Hacker News front page", "stories": rows}

        return await self._run(__event_emitter__, "Reading Hacker News", work)
