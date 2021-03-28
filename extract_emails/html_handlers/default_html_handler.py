import re
import threading
from typing import List
from extractnet import Extractor

from .html_handler_interface import HTMLHandlerInterface
# https://github.com/lorey/social-media-profiles-regexs/blob/master/regexes.json



_patterns = {
    "angellist": {
        "company": {
            "match": "(?:https?:)?\\/\\/angel\\.co\\/company\\/(?P<company>[A-z0-9_-]+)(?:\\/(?P<company_subpage>[A-z0-9-]+))?",
            "keys": ["company",  "subpage"],
        },
        "job": {
            "match": "(?:https?:)?\\/\\/angel\\.co\\/company\\/(?P<company>[A-z0-9_-]+)\\/jobs\\/(?P<job_permalink>(?P<job_id>[0-9]+)-(?P<job_slug>[A-z0-9-]+))",
            "keys": ["company", "job_id", "job_permalink", "job_slug"],
        },
        "user": {
            "match": "(?:https?:)?\\/\\/angel\\.co\\/(?P<type>u|p)\\/(?P<user>[A-z0-9_-]+)",
            "keys": ["type", "user"],
        }
    },
    "linkedin": {
        "company": {
            "match": "(?:https?:)?\\/\\/(?:[\\w]+\\.)?linkedin\\.com\\/company\\/(?P<company_permalink>[A-z0-9-\\.]+)\\/?",
            "keys": ["permalink"]
        },
        "post": {
            "match": "(?:https?:)?\\/\\/(?:[\\w]+\\.)?linkedin\\.com\\/feed\\/update\\/urn:li:activity:(?P<activity_id>[0-9]+)\\/?",
            "keys": ["activity_id"]
        },
        "profile": {
            "match": "(?:https?:)?\\/\\/(?:[\\w]+\\.)?linkedin\\.com\\/in\\/(?P<permalink>[\\w\\-\\_\u00c0-\u00ff%]+)\\/?",
            "keys": ["permalink"]
        },
        "profile_pub": {
            "match": "(?:https?:)?\\/\\/(?:[\\w]+\\.)?linkedin\\.com\\/pub\\/(?P<permalink_pub>[A-z0-9_-]+)(?:\\/[A-z0-9]+){3}\\/?",
            "keys": ["permalink"]
        }
    },
    "crunchbase": {
        "company": {
            "match": "(?:https?:)?\\/\\/crunchbase\\.com\\/organization\\/(?P<organization>[A-z0-9_-]+)",
            "keys": ["org"]
        },
        "person": {
            "match": "(?:https?:)?\\/\\/crunchbase\\.com\\/person\\/(?P<person>[A-z0-9_-]+)",
            "keys": ["person"]
        }
    },
    "medium": {
        "post": {
            "match": "(?:https?:)?\\/\\/medium\\.com\\/(?:(?:@(?P<username>[A-z0-9]+))|(?P<publication>[a-z-]+))\\/(?P<slug>[a-z0-9\\-]+)-(?P<post_id>[A-z0-9]+)(?:\\?.*)?",
            "keys": ["post_id", "slug", "username"]
        },
        "subpost": {
            "match": "(?:https?:)?\\/\\/(?P<publication>(?!www)[a-z-]+)\\.medium\\.com\\/(?P<slug>[a-z0-9\\-]+)-(?P<post_id>[A-z0-9]+)(?:\\?.*)?",
            "keys": ["post_id", "publication", "slug"]
        },
        "user": {
            "match": "(?:https?:)?\\/\\/medium\\.com\\/@(?P<username>[A-z0-9]+)(?:\\?.*)?",
            "keys": ["username"]
        },
        "userid": {
            "match": "(?:https?:)?\\/\\/medium\\.com\\/u\\/(?P<user_id>[A-z0-9]+)(?:\\?.*)",
            "keys": ["user_id"]
        }
    },
    "twitter": {
        "status": {
            "match": "(?:https?:)?\\/\\/(?:[A-z]+\\.)?twitter\\.com\\/@?(?P<username>[A-z0-9_]+)\\/status\\/(?P<tweet_id>[0-9]+)\\/?",
            "keys": ["tweet_id", "username"]
        },
        "user": {
            "match": "(?:https?:)?\\/\\/(?:[A-z]+\\.)?twitter\\.com\\/@?(?!home|share|privacy|tos)(?P<username>[A-z0-9_]+)\\/?",
            "keys": ["username"]
        }
    }
}

_extractor = None
_extractor_lock = threading.Lock()

def config_extractor():
    global _extractor
    if _extractor:
        return
    _extractor = Extractor()

def get_extractor():
    config_extractor()
    return _extractor


class DefaultHTMLHandler(HTMLHandlerInterface):
    def __init__(self):
        # regexp source: https://emailregex.com/
        self.email_pattern = re.compile(
            r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
        )
        self.link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href=(["\'])(.*?)\1')
        self.extractor = get_extractor()
    
    def full_extraction(self, page_source: str):
        res = {
            'emails': self.email_pattern.findall(page_source),
            'links': self.get_links(page_source),
            'socials': self.get_data(page_source),
            'data': self.extractor.extract(page_source, metadata_mining=False)
        }
        return res

    def get_data(self, page_source):
        res = {}
        for platform in _patterns:
            res[platform] = {}
            for src, vals in _patterns[platform].items():
                res[platform][src] = {}
                regex, keys = vals['match'], vals['keys']
                matches = re.finditer(regex, page_source)
                for match in matches:
                    d = match.group(0)
                    res[platform][src][d] = {}
                    findall = re.findall(regex, d)
                    if findall:
                        for x, item in enumerate(findall):
                            item = [i for i in item if i] if not isinstance(item, str) else [item]
                            res[platform][src][d] = {keys[n]: i for n, i in enumerate(item)}
        
        return res
        
    def get_emails(self, page_source: str) -> List[str]:
        """
        Extract all sequences similar to email

        :param str page_source: HTML page source
        :return: List of emails
        """
        return self.email_pattern.findall(page_source)

    def get_links(self, page_source: str) -> List[str]:
        """
        Extract all URLs corresponding to current website

        :param str page_source: HTML page source
        :return: List of URLs
        """
        links = self.link_pattern.findall(page_source)
        links = [x[1] for x in links]
        return links
