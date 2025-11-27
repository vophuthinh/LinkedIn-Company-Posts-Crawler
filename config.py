# -*- coding: utf-8 -*-
"""
Configuration file for LinkedIn Crawler
Contains constants, selectors, and default values
"""

# ==================== Constants ====================

# Scraping settings
MAX_STABLE_ROUNDS = 3  # Số vòng cuộn ổn định trước khi dừng
RANDOM_DELAY_MIN = 8  # Khoảng nghỉ ngẫu nhiên tối thiểu (vòng)
RANDOM_DELAY_MAX = 15  # Khoảng nghỉ ngẫu nhiên tối đa (vòng)
LONG_PAUSE_MIN = 5.0  # Nghỉ dài tối thiểu (giây)
LONG_PAUSE_MAX = 12.0  # Nghỉ dài tối đa (giây)
SCROLL_BASE_PX = 1100  # Khoảng cách cuộn cơ bản (pixels)
SCROLL_VARIATION = 200  # Biến thiên khoảng cách cuộn
SCROLL_DELAY_MIN = 0.6  # Delay cuộn tối thiểu (giây)
SCROLL_DELAY_MAX = 1.2  # Delay cuộn tối đa (giây)
INNER_SCROLL_DELAY_MIN = 0.5  # Delay cuộn inner tối thiểu
INNER_SCROLL_DELAY_MAX = 1.0  # Delay cuộn inner tối đa
BETWEEN_URL_DELAY_MIN = 5.0  # Delay giữa các URL (giây)
BETWEEN_URL_DELAY_MAX = 10.0  # Delay giữa các URL tối đa

# Default values
DEFAULT_WAIT_SEC = 30
DEFAULT_SCROLL_ROUNDS = 60
DEFAULT_MAX_POSTS = 300
DEFAULT_OUTPUT_DIR = "LinkedInOut"

# Rate limiting settings
DEFAULT_RATE_LIMIT_REQUESTS = 10  # Max requests per time window
DEFAULT_RATE_LIMIT_WINDOW = 60    # Time window in seconds
DEFAULT_RATE_LIMIT_MIN_DELAY = 1.0  # Minimum delay between requests (seconds)
USE_ADAPTIVE_RATE_LIMITER = False  # Use adaptive rate limiter

# Retry settings
DEFAULT_RETRY_ATTEMPTS = 3        # Max retry attempts
DEFAULT_RETRY_BASE_DELAY = 4.0    # Base delay for exponential backoff (seconds)
DEFAULT_RETRY_MAX_DELAY = 30.0    # Maximum delay between retries (seconds)

# HTTP/Locale
ACCEPT_LANG = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Timezone
VN_TIMEZONE_OFFSET = 7  # UTC+7

# ==================== CSS Selectors ====================

SELECTORS = {
    # Post containers
    'post_container': '.organization-content-list__posts-list-item, .feed-shared-update-v2',
    'post_node': '[data-urn*="urn:li:activity:"], [data-entity-urn*="urn:li:activity:"], '
                 '[data-urn*="urn:li:ugcPost:"], [data-entity-urn*="urn:li:ugcPost:"], '
                 'article[role="article"], article',
    
    # Time elements
    'time_element': 'time[datetime]',
    'time_meta': '.update-components-actor__sub-description, .feed-shared-actor__sub-description',
    
    # Text content
    'text_candidates': [
        '[data-test-id="main-feed-activity-card__commentary"]',
        '.update-components-text',
        '.feed-shared-update-v2__description',
        '.attributed-text-segment-list__container',
        '.break-words',
        'div[dir]',
        'p[dir]'
    ],
    
    # Links
    'posts_link': 'a[href*="/posts/"]',
    'feed_update_link': 'a[href*="/feed/update/"], a[href*="/posts/"]',
    
    # Overlay buttons (XPath)
    'overlay_xpaths': [
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'đồng ý')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chấp nhận')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'got it')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
        "//button[@aria-label='Dismiss' or contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dismiss')]",
        "//button[contains(@class,'artdeco-modal__dismiss')]",
        "//button[contains(@class,'ember-view') and contains(.,'Close')]",
    ]
}

# ==================== URL Patterns ====================

LINKEDIN_URL_PATTERNS = {
    'company_posts': r'^https://www\.linkedin\.com/company/[\w-]+/posts',
    'company_base': r'^https://www\.linkedin\.com/company/[\w-]+',
    'feed_update': r'^https://www\.linkedin\.com/feed/update/',
}

# ==================== Date Formats ====================

DATE_FORMAT_DMY = "%d-%m-%Y"  # DD-MM-YYYY
DATE_FORMAT_ISO = "%Y-%m-%dT%H:%M:%S"
DATE_FORMAT_DATE_ONLY = "%Y-%m-%d"

# ==================== File Names ====================

COOKIE_FILE = "cookies.json"
CHECKPOINT_FILE = "checkpoint.json"

