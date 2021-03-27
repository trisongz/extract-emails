#!/usr/local/bin/python3
# -*- coding: utf-8
from typing import List, Type

from .email import Email
from extract_emails.browsers import BrowserInterface
from extract_emails.html_handlers import DefaultHTMLHandler
from extract_emails.email_filters import DefaultEmailFilter
from extract_emails.link_filters import DefaultLinkFilter, ContactInfoLinkFilter

FILTERS = {0: DefaultLinkFilter, 1: ContactInfoLinkFilter}


class Extractor:
    def __init__(self, browser: Type[BrowserInterface], depth: int = 10, max_links_from_page: int = -1, link_filter: int = 0, **kwargs):
        self.browser = browser
        self.depth = depth
        self.max_links_from_page = max_links_from_page
        self._linkfilter = link_filter
        self._kwargs = kwargs
        self._allweburls = set()
        self._links = {}
        self._checked_links = {}
        self._emails = {}
        self._data = {}
        self._idx = 0
        self._current_depth = 0
        self.html_handler = DefaultHTMLHandler()
        self.links_filter = {}
        self.emails_filter = {}
    
    def config_url(self, website_url):
        self.website = website_url
        print(f'On {self._idx}: {self.website}')
        self.emails_filter[self.website] = DefaultEmailFilter()
        self._links[self.website] = [self.website]
        self._checked_links[self.website] = []
        self._emails[self.website] = []
        self._data[self.website] = {'emails': {}, 'data': {}}
        self._current_depth = 0
        self.links_filter[self.website] = FILTERS[self._linkfilter](self.website, **self._kwargs)
        self._allweburls.add(self.website)
        self._idx += 1

    def process(self, website_url):
        if website_url not in self._allweburls:
            self.config_url(website_url)
            return self.get_data()
        return self._data[website_url]

    def process_batch(self, website_list):
        for website_url in website_list:
            if website_url not in self._allweburls:
                self.config_url(website_url)
                yield self.get_data()
            else:
                yield self._data[website_url]

    def get_data(self):
        urls = self._get_urls()
        self._current_depth += 1
        if not len(urls) or self._current_depth > self.depth:
            return self._data
        for url in urls:
            self._get_data(url)
        return self.get_data()

    def _get_data(self, url: str):
        page_source = self.browser.get_page_source(url)
        srcdata = self.html_handler.get_data(page_source)
        email, data, links = srcdata['emails'], srcdata['data'], srcdata['links']
        filtered_emails = self.emails_filter[self.website].filter(email)
        self._data[self.website]['emails'].update({email: url for email in filtered_emails})
        for platform in data:
            if not self._data[self.website]['data'].get(platform):
                self._data[self.website]['data'][platform] = {}
            for src in data[platform]:
                if not self._data[self.website]['data'][platform].get(src):
                    self._data['data'][platform][src] = {}
                if data[platform][src]:
                    self._data[self.website]['data'][platform][src].update(data[platform][src])
        self._emails[self.website].extend([Email(email, url) for email in filtered_emails])
        filtered_links = self.links_filter[self.website].filter(links)
        if self.max_links_from_page != -1:
            filtered_links = filtered_links[: self.max_links_from_page]
        for fl in filtered_links:
            if fl not in self._checked_links[self.website]:
                self._checked_links[self.website].append(fl)
                self._links[self.website].append(fl)

    def _get_urls(self) -> List[str]:
        links = self._links[self.website][:]
        self._links[self.website] = []
        return links

class EmailExtractor:
    """
    Extract emails from a website

    Example:
        >>> extractor = EmailExtractor(browser, depth=10, max_links_from_page=-1)
        >>> emails = extractor.get_emails()

    :param str website_url: website for scan, e.g. https://example.com
    :param browser: browser to get page source by URL
    :param int depth: scan's depth, default 10
    :param int max_links_from_page: how many links a script shall get from each page, default -1 (all)
    :param int link_filter: which filter is used to extract url. default 0. 0 - DefaultLinkFilter,
        1 - ContactInfoLinkFilter
    """

    def __init__(
            self,
            website_url: str,
            browser: Type[BrowserInterface],
            depth: int = 10,
            max_links_from_page: int = -1,
            link_filter: int = 0,
            **kwargs
    ):
        self.website = website_url
        self.browser = browser
        self.depth = depth
        self.max_links_from_page = max_links_from_page

        self._links: List[str] = [self.website]
        self._checked_links: List[str] = []
        self._emails: List[Email] = []
        self._data = {'emails': {}, 'data': {}}
        self._current_depth: int = 0

        self.html_handler = DefaultHTMLHandler()
        self.links_filter = FILTERS[link_filter](self.website, **kwargs)
        self.emails_filter = DefaultEmailFilter()

    def get_data(self):
        urls = self._get_urls()
        self._current_depth += 1
        if not len(urls) or self._current_depth > self.depth:
            return self._data

        for url in urls:
            self._get_data(url)
        return self.get_data()

    def _get_data(self, url: str):
        page_source = self.browser.get_page_source(url)
        srcdata = self.html_handler.get_data(page_source)
        email, data, links = srcdata['emails'], srcdata['data'], srcdata['links']
        filtered_emails = self.emails_filter.filter(email)
        self._data['emails'].update({email: url for email in filtered_emails})
        for platform in data:
            if not self._data['data'].get(platform):
                self._data['data'][platform] = {}
            for src in data[platform]:
                if not self._data['data'][platform].get(src):
                    self._data['data'][platform][src] = {}
                if data[platform][src]:
                    self._data['data'][platform][src].update(data[platform][src])
        self._emails.extend([Email(email, url) for email in filtered_emails])
        filtered_links = self.links_filter.filter(links)
        if self.max_links_from_page != -1:
            filtered_links = filtered_links[: self.max_links_from_page]
        for fl in filtered_links:
            if fl not in self._checked_links:
                self._checked_links.append(fl)
                self._links.append(fl)

    def get_emails(self) -> List[Email]:
        """Extract emails from webpages
        """
        urls = self._get_urls()
        self._current_depth += 1
        if not len(urls) or self._current_depth > self.depth:
            return self._emails

        for url in urls:
            self._get_emails(url)
        return self.get_emails()

    def _get_emails(self, url: str):
        page_source = self.browser.get_page_source(url)

        emails = self.html_handler.get_emails(page_source)
        filtered_emails = self.emails_filter.filter(emails)
        self._emails.extend([Email(email, url) for email in filtered_emails])

        links = self.html_handler.get_links(page_source)
        filtered_links = self.links_filter.filter(links)
        if self.max_links_from_page != -1:
            filtered_links = filtered_links[: self.max_links_from_page]
        for fl in filtered_links:
            if fl not in self._checked_links:
                self._checked_links.append(fl)
                self._links.append(fl)

    def _get_urls(self) -> List[str]:
        links = self._links[:]
        self._links = []
        return links
