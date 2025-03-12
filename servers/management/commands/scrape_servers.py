# servers/management/commands/scrape_servers.py
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
import requests
from servers.scraper import scrape_server_details  # Import from scraper.py

class Command(BaseCommand):
    help = 'Scrapes server data from Just-Wiped and inserts only new data into the database'

    def handle(self, *args, **kwargs):
        url = "https://just-wiped.net/rust_servers"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            server_links = soup.find_all("a", href=True)
            server_ids = [link['href'].split('/')[-1] for link in server_links if link['href'].startswith("/rust_servers/") and link['href'].split('/')[-1].isdigit()]

            for server_id in server_ids:
                details = scrape_server_details(server_id)
                if details:
                    # Handle details (e.g., insert into database)
                    pass

            self.stdout.write(self.style.SUCCESS("Scraping completed."))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to fetch main server page, status code: {response.status_code}"))
