# servers/tasks.py
from bs4 import BeautifulSoup
from celery import shared_task
import requests
from .models import Server
from .scraper import scrape_server_details  # Import from scraper.py
import logging

logger = logging.getLogger(__name__)
@shared_task
def scrape_and_store_server_data():
    url = "https://just-wiped.net/rust_servers"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # Parse HTML content
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all links to server pages
        server_links = soup.find_all("a", href=True)

        # Extract server IDs from the links, ensuring it's a valid numeric ID
        server_ids = []
        for link in server_links:
            href = link['href']
            if href.startswith("/rust_servers/"):
                server_id = href.split('/')[-1]
                # Only add numeric IDs to the list (ignore non-numeric like "map")
                if server_id.isdigit():
                    server_ids.append(server_id)

        # Now, for each server ID, scrape its details and insert into the database
        for server_id in server_ids:
            details = scrape_server_details(server_id)
            if details:
                # Check if the server data already exists in the database
                if not Server.objects.filter(server_id=details["server_id"]).exists():
                    # Use Django's ORM to insert new data
                    server = Server.objects.create(
                        server_id=details["server_id"],
                        server_name=details["server_name"],
                        wipe_time=details["wipe_time"],
                        max_group=details["max_group"]
                    )
                    print(f"Inserted new server: {details['server_name']}")
                    logger.info(f"Inserted new server: {details['server_name']} - {details['server_id']}")
                    
                else:
                    print(f"Server already exists: {details['server_name']}")
    else:
        print(f"Failed to fetch main server page, status code: {response.status_code}")
