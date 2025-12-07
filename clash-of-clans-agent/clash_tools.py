import os
import requests
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv("/Users/paddy/Documents/Github/Dump-Truck/clash-of-clans-agent/.env")

BASE_URL = "https://api.clashofclans.com/v1"
TOKEN = os.getenv("CLASH_API_TOKEN")


def get_clan_details(clan_tag: str) -> Dict[str, Any]:
    """
    Fetch clan information by clan tag.
    
    Args:
        clan_tag (str): Clan tag (e.g., "#2YGRG9JCU")
    
    Returns:
        Dict[str, Any]: Clan information from the Clash of Clans API
    
    Raises:
        Exception: If API request fails (non-200 status code)
    """
    encoded_tag = clan_tag.replace("#", "%23")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/clans/{encoded_tag}", headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    
    return response.json()


def get_player_details(player_tag: str) -> Dict[str, Any]:
    """
    Fetch player information by player tag.
    
    Args:
        player_tag (str): Player tag (e.g., "#ABC123")
    
    Returns:
        Dict[str, Any]: Player information from the Clash of Clans API
    
    Raises:
        Exception: If API request fails (non-200 status code)
    """
    encoded_tag = player_tag.replace("#", "%23")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/players/{encoded_tag}", headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    
    return response.json()