import re
import requests
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import urllib3

import subprocess
import os
import platform
import requests
from urllib.parse import urlparse, quote
import json
from collections import defaultdict


def generate_apa7_citation(url: str, scraped_date: str = None) -> str:
    """Generate APA7 citation for a URL"""
    try:
        # Parse URL for basic info
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "")

        # Determine file type
        file_extension = None
        for ext in [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]:
            if ext.lower() in url.lower():
                file_extension = ext
                break

        # Improved title extraction from URL path
        title = "Untitled Document"
        author = None
        pub_date = None

        # Extract potential publication year from URL path first
        url_year = None
        # Look for year patterns in the URL path (e.g., /2018/08/, /2016/, etc.)
        year_patterns = [
            r"/(\d{4})/",  # /2018/
            r"/(\d{4})-",  # /2018-
            r"(\d{4})\.",  # 2018.pdf
            r"(\d{4})guide",  # 2016guide
            r"project(\d{4})",  # project2016
            r"(\d{4})report",  # 2018report
            r"-(\d{4})-",  # -2020-
            r"(\d{4})$",  # ends with year
        ]

        for pattern in year_patterns:
            match = re.search(pattern, url.lower())
            if match:
                year = int(match.group(1))
                # Only accept reasonable publication years (1990-current year)
                if 1990 <= year <= datetime.now().year:
                    url_year = year
                    break

        # Extract title from URL path as fallback
        path_parts = parsed_url.path.split("/")
        if path_parts:
            filename = path_parts[-1]
            if filename and "." in filename:
                # Clean up filename to make a better title
                title = (
                    filename.split(".")[0].replace("-", " ").replace("_", " ").title()
                )

                # If we found a year in URL, remove it from title to avoid duplication
                if url_year:
                    # Remove year patterns from title more thoroughly
                    year_str = str(url_year)
                    title = re.sub(rf"{year_str}", "", title).strip()
                    title = re.sub(
                        r"Project\s*", "Project ", title, flags=re.IGNORECASE
                    )  # Clean up "Project" spacing
                    title = re.sub(
                        r"Analysis\s*", "Analysis ", title, flags=re.IGNORECASE
                    )  # Clean up "Analysis" spacing
                    title = re.sub(
                        r"Report\s*$", "", title, flags=re.IGNORECASE
                    )  # Remove trailing "Report"
                    title = re.sub(r"\s+", " ", title)  # Clean up extra spaces
                    title = title.strip()

                # Clean up common patterns
                title = re.sub(r"[^\w\s\-\.\,\:\;\(\)]", "", title)
                if len(title) > 80:
                    title = title[:77] + "..."

        # Enhanced metadata extraction with better error handling
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # Disable SSL warnings for this request
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.get(url, headers=headers, timeout=8, verify=False)

            if response.status_code == 200 and "text/html" in response.headers.get(
                "content-type", ""
            ):
                soup = BeautifulSoup(response.content, "html.parser")

                # Extract title with better cleaning
                title_tag = soup.find("title")
                if title_tag and title_tag.get_text().strip():
                    extracted_title = title_tag.get_text().strip()
                    # Clean up title
                    extracted_title = re.sub(r"\s+", " ", extracted_title)
                    extracted_title = re.sub(
                        r"[^\w\s\-\.\,\:\;\(\)]", "", extracted_title
                    )
                    if (
                        len(extracted_title) > 5
                        and "untitled" not in extracted_title.lower()
                    ):
                        title = (
                            extracted_title[:100] + "..."
                            if len(extracted_title) > 100
                            else extracted_title
                        )

                # Extract author from various meta tags
                for author_selector in [
                    'meta[name="author"]',
                    'meta[name="dc.creator"]',
                    'meta[property="article:author"]',
                    ".author",
                    ".byline",
                ]:
                    author_elem = soup.select_one(author_selector)
                    if author_elem:
                        if author_elem.name == "meta":
                            author = author_elem.get("content", "").strip()
                        else:
                            author = author_elem.get_text().strip()
                        if author:
                            break

                # Extract publication date
                for date_selector in [
                    'meta[name="dc.date"]',
                    'meta[property="article:published_time"]',
                    'meta[name="pubdate"]',
                    "time[datetime]",
                ]:
                    date_elem = soup.select_one(date_selector)
                    if date_elem:
                        if date_elem.name == "meta":
                            pub_date = date_elem.get("content", "").strip()
                        else:
                            pub_date = (
                                date_elem.get("datetime")
                                or date_elem.get_text().strip()
                            )
                        if pub_date:
                            break

        except Exception as e:
            # Silently continue with URL-based title
            pass

        # Determine resource type for citation
        if file_extension:
            if file_extension.lower() == ".pdf":
                resource_type = "[PDF document]"
            else:
                resource_type = f"[{file_extension.upper().replace('.', '')} document]"
        elif any(edu_domain in domain for edu_domain in ["edu.au", ".edu"]):
            resource_type = "[Educational website]"
        elif any(
            keyword in url.lower() for keyword in ["research", "journal", "academic"]
        ):
            resource_type = "[Research resource]"
        else:
            resource_type = "[Website]"

        # Use scraped date or current date for access date
        if scraped_date:
            try:
                access_date = datetime.fromisoformat(
                    scraped_date.replace("Z", "+00:00")
                )
                access_date_str = access_date.strftime("%B %d, %Y")
            except:
                access_date_str = datetime.now().strftime("%B %d, %Y")
        else:
            access_date_str = datetime.now().strftime("%B %d, %Y")

        # Properly format site name for APA7 (capitalize first letter)
        site_name = (
            domain.replace(".com", "")
            .replace(".au", "")
            .replace(".org", "")
            .replace(".edu", "")
            .replace(".gov", "")
            .title()
        )

        # Remove resource type from title if it's already mentioned
        if resource_type in title:
            title = title.replace(resource_type, "").strip()

        # Clean up title formatting
        title = re.sub(r"\s+", " ", title).strip()
        if not title.endswith("."):
            title += "."

        # Determine if we need "Retrieved" statement (only for likely-to-change content)
        needs_retrieved = any(
            keyword in url.lower()
            for keyword in ["news", "blog", "wiki", "forum", "comment", "social"]
        )

        # Generate APA7 citation based on available information
        if author and pub_date:
            # Full citation with author and date
            try:
                pub_year = re.search(r"(\d{4})", pub_date).group(1)
                if needs_retrieved:
                    citation = f"{author} ({pub_year}). {title} {site_name}. Retrieved {access_date_str}, from {url}"
                else:
                    citation = f"{author} ({pub_year}). {title} {site_name}. {url}"
            except:
                # If no pub_date year found, use URL year if available
                if url_year:
                    if needs_retrieved:
                        citation = f"{author} ({url_year}). {title} {site_name}. Retrieved {access_date_str}, from {url}"
                    else:
                        citation = f"{author} ({url_year}). {title} {site_name}. {url}"
                else:
                    if needs_retrieved:
                        citation = f"{author} (n.d.). {title} {site_name}. Retrieved {access_date_str}, from {url}"
                    else:
                        citation = f"{author} (n.d.). {title} {site_name}. {url}"
        elif author:
            # Citation with author but no date - use URL year if available
            if url_year:
                if needs_retrieved:
                    citation = f"{author} ({url_year}). {title} {site_name}. Retrieved {access_date_str}, from {url}"
                else:
                    citation = f"{author} ({url_year}). {title} {site_name}. {url}"
            else:
                if needs_retrieved:
                    citation = f"{author} (n.d.). {title} {site_name}. Retrieved {access_date_str}, from {url}"
                else:
                    citation = f"{author} (n.d.). {title} {site_name}. {url}"
        else:
            # Basic citation without author - use URL year if available
            if url_year:
                if needs_retrieved:
                    citation = f"{title} ({url_year}). {site_name}. Retrieved {access_date_str}, from {url}"
                else:
                    citation = f"{title} ({url_year}). {site_name}. {url}"
            else:
                if needs_retrieved:
                    citation = f"{title} (n.d.). {site_name}. Retrieved {access_date_str}, from {url}"
                else:
                    citation = f"{title} (n.d.). {site_name}. {url}"

        return citation

    except Exception as e:
        # Fallback citation if all else fails
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "")
        site_name = (
            domain.replace(".com", "")
            .replace(".au", "")
            .replace(".org", "")
            .replace(".edu", "")
            .replace(".gov", "")
            .title()
        )
        access_date_str = datetime.now().strftime("%B %d, %Y")

        # Only use retrieved if likely to change
        needs_retrieved = any(
            keyword in url.lower()
            for keyword in ["news", "blog", "wiki", "forum", "comment", "social"]
        )
        if needs_retrieved:
            return (
                f"Resource (n.d.). {site_name}. Retrieved {access_date_str}, from {url}"
            )
        else:
            return f"Resource (n.d.). {site_name}. {url}"


