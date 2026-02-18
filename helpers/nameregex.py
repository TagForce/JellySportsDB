# helpers/nameregex.py
"""
Filename → structured sports episode parser
Handles dated events, round/week-based naming, session detection (practice/qualifying/race/etc.)
"""

import re
import unicodedata
from typing import Dict, Any, Optional

from . import plexlog as log

pluginid = "NAME PARSER"

# ───────────────────────────────────────────────
#   Main episode filename regex patterns
# ───────────────────────────────────────────────

episode_regexes: Dict[str, list[str]] = {
    'dated': [
        # NHL.2015.09.25.New-York-Islanders.vs.Philadelphia-Flyers.720p.HDTV.60fps.x264-Reborn4HD_h.mp4
        r'^(?P<show>.*?)[^0-9a-zA-Z]+(?P<year>[0-9]{4})[^0-9a-zA-Z]+(?P<month>[0-9]{2})[^0-9a-zA-Z]+(?P<day>[0-9]{2})[^0-9a-zA-Z]+(?P<event>.*)$'
    ],
    'single_event': [
        # NCS.2024.Round.03.Watkins.Glen.Race.FoxSports.720p60.h264.English-egortech
        r'^(?P<show>[a-z]+.*?)[ ]+(?P<season>[0-9]{2,4})[ ]+(?P<preseason>(PS))?[ ]?[wekround]+[ ]?(?P<week>[0-9]+)[ ]+(?P<event>((?!(@| vs | at )).)*?)$'
    ],
    'match': [
        # NFL.2023.Week.01.New.Orleans.Saints.vs.Tennessee.Titans.1st.Half.FoxSports.720p60.h264.English-egortech
        r'^(?P<show>[^0-9]*?)[ ]+(?P<season>[0-9]{2,4})[ ]+(?P<preseason>(PS))?[ ]?[wekround]+[ ]?(?P<week>[0-9]+)[ ]+(?P<event>[a-z0-9 ]+[ ]+( @ | vs | at )[ ]+[a-z0-9 ]*?[ ]*)$'
    ],
    'pack_event': [
        # 02.NASCAR.Cup.Series.2024.R13.Goodyear.400.Race.FS1.720P.mkv
        r'^(?P<ep>[0-9]*)[ ]+(?P<show>.+)[ ]+(?P<season>[0-9]{4})[ ]+(?P<preseason>(PS))?[ ]?[wekround]*[ ]*(?P<week>[0-9]+)[ ]+(?P<event>.*)$'
    ],
    'episodic': [
        # Euro 2024 - s06e01 - Groep F - Turkije - Georgie
        r'^(?P<show>.*?)[ ](?P<year>[0-9]{4})[ ]+s(?P<season>[0-9]+)[ ]*e(?P<ep>[0-9]+)[ ]*(?P<event>.*)$'
    ]
}

# ───────────────────────────────────────────────
#   Session / part detection regexes (practice, qualy, race, half, etc.)
# ───────────────────────────────────────────────

