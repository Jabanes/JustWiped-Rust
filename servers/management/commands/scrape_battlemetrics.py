from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
from django.utils import timezone
from datetime import datetime
import pytz
from servers.models import Server, WipeSchedule
import json
import os

class Command(BaseCommand):
    help = 'Scrapes Rust servers from BattleMetrics website and saves to database'

    def get_base_url(self):
        """Return the base URL for BattleMetrics."""
        return "https://www.battlemetrics.com/servers/rust"

    def get_paginated_url(self, page):
        """Generate URL for specific page number."""
        base = self.get_base_url()
        params = [
            ('sort', '-details.rust_born'),
            ('page', str(page))  # Convert page to string
        ]
        url = f"{base}?{'&'.join(f'{k}={v}' for k, v in params)}"
        self.stdout.write(self.style.NOTICE(f"Generated URL: {url}"))  # Debug URL
        return url

    def format_wipe_time(self, dt):
        """Convert datetime to EST hour format."""
        est = pytz.timezone('US/Eastern')
        dt_est = dt.astimezone(est)
        hour = dt_est.strftime('%I%p').lstrip('0').lower()  # Convert to 1pm format
        return f"{hour} est"

    def get_day_name(self, dt):
        """Convert datetime to day name."""
        return dt.strftime('%A')

    def fetch_data(self, url):
        """Fetches page content using Selenium."""
        # Set up the WebDriver (using Chrome in this case)
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode (no browser UI)
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1920,1080')  # Set window size
        options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems

        # Initialize the WebDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        try:
            driver.get(url)
            time.sleep(random.uniform(5, 10))  # Wait for the page to load
            
            # Wait for the server list to appear
            driver.implicitly_wait(10)
            
            # Print current URL after any redirects
            self.stdout.write(self.style.NOTICE(f"Current URL after loading: {driver.current_url}"))

            # Take screenshot for debugging (optional)
            # driver.save_screenshot(f"page_{url.split('page=')[1]}.png")

            html = driver.page_source
            self.stdout.write(self.style.SUCCESS(f"Successfully fetched {url}"))
            
            # Debug: Print a sample of the HTML to verify content
            soup = BeautifulSoup(html, "html.parser")
            server_cells = soup.select("td.css-1su1bxu")
            self.stdout.write(self.style.NOTICE(f"Number of server cells found: {len(server_cells)}"))
            if server_cells:
                first_server = server_cells[0].find('a')
                if first_server:
                    self.stdout.write(self.style.NOTICE(f"First server on page: {first_server.text}"))
            
            return html
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching page {url}: {e}"))
            return None
        finally:
            driver.quit()

    def has_servers(self, html):
        """Check if the page has any servers listed."""
        if not html:
            return False
        soup = BeautifulSoup(html, "html.parser")
        server_cells = soup.select("td.css-1su1bxu")  # Update the selector if needed
        count = len(server_cells)
        self.stdout.write(self.style.NOTICE(f"Found {count} servers on this page"))
        return count > 0

    def parse_html(self, html):
        """Parses the fetched HTML and extracts server data."""
        soup = BeautifulSoup(html, "html.parser")
        server_cells = soup.select("td.css-1su1bxu")  # Update the selector if needed
        servers_data = []

        # Get all existing server IDs from database for faster lookup
        existing_server_ids = set(Server.objects.values_list('server_id', flat=True))

        for cell in server_cells:
            try:
                # Get server link and extract ID
                server_link = cell.find('a')  # Simplified selector for the anchor tag
                if not server_link:
                    continue

                server_id = server_link['href'].split('/')[-1]
                try:
                    server_id = int(server_id)
                except ValueError:
                    continue

                server_name = server_link.text.strip()


                # Try to determine max group from server name
                name_lower = server_name.lower()
                max_group = None
                if 'quad' in name_lower:
                    max_group = 4
                elif 'trio' in name_lower:
                    max_group = 3
                elif 'duo' in name_lower and 'trio' not in name_lower:
                    max_group = 2
                elif 'solo' in name_lower and 'duo' not in name_lower and 'trio' not in name_lower:
                    max_group = 1

                # For now, just use current time as we're focusing on basic data
                wipe_dt = datetime.now(pytz.UTC)

                # Check if this is a new server or an existing one
                is_existing = server_id in existing_server_ids

                servers_data.append({
                    "server_id": server_id,
                    "server_name": server_name,
                    "wipe_time": self.format_wipe_time(wipe_dt),
                    "wipe_day": self.get_day_name(wipe_dt),
                    "max_group": max_group,
                    "is_existing": is_existing
                })

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error parsing server cell: {e}"))
                continue

        return servers_data

    def update_database(self, servers_data):
        """Updates the database with new servers and additional wipe schedules."""
        for server in servers_data:
            try:
                # Check if server exists
                existing_server = Server.objects.filter(server_id=server["server_id"]).first()
                
                if existing_server:
                    server["is_existing"] = True
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
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error updating database for server {server['server_name']}: {e}")
                )

    def handle(self, *args, **kwargs):
        """Main function to run the scraping process."""
        self.stdout.write(self.style.NOTICE("Starting BattleMetrics scraping process..."))
        
        total_servers_processed = 0
        page = 1
        max_pages = 10
        all_servers_data = []
        seen_server_ids = set()  # Track seen server IDs

        while page <= max_pages:
            self.stdout.write(self.style.NOTICE(f"\nProcessing page {page}..."))
            
            url = self.get_paginated_url(page)
            html = self.fetch_data(url)
            
            if html:
                if not self.has_servers(html):
                    self.stdout.write(
                        self.style.WARNING(f"No more servers found on page {page}. Stopping pagination.")
                    )
                    break

                servers_data = self.parse_html(html)
                if servers_data:
                    # Check for duplicate servers
                    new_servers = []
                    for server in servers_data:
                        if server["server_id"] not in seen_server_ids:
                            seen_server_ids.add(server["server_id"])
                            new_servers.append(server)
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"Duplicate server found: {server['server_name']} (ID: {server['server_id']})")
                            )
                    
                    if new_servers:
                        all_servers_data.extend(new_servers)
                        self.update_database(new_servers)
                        total_servers_processed += len(new_servers)
                        self.stdout.write(
                            self.style.SUCCESS(f"Processed {len(new_servers)} new servers from page {page}")
                        )
                    else:
                        self.stdout.write(self.style.WARNING("No new servers found on this page"))
                        if len(seen_server_ids) > 0:  # If we've seen servers before and now getting all duplicates
                            self.stdout.write(self.style.WARNING("Only found duplicate servers, stopping pagination"))
                            break
                else:
                    self.stdout.write(self.style.WARNING(f"No servers found on page {page}"))
                    break
            else:
                self.stdout.write(self.style.ERROR(f"Failed to retrieve content from page {page}"))
                break

            page += 1
            time.sleep(random.uniform(3, 6))  # Increased delay between pages

        self.stdout.write(
            self.style.SUCCESS(
                f"\nScraping completed. Total unique servers processed: {total_servers_processed}"
            )
        ) 
