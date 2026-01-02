import json
import requests
import urllib.parse
import os
import time
from urllib.parse import urlparse
import base64
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.exceptions import SSLError, ConnectionError, Timeout
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv(override=True)
VT_API_KEY = (
    # os.getenv("VT_API_KEY")
    # or
    "f2ac01e460409228a6376e95732096b7e76f8c33df0f864b2be1f16325cbb1e9"
)
SAFE_BROWSING_API_KEY = os.getenv("GOOGLE_SAFE_KEY")

VT_URL_REPORT = "https://www.virustotal.com/vtapi/v2/url/report"
VT_URL_SCAN = "https://www.virustotal.com/api/v3/urls"
VT_DOMAIN_REPORT = "https://www.virustotal.com/api/v3/domains/"


def clean_and_validate_url(url: str) -> str:
    """Clean and validate URLs before processing"""
    if not url or not url.strip():
        return None

    # Remove extra characters and fix common issues
    url = url.strip()
    url = url.strip("()")  # Remove parentheses
    url = url.rstrip(".")  # Remove trailing periods

    # Skip URLs that are clearly text fragments, not actual URLs
    if any(
        keyword in url.lower()
        for keyword in [
            "ontario, canada:",
            "university of waterloo",
            "available from",
            "provides links to",
            "many organizations",
            "information systems audit",
            "hosts seminars",
            "source for recommended",
        ]
    ):
        return None

    url_pattern = r"https?://[^\s\)]+|www\.[^\s\)]+\.[a-zA-Z]{2,}"
    url_match = re.search(url_pattern, url)
    if url_match:
        url = url_match.group()

    # Fix common URL issues
    if url.startswith("www.") and not url.startswith("http"):
        url = "https://" + url

    # Skip obviously malformed URLs or text fragments
    if not url.startswith(("http://", "https://")):
        return None

    # Skip URLs that are clearly not actual websites
    if any(
        invalid in url.lower()
        for invalid in [
            "ontario,",
            "canada:",
            "university of",
            "available from",
            "provides links",
            "many organizations",
            "information systems",
        ]
    ):
        return None

    # Final validation
    try:
        parsed = urlparse(url)
        if not parsed.netloc or not parsed.scheme:
            return None

        # Check if domain looks valid
        if "." not in parsed.netloc:
            return None

        return url
    except Exception:
        return None


