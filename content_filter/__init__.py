"""
Content Filter Package for LMS Guardian
Enhanced content filtering with JigsawStack AI integration
"""

from .content_filter import (
    ContentFilter,
    content_filter,
    is_pornography_url,
    is_malicious_url,
    is_paywall_url,
    should_exclude_from_apa_citation,
    should_exclude_from_local_storage,
    test_content_filter
)

__all__ = [
    'ContentFilter',
    'content_filter',
    'is_pornography_url', 
    'is_malicious_url',
    'is_paywall_url',
    'should_exclude_from_apa_citation',
    'should_exclude_from_local_storage',
    'test_content_filter'
]
