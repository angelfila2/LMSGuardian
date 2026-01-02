import asyncio
import sys
import os
from scraper.crawler import run_crawler
from reputation.checker import analyze_links
from reportgenerator.report import (
    generate_and_send_module_reports,
    generate_and_send_module_reports_to_security_officer,
)
from scripts.discover_courses import (
    discover_courses,
    create_module,
    get_existing_modules,
    extract_unit_code,
)
import requests
from datetime import datetime, UTC
from collections import defaultdict
import pytz
import os
from dotenv import load_dotenv
import re
import downloadlocalAPA7.main as citation
import time

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


# Load environment variables
load_dotenv(override=True)


# Configuration from Environment Variables
def str_to_bool(value: str) -> bool:
    """
    Converts a string representation of a boolean value to a boolean type.

    Accepts common string variants for truthy values such as 'true', '1', 'yes', and 'on'
    (case-insensitive). All other values are considered False.

    Parameters:
        value (str): The string input to evaluate.

    Returns:
        bool: True if the input string is a recognized truthy value, otherwise False.

    Example:
        >>> str_to_bool("YES")
        True
        >>> str_to_bool("no")
        False
    """
    return value.lower() in ("true", "1", "yes", "on")


# setting up the configurations for debuggin
SCRAPE_ALL_COURSES = str_to_bool(os.getenv("SCRAPE_ALL_COURSES", "true"))
SINGLE_COURSE_MODULE_ID = int(os.getenv("SINGLE_COURSE_MODULE_ID", "2"))
GENERATE_REPORTS = str_to_bool(os.getenv("GENERATE_REPORTS", "true"))
SEND_EMAIL_REPORTS = str_to_bool(os.getenv("SEND_EMAIL_REPORTS", "true"))
DEBUG_MODE = str_to_bool(os.getenv("DEBUG_MODE", "false"))
AUTO_DISCOVER_COURSES = str_to_bool(os.getenv("AUTO_DISCOVER_COURSES", "false"))
ANALYSIS_TIMEOUT = int(os.getenv("ANALYSIS_TIMEOUT", "30"))  # 30 second timeout per URL
SKIP_SLOW_ANALYSIS = str_to_bool(
    os.getenv("SKIP_SLOW_ANALYSIS", "false")
)  # Skip slow URLs after timeout


def print_config():
    """Print current configuration from .env"""
    print("=== LMS Guardian Configuration (.env) ===")
    print(f"Scrape All Courses: {SCRAPE_ALL_COURSES}")
    if not SCRAPE_ALL_COURSES:
        print(f"   Single Course Module ID: {SINGLE_COURSE_MODULE_ID}")
    print(f"Generate Reports: {GENERATE_REPORTS}")
    print(f"Send Email Reports: {SEND_EMAIL_REPORTS}")
    print(f"Auto Discover Courses: {AUTO_DISCOVER_COURSES}")
    print(f"Debug Mode: {DEBUG_MODE}")

    # Show browser settings
    headless = str_to_bool(os.getenv("HEADLESS_BROWSER", "true"))
    browser_timeout = int(os.getenv("BROWSER_TIMEOUT", "60000"))
    crawler_delay = float(os.getenv("CRAWLER_DELAY_SECONDS", "0.5"))

    print(f"Browser Headless: {headless}")
    print(f"Browser Timeout: {browser_timeout}ms")
    print(f"Crawler Delay: {crawler_delay}s")
    print("=" * 45)


def getAllCourseId():
    """
    Retrieves all course/module IDs from the backend API.

    Sends a GET request to the /modules endpoint of the  FastAPI server.
    Returns the parsed JSON response if successful. If the request fails,
    logs the error and returns an empty list.

    Returns:
        list: A list of course/module data dictionaries from the API response.
              Returns an empty list if the request fails.

    Example:
        >>> getAllCourseId()
        [{'module_id': 1, 'module_name': 'ICT302'}, {'module_id': 2, 'module_name': 'ICT290'}]
    """
    try:
        res = requests.get("http://127.0.0.1:8000/modules")
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Failed to get module IDs: {e}")
        return []


def getRecentSessionScan():
    """
    Retrieves the most recent session scan data from the backend API.

    Sends a GET request to the /scrapedcontents/scan endpoint of the  FastAPI server.
    If the request is successful, returns the JSON response containing recently scanned links.
    On failure, logs an error message and returns an empty list.

    Returns:
        list: A list of scanned link records from the most recent session,
              or an empty list if the request fails.
    """
    try:
        res = requests.get("http://127.0.0.1:8000/scrapedcontents/scan")
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Failed to get recent session scan data: {e}")
        return []


