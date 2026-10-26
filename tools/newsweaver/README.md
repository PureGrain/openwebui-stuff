# NewsWeaver: News for Open WebUI

Real headlines, not homepages. Top, U.S., world, business, tech, science, health, sports, entertainment and local news, news search on any subject, and the Hacker News front page. Short lists with source, age and link, sized for small models. No API keys, no extra packages.

**Version:** 1.0.0
**Author:** PureGrain at SLA Ops, LLC
**License:** MIT

## Why Not Web Search

A general web search for "tech news" returns the front pages of news sites, and the free search engines behind SearXNG often block home IP addresses. NewsWeaver reads news feeds instead: every result is a dated article from a named outlet, and feeds do not block or rate-limit normal use. SearXNG's news search is used only as a fallback if you point the tool at one.

## Features

| Function | What it does |
|---|---|
| `get_headlines` | Headlines for a topic: top, us, world, business, tech, science, health, sports, entertainment or local. Tech mixes Google News with Ars Technica, The Verge and TechCrunch. Local uses the user's city. Any other topic is searched instead |
| `search_news` | Recent articles on any subject, person, company or place, 1 to 30 days back, from Google News, with SearXNG news as a fallback |
| `get_hacker_news` | The Hacker News front page with points, comment counts and discussion links |

Stories are taken from each source in turn so one outlet cannot fill the list, repeats are dropped, and stories older than 48 hours are skipped. Feeds are fetched in parallel and kept for 10 minutes. A source that does not answer is skipped and named in `sources_not_answering`.

## Installation

1. In Open WebUI go to **Workspace > Tools > +**, paste in `newsweaver.py`, and click **Save**.
2. Enable it on your model (**Workspace > Models >** edit **> Tools**) or per chat with the **+** button.
3. Set **Function Calling** to **Native** in the model's **Advanced Params**.
4. Optional: set the `searxng_url` valve to your SearXNG instance to turn on the search fallback.

Requires Open WebUI 0.10.0 or newer and outbound internet access to `news.google.com`, `hn.algolia.com` and the outlet feeds.

## Settings

**Valves** (admin, gear icon on the tool):

| Valve | Default | Purpose |
|---|---|---|
| `default_location` | `Louisville, KY` | City for local news when the user has not set one |
| `local_feeds` | WLKY, WHAS11, Louisville Public Media, WAVE 3 | Local outlet RSS feeds, comma separated. Used only when the city is the default location |
| `tech_feeds` | Ars Technica, The Verge, TechCrunch | RSS feeds mixed in with Google News for tech |
| `google_news_region` | `US:en` | Google News edition as COUNTRY:language, for example `GB:en`, `CA:fr` |
| `searxng_url` | empty | SearXNG base URL for the search fallback, for example `http://searxng:8080`. Empty turns the fallback off |
| `max_items` | 8 | Headlines returned when the model does not ask for a number |
| `max_age_hours` | 48 | Skip stories older than this (0 = no limit) |
| `include_summaries` | off | Add a one-line summary when the feed has one. Costs context |
| `include_links` | on | Include the article link for each headline |
| `cache_minutes` | 10 | Reuse a fetched feed for this many minutes |

**User Valves** (each user, in **Chat Controls > Valves**):

| Valve | Purpose |
|---|---|
| `user_location` | Your city for local news. Any city works; outlet feeds are added only for the default location |

## Example Questions

- "What's in the news?" / "Top world headlines?"
- "What are the biggest tech stories right now?"
- "Any local news?"
- "What's the latest on the Anthropic IPO?"
- "What's on Hacker News?"

## Data Sources

- Topic headlines and search: [Google News RSS](https://news.google.com). Google News links are redirect links that open the article in a browser
- Tech: Ars Technica, The Verge and TechCrunch RSS
- Local (Louisville default): WLKY, WHAS11, Louisville Public Media and WAVE 3 RSS
- Hacker News: [Algolia HN Search API](https://hn.algolia.com/api)
- Fallback: SearXNG `categories=news`, if configured

## Changelog

### Version 1.0.0 (2026-10-26)

- First release: `get_headlines`, `search_news`, `get_hacker_news`

## License

MIT. See the LICENSE file in the repository root.
