#!/usr/bin/env python3
"""
Minimal JigsawStack NSFW Detection Integration for LMS Guardian
Used only via enhanced_inappropriate_content_detection()
"""

import requests
import os
from typing import Tuple, Dict, Any
from urllib.parse import urlparse

# Load environment variable
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class JigsawStackNSFWDetector:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("JIGSAWSTACK_API_KEY")
        self.base_url = "https://api.jigsawstack.com/v1"
        self.headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def _text_based_nsfw_detection(
        self, url: str, title: str = "", content: str = ""
    ) -> Tuple[bool, str]:
        adult_keywords = [
            "porn",
            "xxx",
            "sex",
            "nude",
            "naked",
            "erotic",
            "hardcore",
            "nsfw",
            "sexual",
            "explicit",
            "mature",
            "fetish",
            "hentai",
            "orgasm",
            "masturbat",
            "cumshot",
            "blowjob",
            "escort",
            "strip",
        ]
        context_sensitive_keywords = {
            "anal": ["analysis", "analytical", "analog", "canal", "channel"],
        }

        url_lower = url.lower()
        for keyword in adult_keywords:
            if keyword in url_lower:
                if keyword in context_sensitive_keywords:
                    if not any(
                        word in url_lower
                        for word in context_sensitive_keywords[keyword]
                    ):
                        return True, f"Adult keyword in URL: {keyword}"
                else:
                    return True, f"Adult keyword in URL: {keyword}"

        if title:
            title_lower = title.lower()
            for keyword in adult_keywords:
                if keyword in title_lower:
                    if keyword in context_sensitive_keywords:
                        if not any(
                            word in title_lower
                            for word in context_sensitive_keywords[keyword]
                        ):
                            return True, f"Adult keyword in title: {keyword}"
                    else:
                        return True, f"Adult keyword in title: {keyword}"

        if content:
            content_lower = content.lower()
            count = sum(1 for kw in adult_keywords if kw in content_lower)
            if count >= 2:
                return True, f"Multiple adult keywords in content ({count} found)"

        return False, "No adult content detected in text analysis"


class EnhancedContentModerator:
    def __init__(self):
        self.jigsawstack = JigsawStackNSFWDetector()
        self.adult_domains = [
            "pornhub.com",
            "xvideos.com",
            "xhamster.com",
            "redtube.com",
            "tube8.com",
            "youporn.com",
            "spankbang.com",
            "xnxx.com",
            "chaturbate.com",
            "livejasmin.com",
            "cam4.com",
            "myfreecams.com",
            "onlyfans.com",
            "adultfriendfinder.com",
        ]

    def detect_inappropriate_content(
        self, url: str, title: str = "", content: str = "", api_category: str = ""
    ) -> Tuple[bool, str, int]:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if any(adult in domain for adult in self.adult_domains):
            return True, f"Known adult domain: {domain}", 95

        text_nsfw, text_reason = self.jigsawstack._text_based_nsfw_detection(
            url, title, content
        )
        if text_nsfw:
            confidence = (
                90
                if any(term in text_reason.lower() for term in ["business", "analysis"])
                else 60
            )
            return True, f"Text Analysis: {text_reason}", confidence

        if api_category:
            cat = api_category.lower()
            if any(
                nsfw in cat
                for nsfw in [
                    "adult",
                    "pornography",
                    "sex",
                    "adult content",
                    "sexually explicit",
                    "mature",
                    "nsfw",
                    "adult entertainment",
                    "erotic",
                    "xxx",
                    "nude",
                    "naked",
                    "hardcore",
                    "softcore",
                    "sexual",
                    "explicit",
                ]
            ):
                return True, f"API Category: {api_category}", 80

        return False, "Content appears appropriate", 0


def enhanced_inappropriate_content_detection(
    url: str, title: str = "", content: str = "", api_category: str = ""
) -> Tuple[bool, str]:
    moderator = EnhancedContentModerator()
    is_inappropriate, reason, confidence = moderator.detect_inappropriate_content(
        url, title, content, api_category
    )
    return is_inappropriate, f"{reason} (Confidence: {confidence}%)"