session_regexes: Dict[str, list[str]] = {
    'match_split': [
        r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?'
        r'((?P<sesname>half|period|quarter|inning|set)[ ]?)'
        r'((?P<ses2nr>[0-9]+)[ ]?)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ],
    'match_full': [
        r' ((?P<sesname>((full[ ]?))?(game|match))[ ]?)(?P<ses2nr>[0-9]+)?'
        r'[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ],
    'match_extra': [
        r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?'
        r'((?P<sesname>(o(ver)?|e(xtra)?)[ ]?(t(ime)?)(?![a-z])[ ]?))'
        r'(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ],
    'event_quali': [
        r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?'
        r'((?P<sesname>q(ual(y|if(ying( practice)?|ication( practice)?|ier(s)?){1})?)?)[ ]?)'
        r'(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ],
    'event_pract': [
        r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?'
        r'((?P<sesname>((f(ree))[ ]?)?practice|fp)[ ]?)'
        r'(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ],
    'event_shtot': [
        r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?'
        r'((?P<sesname>(top[ ]?([0-9]{1,2}[ ]?)|heat[ ]?)(races|shootout|q(ual(y|if(ying|ication|ier(s)?){1})?)?))[ ]?)'
        r'(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ],
    'event_race': [
        r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?'
        r'((?P<sesname>((full|sprint|feature|main)[ ]?)?(race((?=[^a-z])|$)([a-z ]*)|stage((?=[^a-z])|$)|day((?=[^a-z])|$)|finals((?=[^a-z])|$)|sprint((?=[^a-z])|$)))[ ]?)'
        r'(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'
    ]
}

session_episodes: Dict[str, int] = {
    'match_split': 100,
    'match_full':  100,
    'match_extra': 100,
    'event_quali': 200,
    'event_pract': 100,
    'event_shtot': 300,
    'event_race':  400
}

session_types: Dict[str, str] = {
    'match_split': 'event',
    'match_full':  'event',
    'match_extra': 'event',
    'event_quali': 'session',
    'event_pract': 'session',
    'event_shtot': 'session',
    'event_race':  'session'
}

# ───────────────────────────────────────────────
#   Main parsing functions
# ───────────────────────────────────────────────

def get_episode(cleanname: str) -> Dict[str, Any]:
    """
    Parse filename into structured episode info.
    Returns dict with keys like: show, year, season, week, event, episodenr, retype, etc.
    """
    log.Log(f"Parsing episode from: {cleanname}", pluginid, log.LL_DEBUG)

    for re_type, regex_list in episode_regexes.items():
        for rx in regex_list:
            match = re.search(rx, cleanname, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                episode = {
                    'retype': re_type,
                    'show': groups.get('show', '').strip(),
                    'year': groups.get('year', ''),
                    'season': int(groups.get('season', 0)) if groups.get('season', '').isdigit() else 0,
                    'week': int(groups.get('week', 0)) if groups.get('week', '').isdigit() else 9999,
                    'event': groups.get('event', '').strip(),
                    'preseason': bool(groups.get('preseason')),
                    'episodenr': int(groups.get('ep', 0)) if groups.get('ep', '').isdigit() else 0,
                }
                log.Log(f"Matched pattern '{re_type}': {episode}", pluginid, log.LL_DEBUG)
                return episode

    log.Log("No episode pattern matched – returning basic fallback", pluginid, log.LL_WARN)
    return {'retype': None, 'event': cleanname, 'show': '', 'year': '', 'season': 0, 'week': 0}


def get_session(episode_info: Dict[str, Any], full_cleanname: str) -> Dict[str, Any]:
    """
    Detect session/part (practice, qualy, race, half, etc.) from event string.
    Returns dict with: sessionname, eventname, episodenr, sessiontype, sessionnr
    """
    event_str = episode_info.get('event', '')
    if not event_str:
        return {}

    log.Log(f"Extracting session from event: {event_str}", pluginid, log.LL_DEBUG)

    for re_type, regex_list in session_regexes.items():
        for rx in regex_list:
            match = re.search(rx, event_str, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                session_info = {
                    'sessiontype': session_types.get(re_type, 'unknown'),
                    'sessionname': '',
                    'sessionnr': 1,
                    'eventname': event_str.replace(match.group(0), '').strip(),
                    'episodenr': session_episodes.get(re_type, 100)
                }

                # Build session name
                name_parts = []
                if groups.get('sesname'):
                    name_parts.append(groups['sesname'].strip().lower())
                if groups.get('ses2nr'):
                    session_info['sessionnr'] = int(groups['ses2nr'])
                    name_parts.append(groups['ses2nr'])
                if groups.get('ses3nr'):
                    name_parts.append(groups['ses3nr'])

                session_info['sessionname'] = ' '.join(name_parts).strip()

                # Special handling for sprint races (usually before main race)
                if 'sprint' in session_info['sessionname'].lower():
                    session_info['episodenr'] -= 5

                # Adjust episode number for non-championship / hash fallback
                if episode_info.get('week', 0) != 0 and episode_info.get('preseason'):
                    base = str(episode_info['week'])
                    hash_part = str(abs(hash(episode_info['event'].replace(match.group(0), '').strip())) % 1000)
                    session_info['episodenr'] = int(base + hash_part + str(session_info['episodenr']))
                elif episode_info.get('week', 0) == 0:
                    hash_part = str(abs(hash(episode_info['event'].replace(match.group(0), '').strip())) % 1000)
                    session_info['episodenr'] = int(hash_part + str(session_info['episodenr']))

                log.Log(f"Session detected: {session_info}", pluginid, log.LL_DEBUG)
                return session_info

    # Fallback: treat whole string as event name, no session
    return {
        'sessionname': '',
        'eventname': event_str,
        'episodenr': 100,
        'sessiontype': 'event',
        'sessionnr': 1
    }


def cleanfilenames(name: str) -> str:
    """Basic filename sanitizer – remove extra dots/spaces, normalize unicode."""
    # Normalize unicode form
    name = unicodedata.normalize('NFC', name)

    # Replace multiple dots/spaces with single
    name = re.sub(r'\.+', '.', name)
    name = re.sub(r'\s+', ' ', name)

    # Trim
    return name.strip()


# ───────────────────────────────────────────────
#   Utility / helper functions
# ───────────────────────────────────────────────

def hasSession(instr: str) -> bool:
    """Quick check if string contains any session pattern."""
    instr_lower = instr.lower()
    for rxs in session_regexes.values():
        for rx in rxs:
            if re.search(rx, instr_lower, re.IGNORECASE):
                return True
    return False


def removeSession(instr: str) -> str:
    """Remove detected session part from string."""
    result = instr
    for rxs in session_regexes.values():
        for rx in rxs:
            match = re.search(rx, result, re.IGNORECASE)
            if match:
                result = re.sub(rx, '', result, flags=re.IGNORECASE).strip()
    return result


def strSession(instr: str) -> str:
    """Extract the matched session substring (first match wins)."""
    for rxs in session_regexes.values():
        for rx in rxs:
            match = re.search(rx, instr, re.IGNORECASE)
            if match:
                return match.group(0).strip()
    return instr


def isMainEvent(instr: str) -> bool:
    """
    Heuristic: is this likely the main/feature race/event?
    (can be expanded with more patterns if needed)
    """
    lower = instr.lower()
    main_indicators = [
        r'\b(main|feature|grand prix|gp|final|decider)\b',
        r'\brace\b(?![a-z])',  # race not followed by letter
        r'\bgrand\s+prix\b'
    ]
    for pattern in main_indicators:
        if re.search(pattern, lower):
            return True
    return False


# Legacy / compatibility aliases
clean_file_name = cleanfilenames