def startsession():
    """
    Initiates a new scraper session by sending session metadata to the backend API.

    Constructs a payload containing the current UTC start time, a default status of "running",
    and no error logs. Sends this to the /scrapersession/newsession endpoint to add a new record to
    the scraper session table.

    Returns:
        int or None: The session ID assigned automatically the backend if successful, or None if the request fails.
    """
    payload = {
        "started_at": datetime.now(UTC).isoformat(),
        "completion_status": "running",
        "error_log": None,
    }
    try:
        res = requests.post(
            "http://127.0.0.1:8000/scrapersession/newsession", json=payload
        )
        res.raise_for_status()
        session_data = res.json()
        return session_data["session_id"]
    except Exception as e:
        print(f"Failed to create scraper session: {e}")
        return None


async def batchScrape():
    """Scrape all configured courses in the LMS and log results by session."""

    sessionId = startsession()
    if not sessionId:
        print("[ERROR] Failed to start session")
        return
    moduleIdList = getAllCourseId()
    if not moduleIdList:
        print("[INFO] No modules found in database")
        return

    print(f"[INFO] Found {len(moduleIdList)} courses to scrape")

    for module in moduleIdList:
        module_id = module["module_id"]
        course_id = module_id + 1  # Moodle course ID is module_id + 1
        unit_code = module.get("unit_code", f"Module_{module_id}")

        print(
            f"\n[INFO] Scraping {unit_code} (Module ID: {module_id}, Course ID: {course_id})"
        )

        base_url = f"http://10.51.33.25/moodle/course/view.php?id={course_id}"
        print(f"[STARTING POINT] URL: {base_url}")

        try:
            print(f"[INFO] Starting scrape for {unit_code} at {datetime.now()}")
            await run_crawler(base_url, sessionId, module_id)
            print(f"[SUCCESS] Completed scraping {unit_code} at {datetime.now()}")
        except Exception as e:
            print(f"[ERROR] Failed to scrape {unit_code}: {e}")

    print(f"\n[INFO] Batch scraping completed for {len(moduleIdList)} courses")


async def batchAnalyse():
    """Performs deduplicated URL reputation analysis for the latest scan session, skipping paywalled links and updating risk scores.
    Sents the filtered links to the external cyber reputation site to avoid unnecesary usage of the API calls.
    """
    scans = getRecentSessionScan()
    seen = set()
    unique_scans = []
    for scan in scans:
        url = scan["url_link"]
        if url not in seen:
            seen.add(url)
            unique_scans.append(scan)

    # Count total + duplicates
    total_count = len(scans)
    unique_url_count = len(unique_scans)
    duplicate_count = total_count - unique_url_count

    print(
        f"   Processing {total_count} total scans "
        f"({unique_url_count} unique URLs, {duplicate_count} duplicates ignored)"
    )

    # Sequentially analyze each unique URL
    for scan in unique_scans:
        is_paywall = scan["is_paywall"]
        url = scan["url_link"]

        print("=" * 50)
        print(f"URL: {url}")

        if is_paywall:
            print(
                "Link is paywall content. There is no need to send to reputation checker."
            )

            continue
        scrapeId = scan["scraped_id"]
        url = scan["url_link"]
        from urllib.parse import urlparse, urlunparse

        def normalize_url(url):
            parsed = urlparse(url)
            if not parsed.path or parsed.path.endswith("/"):
                return urlunparse(parsed._replace(path=parsed.path or "/"))
            elif "." not in parsed.path.split("/")[-1]:
                # if last segment has no dot (not a file), add slash
                return urlunparse(parsed._replace(path=parsed.path + "/"))
            return url  # already ends with a file extension

        normalizedurl = normalize_url(url)
        print(normalizedurl)

        print(f"[CURRENT CHECK] Analyzing URL: {url}")

        try:
            analyze_links(scrapeId, normalizedurl)  # Direct call to sync function
        except Exception as e:
            print(f"[ERROR] Error analyzing {url}: {e}")
            try:
                requests.put(
                    f"http://127.0.0.1:8000/scrapedcontents/updaterisk/{scrapeId}",
                    params={"score": 0, "category": "ANALYSIS_ERROR"},
                )
            except:
                pass


async def batchReport():
    """
    Report generation function. Does the following step:
    1. Generate and send email reports to unit coordinators
    2. Generate and email consolidated report to Security Officer

    """
    print("\n" + "=" * 60)
    print("Starting Module-Specific Report Generation")
    print("=" * 60 + "\n")

    # 📬 Unit Coordinators Report Generation
    print("Step 1: Generating and emailing reports to Unit Coordinators")
    print(" Only applicable for modules with flagged or unsafe links...\n")
    generate_and_send_module_reports()

    # 🔐 Security Officer Report Generation
    print("Step 2: Generating and emailing consolidated report to the Security Officer")
    print(" Includes all scanned modules and link classifications...\n")
    generate_and_send_module_reports_to_security_officer()

    print("[SUCCESS] Report generation process completed.\n")


