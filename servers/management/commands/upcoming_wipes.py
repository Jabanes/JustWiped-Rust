from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup
import requests
from django.utils import timezone
from datetime import datetime
from servers.models import Server

class Command(BaseCommand):
    help = 'Scrapes upcoming wipes from Just-Wiped and saves new servers to database'

    def handle(self, *args, **kwargs):
        url = 'https://just-wiped.net/upcoming-wipes?region=europe&max_group=&s_type=&min_rating=40&difficulty='
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            timeago_elements = soup.find_all(class_='timeago')
            server_links = soup.find_all('a', title="Open the server details page")

            for timeago_element, server_link in zip(timeago_elements, server_links):
                try:
                    wipe_time = datetime.fromisoformat(timeago_element['datetime']) if 'datetime' in timeago_element.attrs else timezone.now()
                    server_name = server_link.get_text(strip=True)
                    server_id = int(server_link['href'].split('/')[-1]) if 'href' in server_link.attrs else None
                    max_group = None

                    if server_id:
                        if not Server.objects.filter(server_id=server_id).exists():
                            Server.objects.create(
                                server_id=server_id,
                                server_name=server_name,
                                wipe_time=wipe_time,
                                max_group=max_group
                            )
                            self.stdout.write(
                                self.style.SUCCESS(f"Added new server: {server_name} (ID: {server_id})")
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"Server already exists: {server_name} (ID: {server_id})")
                            )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing server: {e}")
                    )
                    continue

            self.stdout.write(self.style.SUCCESS("Scraping completed."))
        else:
            self.stdout.write(
                self.style.ERROR(f"Failed to retrieve the webpage, status code: {response.status_code}")
            )