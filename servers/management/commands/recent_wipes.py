from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup
import requests
import random
import time
from django.utils import timezone
from datetime import datetime
from servers.models import Server

class Command(BaseCommand):
    help = 'Scrapes recently wiped servers from Just-Wiped and saves new servers to the database'

    def fetch_data(self):
        """Fetches page content while bypassing cache issues."""
        url = f"https://just-wiped.net/rust_servers?nocache={random.randint(1, 1000000)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }

        session = requests.Session()
        session.headers.update(headers)

        try:
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                self.stdout.write(self.style.ERROR(f"Failed to fetch data, status code: {response.status_code}"))
                return None
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Request error: {e}"))
            return None

    def parse_html(self, html):
        """Parses the fetched HTML and extracts server data."""
        soup = BeautifulSoup(html, "html.parser")
        server_links = soup.find_all('a', title="Open the server details page")
        servers_data = []

        for link in server_links:
            try:
                server_id = int(link['href'].split('/')[-1])
                server_name = link.text.strip()

                timeago = link.find_next('time', class_='timeago')
                wipe_time = datetime.fromisoformat(timeago['datetime'].replace('Z', '+00:00')) if timeago else timezone.now()

                max_group = None
                if 'solo' in server_name.lower():
                    max_group = 1
                elif 'duo' in server_name.lower():
                    max_group = 2
                elif 'trio' in server_name.lower():
                    max_group = 3
                elif 'quad' in server_name.lower():
                    max_group = 4

                servers_data.append({
                    "server_id": server_id,
                    "server_name": server_name,
                    "wipe_time": wipe_time,
                    "max_group": max_group
                })
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error parsing server: {e}"))

        return servers_data

    def update_database(self, servers_data):
        """Updates the database with new or updated server information."""
        for server in servers_data:
            existing_server = Server.objects.filter(server_id=server["server_id"]).first()

            if existing_server:
                should_update = False
                if "Unknown" in existing_server.server_name:
                    existing_server.server_name = server["server_name"]
                    existing_server.max_group = server["max_group"]
                    should_update = True
                if not existing_server.wipe_time:
                    existing_server.wipe_time = server["wipe_time"]
                    should_update = True
                if should_update:
                    existing_server.save()
                    self.stdout.write(self.style.SUCCESS(f"Updated server: {server['server_name']} (ID: {server['server_id']})"))
                else:
                    self.stdout.write(self.style.WARNING(f"Server already exists: {server['server_name']} (ID: {server['server_id']})"))
            else:
                Server.objects.create(**server)
                self.stdout.write(self.style.SUCCESS(f"Added new server: {server['server_name']} (ID: {server['server_id']})"))

    def handle(self, *args, **kwargs):
        """Main function to run the scraping process."""
        self.stdout.write(self.style.NOTICE("Starting scraping process..."))
        html = self.fetch_data()
        
        if html:
            servers_data = self.parse_html(html)
            if servers_data:
                self.update_database(servers_data)
            else:
                self.stdout.write(self.style.WARNING("No new servers found."))
        else:
            self.stdout.write(self.style.ERROR("Failed to retrieve page content."))

        self.stdout.write(self.style.SUCCESS("Scraping completed."))