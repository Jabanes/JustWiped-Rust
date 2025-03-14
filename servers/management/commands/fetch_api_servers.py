from django.core.management.base import BaseCommand
import requests
import time
from datetime import datetime
import pytz
from servers.models import Server, WipeSchedule
import json
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Fetches Rust servers data from various APIs and saves to database'

    def __init__(self):
        super().__init__()
        # You should store these in Django settings or environment variables
        self.battlemetrics_api_key = getattr(settings, 'BATTLEMETRICS_API_KEY', '')
        self.headers = {
            'Authorization': f'Bearer {self.battlemetrics_api_key}',
            'Accept': 'application/json'
        }

    def format_wipe_time(self, dt):
        """Convert datetime to EST hour format."""
        est = pytz.timezone('US/Eastern')
        dt_est = dt.astimezone(est)
        hour = dt_est.strftime('%I%p').lstrip('0').lower()  # Convert to 1pm format
        return f"{hour} est"

    def get_day_name(self, dt):
        """Convert datetime to day name."""
        return dt.strftime('%A')  # Returns full day name (Monday, Tuesday, etc.)

    def fetch_battlemetrics_servers(self, page=1):
        """Fetch Rust servers from BattleMetrics API."""
        url = 'https://api.battlemetrics.com/servers'
        params = {
            'filter[game]': 'rust',
            'filter[status]': 'online',
            'page[size]': 100,
            'page[number]': page,
            'sort': '-players'  # Sort by most players
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                self.stdout.write(
                    self.style.ERROR(f"BattleMetrics API error: {response.status_code}")
                )
                return None
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error fetching from BattleMetrics: {e}")
            )
            return None

    def extract_server_info(self, server_data):
        """Extract relevant server information from API response."""
        try:
            attributes = server_data['attributes']
            server_name = attributes['name']
            
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

            # Get wipe info from server details
            details = attributes.get('details', {})
            wipe_info = details.get('rust_last_wipe')
            
            if wipe_info:
                wipe_dt = datetime.fromisoformat(wipe_info.replace('Z', '+00:00'))
            else:
                wipe_dt = datetime.now(pytz.UTC)

            return {
                "server_id": int(attributes['id']),
                "server_name": server_name,
                "wipe_time": self.format_wipe_time(wipe_dt),
                "wipe_day": self.get_day_name(wipe_dt),
                "max_group": max_group,
                "is_existing": False  # Will be updated when checking database
            }
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error extracting server info: {e}")
            )
            return None

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

    def save_existing_servers_to_json(self, existing_servers):
        """Save existing server names to a JSON file."""
        # Extract only the names from the existing_servers list
        server_names = [server['name'] for server in existing_servers]
        
        # Remove duplicates while preserving order
        unique_server_names = list(dict.fromkeys(server_names))
        
        # Define the file path (in the same directory as the script)
        file_path = os.path.join(os.path.dirname(__file__), 'api_servers.json')
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(unique_server_names, f, indent=4)
            
            self.stdout.write(
                self.style.SUCCESS(f"Saved {len(unique_server_names)} server names to {file_path}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error saving server names to JSON: {e}")
            )

    def handle(self, *args, **kwargs):
        """Main function to run the API fetching process."""
        if not self.battlemetrics_api_key:
            self.stdout.write(
                self.style.ERROR("BattleMetrics API key not found. Please add it to your Django settings.")
            )
            return

        self.stdout.write(self.style.NOTICE("Starting API server fetch process..."))
        
        existing_servers = []
        total_servers_processed = 0
        page = 1
        max_pages = 10  # Adjust this based on your needs

        while page <= max_pages:
            self.stdout.write(self.style.NOTICE(f"\nFetching page {page} from BattleMetrics API..."))
            
            response_data = self.fetch_battlemetrics_servers(page)
            if not response_data:
                break

            servers_data = []
            for server in response_data.get('data', []):
                server_info = self.extract_server_info(server)
                if server_info:
                    servers_data.append(server_info)

            if servers_data:
                # Track existing servers
                for server in servers_data:
                    if server["is_existing"]:
                        existing_servers.append({
                            "name": server["server_name"],
                            "id": server["server_id"]
                        })
                
                self.update_database(servers_data)
                total_servers_processed += len(servers_data)
                self.stdout.write(
                    self.style.SUCCESS(f"Processed {len(servers_data)} servers from page {page}")
                )
            else:
                self.stdout.write(self.style.WARNING(f"No servers found on page {page}"))
                break

            # Check if we've reached the last page
            if len(response_data.get('data', [])) < 100:
                break

            page += 1
            time.sleep(2)  # Rate limiting

        # Save existing servers to JSON file
        self.save_existing_servers_to_json(existing_servers)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nAPI fetch completed. Total servers processed: {total_servers_processed}"
            )
        ) 