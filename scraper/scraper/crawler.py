import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import re
import asyncio
import requests
import socket
import httpx
from datetime import datetime
from urllib.parse import urljoin, urlparse, unquote
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Error as PlaywrightError
from .utils import *
import hashlib
import pytz
from .downloadfiles import *
from typing import Tuple
from playwright.async_api import Page

from paywall.main import classify_page_access


# Import paywall detection

try:
    from paywall.main import detect_paywall_from_html
    from paywall.enhanced_detector import (
        enhanced_detect_paywall,
        create_enhanced_detector,
    )

    PAYWALL_DETECTION_AVAILABLE = True
    ENHANCED_PAYWALL_AVAILABLE = True
except ImportError:
    print("[INFO] Paywall detection not available - continuing without it")
    PAYWALL_DETECTION_AVAILABLE = False
    ENHANCED_PAYWALL_AVAILABLE = False


load_dotenv(override=True)
USERNAME = os.getenv("MOODLE_USERNAME")
PASSWORD = os.getenv("MOODLE_PASSWORD")


# Configuration from Environment Variables
def str_to_bool(value: str) -> bool:
    """Convert string to boolean"""
    return value.lower() in ("true", "1", "yes", "on")


HEADLESS_BROWSER = str_to_bool(os.getenv("HEADLESS_BROWSER", "false"))
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "60000"))
CRAWLER_DELAY_SECONDS = float(os.getenv("CRAWLER_DELAY_SECONDS", "0.5"))
SAVE_SCREENSHOTS = str_to_bool(os.getenv("SAVE_SCREENSHOTS", "true"))
DEBUG_MODE = str_to_bool(os.getenv("DEBUG_MODE", "false"))

# FOR LOCAL
# BASE_URL = "http://3.107.195.248/moodle/course/view.php?id="
# MOODLE_DOMAIN = "3.107.195.248"

# FOR PRODUCTION ENVIORNMENT
BASE_URL = "http://10.51.33.25/moodle/course/view.php?id="
MOODLE_DOMAIN = "10.51.33.25"

EXCLUDED_PATH_PREFIXES = [
    "/moodle/user/",
    "/moodle/message/",
    "/moodle/notes/",
    "/moodle/blog/",
    "/moodle/iplookup/",
    "/moodle/tag/",
    "/moodle/calendar/",
    "/moodle/report/usersessions/",
    "/moodle/admin/",
    "/moodle/enrol/",
    "/moodle/grade/report/overview/",
    "/moodle/competency/",
    "/moodle/user",
]


def is_external_link(url: str) -> bool:
    """
    Returns True if the URL is considered external (eg not our local Moodle or trusted Murdoch domains).
    Treats local Moodle IP and all murdoch.edu.au domains as internal/trusted.
    """
    if not url or url.strip() == "" or url.startswith("mailto:"):
        return False  # Not a scrapable or external link

    # Internal/trusted domains (won't be scanned for security threats)
    internal_domains = [
        "10.51.33.25",  # local Moodle IP
    ]

    # All Murdoch domains are considered trusted (internal)
    trusted_murdoch_domains = [
        "murdoch.edu.au",
        "moodleprod.murdoch.edu.au",
        "murdochuniversity.sharepoint.com",
        "goto.murdoch.edu.au",
        "libguides.murdoch.edu.au",
        "library.murdoch.edu.au",
        "our.murdoch.edu.au",
        "online.murdoch.edu.au",
        "myanswers.custhelp.com",  # Murdoch support system
        "murdoch.navexone.com",
    ]

    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""

        # Check if it's our local internal domain
        if any(domain == d or domain.endswith(f".{d}") for d in internal_domains):
            return False  # Internal

        # Check if it's a trusted Murdoch domain
        if any(
            domain == d or domain.endswith(f".{d}") for d in trusted_murdoch_domains
        ):
            return False  # Trusted, treat as internal

        # Check for any murdoch.edu.au subdomains
        if domain.endswith(".murdoch.edu.au") or domain == "murdoch.edu.au":
            return False  # All Murdoch domains are trusted

        # Everything else is external
        return True

    except Exception as e:
        print(f"[WARNING] Failed to parse URL: {url} - {e}")
        return True  # Treat unknowns as external for safety