async def batchSaveToLocal():
    """
    Function for downloading a snapshot of web content into local repository.
    Uses SingleFile library to download html snapshots. Once downloaded into local repository,
    generates APA7 citation for all records that have a corresponding saved local snapshot.


    """
    print("Running local page downloader...")
    citation.process_and_download_unique_safe_links()
    moduleIdList = getAllCourseId()
    if not moduleIdList:
        print("No modules found in database")
        return

    # print(f"[SAVE LOCAL] Found {len(moduleIdList)} courses to scrape")
    print("=" * 45)
    print("Generating citation for local save files")

    for module in moduleIdList:
        module_id = module["module_id"]
        allLocalAvailable = requests.get(
            f"http://127.0.0.1:8000/scrapedcontents/localcopyavailable/{module_id}"
        ).json()
        for link in allLocalAvailable:
            actualurl = link.get("url_link")
            scrapeid = link.get("scraped_id")
            citation_text = citation.generate_apa7_citation(actualurl)
            updatecitationapi = f"http://127.0.0.1:8000/scrapedcontents/updatecitation/{scrapeid}?citation={citation_text}"

            response = requests.put(updatecitationapi)

            if response.status_code == 200:
                print("[CITATION] Citation updated successfully:", response.json())
            else:
                print("[CITATION FAILED] Failed to update:", response.text)
    print("\n")
    print("=" * 45)


async def finalize_all_duplicate_updates():
    """
    Function called after batchAnalyse(). Since batchAnalyse() only sends unique links to conserve API calls,
    this function updates all other record's risk score and risk category with the same URL


    """
    scans = getRecentSessionScan()
    url_to_scans = {}

    # Step 1: Group scans by URL
    for scan in scans:
        url = scan["url_link"]
        url_to_scans.setdefault(url, []).append(scan)

    # Step 2: Process each group
    for url, scan_group in url_to_scans.items():
        if len(scan_group) <= 1:
            continue  # No duplicates, skip

        base_scan = None
        score = None
        category = None

        # Step 3: Find the first scan WITH risk_score and risk_category
        for scan in scan_group:
            try:
                response = requests.get(
                    f"http://127.0.0.1:8000/scrapedcontents/get/{scan['scraped_id']}"
                )
                if response.status_code == 200:
                    data = response.json()
                    s = data.get("risk_score")
                    c = data.get("risk_category")
                    if s is not None and c is not None:
                        base_scan = scan
                        score = s
                        category = c
                        break  # ✅ Found usable base
            except Exception as e:
                print(f"[ERROR] Error checking risk info for {scan['scraped_id']}: {e}")

        if base_scan is None:
            print(f"[INFO] No valid risk info found in duplicates for {url}")
            continue  # nothing to sync

        # Step 4: Update all other scans in the group to match the base
        for scan in scan_group:
            if scan["scraped_id"] == base_scan["scraped_id"]:
                continue  # skip base itself

            try:
                requests.put(
                    f"http://127.0.0.1:8000/scrapedcontents/updaterisk/{scan['scraped_id']}",
                    params={"score": score, "category": category},
                )
                print(f"[SUCCESS] Synced risk info to {scan['scraped_id']} for {url}")
            except Exception as e:
                print(f"[ERROR] Failed to update {scan['scraped_id']} for {url}: {e}")


def update_latest_session_status(status: str, error_log: str = None):
    try:
        # Step 1: Get latest session via API
        res = requests.get("http://10.51.33.25:8000/scrapersession/latest")
        res.raise_for_status()
        session = res.json()

        if not session:
            print("⚠️ No latest running session found.")
            return

        session_id = session["session_id"]

        # Step 2: Update the session status
        params = {"status": status}
        if error_log:
            params["error_log"] = error_log

        update_url = f"http://127.0.0.1:8000/scrapersession/update/{session_id}"
        update_res = requests.put(update_url, params=params)
        update_res.raise_for_status()

        print(f"[SUCCESS] Session {session_id} updated to status '{status}'")

    except Exception as e:
        print(f"[ERROR] Failed to update session status: {e}")


async def main():
    start_time = time.perf_counter()
    try:
        print("LMS Guardian has started...")
        await batchScrape()
        await batchAnalyse()
        await finalize_all_duplicate_updates()
        await batchSaveToLocal()
        await batchReport()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received — exiting gracefully.")
        update_latest_session_status(
            "failed", "Scraper terminated due to keyboard interrupt input"
        )
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        update_latest_session_status("failed", str(e))
    else:
        update_latest_session_status("completed")
    finally:
        elapsed = time.perf_counter() - start_time
        print(f"LMS Guardian completed in {elapsed:.2f} seconds.")


if __name__ == "__main__":
    asyncio.run(main())
