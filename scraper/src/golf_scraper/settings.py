BOT_NAME = "golf_scraper"
SPIDER_MODULES = ["golf_scraper.spiders"]
NEWSPIDER_MODULE = "golf_scraper.spiders"

ROBOTSTXT_OBEY = True
USER_AGENT = "TeeTimeAggregator/0.1 (+local golf tee-time research scraper)"

# One request at a time per site, and never faster than one per second.
DOWNLOAD_DELAY = 1
DOWNLOAD_DELAY_JITTER = 0
CONCURRENT_REQUESTS_PER_DOMAIN = 1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

TELNETCONSOLE_ENABLED = False

DOWNLOADER_MIDDLEWARES = {
    "golf_scraper.middlewares.FixtureResponseMiddleware": 50,
}

ITEM_PIPELINES = {
    "golf_scraper.pipelines.TeeTimePipeline": 300,
}