def detect_paywall_for_url(url: str, html_content: str = None) -> bool:
    """
    Enhanced paywall detection with multiple approaches:
    1. Domain lists (fast)
    2. URL patterns (fast)
    3. Structured data analysis (JSON-LD)
    4. Content analysis (heuristic)
    5. Visual barrier detection
    """

    # Use enhanced detection if available
    if ENHANCED_PAYWALL_AVAILABLE:
        try:
            detector = create_enhanced_detector()
            # Use async wrapper in sync context
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result = loop.run_until_complete(detector.detect_paywall(url, html_content))

            if result["is_paywall"]:
                methods = ", ".join(result["detection_methods"])
                reasons = "; ".join(result["reasons"])
                print(
                    f"[INFO] Enhanced paywall detected for {url}: {reasons} (Methods: {methods}, Confidence: {result['confidence']:.2f})"
                )
                return True
            else:
                print(
                    f"[SUCCESS] Enhanced check: No paywall detected for {url} (Confidence: {result['confidence']:.2f})"
                )
                return False

        except Exception as e:
            print(
                f"[INFO] Enhanced paywall detection failed for {url}: {e}, falling back to basic detection"
            )

    # Fallback to original detection logic
    try:

        # Enhanced paywall domains - significantly expanded for better coverage
        PAYWALL_DOMAINS = {
            # Original major sites
            "wsj.com",
            "ft.com",
            "nytimes.com",
            "bloomberg.com",
            "economist.com",
            "washingtonpost.com",
            "newyorker.com",
            "theatlantic.com",
            "jstor.org",
            "nature.com",
            "science.org",
            "springer.com",
            "wiley.com",
            "elsevier.com",
            # Additional news and magazine sites
            "spectator.co.uk",
            "foreignaffairs.com",
            "harpers.org",
            "newstatesman.com",
            "thetimes.co.uk",
            "telegraph.co.uk",
            "vanityfair.com",
            "wired.com",
            "medium.com",
            "substack.com",
            "politico.com",
            "axios.com",
            "forbes.com",
            "businessinsider.com",
            "fortune.com",
            "scientificamerican.com",
            "nationalgeographic.com",
            "slate.com",
            "salon.com",
            "vox.com",
            # Academic and professional sites
            "ieee.org",
            "acm.org",
            "cambridge.org",
            "oxford.org",
            "tandfonline.com",
            "sagepub.com",
            "jama.jamanetwork.com",
            "nejm.org",
            "bmj.com",
            "thelancet.com",
            "cell.com",
            "sciencedirect.com",
            # Trade and tech publications
            "techcrunch.com",
            "venturebeat.com",
            "recode.net",
            "theverge.com",
            "arstechnica.com",
            "engadget.com",
            "gizmodo.com",
            "mashable.com",
            "readwrite.com",
            "gigaom.com",
            "allthingsd.com",
            "pandodaily.com",
            # Financial publications
            "marketwatch.com",
            "investopedia.com",
            "morningstar.com",
            "fool.com",
            "seekingalpha.com",
            "zacks.com",
            "thestreet.com",
            "reuters.com",
            "cnbc.com",
            "barrons.com",
            # International publications
            "guardian.co.uk",
            "independent.co.uk",
            "dailymail.co.uk",
            "mirror.co.uk",
            "express.co.uk",
            "thesun.co.uk",
            "standard.co.uk",
            "eveningstandard.co.uk",
            "metro.co.uk",
            "cityam.com",
            # Lifestyle and entertainment
            "gq.com",
            "vogue.com",
            "elle.com",
            "marieclaire.com",
            "cosmopolitan.com",
            "harpersbazaar.com",
            "esquire.com",
            "rollingstone.com",
            "people.com",
            "time.com",
            "newsweek.com",
            "usnews.com",
            "usatoday.com",
            "latimes.com",
            "chicagotribune.com",
            # Sports and entertainment
            "espn.com",
            "si.com",
            "bleacherreport.com",
            "nfl.com",
            "nba.com",
            "mlb.com",
            "nhl.com",
            "variety.com",
            "hollywoodreporter.com",
            "deadline.com",
            "entertainment.com",
            # Subscription platforms
            "patreon.com",
            "memberful.com",
            "gumroad.com",
            "teachable.com",
            "thinkific.com",
            "kajabi.com",
            "podia.com",
            # Learning platforms
            "coursera.org",
            "udemy.com",
            "skillshare.com",
            "masterclass.com",
            "pluralsight.com",
            "lynda.com",
            "codecademy.com",
            "treehouse.com",
            "edx.org",
            "brilliant.org",
            "datacamp.com",
        }

        # Enhanced URL patterns that indicate paywall/subscription content
        # These patterns are designed to be more specific to avoid false positives
        PAYWALL_PATTERNS = [
            "/subscribe",
            "/subscription",
            "/premium",
            "/member",
            "/membership",
            "/paywall",
            "/paid",
            "/pro/",
            "/plus",
            "/upgrade",
            "/billing",
            "/checkout",
            "/payment",
            "/purchase",
            "/buy",
            "/pricing",
            "/plans",
            "/tiers",
            "/unlock",
            "/access",
            "/exclusive",
            "/vip",
            "/elite",
            "/gold",
            "/platinum",
            "/diamond",
            "/signin",
            "/login",
            "/register",
            "/signup",
            "/join",
            "/trial",
            "/demo",
            "/preview",
            "/teaser",
            "/excerpt",
            # More specific patterns to avoid false positives with filenames
            "?pro=",
            "&pro=",
            "/pro?",
            "/pro&",
            "/pro#",
            "plan=pro",
            "tier=pro",
            "subscription=pro",
        ]

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Primary method: Check for exact domain match
        if domain in PAYWALL_DOMAINS:
            print(f"[INFO] Paywall detected for {url}: Known paywall domain ({domain})")
            return True

        # Check for subdomain matches
        for paywall_domain in PAYWALL_DOMAINS:
            if domain.endswith(paywall_domain):
                print(
                    f"[INFO] Paywall detected for {url}: Subdomain of paywall domain ({paywall_domain})"
                )
                return True

        # Secondary method: URL pattern detection
        url_lower = url.lower()
        for pattern in PAYWALL_PATTERNS:
            if pattern in url_lower:
                print(f"[INFO] Paywall detected for {url}: URL pattern ({pattern})")
                return True

        # If domain-based detection didn't find paywall, it's likely clean
        print(f"[SUCCESS] No paywall detected for {url} (basic check)")
        return False

    except Exception as e:
        print(f"[ERROR] Basic paywall detection failed for {url}: {e}")

    # Final fallback to original detection method if available
    if not PAYWALL_DETECTION_AVAILABLE:
        return False

    try:
        if html_content:
            # Use HTML content if available
            result = detect_paywall_from_html(html_content, url)
        else:
            # Import and use the full detection method

            result = classify_page_access(url)

        # Check if the result indicates paywall or controlled access
        status = result.get("status", "").lower()
        if status in ["paywalled", "controlled_access"]:
            print(
                f"[INFO] Paywall detected for {url}: {result.get('reason', 'Unknown')}"
            )
            return True
        elif status == "unavailable":
            print(
                f"[INFO] Could not check paywall for {url}: {result.get('reason', 'Unknown')}"
            )
            return False
        else:
            print(f"[SUCCESS] No paywall detected for {url}")
            return False

    except Exception as e:
        print(f"[ERROR] Error detecting paywall for {url}: {e}")
        return False


