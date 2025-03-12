# servers/scraper.py
import requests
from bs4 import BeautifulSoup

def scrape_server_details(server_id):
    url = f"https://just-wiped.net/rust_servers/{server_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # Use .find() and check if the element exists before trying to access its text
        server_name = soup.find("h1", class_="server-name")
        wipe_time = soup.find("span", class_="wipe-time")
        max_group = soup.find("span", class_="max-group")

        # Check if elements exist before accessing their text
        return {
            "server_id": server_id,
            "server_name": server_name.text if server_name else "Unknown Server Name",  # Default value if not found
            "wipe_time": wipe_time.text if wipe_time else "Unknown Wipe Time",  # Default value if not found
            "max_group": max_group.text if max_group else "Unknown Max Group",  # Default value if not found
        }
    else:
        print(f"Failed to fetch server {server_id}, status code: {response.status_code}")
        return None
