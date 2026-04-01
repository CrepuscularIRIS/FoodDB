# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MediaCrawler is a multi-platform social media data collection tool for educational/research purposes. It crawls public information from Chinese social media platforms using Playwright for browser automation and session management.

**Supported Platforms:** Xiaohongshu (xhs), Douyin (dy), Kuaishou (ks), Bilibili (bili), Weibo (wb), Tieba (tieba), Zhihu (zhihu)

**License:** NON-COMMERCIAL LEARNING LICENSE 1.1 - strictly prohibited for commercial use.

## Common Commands

```bash
# Install dependencies
uv sync
uv run playwright install

# Run crawler (CLI)
uv run main.py --platform xhs --lt qrcode --type search
uv run main.py --platform xhs --lt qrcode --type detail
uv run main.py --platform dy --lt qrcode --type creator
uv run main.py --help  # See all options

# Key CLI arguments:
# --platform: xhs | dy | ks | bili | wb | tieba | zhihu
# --lt: qrcode | phone | cookie (login type)
# --type: search | detail | creator (crawl mode)
# --keywords: comma-separated search terms
# --get_comment: yes | no
# --save_data_option: csv | db | json | sqlite | excel | postgres
# --headless: yes | no

# Initialize database
uv run main.py --init_db sqlite
uv run main.py --init_db mysql
uv run main.py --init_db postgres

# Run WebUI API server
uv run uvicorn api.main:app --port 8080 --reload

# Run tests
pytest tests/
pytest test/test_proxy_ip_pool.py -v

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Architecture

### Entry Point & Factory Pattern
- `main.py` - Entry point with `CrawlerFactory` that maps platform names to crawler classes
- `cmd_arg/` - Typer-based CLI argument parsing, overrides `config/base_config.py` settings
- `var.py` - AsyncIO context variables for thread-safe state (crawler_type_var, source_keyword_var)

### Core Abstractions (`base/base_crawler.py`)
- `AbstractCrawler` - Base class: `start()`, `search()`, `launch_browser()`
- `AbstractLogin` - Login strategies: `login_by_qrcode()`, `login_by_mobile()`, `login_by_cookies()`
- `AbstractStore` - Data persistence: `store_content()`, `store_comment()`, `store_creator()`
- `AbstractApiClient` - HTTP requests: `request()`, `update_cookies()`

### Platform Implementations (`media_platform/{platform}/`)
Each platform directory contains:
- `core.py` - Main crawler (inherits `AbstractCrawler`)
- `client.py` - API client (inherits `AbstractApiClient`, `ProxyRefreshMixin`)
- `login.py` - Login implementation
- `field.py` - Enums and constants
- `exception.py` - Custom exceptions
- `help.py` - Platform-specific utilities

### Data Flow
```
CLI args → Config override → CrawlerFactory.create_crawler()
                                    ↓
                          Platform Crawler.start()
                          ├── Launch browser (Playwright or CDP)
                          ├── Login if needed
                          ├── Fetch data via API client
                          └── Store via StoreFactory
```

### Storage Layer (`store/`)
- `StoreFactory` in each platform's store directory creates storage implementations
- Supports: CSV, JSON, SQLite, MySQL, PostgreSQL, MongoDB, Excel
- Database models in `database/models.py` (SQLAlchemy ORM)
- MongoDB support via Motor in `database/mongodb_store_base.py`

### Browser Modes
- **Standard Mode**: Playwright-managed browser with `stealth.min.js` injection
- **CDP Mode** (`ENABLE_CDP_MODE=True`): Uses user's Chrome/Edge via Chrome DevTools Protocol for better anti-detection

### Proxy System (`proxy/`)
- `ProxyIpPool` manages IP rotation with validation
- Providers in `proxy/providers/`: kuaidaili, wandouhttp, jishuhttp

### Caching (`cache/`)
- `LocalCache` - In-memory with TTL
- `RedisCache` - Redis-backed

## Configuration

- `config/base_config.py` - Main settings (platform, login type, crawl limits, storage, browser, proxy)
- `config/db_config.py` - Database connection strings
- `config/{platform}_config.py` - Platform-specific settings (note IDs, creator IDs)
- `.env` - Credentials for databases and proxy providers

Key settings in `base_config.py`:
- `PLATFORM`, `CRAWLER_TYPE`, `LOGIN_TYPE` - Basic operation mode
- `CRAWLER_MAX_NOTES_COUNT`, `MAX_CONCURRENCY_NUM` - Rate limiting
- `ENABLE_CDP_MODE`, `HEADLESS` - Browser behavior
- `SAVE_DATA_OPTION` - Output format
- `ENABLE_GET_COMMENTS`, `ENABLE_GET_SUB_COMMENTS` - Comment crawling

## Key Patterns

- All I/O is async (asyncio, async_playwright, SQLAlchemy async)
- Factory pattern for crawlers and storage
- Mixin pattern: `ProxyRefreshMixin` adds proxy rotation to API clients
- Platform-specific JS signature generation in `libs/` (douyin.js, zhihu.js)

## File Headers

All Python files require copyright headers. Pre-commit hooks enforce this via `file_header_manager.py`.

## Dependencies

Python >= 3.11, Node.js >= 16 (for Douyin/Zhihu signature generation via pyexecjs)