def check_safe_browsing(url):
    """Check URL against Google Safe Browsing API; inverts score if threat found"""
    print(SAFE_BROWSING_API_KEY)
    if not SAFE_BROWSING_API_KEY:
        print("[ERROR] Google Safe Browsing API key not found")
        return None

    payload = {
        "client": {"clientId": "lms-guardian", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
                "THREAT_TYPE_UNSPECIFIED",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        response = requests.post(
            f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={SAFE_BROWSING_API_KEY}",
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("matches"):
            threat_type = result["matches"][0].get("threatType", "MALICIOUS")
            print(f"[INFO] Google Safe Browsing detected threat: {threat_type}")

            # Map threat types to scores
            threat_scores = {
                "MALWARE": 95,
                "SOCIAL_ENGINEERING": 90,
                "UNWANTED_SOFTWARE": 80,
                "POTENTIALLY_HARMFUL_APPLICATION": 70,
                "THREAT_TYPE_UNSPECIFIED": 60,
            }

            score = threat_scores.get(threat_type, 85)
            category = f"GOOGLE_SAFE_BROWSING_{threat_type}"

            # Invert score if it's non-zero
            if score > 0:
                score = -score

            return (score, category)
        else:
            print("[SUCCESS] Google Safe Browsing: URL is clean")
            return (0, "GOOGLE_SAFE_BROWSING_CLEAN")

    except Exception as e:
        print(f"[ERROR] Safe Browsing error: {e}")
        return None


def vt_v3_get_url_info(url):
    """
    Get URL information from VirusTotal v3 API.
    Returns: (reputation, categories) tuple on success, None on failure
    """
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    endpoint = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    headers = {"x-apikey": VT_API_KEY}

    try:
        response = requests.get(endpoint, headers=headers, timeout=8)

        if response.status_code == 200:
            data = response.json()

            # Extract stats
            stats = data["data"]["attributes"].get("categories", {})
            malicious = data["data"]["attributes"]["last_analysis_stats"].get(
                "malicious", 0
            )
            reputation = -malicious  # Invert score if non-zero

            category_values = list(stats.values())
            categories = (
                ", ".join(category_values) if category_values else "UNCATEGORIZED"
            )

            print("\nVirusTotal URL Report")
            print(f"URL: {url}")
            print(f"Reputation Score: {reputation}")
            print(f"Categories: {categories}")

            return reputation, categories

        elif response.status_code in [404, 403, 429]:
            print(f"\nVirusTotal Error {response.status_code} for {url}")
            print(f"Response: {response.text}")
            return None

        else:
            print(f"\nUnexpected VirusTotal API Error for {url}")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"\nVirusTotal request failed for {url}: {e}")
        return None


def is_publicly_accessible(url: str) -> tuple[bool, bool]:
    """
    Returns (is_reachable, is_login_required)
    - is_reachable: True if the URL responded with a valid status
    - is_login_required: True if URL or any redirect appears to lead to a login page
    """
    login_keywords = ["login", "signin", "auth", "session", "noauth", "login.aspx"]

    try:
        # Follow redirects to get the final landing page
        response = requests.get(url, allow_redirects=True, timeout=5)
        final_url = response.url.lower()
        status = response.status_code

        # Check if final URL or redirect location contains login keywords
        if any(k in final_url for k in login_keywords):
            return (True, True)

        # If 200 OK and no login-related patterns, assume it's public
        if status == 200:
            return (True, False)

        # Redirects without login hint (optional)
        if status in (301, 302):
            location = response.headers.get("location", "").lower()
            if any(k in location for k in login_keywords):
                return (True, True)
            return (True, False)

        # Other unexpected status codes
        return (False, False)

    except requests.exceptions.SSLError as e:
        print(f"SSL Error for {url}: {e}")
        try:
            # Try without SSL verification for problematic certificates
            response = requests.get(url, allow_redirects=True, timeout=5, verify=False)
            print(f"SSL verification bypassed for {url}")
            return (True, False)
        except requests.exceptions.RequestException:
            return (False, False)

    except requests.exceptions.Timeout as e:
        print(f" Timeout accessing {url}: {e}")
        return (False, False)

    except requests.exceptions.ConnectionError as e:
        print(f"Connection error for {url}: {e}")
        return (False, False)

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Connection failed for {url}: {e}")
        return (False, False)


def ipqualityscore_fallback(url: str):
    """Fallback to IPQualityScore when VirusTotal fails; returns (risk_score, category), with score inverted if non-zero."""
    try:
        print("[INFO] Switching to IPQualityScore API...")

        API_KEY = os.getenv(
            "IPQUALITYSCORE_API_KEY", "IYd59ukXZEz4gt6tr4wPApSUkxUa074n"
        )

        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url

        encoded_url = urllib.parse.quote_plus(clean_url)
        endpoint = (
            f"https://www.ipqualityscore.com/api/json/url/{API_KEY}/{encoded_url}"
        )
        response = requests.get(endpoint, timeout=20)

        if response.status_code == 200:
            result = response.json()
            print("[SUCCESS] IPQualityScore scan successful.")

            if result.get("success"):
                risk_score = result.get("risk_score", 0)

                # Map to category
                if risk_score >= 85:
                    category = "HIGH_RISK"
                elif risk_score >= 50:
                    category = "MEDIUM_RISK"
                elif risk_score >= 25:
                    category = "LOW_RISK"
                else:
                    category = "CLEAN"

                if result.get("malware"):
                    category += "_MALWARE"
                if result.get("phishing"):
                    category += "_PHISHING"
                if result.get("suspicious"):
                    category += "_SUSPICIOUS"

                # Invert score if it's non-zero
                if risk_score > 0:
                    risk_score = -risk_score

                print(
                    f"[INFO] IPQualityScore Result: Risk Score: {risk_score}, Category: {category}"
                )
                return (risk_score, category)
            else:
                error_msg = result.get("message", "Unknown error")
                print(f"[ERROR] IPQualityScore scan failed: {error_msg}")
                if "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
                    print("[ERROR] IPQualityScore daily quota exceeded")
                return None
        elif response.status_code == 429:
            print("[ERROR] IPQualityScore API quota exceeded")
            return None
        else:
            print(f"[ERROR] IPQualityScore API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"[ERROR] IPQualityScore fallback error: {e}")
        return None


def metadefender_fallback(url: str):
    """Final fallback to MetaDefender when VirusTotal and IPQualityScore fail using URL hash lookup."""
    try:
        print("[INFO] Switching to MetaDefender API...")

        API_KEY = os.getenv("METADEFENDER_API_KEY")
        if not API_KEY:
            print("[ERROR] MetaDefender API key not found in environment")
            return (-1, "API_KEY_MISSING")

        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url

        import hashlib

        headers = {"apikey": API_KEY}
        url_hash = hashlib.sha256(clean_url.encode()).hexdigest()
        print(f"[INFO] Looking up URL hash: {url_hash}")

        hash_endpoint = f"https://api.metadefender.com/v4/hash/{url_hash}"
        response = requests.get(hash_endpoint, headers=headers, timeout=8)

        if response.status_code == 200:
            data = response.json()

            if "scan_results" in data and "scan_details" in data["scan_results"]:
                scan_details = data["scan_results"]["scan_details"]
                total_engines = len(scan_details)
                threats_found = sum(
                    1 for engine in scan_details.values() if engine.get("threat_found")
                )

                if total_engines > 0:
                    risk_percentage = (threats_found / total_engines) * 100

                    if risk_percentage >= 50:
                        category = f"HIGH_RISK_MALWARE_{threats_found}_{total_engines}"
                    elif risk_percentage >= 25:
                        category = (
                            f"MEDIUM_RISK_MALWARE_{threats_found}_{total_engines}"
                        )
                    elif risk_percentage >= 10:
                        category = f"LOW_RISK_MALWARE_{threats_found}_{total_engines}"
                    else:
                        category = "CLEAN_VERIFIED"

                    print(
                        f"[SUCCESS] MetaDefender scan complete: {threats_found}/{total_engines} engines detected threats"
                    )
                    print(
                        f"[INFO] Risk Score: {risk_percentage:.1f}%, Category: {category}"
                    )

                    final_score = (
                        -risk_percentage if risk_percentage > 10 else risk_percentage
                    )
                    return (final_score, category)

                return (-1, "NO_ENGINES_AVAILABLE")

            return (
                -1,
                "NO_SCAN_DETAILS" if "scan_results" in data else "NO_SCAN_RESULTS",
            )

        elif response.status_code == 404:
            print("[INFO] URL not found in MetaDefender database (may be new/clean)")
            return (-1, "URL_NOT_IN_DATABASE")

        else:
            print(f"[ERROR] MetaDefender API error: {response.status_code}")
            if response.status_code == 429:
                print("[ERROR] MetaDefender API quota exceeded")
                return (-1, "QUOTA_EXCEEDED")
            return (-1, f"API_ERROR_{response.status_code}")

    except Exception as e:
        print(f"[ERROR] MetaDefender fallback error: {e}")
        return (-1, "FALLBACK_ERROR")


def is_valid_api_result(result) -> bool:
    """Check if API result is valid and usable"""
    if not result or not isinstance(result, tuple) or len(result) != 2:
        return False

    score, category = result
    return (
        isinstance(score, (int, float))
        and isinstance(category, str)
        and category.strip() != ""
    )


def preprocess_input(url, scrapeID, safe_update_risk, timeout=5):
    result = {
        "url": url,
        "domain": "",
        "is_edu_au": False,
        "is_accessible": False,
        "should_scan": False,
        "http_status": None,
        "notes": "",
    }

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        result["domain"] = domain

        if domain.endswith(".edu.au"):
            result["is_edu_au"] = True
            result["notes"] = "EDUCATION DOMAIN"
            safe_update_risk(scrapeID, -1, "EDUCATION DOMAIN", url, "System")
            return result

        # Try HEAD request — ignore SSL errors
        try:
            response = requests.head(
                url, allow_redirects=True, timeout=timeout, verify=False
            )
            if response.status_code == 405:
                response = requests.get(url, stream=True, timeout=timeout, verify=False)

            result["http_status"] = response.status_code
            result["is_accessible"] = response.status_code in [200, 301, 302]

        except SSLError:
            # SSL error, but still treat as accessible (if response is returned)
            result["http_status"] = "SSL_IGNORED"
            result["is_accessible"] = True
            result["notes"] = "SSL ERROR IGNORED"

        # Final scan decision
        if result["is_accessible"]:
            result["should_scan"] = True
        else:
            safe_update_risk(scrapeID, -1, "SITE UNREACHABLE", url, "System")

    except (ConnectionError, Timeout) as e:
        result["http_status"] = "CONNECTION_FAILED"
        result["notes"] = f"Site not reachable: {str(e)}"
        safe_update_risk(scrapeID, -1, "SITE UNREACHABLE", url, "System")

    return result


def analyze_links(scrapeID: int, url: str):
    def safe_update_risk(scrape_id, score, category, analyzed_url, engine):
        try:
            category = category[:300]
            update_url = f"http://127.0.0.1:8000/scrapedcontents/updaterisk/{scrape_id}"
            response = requests.put(
                update_url, params={"score": score, "category": category}
            )

            if response.status_code == 200:
                print(
                    f"[{engine}] UPDATE SUCCESS | ID={scrape_id} | SCORE={score} | CATEGORY={category} | URL={analyzed_url}"
                )
                print(f"[SUCCESS] Response: {response.json()}")
            else:
                print(
                    f"[{engine}] UPDATE FAILED | ID={scrape_id} | status={response.status_code} | URL={analyzed_url}"
                )
                print(f"[ERROR] Response: {response.text}")
        except Exception as e:
            print(f"[{engine}] ERROR during update for ID={scrape_id}: {e}")

    def check_nsfw_content(url_to_check: str) -> tuple:
        try:
            from content_filter import ContentFilter

            filter_obj = ContentFilter()
            is_nsfw, reason = filter_obj.is_pornography_url(url_to_check)
            confidence = 85 if is_nsfw else 0
            return is_nsfw, f"NSFW_{reason}" if is_nsfw else "SAFE", confidence
        except Exception:
            return False, "NSFW_CHECK_UNAVAILABLE", 0

    cleaned_url = clean_and_validate_url(url)
    if not cleaned_url:
        safe_update_risk(scrapeID, -1, "INVALID_URL", url, "System")
        return
    # TO STOP EDUCAITONAL DOMAINS AND SITE UNREACHABLE
    result = preprocess_input(url, scrapeID, safe_update_risk)

    if not result["should_scan"]:
        # Already handled by safe_update_risk inside preprocess_input
        return  # Do NOT continue to scanning APIs

    is_nsfw, nsfw_reason, nsfw_score = check_nsfw_content(cleaned_url)
    if is_nsfw:
        inversescore = -(nsfw_score)
        safe_update_risk(
            scrapeID, inversescore, nsfw_reason, cleaned_url, "JigsawStack"
        )
        return

    apis_in_order = [
        ("VirusTotal", vt_v3_get_url_info),
        ("IPQualityScore", ipqualityscore_fallback),
        ("MetaDefender", metadefender_fallback),
        ("Google Safe Browsing", check_safe_browsing),
    ]

    for engine, func in apis_in_order:
        try:
            result = func(cleaned_url)
            if is_valid_api_result(result):
                score, category = result
                safe_update_risk(scrapeID, score, category, cleaned_url, engine)
                return
        except Exception as e:
            print(f"[{engine}] ERROR during scan: {e}")

    safe_update_risk(
        scrapeID, -1, "UNKNOWN_ALL_APIS_FAILED", cleaned_url, "AllEnginesFailed"
    )


# def main():
#     print("🧪 Starting manual test of analyze_links()")

#     # Example test cases: (scrapeID, url)
#     test_cases = [
#         (5174, "https://coinlab.biz/"),
#         (5244, "https://www.coinlab.biz"),
#     ]

#     for scrape_id, test_url in test_cases:
#         print("\n" + "=" * 40)
#         print(f"🔗 Test URL: {test_url}")
#         analyze_links(scrape_id, test_url)
#         print("=" * 40)


if __name__ == "__main__":
    main()
