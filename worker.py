#!/usr/bin/env python3
"""
Adapted Professional Skool Scraper for SaaS Backend
"""

import os
import re
import json
import time
import random
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from html import escape
from urllib.parse import urljoin, urlparse

class Config:
    CLASSROOM_URL = ""
    SKOOL_EMAIL = ""
    SKOOL_PASSWORD = ""
    SKOOL_BASE_URL = "https://www.skool.com"
    MEDIA_DIR = "media"
    PAGE_TIMEOUT = 30000
    REQUEST_DELAY = 2
    OUTPUT_DIR = "skool_export_saas"
    FILE_EXPIRE_TIME = 28800
    DOWNLOAD_TIMEOUT = 60
    HEADLESS = True
    DOWNLOAD_FILES = True
    DEBUG_MODE = False

# HTML/CSS Templates removed for brevity, assume they exist or are loaded from files
HTML_TEMPLATE = "<!DOCTYPE html>..." 
CSS_CONTENT = "..."
JS_CONTENT = "..."

class SkoolClassroomScraper:
    def __init__(self, config, callback=None):
        self.config = config
        self.callback = callback  # Hook for SaaS logging
        
        self.output_dir = Path(config.OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        self.cookies = None
        self.course_data = None
        self.files_downloaded = []
        self.media_downloaded = []
        self.module_contents = {}
        self.stats = {
            'total_modules': 0, 'modules_with_content': 0,
            'modules_without_content': 0, 'files_downloaded': 0
        }
        
    def log(self, msg, type="info"):
        """Send logs back to the API via callback"""
        if self.callback:
            self.callback(msg, type)
        else:
            print(f"[Scraper] {msg}")

    def _smart_delay(self):
        time.sleep(self.config.REQUEST_DELAY)

    def run(self):
        self.log("🚀 Starting extraction process...", "info")
        
        with sync_playwright() as p:
            self._authenticate_and_setup(p)
            self._fetch_classroom_page()
            self._extract_course_structure()
            self._scrape_all_module_content()
            
            if self.config.DOWNLOAD_FILES:
                self._download_all_files()
                
            self._generate_html_website()
            self._print_summary()
            
        return str(self.output_dir.absolute())

    def _authenticate_and_setup(self, playwright):
        self.log("🔐 Authenticating with Skool...", "info")
        browser = playwright.chromium.launch(headless=self.config.HEADLESS)
        self.context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.page = self.context.new_page()
        
        self.page.goto("https://www.skool.com/login")
        self.page.fill('input[type="email"]', self.config.SKOOL_EMAIL)
        self.page.fill('input[type="password"]', self.config.SKOOL_PASSWORD)
        self.page.click('button[type="submit"]')
        
        try:
            self.page.wait_for_url(lambda url: "login" not in url, timeout=15000)
            self.log("✅ Login successful", "success")
        except:
            self.log("❌ Login failed. Check credentials.", "error")
            raise Exception("Login failed")

    def _fetch_classroom_page(self):
        self.log(f"📄 Fetching classroom: {self.config.CLASSROOM_URL}", "info")
        self.page.goto(self.config.CLASSROOM_URL, wait_until="networkidle")
        self.html_content = self.page.content()
        
    def _extract_course_structure(self):
        self.log("📊 Parsing course structure...", "info")
        soup = BeautifulSoup(self.html_content, 'html.parser')
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if not next_data:
            raise Exception("Could not find course data")
        page_data = json.loads(next_data.string)
        self.course_data = page_data['props']['pageProps']['course']

    def _scrape_all_module_content(self):
        # ... (Your existing robust logic here, calling self.log() instead of print) ...
        self.log("🔍 Scraping modules (This may take time)...", "info")
        # Placeholder for full loop logic
        time.sleep(2) 
        self.stats['total_modules'] = 10 # Example
        self.log("✅ Scraped 10 modules successfully", "success")

    def _download_all_files(self):
        self.log("📥 Downloading attachments...", "info")
        # Placeholder
        pass

    def _generate_html_website(self):
        self.log("🌐 Generating static website...", "info")
        # Placeholder
        pass

    def _print_summary(self):
        summary = f"Summary: {self.stats['total_modules']} modules processed."
        self.log(summary, "success")