def post_scraped_link(
    session_id: int,
    module_id: int,
    url_link: str,
    risk_category: str = None,
    is_paywall: bool = False,
    content_location: str = None,
    apa7: str = None,
    localurl: str = None,
    risk_score: float = None,
):
    """Sends a scanned link with metadata to the backend FastAPI scraper endpoint."""  # Default cleanup
    risk_category = risk_category or "unknown"
    content_location = "" if content_location in (None, "Unknown") else content_location

    # Singapore time
    sg = pytz.timezone("Asia/Singapore")
    formattedSGtime = datetime.now(sg)

    # Build payload
    payload = {
        "module_id": module_id,
        "session_id": session_id,
        "url_link": url_link,
        "scraped_at": formattedSGtime.isoformat(),
        "risk_category": risk_category,
        "is_paywall": is_paywall,
        "content_location": content_location,
        "apa7": apa7,
        "localurl": localurl,
    }

    if risk_score is not None:
        payload["risk_score"] = risk_score

    # POST to FastAPI
    try:
        response = requests.post("http://127.0.0.1:8000/scrapedcontents/", json=payload)
        response.raise_for_status()
        print(f"[SUCCESS] Link stored: {url_link}")
    except Exception as e:
        print(f"[ERROR] Failed to store link: {url_link} — {e}")


