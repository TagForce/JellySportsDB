# helpers/sportsdb_client.py
"""
TheSportsDB v2 API client – object-oriented version
Handles league/event lookup, fuzzy matching, caching awareness, etc.
"""

import os
import json
import re
import time
import ssl
import unicodedata
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from . import nameregex
from . import plexlog as log
from .jaro import jaro_winkler_metric
from .fuzzy import compare as fuzzy_compare   # if you have fuzzy.py

pluginid = "SPORTSDB API"

season_rx = r'[_ ]?\([0-9]{4}\)'
sportsrx = {
    'TeamvsTeam': [
        r'(?P<hometeam>.*) vs (?P<awayteam>.*)',
        r'(?P<awayteam>.*) (@| at ) (?P<hometeam>.*)'
    ],
    'Event': [
        r'(?P<eventname>.*) (@| at ) (?P<venue>.*)',
        r'(?P<eventname>.*)'
    ]
}


class TheSportsDBClient:
    def __init__(self, apikey_path: str = "tsdbapi.txt"):
        self.apikey = self._load_apikey(apikey_path)
        self.headers = {'X-API-KEY': self.apikey}
        self.baseurl = 'https://www.thesportsdb.com/api/v2/json'
        self.ssl_ctx = ssl._create_unverified_context()

        # Cache settings (in-memory for simplicity; disk cache can be added later)
        self.cache = {}
        self.cache_time = {}

    def _load_apikey(self, path: str) -> str:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            log.Log(f"API key file not found: {path}", pluginid, log.LL_CRIT)
            raise ValueError(f"Missing TheSportsDB API key file: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            key = f.readline().strip()
        log.Log(f"Loaded TheSportsDB API key from {path}", pluginid, log.LL_INFO)
        return key

    def _fetch_json(self, endpoint: str, retries: int = 3) -> dict:
        url = self.baseurl + endpoint
        log.Log(f"Fetching: {url}", pluginid, log.LL_DEBUG)

        for attempt in range(retries):
            try:
                req = Request(url, headers=self.headers)
                with urlopen(req, context=self.ssl_ctx) as resp:
                    if resp.getcode() == 429:
                        log.Log("Rate limit hit (429) – waiting 1s", pluginid, log.LL_WARN)
                        time.sleep(1.2)
                        continue
                    data = json.load(resp)
                    return data
            except HTTPError as e:
                if e.code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                log.Log(f"HTTP {e.code} on {endpoint}", pluginid, log.LL_ERROR)
                return {}
            except Exception as e:
                log.LogExcept(f"Fetch failed for {endpoint}", e, pluginid)
                return {}

        log.Log(f"Gave up after {retries} attempts on {endpoint}", pluginid, log.LL_ERROR)
        return {}

    # ───────────────────────────────────────────────
    #   Core lookup methods (ported from original)
    # ───────────────────────────────────────────────

    def search_league(self, showname: str) -> str:
        """Try to find a league ID from a show/series name."""
        if not showname:
            return ""

        # Basic cleaning
        clean = re.sub(r'\s*\([0-9]{4}\)', '', showname).strip().lower()

        # You can expand this with more heuristics / known mappings
        # For now: direct name search (v2 endpoint)
        data = self._fetch_json(f"/searchleagues.php?l={clean.replace(' ', '_')}")
        if not data or 'leagues' not in data or not data['leagues']:
            log.Log(f"No league found for '{showname}'", pluginid, log.LL_WARN)
            return ""

        # Take first reasonable match (can be improved with fuzzy later)
        league = data['leagues'][0]
        log.Log(f"League match: {league.get('strLeague')} → ID {league.get('idLeague')}", pluginid)
        return league.get('idLeague', '')

    def get_episode(self, filename: str, league_id: str, episode_info: dict) -> tuple[dict, dict]:
        """
        Main high-level method: find league + best matching event.
        Returns (league_dict, event_dict)
        """
        if not league_id:
            log.Log("No league ID provided → cannot lookup event", pluginid, log.LL_WARN)
            return {}, {}

        # Fetch season events (you may want to add caching here)
        season_events = self._fetch_season_events(league_id, episode_info.get('year', ''))
        if not season_events:
            return {}, {}

        # Try to find best event match
        matched_event = self._find_best_event_match(season_events, episode_info)

        if matched_event:
            full_event = self._fetch_json(f"/lookupevent.php?id={matched_event['idEvent']}")
            event_data = full_event.get('events', [{}])[0] if full_event.get('events') else {}
            league_data = self._fetch_json(f"/lookupleague.php?id={league_id}").get('leagues', [{}])[0]
            return league_data, event_data

        log.Log(f"No matching event found in league {league_id}", pluginid, log.LL_INFO)
        return {}, {}

    def _fetch_season_events(self, league_id: str, year: str = "") -> list:
        """Get all events for a league + season year."""
        endpoint = f"/eventsseason.php?id={league_id}"
        if year:
            endpoint += f"&s={year}"
        data = self._fetch_json(endpoint)
        return data.get('events', []) or []

    def _find_best_event_match(self, events: list, ep: dict) -> dict | None:
        """
        Core fuzzy matching logic – tries different strategies.
        Returns best matching event dict or None.
        """
        candidates = []

        target_name = ep.get('event', '').lower()
        target_session = ep.get('session', '').lower()
        target_week = ep.get('week', 0)

        for event in events:
            ev_name = (event.get('strEvent') or '').lower()
            ev_round = int(event.get('intRound') or 0)

            # Exact week + session keyword match (strongest)
            if target_week and target_week == ev_round:
                if target_session and target_session in ev_name:
                    log.Log(f"Strong match: week {target_week} + '{target_session}' in '{ev_name}'", pluginid)
                    return event

            # Fuzzy name + session similarity
            score = fuzzy_compare(target_name, ev_name)
            if score > 0.82:
                candidates.append((score, event))

            # Fallback: main race / feature event heuristic
            if nameregex.isMainEvent(ev_name) and target_session in ('race', 'feature', 'main'):
                candidates.append((0.90, event))  # high artificial score

        if not candidates:
            return None

        # Sort by descending score
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]
        log.Log(f"Best fuzzy match: {best.get('strEvent')} (score ≈ {candidates[0][0]:.3f})", pluginid)
        return best

    # ───────────────────────────────────────────────
    #   Optional extra helpers (can be expanded)
    # ───────────────────────────────────────────────

    def get_teamgame(self, league_id: str, episode: dict) -> dict:
        """Alternative lookup path for team-vs-team naming patterns."""
        # Implement if needed – similar to get_episode but using sportsrx['TeamvsTeam']
        return {}

    def fetch_artwork(self, url: str) -> bytes | None:
        """Download raw image bytes from any artwork URL."""
        if not url:
            return None
        try:
            req = Request(url, headers=self.headers)
            with urlopen(req, context=self.ssl_ctx) as resp:
                return resp.read()
        except Exception as e:
            log.LogExcept(f"Artwork download failed: {url}", e, pluginid)
            return None

    def test_event_file(self, filename: str) -> str:
        """Check for .tsdbevt sidecar file with event ID."""
        base, _ = os.path.splitext(filename)
        evtfile = base + '.tsdbevt'
        if not os.path.isfile(evtfile):
            return ''
        try:
            with open(evtfile, 'r', encoding='utf-8') as f:
                event_id = f.readline().strip()
            if re.match(r'^[0-9]{3,10}$', event_id):
                return event_id
        except Exception:
            pass
        return ''