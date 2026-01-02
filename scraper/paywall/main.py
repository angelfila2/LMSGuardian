from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse


class PaywallDetector:
    """Advanced paywall detection with multiple detection methods"""
    
    def __init__(self):
        self.paywall_keywords = [
            "subscribe to continue", "already a subscriber", "subscription required",
            "this content is for subscribers", "subscriber exclusive", "premium content",
            "you've reached your limit", "free articles remaining", "your trial has ended",
            "trial expired", "upgrade to continue", "unlock full access",
            "paywall", "pay to read", "become a member", "join now to read",
            "this story is premium", "premium access required",
            "please sign in to continue", "log in to continue reading",
            "sign up to continue", "create account to continue",
            "content blocked", "access denied", "restricted content",
            "this article is locked", "full story available to"
        ]
        
        self.paywall_selectors = [
            '[class*="paywall"]', '[id*="paywall"]',
            '[class*="subscription"]', '[id*="subscription"]',
            '[class*="premium"]', '[id*="premium"]',
            '[class*="metered"]', '[id*="metered"]',
            '[class*="overlay"]', '[class*="modal"]',
            '[class*="popup"]', '[class*="barrier"]',
            '[data-qa-id="paywall"]', '[data-testid*="paywall"]',
            '.subscription-wall', '.paywall-container',
            '.meter-wall', '.premium-wall',
            '.login-wall', '.signin-wall', '.auth-wall'
        ]
        
        self.bot_protection_indicators = [
            "datadome", "cloudflare", "cf-chl", "captcha", "recaptcha",
            "bot protection", "anti-bot", "security check", "verify you are human"
        ]
        
        self.domain_patterns = {
            'wsj.com': ['wsj-paywall', 'article-wrap-paywall'],
            'nytimes.com': ['css-paywall', 'paywall-bar'],
            'bloomberg.com': ['paywall-banner', 'fence-body'],
            'ft.com': ['barrier-app', 'subscription-barrier'],
            'economist.com': ['paywall-container', 'subscription-required']
        }

    def detect_paywall(self, url: str, timeout: int = 20000) -> Dict[str, str]:
        """Comprehensive paywall detection using multiple methods"""
        result = {"url": url, "status": None, "reason": None, "confidence": "medium"}
        
        try:
            html, page_metrics = self._get_page_content(url, timeout)
            if not html:
                result["status"] = "unavailable"
                result["reason"] = "Failed to load page content"
                return result
                
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text().strip().lower()
            
            # Check bot protection first
            bot_check = self._check_bot_protection(html, text)
            if bot_check["detected"]:
                result["status"] = "controlled_access"
                result["reason"] = bot_check["reason"]
                result["confidence"] = "high"
                return result
            
            # Check paywall elements
            element_check = self._check_paywall_elements(soup, url)
            if element_check["detected"]:
                result["status"] = "paywalled"
                result["reason"] = element_check["reason"]
                result["confidence"] = "high"
                return result
            
            # Check keywords
            keyword_check = self._check_paywall_keywords(text)
            if keyword_check["detected"]:
                result["status"] = "paywalled"
                result["reason"] = keyword_check["reason"]
                result["confidence"] = "medium"
                return result
            
            # Check content quality
            content_check = self._check_content_quality(soup, page_metrics, url)
            if content_check["detected"]:
                result["status"] = "paywalled"
                result["reason"] = content_check["reason"]
                result["confidence"] = "low"
                return result
            
            # Check login requirements
            login_check = self._check_login_requirements(text, soup)
            if login_check["detected"]:
                result["status"] = "controlled_access"
                result["reason"] = login_check["reason"]
                result["confidence"] = "medium"
                return result
            
            result["status"] = "clean"
            result["reason"] = "No access restrictions detected"
            result["confidence"] = "high"
            
        except Exception as e:
            result["status"] = "unavailable"
            result["reason"] = f"Detection failed: {str(e)}"
            result["confidence"] = "high"
        
        return result

    def _get_page_content(self, url: str, timeout: int) -> tuple[Optional[str], Dict]:
        """Get page content with proper browser settings"""
        metrics = {"load_time": 0, "content_length": 0, "redirects": 0}
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage', '--no-sandbox']
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            page = context.new_page()
            
            redirects = []
            page.on("response", lambda response: redirects.append(response.url) if response.status in [301, 302, 303, 307, 308] else None)
            
            start_time = time.time()
            try:
                response = page.goto(url, wait_until="networkidle", timeout=timeout)
                metrics["load_time"] = time.time() - start_time
                metrics["redirects"] = len(redirects)
                
                page.wait_for_timeout(2000)
                
                html = page.content()
                metrics["content_length"] = len(html)
                
                browser.close()
                return html, metrics
                
            except Exception as e:
                browser.close()
                raise e

    def _check_bot_protection(self, html: str, text: str) -> Dict:
        """Check for bot protection systems"""
        for indicator in self.bot_protection_indicators:
            if indicator in html.lower() or indicator in text:
                return {"detected": True, "reason": f"Bot protection detected: {indicator}"}
        return {"detected": False, "reason": None}

    def _check_paywall_elements(self, soup: BeautifulSoup, url: str) -> Dict:
        """Check for paywall-specific HTML elements"""
        domain = urlparse(url).netloc.lower()
        
        # Check domain-specific patterns
        for domain_key, patterns in self.domain_patterns.items():
            if domain_key in domain:
                for pattern in patterns:
                    if soup.select_one(f'[class*="{pattern}"]') or soup.select_one(f'[id*="{pattern}"]'):
                        return {"detected": True, "reason": f"Domain-specific paywall element detected: {pattern}"}
        
        # Check generic selectors
        for selector in self.paywall_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    if self._is_paywall_element_active(element):
                        return {"detected": True, "reason": f"Paywall element detected: {selector}"}
        
        return {"detected": False, "reason": None}

    def _is_paywall_element_active(self, element) -> bool:
        """Check if a paywall element is actually active"""
        style = element.get('style', '').lower()
        if 'display:none' in style or 'visibility:hidden' in style:
            return False
        
        classes = element.get('class', [])
        if isinstance(classes, list):
            classes = ' '.join(classes)
        if 'hidden' in classes.lower():
            return False
        
        text = element.get_text(strip=True)
        if len(text) > 10:
            return True
        
        if element.find_all():
            return True
        
        return False

    def _check_paywall_keywords(self, text: str) -> Dict:
        """Check for paywall-related keywords"""
        for keyword in self.paywall_keywords:
            if keyword in text:
                return {"detected": True, "reason": f"Paywall keyword detected: '{keyword}'"}
        return {"detected": False, "reason": None}

    def _check_content_quality(self, soup: BeautifulSoup, metrics: Dict, url: str = "") -> Dict:
        """Analyze content quality to detect paywall truncation"""
        body = soup.body
        if not body:
            return {"detected": True, "reason": "No body content found"}
        
        # Check if this is a direct file download
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.txt', '.rtf']
        is_direct_file = any(parsed_url.path.lower().endswith(ext) for ext in file_extensions)
        
        main_text = body.get_text(separator=" ", strip=True)
        
        if len(main_text) < 200:
            if is_direct_file:
                # Direct file downloads are expected to have minimal HTML content
                return {"detected": False, "reason": f"Direct file download ({parsed_url.path.split('/')[-1]}) with minimal HTML wrapper"}
            else:
                return {"detected": True, "reason": f"Short content ({len(main_text)} chars) suggests paywall"}
        
        if self._has_suspicious_content_patterns(main_text):
            return {"detected": True, "reason": "Content shows signs of truncation"}
        
        if metrics["content_length"] > 50000 and len(main_text) < 1000:
            return {"detected": True, "reason": "Low content-to-HTML ratio suggests paywall"}
        
        return {"detected": False, "reason": None}

    def _has_suspicious_content_patterns(self, text: str) -> bool:
        """Check for patterns that suggest paywall truncation"""
        patterns = [r"\.{3,}", r"\[read more\]", r"\[continue reading\]", r"story continues", r"article continues"]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False

    def _check_login_requirements(self, text: str, soup: BeautifulSoup) -> Dict:
        """Check for login requirements"""
        login_indicators = [
            "please sign in", "log in to continue", "sign up to continue",
            "create account to continue", "login required", "authentication required"
        ]
        
        for indicator in login_indicators:
            if indicator in text:
                return {"detected": True, "reason": f"Login requirement detected: '{indicator}'"}
        
        # Check for login forms
        login_forms = soup.find_all("form")
        for form in login_forms:
            form_text = form.get_text().lower()
            if any(word in form_text for word in ["login", "sign in", "username", "password"]):
                return {"detected": True, "reason": "Login form detected"}
        
        return {"detected": False, "reason": None}


