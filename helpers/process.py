'''
helpers/process.py
Object-oriented / client-injected version – 2026 refactor
'''

import os
import unicodedata
from pathlib import Path

from . import nameregex
from . import kobimeta
from . import plexlog as log
from . import fuzzy
from .jellyfin_client import JellyfinClient
from .sportsdb_client import TheSportsDBClient

pluginid = "PROCESSOR"

# Global references – set by jellysportsdb.py via set_clients()
_jellyfin_client: JellyfinClient = None
_sportsdb_client: TheSportsDBClient = None


def set_clients(jellyfin: JellyfinClient, sportsdb: TheSportsDBClient):
    """Called once at startup by the main application."""
    global _jellyfin_client, _sportsdb_client
    _jellyfin_client = jellyfin
    _sportsdb_client = sportsdb


def process_file(file: str, depth: int):
    """
    Main entry point for processing one sports video file.
    Called from filesystem watcher.
    """
    if not _jellyfin_client or not _sportsdb_client:
        log.Log("Clients not initialized – cannot process file", pluginid, log.LL_ERROR)
        return {'message': 'clients not ready'}

    log.Log(f"Working on file | {file} | (depth={depth})", pluginid)

    diskfile = {}
    diskfile['entity'] = {}
    diskfile['entity']['path'] = os.path.dirname(file)
    diskfile['entity']['filename'] = os.path.basename(file)
    diskfile['entity']['name'], diskfile['entity']['ext'] = os.path.splitext(diskfile['entity']['filename'])
    diskfile['entity']['cleanname'] = nameregex.cleanfilenames(
        unicodedata.normalize('NFC', diskfile['entity']['name'])
    )

    # Parse episode info from filename
    diskfile['episode'] = nameregex.get_episode(diskfile['entity']['cleanname'])

    if diskfile['episode'].get('retype'):
        session_info = nameregex.get_session(diskfile['episode'], diskfile['entity']['cleanname'])
        diskfile['episode']['session'] = session_info.get('sessionname', '')
    else:
        diskfile['episode']['session'] = ''

    # Kobi/XBMC-style .nfo metadata (preferred if present)
    diskfile['kobimeta'] = kobimeta.get_metadata(file)

    # Build display names / numbers – preference: kobi > filename parsing
    showname = ''
    episodename = ''
    episodenr = 0
    season = 0
    year = diskfile['episode'].get('year', '')

    if 'show' in diskfile['episode']:
        showname = diskfile['episode']['show']

    if 'season' in diskfile['episode']:
        if diskfile['episode'].get('week', 9999) != 9999 and not diskfile['episode'].get('preseason'):
            season = diskfile['episode']['week']
            showname = f"{showname} ({diskfile['episode']['season']})"
        else:
            season = diskfile['episode']['season']
            showname = f"{showname} ({diskfile['episode']['season']})"

    if 'event' in diskfile['episode']:
        episodename = diskfile['episode']['event']

    if 'episodenr' in diskfile['episode']:
        episodenr = diskfile['episode']['episodenr']

    # Session / event refinement
    if 'sessionname' in diskfile.get('session', {}):
        event_part = diskfile['session'].get('eventname', '')
        session_part = diskfile['session']['sessionname']
        episodename = f"{event_part} - {session_part}"
        if diskfile['episode'].get('week', 0):
            episodename = f"{diskfile['episode']['week']}: {episodenename}"
        if diskfile['episode'].get('preseason'):
            episodename = f"Preseason {episodenename}"
        diskfile['episode']['event'] = event_part

    if 'episodenr' in diskfile.get('session', {}):
        episodenr = diskfile['session']['episodenr']

    # Kobi override
    if 'show' in diskfile['kobimeta'] and diskfile['kobimeta']['show']:
        showname = diskfile['kobimeta']['show']
    if 'season' in diskfile['kobimeta']:
        season = diskfile['kobimeta']['season']
    if 'episode' in diskfile['kobimeta']:
        episodenr = diskfile['kobimeta']['episode']
    if 'title' in diskfile['kobimeta']:
        episodename = diskfile['kobimeta']['title']

    # TheSportsDB lookup
    diskfile['tsdb'] = {}
    tsdb_loaded = False

    if showname:
        log.Log(f"Looking up '{showname}' on TheSportsDB", pluginid, log.LL_INFO)
        league_info, event_info = _sportsdb_client.get_episode(
            file,
            _sportsdb_client.search_league(showname),
            diskfile['episode']
        )
        diskfile['tsdb']['league'] = league_info
        diskfile['tsdb']['event'] = event_info

        if diskfile['tsdb']['event'] and 'strEvent' in diskfile['tsdb']['event']:
            log.Log("Found TSDB event data", pluginid, log.LL_DEBUG)
            tsdb_loaded = True

            # Enhance title with round / venue
            if season == 0:
                diskfile['tsdb']['event']['strEvent'] = f"Non-Championship : {diskfile['tsdb']['event']['strEvent']}"
            elif 'strVenue' in diskfile['tsdb']['event'] and diskfile['tsdb']['event']['strVenue'] != 'Unknown':
                diskfile['tsdb']['event']['strEvent'] = (
                    f"{str(season).zfill(2)} : {diskfile['tsdb']['event']['strEvent']} @ {diskfile['tsdb']['event']['strVenue']}"
                )
            else:
                diskfile['tsdb']['event']['strEvent'] = (
                    f"{str(season).zfill(2)} : {diskfile['tsdb']['event']['strEvent']}"
                )

            seasonname = diskfile['tsdb']['event']['strEvent']

            # Write .nfo
            kobimeta.makenfo(
                file,
                depth,
                diskfile['tsdb'],
                diskfile.get('nfo', {}),
                showname,
                episodename,
                episodenr,
                season
            )
        else:
            log.Log("No usable TSDB event found", pluginid, log.LL_DEBUG)

    # Fallback: no TSDB data → still create basic .nfo from parsed info
    if not tsdb_loaded:
        log.Log("Using fallback metadata creation (no TSDB)", pluginid, log.LL_INFO)

        posterfile   = os.path.join(diskfile['entity']['path'], f"season{season:02d}.jpg")
        bannerfile   = os.path.join(diskfile['entity']['path'], f"season{season:02d}-banner.jpg")
        squarefile   = os.path.join(diskfile['entity']['path'], f"season{season:02d}-square.jpg")
        thumbfile    = os.path.join(diskfile['entity']['path'], f"{diskfile['entity']['name']}.jpg")

        dirname = diskfile['entity']['path']
        showjpg = os.path.join(dirname, "show.jpg")

        # Try to find show poster one level up if in season folder
        if depth == 2:
            parent_dir = os.path.dirname(dirname)
            if os.path.exists(os.path.join(parent_dir, "show.jpg")):
                showjpg = os.path.join(parent_dir, "show.jpg")

        nfo_art = {
            'season': {
                'thumb': thumbfile if os.path.isfile(thumbfile) else '',
                'poster': posterfile if os.path.isfile(posterfile) else ''
            },
            'sport': {
                'poster': showjpg if os.path.exists(showjpg) else ''
            }
        }

        nfo_event = {'event': {}, 'league': {}}
        nfo_event['event']['strEvent'] = diskfile['episode'].get('event', 'Unknown Event')
        nfo_event['event']['strVenue'] = 'Unknown'  # can be improved later

        if season == 0:
            title = "Non-Championship"
        elif nfo_event['event']['strVenue'] == 'Unknown':
            title = f"{season:02d} : {nfo_event['event']['strEvent']}"
        else:
            title = f"{season:02d} : {nfo_event['event']['strEvent']} @ {nfo_event['event']['strVenue']}"

        seasonname = title
        nfo_event['event']['strEvent'] = title

        kobimeta.makenfo(
            file,
            depth,
            nfo_event,
            nfo_art,
            showname,
            episodename,
            episodenr,
            season
        )

    # Final validation & Jellyfin push
    if not showname or not episodename or episodenr == 0:
        log.Log(f"No usable match for {file}", pluginid, log.LL_WARN)
        return {'message': 'no match'}

    backup_showname = diskfile['kobimeta'].get('show', '') if 'kobimeta' in diskfile else ''

    # Push to Jellyfin
    dirname = diskfile['entity']['path']
    filename = diskfile['entity']['filename']

    _jellyfin_client.dump_to_jelly(           # ← you'll need to implement or rename this method
        showname,
        backup_showname,
        dirname,
        filename,
        diskfile.get('nfo', {}),
        episodenr,
        episodename,
        season,
        seasonname if 'seasonname' in locals() else episodename
    )

    log.Log("Episode added to Jellyfin queue:", pluginid, log.LL_DEBUG)
    log.Log(f"  Series    : {showname}", pluginid, log.LL_DEBUG)
    log.Log(f"  Round/Week: {season}", pluginid, log.LL_DEBUG)
    log.Log(f"  Episode Nr: {episodenr}", pluginid, log.LL_DEBUG)
    log.Log(f"  Title     : {episodenename}", pluginid, log.LL_DEBUG)
    log.Log(f"  Year      : {year}", pluginid, log.LL_DEBUG)

    return {
        'showname': showname,
        'season': season,
        'episode': episodenr,
        'eptitle': episodename,
        'year': year
    }