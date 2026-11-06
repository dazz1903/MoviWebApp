"""Fetch movie details from OMDb without storing API keys in source code."""

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen


class OMDbError(Exception):
    """An OMDb lookup failed with a message safe to show to the user."""

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def fetch_movie(title):
    """Return normalized metadata for a movie found by its title."""
    if not title or len(title) > 200:
        raise OMDbError('Enter a movie title of 1–200 characters.', 400)
    api_key = os.environ.get('OMDB_API_KEY', '').strip()
    if not api_key:
        raise OMDbError('OMDb is not configured. Set OMDB_API_KEY and restart the app.', 503)

    parameters = urlencode({'apikey': api_key, 't': title, 'type': 'movie'})
    try:
        with urlopen(f'https://www.omdbapi.com/?{parameters}', timeout=10) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Do not expose exception URLs: they contain the API key.
        raise OMDbError('Could not reach OMDb. Please try again later.') from None

    if not isinstance(data, dict):
        raise OMDbError('OMDb returned an unexpected response. Please try again.')
    if data.get('Response') == 'False':
        if data.get('Error') == 'Movie not found!':
            raise OMDbError('Movie not found. Try another title.', 404)
        raise OMDbError('OMDb rejected the request. Check the API key and usage limit.')
    name = data.get('Title')
    if data.get('Response') != 'True' or not isinstance(name, str) or not name.strip():
        raise OMDbError('OMDb returned incomplete movie details.')
    if len(name.strip()) > 200:
        raise OMDbError('The returned movie title is too long to save.')

    raw_year = str(data.get('Year', ''))
    year_match = re.fullmatch(r'\d{4}', raw_year)
    poster = data.get('Poster')
    if not isinstance(poster, str) or urlparse(poster).scheme not in ('http', 'https'):
        poster = None
    director = data.get('Director')
    if director == 'N/A' or not isinstance(director, str):
        director = None
    return {
        'name': name.strip(),
        'director': director,
        'year': int(raw_year) if year_match else None,
        'poster_url': poster,
    }