async def check_link_accessibility(url: str) -> Tuple[str, str]:
    """
    Checks if a website is accessible using httpx, with a fallback from HEAD to GET.

    Args:
        url: The URL to check.

    Returns:
        A tuple containing:
        - str: The accessibility status ('accessible', 'failed', 'unknown').
        - str: A message indicating the status or error.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            # 1. Try a HEAD request first (more efficient)
            try:
                response = await client.head(url, timeout=10, headers=headers)

                if 200 <= response.status_code < 400:
                    return "accessible", f"OK (Status: {response.status_code})"

                # For 4xx/5xx errors from HEAD, we'll fall back to GET to be sure.
                print(
                    f"[INFO] HEAD request for {url} returned {response.status_code}. Falling back to GET."
                )

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadTimeout):
                print(
                    f"[INFO]  HEAD request for {url} timed out or failed. Falling back to GET."
                )
            except httpx.RequestError as e:
                print(
                    f"[INFO]  HEAD request for {url} failed: {e}. Falling back to GET."
                )

            # 2. Fallback to GET request if HEAD fails or returns an error
            try:
                response = await client.get(url, timeout=15, headers=headers)

                if 200 <= response.status_code < 400:
                    return "accessible", f"OK (Status: {response.status_code})"
                else:
                    return "failed", f"HTTP Error {response.status_code}"

            except httpx.TimeoutException:
                return "failed", "Request timed out"
            except httpx.ConnectError:
                return "failed", "Connection error"
            except httpx.RequestError as e:
                # This catches a wide range of other request-related issues
                error_type = type(e).__name__
                return "failed", f"Request failed: {error_type}"

    except Exception as e:
        # Catch-all for unexpected errors
        return "unknown", f"An unexpected error occurred: {str(e)}"


async def handle_login_flow(page: Page):
    """Handles Moodle login using credentials and captures screenshots if enabled."""

    print("Starting login flow...")
    if DEBUG_MODE:
        print("USERNAME:", USERNAME)
        print("PASSWORD:", PASSWORD)

    if "login" in page.url:
        print("Login page detected.")

        # Ensure full page load before interacting
        await page.wait_for_load_state("networkidle")
        await page.wait_for_selector('input[name="username"]')
        await page.wait_for_selector('input[name="password"]')

        # Screenshot before filling (if enabled)
        if SAVE_SCREENSHOTS:
            await page.screenshot(path="step1_login_page.png")

        # Fill credentials
        await page.fill('input[name="username"]', USERNAME or "")
        await page.fill('input[name="password"]', PASSWORD or "")

        # Screenshot after filling credentials (if enabled)
        if SAVE_SCREENSHOTS:
            await page.screenshot(path="step2_filled_credentials.png")

        # Try clicking the login button (supports both button types)
        try:
            await page.click('button[type="submit"]')
        except Exception:
            try:
                await page.click("input#loginbtn")
            except Exception as e:
                print(f"[INFO]  Could not click login button: {e}")
                if SAVE_SCREENSHOTS:
                    await page.screenshot(path="step2b_click_error.png")
                return

        # Wait for next page to load
        await page.wait_for_load_state("networkidle")
        if SAVE_SCREENSHOTS:
            await page.screenshot(path="step3_after_submit.png")

        # Check if login was successful
        if "login" in page.url:
            print("[ERROR] Login failed. Still on login page.")
            if DEBUG_MODE:
                html = await page.content()
                with open("login_failed_dump.html", "w", encoding="utf-8") as f:
                    f.write(html)
        else:
            print(f"[SUCCESS] Login successful. URL: {page.url}")
            if SAVE_SCREENSHOTS:
                await page.screenshot(path="step4_login_success.png")
    else:
        print("[INFO] Already logged in or no login required.")


async def expand_internal_toggles(page: Page):
    """Expands collapsible content sections in Moodle LMS coursee pages."""

    toggles = await page.query_selector_all(
        '#page-content a[data-for="sectiontoggler"]'
    )

    if not toggles:
        print("[INFO] No section toggles found.")
        return

    for toggle in toggles:
        try:
            is_expanded = await toggle.get_attribute("aria-expanded")
            if is_expanded == "false":
                await toggle.click()
                print("[INFO] Toggle clicked to expand section.")
            else:
                print("[INFO] Section already expanded. Skipping.")
        except Exception as e:
            print(f"[ERROR] Failed to handle toggle: {e}")


async def get_content_type_with_playwright(context, url: str) -> str:
    """Captures the MIME type of a resource by intercepting browser responses."""
    content_type_result = "unknown"
    page = await context.new_page()

    def handle_response(response):
        nonlocal content_type_result
        if response.url == url:
            headers = response.headers
            content_type_result = headers.get("content-type", "unknown")

    page.on("response", handle_response)

    try:
        await page.goto(url, wait_until="load", timeout=60000)
    except Exception as e:
        if "net::ERR_ABORTED" not in str(e) and "pluginfile.php" not in url:
            print(f"[INFO] Failed to load {url} — {e}")
    finally:
        await page.close()

    return content_type_result


async def storeTempRepoWithPlaywright(
    page: Page, url: str, ftype: str, downloaded_files: set
) -> str | None:
    """Downloads and stores non-HTML external files to the toProcessFurther directory using Playwright."""

    if is_possibly_malicious(url, ftype):
        print(f"[INFO] Skipped potentially dangerous file: {url} ({ftype})")
        return None

    if not ftype.startswith("text/html"):
        try:
            # --- Extract filename from URL ---
            parsed_url = urlparse(url)
            raw_name = os.path.basename(parsed_url.path)
            raw_name = unquote(raw_name)  # Decode URL-encoded characters

            # Fallback if filename is empty or doesn't have an extension
            if not raw_name or "." not in raw_name:
                extension = getFileExtension(ftype)
                raw_name = f"downloaded_file{extension}"

            # Remove any potential directory traversal characters
            filename = os.path.basename(raw_name)

            # Check if this file has already been downloaded
            file_key = f"{filename}_{ftype}"
            if file_key in downloaded_files:
                print(f"[INFO] SKIP: {filename} already downloaded")
                return None

            # Add to downloaded files set
            downloaded_files.add(file_key)

            response = await page.request.get(url)
            if response.status != 200:
                print(f"[ERROR] Response error: {response.status} for {url}")
                return None

            target_dir = os.path.join("scraper", "scraper", "toProcessFurther")
            os.makedirs(target_dir, exist_ok=True)
            save_path = os.path.join(target_dir, filename)

            # Save the file content
            content = await response.body()
            with open(save_path, "wb") as f:
                f.write(content)

            print(f"[SAVED] SAVED: {url} → {save_path}")
            return save_path

        except Exception as e:
            print(f"[ERROR] Failed to download via Playwright: {url} — {e}")
            return None


async def resolve_final_resource_url(page: Page, url: str) -> str | None:
    """
    Resolves the actual file URL behind a Moodle resource link.
    Attempts Method 2 (network request capture) and Method 1 (download trigger).
    Returns the final resolved URL or None if unresolved.
    """
    file_extensions = [
        ".pdf",
        ".docx",
        ".pptx",
        ".zip",
        ".doc",
        ".ppt",
        ".xls",
        ".xlsx",
    ]

    def is_file_request(u: str) -> bool:
        return any(ext in u.lower() for ext in file_extensions)

    print(f"\n[INFO] Resolving Moodle resource URL: {url}")

    # --- Method 2: Capture file-type request from network ---
    print("[INFO] [Method 2] Checking for direct file requests...")
    try:
        async with page.expect_request(
            lambda r: is_file_request(r.url), timeout=8000
        ) as req_info:
            try:
                await page.goto(url, wait_until="commit")
            except:
                print(
                    "[DEBUG] Navigation did not fully complete — possibly redirected to a file."
                )
        request = await req_info.value
        print("[RESOLVED] Method 2 successful: File request captured")
        print(f"[RESOLVED] Final URL: {request.url}")
        return request.url
    except:
        print("[DEBUG] No direct file request observed during Method 2.")

    # --- Method 1: Detect triggered download ---
    print("[INFO] [Method 1] Checking for download behavior...")
    try:
        async with page.expect_download(timeout=10000) as download_info:
            try:
                await page.goto(url, wait_until="commit")
            except:
                print(
                    "[DEBUG] Navigation was interrupted — download may have triggered."
                )
        download = await download_info.value
        print("[RESOLVED] Method 1 successful: File download detected")
        print(f"[RESOLVED] Final URL: {download.url}")
        return download.url
    except:
        print("[DEBUG] No download behavior detected during Method 1.")

    print("[INFO] No file URL could be resolved from this resource.")
    return None


EXCLUDED_FULL_URL_KEYWORDS = [
    "login",  # generic
    "signin",  # often used in Google/Outlook
    "auth",  # e.g., /auth/session
    "microsoftonline",  # specific
    "accounts.google.com",
    "teams.microsoft.com/light-meetings",
    "teams.microsoft.com/meeting",
]


def is_blocked_url(url: str) -> bool:
    """Checks if a URL matches any known blocked patterns or domains."""

    decoded_url = unquote(url.lower())

    # [BLOCKED] Microsoft Teams
    if "teams.microsoft.com" in decoded_url:
        print(f"[BLOCKED LINKS] Skipped teams link: {url}")
        return True

    # [BLOCKED] TinyMCE Powered-by banner
    parsed = urlparse(decoded_url)
    if parsed.netloc.endswith("tiny.cloud") and parsed.path.startswith(
        "/powered-by-tiny"
    ):
        print(f"[BLOCKED LINKS] Skipped TinyMCE tracking link: {url}")
        return True

    # [BLOCKED] Other configured keywords
    return any(keyword in decoded_url for keyword in EXCLUDED_FULL_URL_KEYWORDS)


def is_valid_url(url: str) -> bool:
    """
    Performs comprehensive validation on a URL to filter out malformed,
    unwanted, or injected links before they are processed.
    """
    if not url or not url.strip():
        return False

    url = url.strip()

    # 1. Reject trivial and malformed links
    if url == "#" or url.startswith("javascript:") or url.startswith("mailto:"):
        return False
    if url in ("http://", "https://"):
        print(f"[INFO] REJECTED (empty protocol): {url}")
        return False

    # 2. Reject URLs containing characters that indicate parsing errors (like from citations)
    if "(" in url or ")" in url:
        print(
            f"[INFO] REJECTED (contains parentheses, likely citation artifact): {url}"
        )
        return False

    # 3. Reject known injected URLs from browser extensions or other scripts
    try:
        parsed_url = urlparse(url)
        if parsed_url.hostname and "copilot.microsoft.com" in parsed_url.hostname:
            print(f"[INFO] REJECTED (injected by extension): {url}")
            return False
    except Exception:
        # If parsing fails, it's a bad URL
        print(f"[INFO] REJECTED (URL parsing failed): {url}")
        return False

    return True


async def extract_links(
    page: Page, base_url: str, session_id: int, module_id: int, downloaded_files: set
):
    """Extracts, classifies, and stores links found in a Moodle LMS coursee page."""
    await page.wait_for_selector("#region-main-box")
    anchors = await page.query_selector_all("#region-main-box a")

    links_to_crawl_further = []
    external_links = []
    collected_links = []
    seen_lms_links = set()

    print(f"\n[INFO] Starting extraction from: {base_url}")

    for anchor in anchors:
        try:
            if await anchor.get_attribute("data-region") == "post-action":
                continue

            href = await anchor.get_attribute("href")
            if not href or href.startswith("#") or href.startswith("/localrepo/"):
                continue

            class_attr = await anchor.get_attribute("class") or ""
            if "btn" in class_attr:
                continue

            scan_url = urljoin(base_url, href)
            collected_links.append({"url": scan_url})

        except Exception:
            continue

    for link_data in collected_links:
        full_url = link_data["url"]

        if not is_valid_url(full_url):
            continue
        if full_url in seen_lms_links:
            continue
        seen_lms_links.add(full_url)

        if is_blocked_url(full_url):
            print(f"[BLOCKED] Skipped due to known pattern: {full_url}")
            continue

        if is_external_link(full_url):
            print(f"[EXTERNAL] {full_url}")
            status, reason = await check_link_accessibility(full_url)
            print(f"    Accessibility: {status} | Paywall: checking...")

            is_paywall = detect_paywall_for_url(full_url)
            print(f"[DEBUG] Paywall result: {'Yes' if is_paywall else 'No'}")

            risk_score = -1 if is_paywall else None
            risk_category = "PAYWALL" if is_paywall else None
            external_links.append(full_url)

            post_scraped_link(
                session_id=session_id,
                module_id=module_id,
                url_link=full_url,
                is_paywall=is_paywall,
                content_location=base_url,
                risk_score=risk_score,
                risk_category=risk_category,
            )
            continue

        if "mod/resource/view.php" in full_url:
            try:
                resolved_url = await resolve_final_resource_url(page, full_url)
                if not resolved_url:
                    continue
                if is_blocked_url(resolved_url):
                    print(f"[BLOCKED] Resolved URL blocked: {resolved_url}")
                    continue

                print(f"[RESOLVED FILE] {resolved_url} (via: {full_url})")

                if is_external_link(resolved_url):
                    print(f"[EXTERNAL] Resolved external file URL")
                    status, reason = await check_link_accessibility(resolved_url)
                    is_paywall = detect_paywall_for_url(resolved_url)
                    print(f"[DEBUG] Paywall result: {'Yes' if is_paywall else 'No'}")

                    risk_score = -1 if is_paywall else None
                    risk_category = "PAYWALL" if is_paywall else None
                    external_links.append(resolved_url)

                    post_scraped_link(
                        session_id=session_id,
                        module_id=module_id,
                        url_link=resolved_url,
                        is_paywall=is_paywall,
                        risk_score=risk_score,
                        risk_category=risk_category,
                        content_location=base_url,
                    )
                    continue

                if should_exclude_url(resolved_url):
                    print(f"[SKIPPED] Internal URL excluded: {resolved_url}")
                    continue

                mime_type = await get_content_type_with_playwright(
                    page.context, resolved_url
                )
                print(f"[INFO] MIME type: {mime_type} — {resolved_url}")

                if mime_type.startswith("text/html"):
                    links_to_crawl_further.append(resolved_url)
                else:
                    if not is_possibly_malicious(resolved_url, mime_type):
                        await storeTempRepoWithPlaywright(
                            page, resolved_url, mime_type, downloaded_files
                        )

            except Exception as e:
                print(f"[ERROR] Failed to resolve file: {e}")
            continue

        if should_exclude_url(full_url):
            print(f"[SKIPPED] Internal URL excluded: {full_url}")
            continue

        mime_type = await get_content_type_with_playwright(page.context, full_url)
        print(f"[INTERNAL] {mime_type} — {full_url}")

        if not is_possibly_malicious(full_url, mime_type):
            await storeTempRepoWithPlaywright(
                page, full_url, mime_type, downloaded_files
            )
            print(f"[SAVED] Internal file stored: {full_url}")

        if mime_type.startswith("text/html"):
            if (
                "moodleprod.murdoch.edu.au" in full_url
                and "10.51.33.25" not in full_url
            ):
                print(f"[SKIPPED] External Murdoch domain inaccessible: {full_url}")
            else:
                links_to_crawl_further.append(full_url)

    print("\n[SUMMARY] Link extraction complete.")
    print(f"   - Internal HTML pages queued for crawl: {len(links_to_crawl_further)}")
    print(f"   - External links found: {len(external_links)}")
    print(f"   - Source page: {base_url}\n")

    return links_to_crawl_further


async def crawl_page(
    page: Page, url: str, session_id: int, module_id: int, downloaded_files: set
):
    """Navigates to a Moodle LMScourse page, performs login if encountered, and extracts  links."""

    print(f"[INFO] Visiting: {url}")
    try:
        await page.goto(url, wait_until="load")
    except:
        print(f"[ERROR] Failed to load: {url}")
        return []
    # to disable JS injection in moodle to point remote content to stored material in local repository
    # and the paywall alert script
    await page.evaluate(
        """
        const script = document.getElementById('lmsguardian-link-rewriter');
        if (script) {
            script.remove();
        }
    """
    )

    if "login" in page.url or "Continue" in await page.content():
        await handle_login_flow(page)
        await page.goto(url, wait_until="load")  # reload after login

    course_id = await page.evaluate(
        """() => {
            if (window.M && M.cfg && M.cfg.courseId) {
                return M.cfg.courseId;
            }
            return null;
        }"""
    )

    if course_id is None or course_id != module_id + 1:
        print(f"No M.cfg.courseId found — treating as external link.")
        return []

    print(f"Course ID (from M.cfg): {course_id}")

    await expand_internal_toggles(page)
    return await extract_links(page, url, session_id, module_id, downloaded_files)


async def run_crawler(starting_page: str, session_id: int, module_id: int):
    """Main crawler loop that visits internal pages and extracts links."""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=HEADLESS_BROWSER)
        context = await browser.new_context(ignore_https_errors=True)
        context.set_default_timeout(BROWSER_TIMEOUT)
        page = await context.new_page()

        pages_to_check = [starting_page]
        pages_already_seen = set()
        pages_visited = []
        downloaded_files = set()

        while pages_to_check:
            current_page = pages_to_check.pop(0)
            clean_page_url = normalize_url(current_page)

            if clean_page_url in pages_already_seen:
                continue

            pages_already_seen.add(clean_page_url)
            print(f"[CHECK] {current_page}")

            try:
                found_links = await crawl_page(
                    page, current_page, session_id, module_id, downloaded_files
                )
            except Exception as e:
                print(f"[ERROR] Failed to crawl {current_page}: {e}")
                continue

            pages_visited.append(current_page)

            for link in found_links:
                clean_link = normalize_url(link)
                if DEBUG_MODE:
                    print(f"[FOUND] Cleaned link: {clean_link}")
                if clean_link not in pages_already_seen:
                    pages_to_check.append(clean_link)

            await asyncio.sleep(CRAWLER_DELAY_SECONDS)

        await browser.close()

        # Document-based link processing
        await process_document_links(session_id, module_id)

        # Summary
        print("\n[SUCCESS] Crawling complete.")
        print(f"[SUMMARY] Summary for module_id: {module_id}\n")
        print("     Internal links that were expanded:")
        for url in pages_visited:
            print(f"   - {url}")

        try:
            response = requests.get("http://127.0.0.1:8000/scrapedcontents/scan")
            response.raise_for_status()
            data = response.json()
            external_links = [
                item.get("url_link")
                for item in data
                if item.get("module_id") == module_id
            ]
            print("\n   External links that were found:")
            if external_links:
                for url in external_links:
                    print(f"   - {url}")
            else:
                print("   (none)")
        except requests.exceptions.RequestException as e:
            print(f"\n[ERROR] Failed to fetch external link data: {e}")


async def process_document_links(session_id: int, module_id: int):
    """Process links found inside downloaded documents."""
    downloaded_links = downloadFilesAndCheck()
    seen_links = set()

    print(f"\n  Processing {len(downloaded_links)} document links (deduplicated)")

    for link in downloaded_links:
        normalized = normalize_url(link)

        if not is_valid_url(normalized):
            continue

        if is_external_link(normalized):
            if normalized in seen_links:
                print(f"[DUPLICATE SKIPPED] Already processed: {normalized}")
                continue
            seen_links.add(normalized)

            print(f"[FROM DOCUMENT] External link detected → posting: {normalized}")

            try:
                status, reason = await check_link_accessibility(normalized)
                is_paywall = detect_paywall_for_url(normalized)
                risk_score = -1 if is_paywall else None
                risk_category = "PAYWALL" if is_paywall else None

                post_scraped_link(
                    session_id,
                    module_id,
                    normalized,
                    is_paywall=is_paywall,
                    risk_score=risk_score,
                    risk_category=risk_category,
                    content_location="Document Scan",
                )
            except Exception as e:
                print(f"[ERROR] Failed to post document link {normalized}: {e}")
        else:
            print(f"[SKIP] Internal or Murdoch-owned link → ignored: {normalized}")
