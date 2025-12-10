import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

# Load environment variables once when the module is imported.
load_dotenv()

# Last.fm configuration
LASTFM_BASE_URL: str = "https://ws.audioscrobbler.com/2.0"
LASTFM_API_KEY: Optional[str] = os.getenv("LASTFM_API_KEY")

# Spotify configuration
SPOTIFY_CLIENT_ID: Optional[str] = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET: Optional[str] = os.getenv("SPOTIFY_CLIENT_SECRET")

# Token cache for Spotify (internal use).
_spotify_token_cache: Optional[Dict[str, Any]] = None


def _lastfm_get(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call a Last.fm API method and return the JSON response.

    This helper automatically adds the API key and JSON format, and raises on
    HTTP errors or explicit Last.fm API errors.

    Args:
        params:
            Query parameters for the Last.fm API call. Must include a "method"
            key and any method-specific parameters (e.g., "user", "artist").

    Returns:
        The decoded JSON response as a dictionary.

    Raises:
        Exception: If the API key is missing, the HTTP request fails, or
        Last.fm returns an error in the JSON payload.
    """
    if not LASTFM_API_KEY:
        raise Exception("LASTFM_API_KEY environment variable is not set.")

    base_params: Dict[str, Any] = {
        "api_key": LASTFM_API_KEY,
        "format": "json",
    }

    response = requests.get(LASTFM_BASE_URL, params={**base_params, **params})
    if response.status_code != 200:
        raise Exception(f"Last.fm HTTP {response.status_code}: {response.text}")

    data: Dict[str, Any] = response.json()
    if "error" in data:
        raise Exception(f"Last.fm error {data.get('error')}: {data.get('message')}")
    return data


def _get_spotify_token() -> str:
    """
    Obtain a Spotify access token using the client credentials flow.

    Tokens are cached in memory until shortly before they expire, so repeated
    calls reuse an existing token when possible.

    Returns:
        A bearer token string for use with Spotify Web API requests.

    Raises:
        Exception: If Spotify client credentials are missing or the token
        request fails.
    """
    global _spotify_token_cache

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise Exception(
            "Spotify credentials are not configured. "
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
        )

    if _spotify_token_cache and _spotify_token_cache["expires_at"] > datetime.now():
        return _spotify_token_cache["token"]

    auth_url = "https://accounts.spotify.com/api/token"
    auth_data = {
        "grant_type": "client_credentials",
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(auth_url, data=auth_data)
    if response.status_code != 200:
        raise Exception(f"Spotify auth failed: {response.text}")

    token_data: Dict[str, Any] = response.json()
    expires_in: int = int(token_data.get("expires_in", 3600))

    _spotify_token_cache = {
        "token": token_data["access_token"],
        "expires_at": datetime.now() + timedelta(seconds=expires_in - 60),
    }
    return _spotify_token_cache["token"]


def _spotify_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Call a Spotify Web API endpoint and return the JSON response.

    This helper attaches a bearer token and raises on HTTP errors.

    Args:
        endpoint:
            The Spotify API path starting with a slash (e.g., "/search").
        params:
            Optional query parameters for the request.

    Returns:
        The decoded JSON response as a dictionary.

    Raises:
        Exception: If acquiring a token fails or the HTTP request is not
        successful.
    """
    token = _get_spotify_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"https://api.spotify.com/v1{endpoint}",
        headers=headers,
        params=params,
    )
    if response.status_code != 200:
        raise Exception(f"Spotify HTTP {response.status_code}: {response.text}")
    return response.json()


# ---------------------------------------------------------------------------
# Public Last.fm functions
# ---------------------------------------------------------------------------


def get_lastfm_user_info(username: str) -> Dict[str, Any]:
    """
    Get public profile information for a Last.fm user.

    This wraps the Last.fm "user.getInfo" method.

    Args:
        username:
            The Last.fm username to look up.

    Returns:
        The Last.fm JSON response describing the user.

    Raises:
        Exception: If the request fails or Last.fm returns an error.
    """
    return _lastfm_get({"method": "user.getInfo", "user": username})


def get_artist_info(artist_name: str) -> Dict[str, Any]:
    """
    Get metadata for an artist from Last.fm.

    This wraps the Last.fm "artist.getInfo" method.

    Args:
        artist_name:
            The name of the artist to look up.

    Returns:
        The Last.fm JSON response describing the artist.

    Raises:
        Exception: If the request fails or Last.fm returns an error.
    """
    return _lastfm_get({"method": "artist.getInfo", "artist": artist_name})


def get_track_info(artist_name: str, track_name: str) -> Dict[str, Any]:
    """
    Get metadata for a track from Last.fm.

    This wraps the Last.fm "track.getInfo" method.

    Args:
        artist_name:
            Name of the track's artist.
        track_name:
            Title of the track.

    Returns:
        The Last.fm JSON response describing the track.

    Raises:
        Exception: If the request fails or Last.fm returns an error.
    """
    return _lastfm_get(
        {
            "method": "track.getInfo",
            "artist": artist_name,
            "track": track_name,
        }
    )

