"""
Enhanced Paywall Detection System
Implements all 4 approaches for robust paywall detection:
1. Domain Lists (existing)
2. Heuristic-Based Scraping (enhanced)
3. Structured Data Analysis (JSON-LD)
4. Content Analysis (length, overlays, etc.)
"""

import json
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


class EnhancedPaywallDetector:
    """
    Comprehensive paywall detection using multiple approaches
    to minimize false positives and false negatives
    """
    
    def __init__(self):
        # Approach 1: Domain Lists (existing)
        self.known_paywall_domains = {
            # News & Media
            'wsj.com', 'ft.com', 'nytimes.com', 'bloomberg.com', 'economist.com',
            'washingtonpost.com', 'newyorker.com', 'theatlantic.com', 'thetimes.co.uk',
            'telegraph.co.uk', 'spectator.co.uk', 'foreignaffairs.com', 'harpers.org',
            
            # Academic & Professional
            'nature.com', 'science.org', 'jstor.org', 'ieee.org', 'acm.org',
            'springer.com', 'wiley.com', 'elsevier.com', 'cambridge.org', 'oxford.org',
            
            # Subscription Platforms
            'medium.com', 'substack.com', 'patreon.com', 'masterclass.com',
            'coursera.org', 'skillshare.com', 'pluralsight.com'
        }
        
        # Approach 2: Enhanced Heuristic Patterns
        self.paywall_keywords = [
            # Direct paywall indicators
            "subscribe to continue", "subscription required", "premium content",
            "subscriber exclusive", "this content is for subscribers",
            "paywall", "pay to read", "unlock full access",
            
            # Metered paywall (soft paywall)
            "you've reached your limit", "free articles remaining", 
            "your trial has ended", "trial expired",
            "you have viewed your allotment", "free views remaining",
            
            # Login-based restrictions
            "please sign in to continue", "log in to continue reading",
            "sign up to continue", "create account to continue",
            "members only", "subscribers only",
            
            # Content blocking
            "content blocked", "access denied", "restricted content",
            "this article is locked", "full story available to",
            "premium access required", "upgrade to continue"
        ]
        
        # Overlay/Modal selectors (visual barriers)
        self.paywall_selectors = [
            # Generic paywall containers
            '[class*="paywall"]', '[id*="paywall"]',
            '[class*="subscription"]', '[id*="subscription"]',
            '[class*="premium"]', '[id*="premium"]',
            '[class*="meter"]', '[class*="metered"]',
            
            # Overlay/Modal patterns
            '[class*="overlay"]', '[class*="modal"]',
            '[class*="popup"]', '[class*="barrier"]',
            '[style*="position: fixed"]', '[style*="z-index"]',
            
            # Common paywall class names
            '.subscription-wall', '.paywall-container', '.paywall-overlay',
            '.meter-wall', '.premium-wall', '.login-wall', '.auth-wall',
            '.registration-wall', '.signup-wall',
            
            # Data attributes
            '[data-qa-id*="paywall"]', '[data-testid*="paywall"]',
            '[data-paywall]', '[data-subscription]'
        ]
        
        # URL patterns indicating subscription pages
        self.paywall_url_patterns = [
            r'/subscribe/?(\?|$)', r'/subscription/?(\?|$)',
            r'/premium/?(\?|$)', r'/pro/?(\?|$)',
            r'/membership/?(\?|$)', r'/member/?(\?|$)',
            r'/pricing/?(\?|$)', r'/plans/?(\?|$)',
            r'/upgrade/?(\?|$)', r'/unlock/?(\?|$)',
            r'[?&]paywall=', r'[?&]subscription=', r'[?&]premium='
        ]
    
    async def detect_paywall(self, url: str, html_content: Optional[str] = None) -> Dict:
        """
        Comprehensive paywall detection using all 4 approaches
        Returns detailed analysis with confidence score
        """
        result = {
            "url": url,
            "is_paywall": False,
            "confidence": 0.0,
            "detection_methods": [],
            "reasons": [],
            "approach_results": {
                "domain_check": False,
                "url_patterns": False,
                "structured_data": False,
                "content_analysis": False,
                "visual_barriers": False
            }
        }
        
        # Approach 1: Domain-based detection (fastest)
        domain_result = self._check_domain(url)
        result["approach_results"]["domain_check"] = domain_result["detected"]
        if domain_result["detected"]:
            result["detection_methods"].append("domain_list")
            result["reasons"].append(domain_result["reason"])
            result["confidence"] += 0.9  # High confidence for known domains
        
        # Approach 2: URL pattern analysis
        pattern_result = self._check_url_patterns(url)
        result["approach_results"]["url_patterns"] = pattern_result["detected"]
        if pattern_result["detected"]:
            result["detection_methods"].append("url_patterns")
            result["reasons"].append(pattern_result["reason"])
            result["confidence"] += 0.7  # Medium-high confidence
        
        # If we have HTML content, perform deeper analysis
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Approach 3: Structured data analysis (JSON-LD)
            structured_result = self._check_structured_data(soup)
            result["approach_results"]["structured_data"] = structured_result["detected"]
            if structured_result["detected"]:
                result["detection_methods"].append("structured_data")
                result["reasons"].append(structured_result["reason"])
                result["confidence"] += 0.95  # Very high confidence for structured data
            
            # Approach 4: Content analysis
            content_result = self._analyze_content(soup, url)
            result["approach_results"]["content_analysis"] = content_result["detected"]
            if content_result["detected"]:
                result["detection_methods"].append("content_analysis")
                result["reasons"].append(content_result["reason"])
                result["confidence"] += 0.6  # Medium confidence
            
            # Visual barrier detection
            visual_result = self._check_visual_barriers(soup)
            result["approach_results"]["visual_barriers"] = visual_result["detected"]
            if visual_result["detected"]:
                result["detection_methods"].append("visual_barriers")
                result["reasons"].append(visual_result["reason"])
                result["confidence"] += 0.8  # High confidence for visual barriers
        
        # Final determination
        result["is_paywall"] = result["confidence"] >= 0.5
        result["confidence"] = min(result["confidence"], 1.0)  # Cap at 100%
        
        return result
    
    def _check_domain(self, url: str) -> Dict:
        """Approach 1: Check against known paywall domains"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Check exact match
            if domain in self.known_paywall_domains:
                return {
                    "detected": True,
                    "reason": f"Known paywall domain: {domain}"
                }
            
            # Check subdomain matches
            for paywall_domain in self.known_paywall_domains:
                if domain.endswith(f'.{paywall_domain}'):
                    return {
                        "detected": True,
                        "reason": f"Subdomain of paywall domain: {paywall_domain}"
                    }
            
            return {"detected": False, "reason": "Domain not in paywall list"}
            
        except Exception as e:
            return {"detected": False, "reason": f"Domain check failed: {e}"}
    
    def _check_url_patterns(self, url: str) -> Dict:
        """Approach 2: Check URL patterns for subscription indicators"""
        try:
            url_lower = url.lower()
            
            for pattern in self.paywall_url_patterns:
                if re.search(pattern, url_lower):
                    return {
                        "detected": True,
                        "reason": f"URL pattern match: {pattern}"
                    }
            
            return {"detected": False, "reason": "No paywall URL patterns found"}
            
        except Exception as e:
            return {"detected": False, "reason": f"URL pattern check failed: {e}"}
    
    def _check_structured_data(self, soup: BeautifulSoup) -> Dict:
        """Approach 3: Analyze JSON-LD structured data for isAccessibleForFree"""
        try:
            # Find all JSON-LD script tags
            json_scripts = soup.find_all('script', {'type': 'application/ld+json'})
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle both single objects and arrays
                    objects_to_check = [data] if isinstance(data, dict) else data
                    if isinstance(data, list):
                        objects_to_check = data
                    
                    for obj in objects_to_check:
                        if isinstance(obj, dict):
                            # Check isAccessibleForFree property
                            if obj.get('isAccessibleForFree') is False:
                                return {
                                    "detected": True,
                                    "reason": "JSON-LD indicates isAccessibleForFree: false"
                                }
                            
                            # Check for subscription requirements in properties
                            if obj.get('@type') == 'NewsArticle':
                                if obj.get('isPartOf', {}).get('productID') == 'subscription':
                                    return {
                                        "detected": True,
                                        "reason": "JSON-LD indicates subscription required"
                                    }
                
                except json.JSONDecodeError:
                    continue
            
            return {"detected": False, "reason": "No paywall indicators in structured data"}
            
        except Exception as e:
            return {"detected": False, "reason": f"Structured data check failed: {e}"}
    
    def _analyze_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """Approach 4: Analyze content for paywall indicators"""
        try:
            # Extract main text content
            main_content = self._extract_main_content(soup)
            content_length = len(main_content)
            
            # Check for paywall keywords in text
            content_lower = main_content.lower()
            for keyword in self.paywall_keywords:
                if keyword in content_lower:
                    return {
                        "detected": True,
                        "reason": f"Paywall keyword found: '{keyword}'"
                    }
            
            # Check content length (but exclude direct file downloads)
            if not self._is_direct_file(url):
                if content_length < 200:
                    return {
                        "detected": True,
                        "reason": f"Suspiciously short content ({content_length} chars)"
                    }
                
                # Check for truncated content indicators
                if content_lower.endswith(('...', '…', 'read more', 'continue reading')):
                    return {
                        "detected": True,
                        "reason": "Content appears truncated"
                    }
            
            return {"detected": False, "reason": "Content analysis shows no paywall"}
            
        except Exception as e:
            return {"detected": False, "reason": f"Content analysis failed: {e}"}
    
    def _check_visual_barriers(self, soup: BeautifulSoup) -> Dict:
        """Check for visual paywall barriers (overlays, modals)"""
        try:
            # Check for paywall-related elements
            for selector in self.paywall_selectors:
                elements = soup.select(selector)
                if elements:
                    return {
                        "detected": True,
                        "reason": f"Paywall element found: {selector}"
                    }
            
            # Check for high z-index overlays (common paywall technique)
            style_elements = soup.find_all(attrs={"style": True})
            for element in style_elements:
                style = element.get('style', '').lower()
                if ('z-index' in style and 'position' in style and 
                    ('fixed' in style or 'absolute' in style)):
                    # Look for high z-index values
                    z_match = re.search(r'z-index:\s*(\d+)', style)
                    if z_match and int(z_match.group(1)) > 1000:
                        return {
                            "detected": True,
                            "reason": "High z-index overlay detected (possible paywall)"
                        }
            
            return {"detected": False, "reason": "No visual barriers detected"}
            
        except Exception as e:
            return {"detected": False, "reason": f"Visual barrier check failed: {e}"}
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content text from HTML"""
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Try to find main content areas
        main_selectors = [
            'article', 'main', '[role="main"]',
            '.article-body', '.story-body', '.content',
            '.post-content', '.entry-content'
        ]
        
        for selector in main_selectors:
            main_element = soup.select_one(selector)
            if main_element:
                return main_element.get_text(strip=True)
        
        # Fallback to body text
        return soup.get_text(strip=True)
    
    def _is_direct_file(self, url: str) -> bool:
        """Check if URL points to a direct file download"""
        file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                          '.zip', '.rar', '.png', '.jpg', '.jpeg', '.gif', '.mp4']
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in file_extensions)


# Factory function for easy integration
def create_enhanced_detector() -> EnhancedPaywallDetector:
    """Create and return an enhanced paywall detector instance"""
    return EnhancedPaywallDetector()


# Async wrapper for the existing system
async def enhanced_detect_paywall(url: str, html_content: Optional[str] = None) -> bool:
    """
    Enhanced paywall detection function that can be used as a drop-in replacement
    Returns True if paywall detected, False otherwise
    """
    detector = create_enhanced_detector()
    result = await detector.detect_paywall(url, html_content)
    return result["is_paywall"]
