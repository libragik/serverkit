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

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="{css_path}style.css">
</head>
<body>
    <div class="container">
        <aside class="sidebar">
            <div class="logo"><h2>{course_name}</h2></div>
            <nav class="navigation">{navigation}</nav>
        </aside>
        <main class="content">{content}</main>
    </div>
    <script src="{js_path}script.js"></script>
</body>
</html>"""

CSS_CONTENT = """
body { font-family: sans-serif; margin: 0; display: flex; height: 100vh; }
.sidebar { width: 280px; background: #1a1d23; color: white; overflow-y: auto; padding: 20px; }
.content { flex: 1; padding: 40px; overflow-y: auto; }
.nav-item { display: block; padding: 10px; color: #ccc; text-decoration: none; }
.nav-item:hover, .nav-item.active { color: white; background: rgba(255,255,255,0.1); }
img { max-width: 100%; }
"""

JS_CONTENT = "console.log('Loaded');"

class SkoolClassroomScraper:
    def __init__(self, config, callback=None):
        self.config = config
        self.callback = callback
        
        self.output_dir = Path(config.OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        (self.output_dir / self.config.MEDIA_DIR).mkdir(exist_ok=True)
        
        self.cookies = None
        self.course_data = None
        self.files_downloaded = []
        self.media_downloaded = []
        self.module_contents = {}
        self.stats = {'total_modules': 0, 'modules_with_content': 0, 'modules_without_content': 0, 'files_downloaded': 0}
        
    def log(self, msg, type="info"):
        if self.callback: self.callback(msg, type)
        else: print(f"[Scraper] {msg}")

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
        if not next_data: raise Exception("Could not find course data")
        page_data = json.loads(next_data.string)
        self.course_data = page_data['props']['pageProps']['course']

    def _scrape_all_module_content(self):
        self.log("🔍 Scraping modules...", "info")
        structure = self._build_course_structure(self.course_data)
        base_url_match = re.match(r'(https://www.skool.com/[^/]+/classroom/[^?]+)', self.config.CLASSROOM_URL)
        base_url = base_url_match.group(1) if base_url_match else self.config.CLASSROOM_URL
        
        count = 0
        for section in structure['modules']:
            for module in section['modules']:
                count += 1
                self.log(f"Processing module: {module['name']}", "info")
                module_url = f"{base_url}?md={module['id']}"
                try:
                    self.page.goto(module_url, wait_until="networkidle")
                    content = self._extract_tiptap_content(self.page.content(), module['name'])
                    if content:
                        self.module_contents[module['id']] = content
                        self.stats['modules_with_content'] += 1
                except Exception as e:
                    self.log(f"Error scraping module: {e}", "error")
                self._smart_delay()
        self.stats['total_modules'] = count

    def _extract_tiptap_content(self, html, module_name):
        soup = BeautifulSoup(html, 'html.parser')
        tiptap_div = soup.find('div', class_='tiptap') or soup.find('div', class_=re.compile(r'styled__PostContent'))
        if not tiptap_div: return ""
        
        # Download images
        for img in tiptap_div.find_all('img'):
            src = img.get('originalsrc') or img.get('src')
            if src and 'assets.skool.com' in src:
                local = self._download_media(src, module_name)
                if local: img['src'] = local
        return str(tiptap_div.decode_contents())

    def _download_media(self, url, module_name):
        try:
            filename = f"{self._sanitize(module_name)}_{os.path.basename(urlparse(url).path)}"
            local_path = self.output_dir / self.config.MEDIA_DIR / filename
            if not local_path.exists():
                resp = requests.get(url, stream=True)
                if resp.status_code == 200:
                    with open(local_path, 'wb') as f: f.write(resp.content)
            return f"{self.config.MEDIA_DIR}/{filename}"
        except: return None

    def _download_all_files(self):
        self.log("📥 Downloading attachments...", "info")
        files_dir = self.output_dir / "downloads"
        files_dir.mkdir(exist_ok=True)
        # Simplified file download logic for brevity
        # In real usage, iterate self.course_data similar to scraping modules
        pass 

    def _generate_html_website(self):
        self.log("🌐 Generating static website...", "info")
        assets_dir = self.output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        with open(assets_dir / "style.css", 'w') as f: f.write(CSS_CONTENT)
        with open(assets_dir / "script.js", 'w') as f: f.write(JS_CONTENT)
        
        structure = self._build_course_structure(self.course_data)
        # Generate Index
        with open(self.output_dir / "index.html", 'w', encoding='utf-8') as f:
            f.write(HTML_TEMPLATE.format(
                title="Course Index", course_name=structure['name'], 
                css_path="assets/", js_path="assets/", 
                navigation="", content="<h1>Course Index</h1><p>Open sidebar to navigate.</p>"
            ))

    def _build_course_structure(self, course_data):
        # ... (Existing logic to parse Skool JSON) ...
        # Simplified for template:
        return {'name': 'Course', 'modules': []}

    def _sanitize(self, name):
        return re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()

    def _print_summary(self):
        self.log(f"Job finished! Processed {self.stats['total_modules']} modules.", "success")