SINGLEFILE_PATH = "/usr/bin/single-file"
BASE_FOLDER = "/var/www/html/localrepo"


os.makedirs(BASE_FOLDER, exist_ok=True)
API_BASE = "http://127.0.0.1:8000"


def get_chrome_path():
    """Returns the system-specific path to the Chrome browser executable."""

    return (
        "/usr/bin/google-chrome"
        if platform.system() != "Windows"
        else r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )


# def sanitize_filename(s):
#     """Clean filename for filesystem safety"""
#     return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)


def save_pdf_file(url, scraped_id, module_info):
    """Downloads a PDF from the given URL and saves it to the appropriate local repository path."""

    module_id = module_info.get("module_id", "UNKNOWN")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Create subpath ONLY under /var/www/html/localrepo
    relative_path = f"module_{module_id}/{timestamp}/{scraped_id}"
    base_path = os.path.join(BASE_FOLDER, relative_path)  # Absolute path
    os.makedirs(base_path, exist_ok=True)

    filename = os.path.join(base_path, "document.pdf")
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, stream=True, timeout=10, headers=headers)
        response.raise_for_status()

        with open(filename, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print(f"[INFO] PDF saved at: {filename}")
        return f"localrepo/{relative_path}"  # Correct relative URL for rewriting
    except Exception as e:
        print(f"[ERROR] PDF download failed: {e}")
        return None


def save_page_with_singlefile(url, scraped_id, module_info):
    """Uses the SingleFile  to save a webpage as a single HTML file to the local repo."""

    module_id = module_info.get("module_id", "UNKNOWN")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Store under /var/www/html/localrepo/...
    relative_path = f"module_{module_id}/{timestamp}/{scraped_id}"
    base_path = os.path.join(BASE_FOLDER, relative_path)
    os.makedirs(base_path, exist_ok=True)

    output_path = os.path.join(base_path, "index.html")
    chrome_path = get_chrome_path()

    command = [
        SINGLEFILE_PATH,
        url,
        output_path,
        "--browser-executable-path",
        chrome_path,
        "--max-resource-size-enabled",
        "--max-resource-size",
        "10",
    ]

    try:
        subprocess.run(command, check=True, timeout=30)
        print(f"    [INFO]HTML saved at: {output_path}")
        return f"localrepo/{relative_path}"  # Relative to /var/www/html
    except Exception as e:
        print(f"[ERROR] HTML save failed: {e}")
        return None


# def download_all_safe_links():
#     """Fetches and prints all safe links grouped by module using the backend API."""

#     safe_links = getAllSafeLinks()
#     if not safe_links:
#         print("[INFO] No safe links found.")
#         return

#     # Group links by module_id
#     grouped = defaultdict(list)
#     for link in safe_links:
#         module_id = link.get("module_id", "UNKNOWN")
#         grouped[module_id].append(link)

#     # Print links per module
#     for module_id, links in grouped.items():
#         try:
#             response = requests.get(f"{API_BASE}/modules/{module_id}", timeout=5)
#             if response.status_code == 200:
#                 module_data = response.json()
#                 unit_code = module_data.get("unit_code", f"MODULE_{module_id}")
#                 module_full_name = module_data.get(
#                     "module_full_name", f"Module {module_id}"
#                 )
#             else:
#                 unit_code = f"MODULE_{module_id}"
#                 module_full_name = (
#                     f"Module {module_id} (API ERROR {response.status_code})"
#                 )
#         except Exception as e:
#             unit_code = f"MODULE_{module_id}"
#             module_full_name = f"Module {module_id} (API ERROR: {e})"

#         print(f"\n {unit_code} - {module_full_name}")
#         print(f"Safe links: {len(links)}")
#         for i, link in enumerate(links, 1):
#             print(f"  {i}. {link.get('url_link')}")

#     print(
#         f"\n[SUCCESS] Printed {len(safe_links)} safe links across {len(grouped)} modules."
#     )


def getAllSafeLinks(include_paywalled=False, min_score=0):
    """Retrieves all links with non-negative risk scores from the backend, optionally including paywalled links."""

    try:
        response = requests.get(f"{API_BASE}/scrapedcontents/scan")
        response.raise_for_status()
        all_links = response.json()

        safe_links = []
        skipped_low_score = 0
        skipped_paywall = 0

        for link in all_links:
            score = link.get("risk_score", -1)
            paywalled = link.get("is_paywall", False)

            if score < min_score:
                skipped_low_score += 1
                continue

            if paywalled and not include_paywalled:
                skipped_paywall += 1
                continue

            safe_links.append(link)
        return safe_links

    except Exception as e:
        print(f"[ERROR] Failed to fetch safe links: {e}")
        return []


# def clean_and_validate_url(url):
#     """Clean and validate URL before processing"""
#     if not url or not isinstance(url, str):
#         return None

#     # Remove extra parentheses and trailing dots
#     url = re.sub(r"^\(+|\)+$|^\s+|\s+$", "", url)
#     url = re.sub(r"[.)]+$", "", url)

#     # Skip complex text that contains URLs but isn't a URL itself
#     if any(
#         word in url.lower()
#         for word in ["available from", "ontario, canada", "university of"]
#     ):
#         return None

#     # Skip obviously invalid URLs
#     if url in ["https://", "http://", "", "www.", "."]:
#         return None

#     # Add protocol if missing
#     if url.startswith("www."):
#         url = "https://" + url
#     elif not url.startswith(("http://", "https://")):
#         url = "https://" + url

#     # Basic URL validation - must have domain with at least one dot
#     if not re.match(r"^https?://[^/]+\.[^/]+", url):
#         return None

#     return url


def process_and_download_unique_safe_links():
    """Processes all unique safe links by downloading and updating local storage paths and syncing duplicates in the DB."""

    try:
        safe_links = getAllSafeLinks()  #
    except Exception as e:
        print(f"[ERROR] Failed to fetch safe links: {e}")
        return

    if not safe_links:
        print("[INFO] No safe links to process.")
        return

    grouped = defaultdict(list)
    for link in safe_links:
        module_id = link.get("module_id", "UNKNOWN")
        grouped[module_id].append(link)

    summary = []

    for module_id, links in grouped.items():
        print(f"\n MODULE {module_id} — {len(links)} links")

        seen = {}
        for link in links:
            url = link.get("url_link")
            scraped_id = link.get("scraped_id")
            title = link.get("title", "Untitled")
            if not url or not scraped_id:
                continue
            if url not in seen:
                seen[url] = {"primary": scraped_id, "title": title, "duplicates": []}
            else:
                seen[url]["duplicates"].append(scraped_id)

        for url, info in seen.items():
            primary_id = info["primary"]
            duplicates = info["duplicates"]
            title = info["title"]

            print(f"\n[INFO] Downloading scraped_id={primary_id}: {url}")

            # Build module info for metadata
            module_info = {
                "module_name": f"MODULE_{module_id}",
                "unit_code": f"MODULE_{module_id}",
                "module_full_name": f"Module {module_id}",
                "module_id": module_id,
                "content_type": "pdf" if ".pdf" in url.lower() else "html",
                "source_url": url,
                "title": title,
                "scraped_date": datetime.now().isoformat(),
            }

            # Call appropriate download method
            try:
                if ".pdf" in url.lower():
                    localurl = save_pdf_file(url, primary_id, module_info)
                else:
                    localurl = save_page_with_singlefile(url, primary_id, module_info)

                if not localurl:
                    print(f"[ERROR] Download failed for scraped_id={primary_id}")
                    continue
            except Exception as e:
                print(f"[ERROR] Error downloading scraped_id={primary_id}: {e}")
                continue

            print(f"  [SUCCESS] Saved at: {localurl}")

            # Update primary record
            try:
                encoded = quote(localurl, safe="")
                update_url = f"{API_BASE}/scrapedcontents/localurl/{primary_id}?localurl={encoded}"
                r = requests.put(update_url)
                r.raise_for_status()
                print(f"  [SUCCESS] Updated DB for primary {primary_id}")
            except Exception as e:
                print(f"[ERROR] Failed to update DB for primary {primary_id}: {e}")
                continue

            # Update duplicates
            for dup_id in duplicates:
                try:
                    update_url = f"{API_BASE}/scrapedcontents/localurl/{dup_id}?localurl={encoded}"
                    r = requests.put(update_url)
                    r.raise_for_status()
                    print(f"      Synced duplicate {dup_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to update duplicate {dup_id}: {e}")

            summary.append(
                {
                    "module_id": module_id,
                    "url": url,
                    "primary_id": primary_id,
                    "duplicates": duplicates,
                    "localurl": localurl,
                }
            )

    # Print summary
    print("\nSUMMARY:")
    for entry in summary:
        print(
            f"- Module {entry['module_id']} | Primary: {entry['primary_id']} | Duplicates: {len(entry['duplicates'])}"
        )
        print(f"  -> URL: {entry['url']}")
        print(f"  -> LocalURL: {entry['localurl']}")


if __name__ == "__main__":
    process_and_download_unique_safe_links()