def get_lastfm_user_top_artists(
    username: str,
    period: str = "overall",
    limit: int = 50,
    page: int = 1,
) -> Dict[str, Any]:
    """
    Get the top artists listened to by a Last.fm user.

    This wraps the Last.fm "user.getTopArtists" method.

    Args:
        username:
            The Last.fm username to look up.
        period:
            Time period for top artists. Options: "overall", "7day", 
            "1month", "3month", "6month", "12month". Defaults to "overall".
        limit:
            Maximum number of artist results (1–50). Defaults to 50.
        page:
            Page number to fetch. Defaults to 1.

    Returns:
        The Last.fm JSON response containing top artists with playcount.

    Raises:
        Exception: If the request fails or Last.fm returns an error.
    """
    return _lastfm_get(
        {
            "method": "user.getTopArtists",
            "user": username,
            "period": period,
            "limit": limit,
            "page": page,
        }
    )


# ---------------------------------------------------------------------------
# Public Spotify functions
# ---------------------------------------------------------------------------


def search_artists_by_genre(genre: str, limit: int = 20) -> Dict[str, Any]:
    """
    Search for Spotify artists associated with a given genre.

    This uses the Spotify "/search" endpoint with a genre query.

    Args:
        genre:
            Genre string to search for (e.g., "rock", "synthwave").
        limit:
            Maximum number of artist results to request (1–50). Defaults to 20.

    Returns:
        The Spotify JSON search response.

    Raises:
        Exception: If token acquisition or the HTTP request fails.
    """
    return _spotify_get(
        "/search",
        {
            "q": f'genre:"{genre}"',
            "type": "artist",
            "limit": limit,
        },
    )


def get_artist_details(artist_id: str) -> Dict[str, Any]:
    """
    Get detailed information for a Spotify artist by ID.

    This uses the Spotify "/artists/{id}" endpoint.

    Args:
        artist_id:
            The Spotify artist ID.

    Returns:
        The Spotify JSON response describing the artist.

    Raises:
        Exception: If token acquisition or the HTTP request fails.
    """
    return _spotify_get(f"/artists/{artist_id}")


def get_artist_top_tracks(artist_id: str, market: str = "US") -> Dict[str, Any]:
    """
    Get an artist's top tracks from Spotify for a given market.

    This uses the Spotify "/artists/{id}/top-tracks" endpoint.

    Args:
        artist_id:
            The Spotify artist ID.
        market:
            ISO 3166-1 alpha-2 country code used as the market context
            (e.g., "US"). Defaults to "US".

    Returns:
        The Spotify JSON response containing the top tracks.

    Raises:
        Exception: If token acquisition or the HTTP request fails.
    """
    return _spotify_get(f"/artists/{artist_id}/top-tracks", {"market": market})


def get_artist_albums(
    artist_id: str,
    limit: int = 20,
    include_groups: str = "album",
) -> Dict[str, Any]:
    """
    Get a list of albums or releases for a Spotify artist.

    This uses the Spotify "/artists/{id}/albums" endpoint.

    Args:
        artist_id:
            The Spotify artist ID.
        limit:
            Maximum number of album items to request (1–50). Defaults to 20.
        include_groups:
            Comma-separated album group filters (e.g., "album", "single",
            "appears_on", "compilation"). Defaults to "album".

    Returns:
        The Spotify JSON response containing the artist's releases.

    Raises:
        Exception: If token acquisition or the HTTP request fails.
    """
    return _spotify_get(
        f"/artists/{artist_id}/albums",
        {
            "limit": limit,
            "include_groups": include_groups,
        },
    )

def search_artist_by_name(artist_name: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search for Spotify artists by name.

    This uses the Spotify "/search" endpoint with artist type.

    Args:
        artist_name:
            Name of the artist to search for (e.g., "Metallica", "Bon Jovi").
        limit:
            Maximum number of results to return (1–50). Defaults to 10.

    Returns:
        The Spotify JSON search response containing matching artists.

    Raises:
        Exception: If token acquisition or the HTTP request fails.
    """
    return _spotify_get(
        "/search",
        {
            "q": artist_name,
            "type": "artist",
            "limit": limit,
        },
    )


def get_artist_details_by_name(artist_name: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information for a Spotify artist by name.

    This is a convenience function that searches for the artist by name,
    selects the top match, and returns full details including followers,
    popularity, and genres.

    Args:
        artist_name:
            Name of the artist (e.g., "Metallica", "Bon Jovi").

    Returns:
        The Spotify JSON response with artist details (followers, popularity,
        genres), or None if no artist is found.

    Raises:
        Exception: If token acquisition or HTTP requests fail.
    """
    search_results = search_artist_by_name(artist_name, limit=1)
    
    artists = search_results.get("artists", {}).get("items", [])
    if not artists:
        return None
    
    # Get the first (best) match
    artist_id = artists[0]["id"]
    return get_artist_details(artist_id)