def classify_page_access(url: str) -> Dict[str, str]:
    """Main function to classify page access - simplified interface"""
    detector = PaywallDetector()
    return detector.detect_paywall(url)


def detect_paywall_from_html(html: str, url: str = "") -> Dict[str, str]:
    """Detect paywall from existing HTML content"""
    detector = PaywallDetector()
    result = {"status": None, "reason": None, "confidence": "medium"}
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text().strip().lower()
        
        # Check bot protection
        bot_check = detector._check_bot_protection(html, text)
        if bot_check["detected"]:
            result["status"] = "controlled_access"
            result["reason"] = bot_check["reason"]
            result["confidence"] = "high"
            return result
        
        # Check paywall elements
        element_check = detector._check_paywall_elements(soup, "")
        if element_check["detected"]:
            result["status"] = "paywalled"
            result["reason"] = element_check["reason"]
            result["confidence"] = "high"
            return result
        
        # Check keywords
        keyword_check = detector._check_paywall_keywords(text)
        if keyword_check["detected"]:
            result["status"] = "paywalled"
            result["reason"] = keyword_check["reason"]
            result["confidence"] = "medium"
            return result
        
        # Check content quality (skip for direct file downloads)
        from urllib.parse import urlparse
        parsed_url = urlparse(url if url else "")
        file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.txt', '.rtf']
        is_direct_file = any(parsed_url.path.lower().endswith(ext) for ext in file_extensions)
        
        main_text = soup.body.get_text(separator=" ", strip=True) if soup.body else ""
        if len(main_text) < 200 and not is_direct_file:
            result["status"] = "paywalled"
            result["reason"] = f"Short content ({len(main_text)} chars) suggests paywall"
            result["confidence"] = "low"
            return result
        elif is_direct_file and len(main_text) < 200:
            # For direct files, short content is expected - not a paywall indicator
            result["status"] = "clean"
            result["reason"] = f"Direct file download ({parsed_url.path.split('/')[-1]}) with minimal HTML wrapper"
            result["confidence"] = "high"
            return result
        
        # Check login requirements
        login_check = detector._check_login_requirements(text, soup)
        if login_check["detected"]:
            result["status"] = "controlled_access"
            result["reason"] = login_check["reason"]
            result["confidence"] = "medium"
            return result
        
        result["status"] = "clean"
        result["reason"] = "No access restrictions detected"
        result["confidence"] = "high"
        
    except Exception as e:
        result["status"] = "unavailable"
        result["reason"] = f"Analysis failed: {str(e)}"
        result["confidence"] = "high"
    
    return result
