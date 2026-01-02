#!/usr/bin/env python3
"""
Content filtering utility for LMS Guardian
Detects and filters inappropriate content (pornography, paywall, etc.)
Enhanced with JigsawStack NSFW API (98% accuracy)
"""

from urllib.parse import urlparse
from typing import Tuple

# Import JigsawStack NSFW detector
try:
    from jigsawstack_nsfw_detector import enhanced_inappropriate_content_detection

    JIGSAWSTACK_AVAILABLE = True
except ImportError:
    JIGSAWSTACK_AVAILABLE = False
    print("JigsawStack NSFW detector not available. Using fallback detection.")


class ContentFilter:
    """Content filtering system for LMS Guardian"""

    def __init__(self):
        self.porn_keywords = [
            "porn",
            "pornography",
            "sex",
            "adult",
            "xxx",
            "explicit",
            "nude",
            "naked",
            "erotic",
            "sexual",
            "hardcore",
            "softcore",
            "mature",
            "nsfw",
            "adult entertainment",
            "adult content",
        ]
        self.porn_domains = [
            "xvideos.com",
            "pornhub.com",
            "xnxx.com",
            "redtube.com",
            "youporn.com",
            "tube8.com",
            "spankbang.com",
            "xhamster.com",
            "beeg.com",
            "tnaflix.com",
            "porn.com",
            "chaturbate.com",
            "cam4.com",
            "myfreecams.com",
            "livejasmin.com",
            "camsoda.com",
        ]

    def is_pornography_url(
        self, url: str, title: str = "", content: str = "", risk_category: str = ""
    ) -> Tuple[bool, str]:
        """Enhanced pornography detection using JigsawStack AI (98% accuracy)"""
        if not url:
            return False, ""

        if JIGSAWSTACK_AVAILABLE:
            try:
                is_inappropriate, reason = enhanced_inappropriate_content_detection(
                    url, title, content, risk_category
                )
                if is_inappropriate:
                    return True, f"JigsawStack AI: {reason}"
            except Exception as e:
                print(f"⚠️ JigsawStack detection failed: {e}")

        return self._legacy_pornography_detection(url, title, content, risk_category)

    def _legacy_pornography_detection(
        self, url: str, title: str = "", content: str = "", risk_category: str = ""
    ) -> Tuple[bool, str]:
        """Fallback multi-layer detection if AI unavailable"""
        if risk_category:
            category_lower = risk_category.lower()
            for porn_cat in self.porn_keywords:
                if porn_cat in category_lower:
                    return True, f"Pornographic category from API: {risk_category}"

        domain = urlparse(url).netloc.lower().replace("www.", "")
        if any(porn_domain in domain for porn_domain in self.porn_domains):
            return True, f"Pornographic domain detected: {domain}"

        url_lower = url.lower()
        if any(keyword in url_lower for keyword in self.porn_keywords):
            return True, f"Pornographic keyword in URL: {url}"

        if title and any(keyword in title.lower() for keyword in self.porn_keywords):
            return True, f"Pornographic keyword in title: {title[:50]}..."

        if content:
            content_lower = content.lower()
            porn_count = sum(
                1 for keyword in self.porn_keywords if keyword in content_lower
            )
            if porn_count >= 3:
                return (
                    True,
                    f"Multiple pornographic keywords in content ({porn_count} found)",
                )

        return False, ""


def main():
    test_url = "https://www.example.com"
    test_title = "Just a test page"
    test_content = ""
    test_risk_category = ""

    filter_obj = ContentFilter()
    is_nsfw, reason = filter_obj.is_pornography_url(
        url=test_url,
        title=test_title,
        content=test_content,
        risk_category=test_risk_category,
    )

    print("\n🔍 NSFW Detection Result")
    print("=======================")
    print(f"URL: {test_url}")
    print(f"NSFW Detected: {is_nsfw}")
    print(f"Reason: {reason or 'None'}")


if __name__ == "__main__":
    main()
