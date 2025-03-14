from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup
import requests
import random
import time
from django.utils import timezone
from datetime import datetime
from servers.models import Server, WipeSchedule
import pytz  # Add this import at the top

class Command(BaseCommand):
    help = 'Scrapes recently wiped servers from Just-Wiped and saves new servers to the database'

    def get_urls(self):
        """List of URLs to scrape."""
        return [
            "https://just-wiped.net/rust_servers",  # All servers
            "https://just-wiped.net/best-solo-servers",  # Solo servers
            "https://just-wiped.net/best-duo-servers",  # Duo servers
            "https://just-wiped.net/best-trio-servers",  # Trio servers
        ]

    def get_paginated_url(self, page):
        """Generate URL for specific page number."""
        return f"https://just-wiped.net/rust_servers?max_max_group=1&min_max_group=1&min_rating=80&page={page}&region=any"

    def has_servers(self, html):
        """Check if the page has any servers listed."""
        if not html:
            return False
        soup = BeautifulSoup(html, "html.parser")
        server_links = soup.find_all('a', title="Open the server details page")
        count = len(server_links)
        self.stdout.write(self.style.NOTICE(f"Found {count} servers on this page"))
        return count > 0

    def fetch_data(self, url):
        """Fetches page content while bypassing cache issues."""
        # Check if URL already has parameters
        cache_param = f"nocache={random.randint(1, 1000000)}"
        if '?' in url:
            url_with_cache = f"{url}&{cache_param}"
        else:
            url_with_cache = f"{url}?{cache_param}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Referer": "https://just-wiped.net/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        }

        session = requests.Session()
        session.headers.update(headers)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(1, 3))
                response = session.get(url_with_cache, timeout=10)
                if response.status_code == 200:
                    return response.text
                else:
                    self.stdout.write(self.style.WARNING(f"Attempt {attempt + 1} failed for {url}, status code: {response.status_code}"))
                    time.sleep(random.uniform(2, 5))
            except requests.RequestException as e:
                self.stdout.write(self.style.WARNING(f"Attempt {attempt + 1} failed for {url}: {e}"))
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
        
        self.stdout.write(self.style.ERROR(f"All fetch attempts failed for {url}"))
        return None

    def format_wipe_time(self, dt):
        """Convert datetime to EST hour format."""
        est = pytz.timezone('US/Eastern')
        dt_est = dt.astimezone(est)
        hour = dt_est.strftime('%I%p').lstrip('0').lower()  # Convert to 1pm format
        return f"{hour} est"

    def get_day_name(self, dt):
        """Convert datetime to day name."""
        return dt.strftime('%A')  # Returns full day name (Monday, Tuesday, etc.)

    def parse_html(self, html):
        """Parses the fetched HTML and extracts server data."""
        soup = BeautifulSoup(html, "html.parser")
        server_links = soup.find_all('a', title="Open the server details page")
        servers_data = []

        # Get all existing server IDs from database for faster lookup
        existing_server_ids = set(Server.objects.values_list('server_id', flat=True))

        for link in server_links:
            try:
                server_id = int(link['href'].split('/')[-1])
                server_container = link.find_parent('div', class_='server')
                
                # Get server rating
                rating = 0
                if server_container:
                    rating_div = server_container.find('div', class_='sinfo i-rating')
                    if rating_div:
                        rating_value = rating_div.find('div', class_='value')
                        if rating_value:
                            rating_text = rating_value.text.strip().replace('%', '')
                            if rating_text.isdigit():
                                rating = int(rating_text)

                # Only process servers with 60% or higher rating
                if rating >= 60:
                    server_name = link.text.strip()
                    max_group = None
                    
                    # Find max group value
                    if server_container:
                        max_group_div = server_container.find('div', class_='sinfo i-max-group')
                        if max_group_div:
                            max_group_value = max_group_div.find('div', class_='value')
                            if max_group_value and max_group_value.text.strip().isdigit():
                                max_group = int(max_group_value.text.strip())

                    # Modified time handling
                    timeago = link.find_next('time', class_='timeago')
                    if timeago and 'datetime' in timeago.attrs:
                        full_time = datetime.fromisoformat(timeago['datetime'].replace('Z', '+00:00'))
                        wipe_time = self.format_wipe_time(full_time)
                        wipe_day = self.get_day_name(full_time)  # Get the day name
                    else:
                        current_time = timezone.now()
                        wipe_time = self.format_wipe_time(current_time)
                        wipe_day = self.get_day_name(current_time)

                    # Get correct max_group based on server name, prioritizing larger groups
                    name_lower = server_name.lower()
                    if 'quad' in name_lower:
                        max_group = 4
                    elif 'trio' in name_lower:
                        max_group = 3
                    elif 'duo' in name_lower and 'trio' not in name_lower:
                        max_group = 2
                    elif 'solo' in name_lower and 'duo' not in name_lower and 'trio' not in name_lower:
                        max_group = 1

                    # Check if this is a new server or an existing one
                    is_existing = server_id in existing_server_ids

                    servers_data.append({
                        "server_id": server_id,
                        "server_name": server_name,
                        "wipe_time": wipe_time,
                        "max_group": max_group,
                        "wipe_day": wipe_day,
                        "is_existing": is_existing  # Add flag to indicate if server exists
                    })
                    
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Skipping low-rated server: {link.text.strip()} (Rating: {rating}%)")
                    )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error parsing server: {e}"))

        return servers_data

    def get_max_group_from_name(self, server_name):
        """Determine max group size from server name, prioritizing larger groups."""
        name_lower = server_name.lower()
        # Check in order from largest to smallest group size
        if 'quad' in name_lower:
            return 4
        elif 'trio' in name_lower:
            return 3
        elif 'duo' in name_lower and 'trio' not in name_lower:  # Only duo if not trio
            return 2
        elif 'solo' in name_lower and 'duo' not in name_lower and 'trio' not in name_lower:  # Only solo if not duo/trio
            return 1
        return None

    def update_database(self, servers_data):
        """Updates the database with new servers and additional wipe schedules."""
        for server in servers_data:
            if server["is_existing"]:
                # Get existing server
                existing_server = Server.objects.get(server_id=server["server_id"])
                
                # Check if this wipe schedule already exists
                existing_schedule = WipeSchedule.objects.filter(
                    server=existing_server,
                    day_name=server["wipe_day"],
                    wipe_hour=server["wipe_time"]
                ).first()

                if not existing_schedule:
                    # Add new wipe schedule for existing server
                    WipeSchedule.objects.create(
                        server=existing_server,
                        day_name=server["wipe_day"],
                        wipe_hour=server["wipe_time"]
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Added new wipe schedule for existing server: {server['server_name']} - "
                            f"{server['wipe_day']} at {server['wipe_time']}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping duplicate wipe schedule for server: {server['server_name']} - "
                            f"{server['wipe_day']} at {server['wipe_time']}"
                        )
                    )
            else:
                # Create new server
                new_server = Server.objects.create(
                    server_id=server["server_id"],
                    server_name=server["server_name"],
                    max_group=server["max_group"]
                )

                # Create first wipe schedule
                WipeSchedule.objects.create(
                    server=new_server,
                    day_name=server["wipe_day"],
                    wipe_hour=server["wipe_time"]
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Added new server with wipe schedule: {server['server_name']} - "
                        f"{server['wipe_day']} at {server['wipe_time']}"
                    )
                )

    def handle(self, *args, **kwargs):
        """Main function to run the scraping process."""
        self.stdout.write(self.style.NOTICE("Starting scraping process..."))
        
        # First, process the main URLs
        urls = self.get_urls()
        total_servers_processed = 0

        for url in urls:
            self.stdout.write(self.style.NOTICE(f"\nProcessing URL: {url}"))
            html = self.fetch_data(url)
            
            if html:
                servers_data = self.parse_html(html)
                if servers_data:
                    self.update_database(servers_data)
                    total_servers_processed += len(servers_data)
                    self.stdout.write(
                        self.style.SUCCESS(f"Processed {len(servers_data)} servers from {url}")
                    )
                else:
                    self.stdout.write(self.style.WARNING(f"No servers found at {url}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to retrieve content from {url}"))

            # Add delay between URLs to avoid rate limiting
            time.sleep(random.uniform(2, 5))

        # Now process paginated URLs
        self.stdout.write(self.style.NOTICE("\nStarting pagination scraping..."))
        page = 1
        max_pages = 11

        while page <= max_pages:
            paginated_url = self.get_paginated_url(page)
            self.stdout.write(self.style.NOTICE(f"\nProcessing page {page}: {paginated_url}"))
            
            html = self.fetch_data(paginated_url)
            
            if html:
                # Check if page has any servers
                if not self.has_servers(html):
                    self.stdout.write(self.style.WARNING(f"No more servers found on page {page}. Stopping pagination."))
                    break

                servers_data = self.parse_html(html)
                if servers_data:
                    self.update_database(servers_data)
                    total_servers_processed += len(servers_data)
                    self.stdout.write(
                        self.style.SUCCESS(f"Processed {len(servers_data)} servers from page {page}")
                    )
                else:
                    self.stdout.write(self.style.WARNING(f"No new servers found on page {page}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to retrieve content from page {page}"))
                break

            page += 1
            # Add delay between pages to avoid rate limiting
            time.sleep(random.uniform(2, 5))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nScraping completed. Total servers processed: {total_servers_processed}"
            )
        )