# helpers/kobimeta.py
"""
Kodi/XBMC-style .nfo metadata parser and writer for episodes
Used as fallback / override source for showname, season, episode, title
"""

import os
from pathlib import Path
import unicodedata
from xml.etree import ElementTree as ET
from xml.dom import minidom

from . import plexlog as log

pluginid = "KOBI META"

# ───────────────────────────────────────────────
#   Helper functions for XML pretty-printing
# ───────────────────────────────────────────────

def _pretty_print(elem):
    """Indent XML element for human-readable output."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8')


def _dict_to_element(tag: str, data: dict) -> ET.Element:
    """Convert nested dict back to XML Element (simplified recursive version)."""
    elem = ET.Element(tag)

    for key, value in data.items():
        if isinstance(value, dict):
            child = _dict_to_element(key, value)
            elem.append(child)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    child = _dict_to_element(key, item)
                else:
                    child = ET.Element(key)
                    child.text = str(item)
                elem.append(child)
        else:
            child = ET.Element(key)
            child.text = str(value) if value is not None else ''
            elem.append(child)

    return elem


# ───────────────────────────────────────────────
#   Main functions
# ───────────────────────────────────────────────

def get_metadata(filepath: str) -> dict:
    """
    Read Kodi-style episode .nfo file (if exists) and extract useful fields.
    Also looks for tvshow.nfo one or two levels up if needed.
    Returns dict with: show, season, episode, title, aired, etc.
    """
    log.Log(f"Fetching Kodi metadata for {filepath}", pluginid, log.LL_DEBUG)

    path = Path(filepath)
    nfo_path = path.with_suffix('.nfo')

    episode_info = {}

    if not nfo_path.is_file():
        log.Log(f"No episode .nfo found at {nfo_path}", pluginid, log.LL_DEBUG)
    else:
        try:
            tree = ET.parse(str(nfo_path))
            root = tree.getroot()
            if root.tag != 'episodedetails':
                log.Log(f"Unexpected root tag in {nfo_path}: {root.tag}", pluginid, log.LL_WARN)
            else:
                for child in root:
                    if child.tag == 'showtitle' and child.text:
                        episode_info['show'] = child.text.strip()
                    elif child.tag == 'title' and child.text:
                        episode_info['title'] = child.text.strip()
                    elif child.tag == 'season' and child.text and child.text.isdigit():
                        episode_info['season'] = int(child.text)
                    elif child.tag == 'episode' and child.text and child.text.isdigit():
                        episode_info['episode'] = int(child.text)
                    elif child.tag == 'aired' and child.text:
                        episode_info['aired'] = child.text.strip()
        except ET.ParseError as e:
            log.Log(f"Failed to parse episode .nfo {nfo_path}: {e}", pluginid, log.LL_WARN)
        except Exception as e:
            log.Log(f"Unexpected error reading {nfo_path}: {e}", pluginid, log.LL_ERROR)

    # If no show title in episode nfo → try tvshow.nfo (same folder or parent)
    if 'show' not in episode_info:
        candidates = [
            path.parent / 'tvshow.nfo',
            path.parent.parent / 'tvshow.nfo'
        ]
        for tv_nfo in candidates:
            if tv_nfo.is_file():
                try:
                    tree = ET.parse(str(tv_nfo))
                    root = tree.getroot()
                    if root.tag == 'tvshow':
                        for child in root:
                            if child.tag == 'title' and child.text:
                                episode_info['show'] = child.text.strip()
                                log.Log(f"Found show title from tvshow.nfo: {episode_info['show']}", pluginid)
                                break
                except Exception as e:
                    log.Log(f"Could not read tvshow.nfo {tv_nfo}: {e}", pluginid, log.LL_DEBUG)
                if 'show' in episode_info:
                    break

    if not episode_info:
        log.Log("No usable Kodi metadata found", pluginid, log.LL_DEBUG)

    return episode_info


def makenfo(
    filepath: str,
    depth: int,
    metadata: dict,          # usually tsdb dict or fallback event dict
    artwork: dict,           # {'season': {'poster':..., 'thumb':...}, 'sport': {...}}
    showname: str,
    episodename: str,
    episodenr: int,
    season: int
):
    """
    Create / update Kodi-style episode .nfo file.
    Uses the new metadata (from TheSportsDB or fallback).
    """
    path = Path(filepath)
    nfo_path = path.with_suffix('.nfo')

    log.Log(f"Creating/updating .nfo: {nfo_path}", pluginid)

    root = ET.Element('episodedetails')

    # Core fields
    ET.SubElement(root, 'title').text = episodename
    ET.SubElement(root, 'showtitle').text = showname
    ET.SubElement(root, 'season').text = str(season)
    ET.SubElement(root, 'episode').text = str(episodenr)

    # Event / league info from metadata (TheSportsDB style)
    if 'event' in metadata and 'strEvent' in metadata['event']:
        ET.SubElement(root, 'plot').text = metadata['event'].get('strEvent', '')
        ET.SubElement(root, 'original_filename').text = path.name  # optional helper

    if 'league' in metadata and 'strLeague' in metadata['league']:
        ET.SubElement(root, 'genre').text = metadata['league']['strLeague']

    # Air date if available
    if 'dateEvent' in metadata.get('event', {}):
        ET.SubElement(root, 'aired').text = metadata['event']['dateEvent']

    # Artwork paths (local only – Kodi likes relative or absolute paths)
    if artwork.get('season', {}).get('poster'):
        ET.SubElement(root, 'thumb').text = artwork['season']['poster']
    if artwork.get('season', {}).get('thumb'):
        thumb = ET.SubElement(root, 'thumb')
        thumb.text = artwork['season']['thumb']
        thumb.set('type', 'thumb')  # Kodi sometimes uses aspect or type

    # Optional: try to add more from TheSportsDB (venue, teams, etc.)
    event = metadata.get('event', {})
    if 'strVenue' in event and event['strVenue']:
        ET.SubElement(root, 'venue').text = event['strVenue']
    if 'strHomeTeam' in event and 'strAwayTeam' in event:
        ET.SubElement(root, 'teams').text = f"{event['strHomeTeam']} vs {event['strAwayTeam']}"

    # Write pretty XML
    try:
        xml_str = _pretty_print(root)
        with open(nfo_path, 'wb') as f:
            f.write(xml_str)
        log.Log(f"Successfully wrote .nfo: {nfo_path}", pluginid)
    except Exception as e:
        log.Log(f"Failed to write .nfo {nfo_path}: {e}", pluginid, log.LL_ERROR)


# Legacy / compatibility alias (if any old code still calls this name)
create_episode_nfo = makenfo