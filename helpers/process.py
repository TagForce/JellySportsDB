'''
Created on 21 mei 2025

@author: Raymond
'''
import os.path, unicodedata
import nameregex as nameregex
import kobimeta
import plexlog as log
import sportsdb as tsdb
import jellyapi as api


pluginid = "PROCESSOR"

def ProcessFile(file, depth):
    
    # Immediately refresh Jellyfin as well.
    #log.Log("Refreshing Jellyfin Libraries", pluginid)
    #api.push_api("Library/Refresh")
    
    log.Log("Working on file | {0} |".format(file), pluginid)
    diskfile = {}
    
    # 'entity' is the part of the episode that holds the file system and general file information. It has no episode info
    diskfile['entity'] = {}
    diskfile['entity']['path'] = os.path.dirname(file)
    diskfile['entity']['filename'] = os.path.basename(file)
    diskfile['entity']['name'], diskfile['entity']['ext'] = os.path.splitext(diskfile['entity']['filename'])
    diskfile['entity']['cleanname'] = nameregex.cleanfilenames(unicodedata.normalize('NFC', unicode(diskfile['entity']['name'])))
    
    # 'episode' holds the episode information that can be derived from the file name.
    # It can be used to search TSDB for more elaborate information, or used on its own.
    diskfile['episode'] = nameregex.get_episode(diskfile['entity']['cleanname'])
    if diskfile['episode']['retype'] != None:
        diskfile['session'] = nameregex.get_session(diskfile['episode'], diskfile['entity']['cleanname'])
    else:
        diskfile['session'] = {}
    
    # 'kobimeta' holds the information that is derived from Kobi (formerly xbmc) Metadata .nfo files.
    # It is assumed to be purposefully added, so it takes preference over any other derived information.
    
    diskfile['kobimeta'] = kobimeta.get_metadata(file)
    
    showname = ''
    episodename = ''
    episodenr = 0
    season = 0
    year = diskfile['episode']['year']
    
    if 'show' in diskfile['episode'].keys():
        showname = diskfile['episode']['show']
    if 'season' in diskfile['episode'].keys():
        if diskfile['episode']['week'] != 9999:
            if not diskfile['episode']['preseason']:
                season = diskfile['episode']['week']
            showname = showname + ' (' + str(diskfile['episode']['season']) + ')'
        else:
            season = diskfile['episode']['season']
            showname = showname + ' (' + str(diskfile['episode']['season']) + ')'
    if 'event' in diskfile['episode'].keys():
        episodename = diskfile['episode']['event']
        eventname = episodename
    if 'episodenr' in diskfile['episode'].keys():
        episodenr = diskfile['episode']['episodenr']
    if 'sessionname' in diskfile['session'].keys():
        episodename = diskfile['session']['eventname'] + ' - ' + diskfile['session']['sessionname']
        if diskfile['episode']['week'] != 0:
            episodename = str(diskfile['episode']['week']) + ': ' + episodename
        if diskfile['episode']['preseason']:
            episodename = 'Preseason ' + episodename
        eventname = diskfile['session']['eventname']
        diskfile['episode']['event'] = eventname
    if 'episodenr' in diskfile['session'].keys():
        episodenr = diskfile['session']['episodenr']
    if 'show' in diskfile['kobimeta'].keys():
        if diskfile['kobimeta']['show'] != '':
            showname = diskfile['kobimeta']['show']
    if 'season' in diskfile['kobimeta'].keys():
        season = diskfile['kobimeta']['season']
    if 'episode' in diskfile['kobimeta'].keys():
        episodenr = diskfile['kobimeta']['episode']
    if 'title' in diskfile['kobimeta'].keys():
        episodename = diskfile['kobimeta']['title']
    
    diskfile['tsdb'] = {}
    tsdbloaded = False
    #if (len(diskfile['kobimeta']) == 0): # If there is kobimetadata, we trust it has all the info.
    if True:
        # If there is a showname look it up on the SportsDB, if there's not, skip it.
        log.Log("Looking up event on The SportsDB", pluginid, log.LL_INFO)
        diskfile['tsdb'] = {}
        diskfile['tsdb']['league'], diskfile['tsdb']['event'] = tsdb.get_episode(file, tsdb.search_league(showname), diskfile['episode'])
        log.Log("Finished lookup. Parsing results", pluginid, log.LL_INFO)
        log.Log("diskfile contents: {0}".format(diskfile['tsdb']['event']), pluginid, log.LL_DEBUG)
        if 'strLeague' in diskfile['tsdb']['event'].keys():
            if diskfile['tsdb']['event']['strLeague'] != '':
                log.Log("TSDB league: {0}".format(diskfile['tsdb']['event']['strLeague']), pluginid, log.LL_INFO)
                showname = '{0} ({1})'.format(diskfile['tsdb']['event']['strLeague'], diskfile['tsdb']['event']['strSeason'])
            if diskfile['tsdb']['event']['strEvent'] != '':
                log.Log("TSDB event : {0}".format(diskfile['tsdb']['event']['strEvent']), pluginid, log.LL_INFO)
                if nameregex.hasSession(diskfile['tsdb']['event']['strEvent']):
                    diskfile['tsdb']['event']['strEvent'] = nameregex.removeSession(diskfile['tsdb']['event']['strEvent'])
                episodename = diskfile['tsdb']['event']['strEvent'] + ' - ' + diskfile['session']['sessionname']
            
            # Event artwork
            posterfile = os.path.join(diskfile['entity']['path'], 'season{:02d}'.format(season) + '.jpg')
            bannerfile = os.path.join(diskfile['entity']['path'], 'season{:02d}'.format(season) + '-banner.jpg')
            squarefile = os.path.join(diskfile['entity']['path'], 'season{:02d}'.format(season) + '-square.jpg')
            thumbfile  = os.path.join(diskfile['entity']['path'], diskfile['entity']['name'] + '.jpg')
            
            # Season artwork
            dirname, filename = os.path.split(file)
            if depth == 2:
                # We're assuming to be in a season folder, so the show.jpg file should be one up.
                sdir, tail = os.path.split(dirname)
                showjpg = os.path.join(sdir, "show.jpg")
                if os.path.exists(showjpg):
                    sportfile = showjpg
                elif os.path.exists(os.path.join(dirname, "show.jpg")):
                    showjpg = os.path.join(dirname, "show.jpg")
                    sportfile = showjpg
                else:
                    sportfile = showjpg
            else:
                sportfile = os.path.join(dirname, "show.jpg")
            
            # Fetch information for NFO files.
            diskfile['nfo'] = {}
            if diskfile['tsdb'] != {}:
                # Get the league poster
                diskfile['nfo']['sport'] = {}
                diskfile['nfo']['sport']['poster'] = sportfile
                if not (os.path.isfile(sportfile)):
                    if (diskfile['tsdb']['league']['strPoster'] != ''):
                        try:
                            with open(sportfile, 'wb') as fp:
                                fp.write(tsdb.fetch_tsdb_art(diskfile['tsdb']['league']['strPoster']))
                        except Exception as e:
                            log.LogExcept('Failed to write season poster file', e, pluginid)
                            pass
                
                # Get the event artwork
                diskfile['nfo']['season'] = {}
                diskfile['nfo']['season']['poster'] = posterfile
                if not (os.path.isfile(posterfile)):
                    if (diskfile['tsdb']['event']['strPoster'] != ''):
                        try:
                            with open(posterfile, 'wb') as fp:
                                fp.write(tsdb.fetch_tsdb_art(diskfile['tsdb']['event']['strPoster']))
                        except Exception as e:
                            log.LogExcept('Failed to write season poster file', e, pluginid)
                            pass
                diskfile['nfo']['season']['banner'] = bannerfile
                if not (os.path.isfile(bannerfile)):
                    if (diskfile['tsdb']['event']['strBanner'] != ''):
                        try:
                            with open(bannerfile, 'wb') as fp:
                                fp.write(tsdb.fetch_tsdb_art(diskfile['tsdb']['event']['strBanner']))
                        except Exception as e:
                            log.LogExcept('Failed to write banner file', e, pluginid)
                            pass               
                diskfile['nfo']['season']['square'] = squarefile
                if not (os.path.isfile(squarefile)):
                    if (diskfile['tsdb']['event']['strSquare'] != ''):
                        try:
                            with open(squarefile, 'wb') as fp:
                                fp.write(tsdb.fetch_tsdb_art(diskfile['tsdb']['event']['strSquare']))
                        except Exception as e:
                            log.LogExcept('Failed to write square file', e, pluginid)
                            pass
                diskfile['nfo']['season']['thumb'] = thumbfile
                if not (os.path.isfile(thumbfile)):
                    if (diskfile['tsdb']['event']['strThumb'] != ''):
                        try:
                            with open(thumbfile, 'wb') as fp:
                                fp.write(tsdb.fetch_tsdb_art(diskfile['tsdb']['event']['strThumb']))
                        except Exception as e:
                            log.LogExcept('Failed to write thumb file', e, pluginid)
                            pass
                
                    log.Log("Creating .NFO file", pluginid, log.LL_INFO)
                if not 'strVenue' in diskfile['tsdb']['event'].keys():
                    diskfile['tsdb']['event']['strVenue'] = 'Unknown'
                    
                if season == 0:
                    diskfile['tsdb']['event']['strEvent'] = "Non-Championship"
                elif diskfile['tsdb']['event']['strVenue'] == 'Unknown':
                    diskfile['tsdb']['event']['strEvent'] = str(season).zfill(2) + " : " + diskfile['tsdb']['event']['strEvent']
                else:
                    diskfile['tsdb']['event']['strEvent'] = str(season).zfill(2) + " : " + diskfile['tsdb']['event']['strEvent'] + " @ " + diskfile['tsdb']['event']['strVenue']
                kobimeta.makenfo(file, depth, diskfile['tsdb'], diskfile['nfo'], showname, episodename, episodenr, season) 
                tsdbloaded = True
                seasonname = diskfile['tsdb']['event']['strEvent']
                                        
        else:
            log.Log('diskfile does not contain tsdb data', pluginid, log.LL_DEBUG)
    
    if not tsdbloaded:
        # We do have some information that we can add to an NFO file, just not from TSDB.
        posterfile = os.path.join(diskfile['entity']['path'], 'season{:02d}'.format(season) + '.jpg')
        bannerfile = os.path.join(diskfile['entity']['path'], 'season{:02d}'.format(season) + '-banner.jpg')
        squarefile = os.path.join(diskfile['entity']['path'], 'season{:02d}'.format(season) + '-square.jpg')
        thumbfile  = os.path.join(diskfile['entity']['path'], diskfile['entity']['name'] + '.jpg')
        dirname, filename = os.path.split(file)
        if depth == 2:
            # We're assuming to be in a season folder, so the show.jpg file should be one up.
            sdir, tail = os.path.split(dirname)
            showjpg = os.path.join(sdir, "show.jpg")
            if os.path.exists(showjpg):
                sportfile = showjpg
            elif os.path.exists(os.path.join(dirname, "show.jpg")):
                showjpg = os.path.join(dirname, "show.jpg")
                sportfile = showjpg
            else:
                sportfile = showjpg
        else:
            sportfile = os.path.join(dirname, "show.jpg")
        
        diskfile['nfo'] = {'season':{}, 'sport': {}}
        
        # We only really need the poster for the series, and the poster and thumb for the event.
        if (os.path.isfile(thumbfile)):
            diskfile['nfo']['season']['thumb'] = thumbfile
        else: 
            diskfile['nfo']['season']['thumb'] = ''
        if (os.path.isfile(posterfile)):
            diskfile['nfo']['season']['poster'] = posterfile
        else: 
            diskfile['nfo']['season']['poster'] = ''
        if (os.path.isfile(sportfile)):
            diskfile['nfo']['sport']['poster'] = sportfile
        else: 
            diskfile['nfo']['sport']['poster'] = ''
        
        nfoinfo = {'event': {}, 'league': {}}
        nfoinfo['event']['strEvent'] = diskfile['episode']['event']
        if not 'strVenue' in nfoinfo['event'].keys():
            nfoinfo['event']['strVenue'] = 'Unknown'
            
        if season == 0:
            nfoinfo['event']['strEvent'] = "Non-Championship"
        elif nfoinfo['event']['strVenue'] == 'Unknown':
            nfoinfo['event']['strEvent'] = str(season).zfill(2) + " : " + nfoinfo['event']['strEvent']
        else:
            nfoinfo['event']['strEvent'] = str(season).zfill(2) + " : " + nfoinfo['event']['strEvent'] + " @ " + nfoinfo['event']['strVenue']
        seasonname = nfoinfo['event']['strEvent']
        kobimeta.makenfo(file, depth, nfoinfo, diskfile['nfo'], showname, episodename, episodenr, season)
        
    if (showname == '') or (episodename == '') or (episodenr == 0):
        log.Log("No match found for {0}".format(file), pluginid, log.LL_WARN)
        return {'message': 'no match'}
    else:
        if 'kobimeta' in diskfile.keys():
            if 'show' in diskfile['kobimeta'].keys():
                backupshowname = diskfile['kobimeta']['show']
            else:
                backupshowname = ''
        else:
            backupshowname = ''
        api.dump_to_jelly(showname, backupshowname, dirname, filename, diskfile['nfo'], episodenr, episodename, season, seasonname)
        log.Log("Adding episode to list:", pluginid, log.LL_DEBUG)
        log.Log("Series    : {0}".format(showname), pluginid, log.LL_DEBUG)
        log.Log("Round/Week: {0}".format(season), pluginid, log.LL_DEBUG)
        log.Log("Episode Nr: {0}".format(episodenr), pluginid, log.LL_DEBUG)
        log.Log("Title     : {0}".format(episodename), pluginid, log.LL_DEBUG)
        log.Log("Year      : {0}".format(year), pluginid, log.LL_DEBUG)
        return {'showname': showname,
                'season': season,
                'episode': episodenr,
                'eptitle': episodename,
                'year': year}
        
    
