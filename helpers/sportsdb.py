# -*- coding: utf-8 -*-
'''
Created on 1 aug. 2024

@author: Raymond
'''
import ssl
import json
import re, time, sys, os, os.path, inspect, traceback
import unicodedata
import plexlog as log
import platform
import jaro



try:                 from ssl import PROTOCOL_TLS    as SSL_PROTOCOL
except ImportError:  from ssl import PROTOCOL_SSLv23 as SSL_PROTOCOL
try:                 from urllib.request import urlopen, Request
except ImportError:  from urllib2        import urlopen, Request


season_rx = r'[_ ]?\([0-9]{4}\)'
pluginid = "SPORTSDB API"
apikey = '418171' # Remove this, get the API key from the user.
headers = {'X-API-KEY': '418171'}
baseurl = 'https://www.thesportsdb.com/api/v2/json'
cachemax= 86400 # Diskcache can exist for a day
memcachemax = 600 # Reread the diskcache at least every 10 minutes (so we don't read it every meta run)

sportsrx = {'TeamvsTeam': ['(?P<hometeam>.*) vs (?P<awayteam>.*)',
                           '(?P<awayteam>.*) (@|at) (?P<hometeam>.*)'],
            'Event':      ['(?P<eventname>.*) (@|at) (?P<venue>.*)',
                           '(?P<eventname>.*)']}


daterx = r'(?P<year>)-(?P<month>)-(?P<day>)'


def fetch_tsdb_data(endpoint):
    
    
    log.Log("Building request for {0}".format(baseurl + endpoint), pluginid, log.LL_DEBUG)
    try:
        request = Request(baseurl + endpoint, headers=headers)
        unverified = ssl._create_unverified_context()
        log.Log("Retrieving data", pluginid, log.LL_DEBUG)
        req_data = urlopen(request, context=unverified)
        while req_data.code == 429:
            log.Log("Hitting rate limiter. Waiting.", pluginid, log.LL_DEBUG)
            time.sleep(0.5)
            req_data = urlopen(request, context=unverified)
    except Exception as e:
        log.LogExcept("Error in loading request: \n", e, pluginid)
        return {}
    log.Log("Fetched request. Parsing.".format(baseurl + endpoint), pluginid, log.LL_DEBUG)
    return json.load(req_data)


def fetch_tsdb_art(url): # Queries the API endpoint to fetch data, returns a dict
    
    log.Log("Building request for {0}".format(url), pluginid, log.LL_DEBUG)
    try:
        request = Request(url, headers=headers)
        unverified = ssl._create_unverified_context()
        log.Log("Retrieving data", pluginid, 0)
        req_data = urlopen(request, context=unverified)
        while req_data.code == 429:
            log.Log("Hitting rate limiter. Waiting.", pluginid, 0)
            time.sleep(0.5)
            req_data = urlopen(request, context=unverified)
    except Exception as e:
        log.LogExcept("Error in loading request: \n", e, pluginid)
        return {}
    
    log.Log("Fetched artwork.", pluginid, 0)
    art_data = req_data.read()
    return art_data


def test_file(filename):
    
    log.Log("Testing for event file for {0}".format(filename), pluginid, log.LL_DEBUG)
    tsdbevtfile, ext = os.path.splitext(filename)
    tsdbevtfile = tsdbevtfile + '.tsdbevt'
    eventid = ''
    if os.path.isfile(tsdbevtfile):
        log.Log("File exists. Trying to read it.", pluginid, log.LL_DEBUG)
        try:
            with open(tsdbevtfile, "r") as fp:
                eventid = fp.readline()
        except Exception as e:
            log.LogExcept("Error reading file.", e, pluginid)
    if re.match('^[0-9]{3,8}$', eventid):
        log.Log("Found eventid {0} in file.".format(eventid), pluginid, log.LL_DEBUG)
        return eventid
    log.Log("No eventid found", pluginid, log.LL_DEBUG)
    return ''
            

def read_cache(leagues):
    
    log.Log("Fetching Cache", pluginid, log.LL_INFO)
    current_time = time.time()
    if 'cachetime' in leagues.items():
        if (leagues['cachetime'] - current_time < memcachemax):
            log.Log("Using existing cache", pluginid, log.LL_DEBUG)
            return leagues
    
    log.Log("Reading cache from file if possible", pluginid, log.LL_DEBUG)
    lcache = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
    if os.path.isdir(lcache):
        if os.path.isfile(os.path.join(lcache, 'lcache.json')):
            try:
                with open(os.path.join(lcache, 'lcache.json'), "r") as fp:
                    leagues = json.load(fp)
            except Exception as e:
                log.LogExcept("Failed reading cachefile", e, pluginid)
                leagues = {}
                pass
    if 'cachetime' in leagues.keys():
        if (current_time - leagues['cachetime'] < cachemax):
            log.Log("Using file cache", pluginid, log.LL_DEBUG)
            return leagues
    leagues['cachetime'] = current_time
    leagues['leagues'] = fetch_leagues()
    log.Log("Refreshing cache from TSDB", pluginid, log.LL_DEBUG)
    if os.path.isdir(lcache):
        try:
            with open(os.path.join(lcache, 'lcache.json'), "w") as fp:
                json.dump(leagues, fp)
        except Exception as e:
            log.LogExcept("Failed saving cachefile", e, pluginid)
            pass
    return leagues


def read_sports(sports):
    
    log.Log("Fetching list of all sport types", pluginid, log.LL_DEBUG)
    current_time = time.time()
    log.Log("Checking memory for cache", pluginid, log.LL_DEBUG)
    if 'cachetime' in sports.items():
        if (sports['cachetime'] - current_time < memcachemax):
            return sports
    log.Log("Checking file for cache", pluginid, log.LL_DEBUG)
    lcache = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
    if os.path.isdir(lcache):
        if os.path.isfile(os.path.join(lcache, 'scache.json')):
            try:
                with open(os.path.join(lcache, 'scache.json'), "r") as fp:
                    sports = json.load(fp)
            except Exception as e:
                log.LogExcept("Failed reading cachefile", e, pluginid)
                sports = {}
                pass
    if 'cachetime' in sports.keys():
        if (current_time - sports['cachetime'] < cachemax):
            return sports
    log.Log("Refreshing cache from TSDB", pluginid, log.LL_DEBUG)
    sports['cachetime'] = current_time
    sports['sports'] = fetch_sports()
    if os.path.isdir(lcache):
        log.Log("Saving cache to disk", pluginid, log.LL_DEBUG)
        try:
            with open(os.path.join(lcache, 'scache.json'), "w") as fp:
                json.dump(sports, fp)
        except Exception as e:
            log.LogExcept("Failed saving cachefile", e, pluginid)
            pass
    return sports



def fetch_leagues():
    
    log.Log("Downloading list of all leagues", pluginid, log.LL_DEBUG)
    info = fetch_tsdb_data('/all/leagues')
    log.Log("Parsing request", pluginid, log.LL_DEBUG)
    full_leagues = {}
    log.Log("Parsing all league names and alternates.", pluginid, log.LL_DEBUG)
    for league in info['all']:
        full_leagues[league['strLeague'].encode('utf-8').strip().lower()] = league['idLeague']
        if (league['strLeagueAlternate'] is not None) and (len(league['strLeagueAlternate']) > 0):
            alt = league['strLeagueAlternate'].split(',')
            for name in alt:
                full_leagues[name.encode('utf-8').strip().lower()] = league['idLeague']
    log.Log("Returning new cache", pluginid, log.LL_DEBUG) 
    return full_leagues



def fetch_sports():
    
    log.Log("Downloading list of all sports", pluginid, log.LL_DEBUG)
    info = fetch_tsdb_data('/all/sports')
    fullsports = {}
    if 'all' in info.keys():
        log.Log("Parsing list", pluginid, log.LL_DEBUG)
        for sport in info['all']:
            fullsports[sport['strSport']] = sport
    else:
        log.Log("No sports", pluginid, log.LL_DEBUG)
    log.Log("Returning list", pluginid, log.LL_DEBUG)
    return fullsports



def search_league(leaguename):
    
    if leaguename == '':
        log.Log("Can't lookup an empty string.", pluginid, log.LL_WARN)
        return ''
    log.Log("Lookup up league " + leaguename + " on TSDB", pluginid, log.LL_INFO)
    leagues = {}
    leagues = read_cache(leagues)
    log.Log("Cache read", pluginid, log.LL_INFO)
    leaguename = re.sub(season_rx, '', leaguename)
    #First see if we have a full name match...
    if leaguename.lower() in leagues['leagues'].keys():
        log.Log("Found league in cache. LeagueID is {0}".format(leagues['leagues'][leaguename.lower()]), pluginid, log.LL_DEBUG)
        return leagues['leagues'][leaguename.lower()]
    leaguename = str(leaguename).replace(' ', '_')
    log.Log("Trying last ditch direct TSDB search", pluginid, log.LL_DEBUG)
    info = fetch_tsdb_data(str('/search/league/') + leaguename)
    if 'Message' not in info.keys():
        if len(info['search']) > 0:
            log.Log("More than one possible league found. Exiting.", pluginid, log.LL_WARN)
            return ''
        log.Log("Against all odds, we found a match", pluginid, log.LL_DEBUG)
        return info['search']['idLeague']
    log.Log("No league found", pluginid, log.LL_WARN)
    return ''

 
def get_episode(filename, leagueid, episode): # Make sure this adds an episode hash for teamvsteam sports.
    
    log.Log('Beginning TSDB lookups', pluginid, log.LL_INFO)
    log.Log('Looking for file containing event', pluginid, log.LL_DEBUG)
    eventid = test_file(filename)
    if eventid != '':
        ret_event = fetch_tsdb_data(str('/lookup/event/') + eventid)['lookup'][0]
        info = fetch_tsdb_data(str('/lookup/league/') + ret_event['idLeague'])
        log.Log('Downloaded event from file, exiting', pluginid, log.LL_INFO)
        return info['lookup'][0], ret_event
    if leagueid == '':
        log.Log('League ID not found, retrying search using different name', pluginid, log.LL_WARN)
        leagueid = search_league(episode['show'])
    if leagueid == '':
        log.Log('League not found on TSDB', pluginid, log.LL_INFO)
        return {}, episode
    log.Log('League found: {0}'.format(leagueid), pluginid, log.LL_INFO)
    log.Log('Looking for sporttype on TSDB', pluginid, log.LL_INFO)
    info = fetch_tsdb_data(str('/lookup/league/') + leagueid)
    if 'Message' not in info.keys():
        sport = info['lookup'][0]['strSport']
        log.Log('Sport type is {0}'.format(sport), pluginid, log.LL_INFO)
    log.Log('Sport found on TSDB, fetching information', pluginid, log.LL_INFO)
    return info['lookup'][0], get_sportsinfo(sport, leagueid, episode)


def get_sportsinfo(sport, leagueid, episode):
    
    sports = {}
    log.Log('Reading Sports cache', pluginid, log.LL_INFO)
    sports = read_sports(sports)
    strFormat = sports['sports'][sport]['strFormat'] if sport in sports['sports'].keys() else ''
    log.Log('Sports format is {0}'.format(strFormat), pluginid, log.LL_INFO)
    if strFormat != '':
        if (strFormat == 'TeamvsTeam'):
            event = get_teamgame(leagueid, episode)
            log.Log('TeamvsTeam match found:\n{0}'.format(event), pluginid, log.LL_INFO)
        elif (strFormat == 'EventSport'):
            event = get_event(leagueid, episode)
            log.Log('Event found:\n{0}'.format(event), pluginid, log.LL_INFO)
        else:
            log.Log('No or unknown format found, returning nothing', pluginid, log.LL_INFO)
            return {}
    return event
         
def get_season(leagueid, year, flt = True, list = False):
    
    seasons = fetch_tsdb_data(str('/list/seasons/') + leagueid)
    seasonlist = []
    for season in seasons["list"]:
        if str(year) in season['strSeason']:
            seasonlist.append(season['strSeason'])
    events = []
    endpoint = '/filter/events/' if flt else '/schedule/league/'
    keyval = 'filter' if flt else 'schedule'
    for season in seasonlist:
        info = fetch_tsdb_data(str(endpoint) + leagueid + '/' + season)
        for event in info[keyval]:
            events.append(event)
    if list:
        return seasonlist, events
    else:
        return events
    
def get_teamgame(leagueid, episode):
    
    log.Log('Looking for teams in game', pluginid, log.LL_INFO)
    for rx in sportsrx['TeamvsTeam']:
        match = re.search(rx, episode['event'], re.IGNORECASE)
        if match:
            groups = match.groupdict()
            home = re.sub(r'[\.\-_]', '', groups['hometeam']).lower()
            away = re.sub(r'[\.\-_]', '', groups['awayteam']).lower()
            break
    log.Log('Found {0} as home team, and {1} as away team'.format(home, away), pluginid, log.LL_INFO)
    log.Log('Getting all events from season {0}'.format(episode['year']), pluginid, log.LL_INFO)
    seasonevents = get_season(leagueid, episode['year'])
    matchevents = []
    log.Log('Checking all events for correct teams', pluginid, log.LL_INFO)
    for event in seasonevents:
        hometeam = re.sub(r'[\.\-_]', '', event['strHomeTeam']).lower()
        awayteam = re.sub(r'[\.\-_]', '', event['strAwayTeam']).lower()
        if ((home in hometeam) or (hometeam in home) or (home == hometeam)) and ((away in awayteam) or (awayteam in away) or (away == awayteam)):
            log.Log('Found possible match for event: '.format(event['strEvent']), pluginid, log.LL_INFO)
            matchevents.append(event)
    if len(matchevents) == 0:
        log.Log('No matching events found, returning empty event', pluginid, log.LL_INFO)
        return {}
    if len(matchevents) == 1:
        log.Log('Found a single match, considering it correct', pluginid, log.LL_INFO)
        ret_event = fetch_tsdb_data(str('/lookup/event/') + matchevents[0]['idEvent'])['lookup'][0]
        return ret_event
    log.Log('Multiple events found, need to narrow it down.', pluginid, log.LL_INFO)
    selected = []
    wk = 0
    foundevents = []
    log.Log('Fetching each event record', pluginid, log.LL_INFO)
    for event in matchevents:
        foundevents.append(fetch_tsdb_data(str('/lookup/event/') + event['idEvent'])['lookup'][0])
    log.Log('Finding highest found regular season Round', pluginid, log.LL_INFO)
    for event in foundevents:
        if event['intRound'] < 100 and event['intRound'] > wk:
            wk = event['intRound']
    log.Log('Highest round is {0}'.format(wk), pluginid, log.LL_INFO)
    matchevents = foundevents
    log.Log('Matching events on multiple criteria', pluginid, log.LL_INFO)
    for event in matchevents:
        if episode['airdate'] == event['dateEvent']:
            log.Log('Airdate match', pluginid, log.LL_INFO)
            selected.append(event)
            continue
        if episode['preseason'] and int(event['intRound']) == 500:
            log.Log('Preseason match with correct teams', pluginid, log.LL_INFO)
            selected.append(event)
            continue
        if episode['week'] > wk and int(event['intRound']) > 100:
            log.Log('Playoff event and week greater than regular season', pluginid, log.LL_INFO)
            selected.append(event)
            continue
        if episode['week'] == int(event['intRound']):
            log.Log('Correct week or round number', pluginid, log.LL_INFO)
            selected.append(event)
            continue
        
    if len(selected) != 1:
        log.Log('Failed to find a singular correct match. Returning nothing.', pluginid, log.LL_INFO)
        return {}
    log.Log('Finally found a match in event {0}'.format(selected[0]['strEvent']), pluginid, log.LL_INFO)
    ret_event = fetch_tsdb_data(str('/lookup/event/') + selected[0]['idEvent'])['lookup'][0]
    return ret_event
    
def get_event(leagueid, episode):
    
    log.Log('Looking for event', pluginid, log.LL_INFO)
    for rx in sportsrx['Event']:
        match = re.search(rx, episode['event'], re.IGNORECASE)
        if match:
            groups = match.groupdict()
            eventname = groups['eventname'].lower()
            venue = groups['venue'] if 'venue' in groups.keys() else '*__*'
            log.Log('Extracted eventname {0} and venue name {1}'.format(eventname, venue), pluginid, log.LL_INFO)
            break
    log.Log('Getting all events of season {0}'.format(episode['year']), pluginid, log.LL_INFO)
    seasons, seasonevents = get_season(leagueid, episode['year'], flt=False, list=True)
    matchevents = []
    log.Log('Trying to match on week/round, event year and venue names', pluginid, log.LL_INFO)
    for event in seasonevents:
        seasonmatch = False
        for season in seasons:
            if episode['year'] in season:
                seasonmatch = True
        if (episode['week'] != 0) and (episode['week'] == int(event['intRound'])) and (seasonmatch or (episode['year'] == event['dateEvent'][:4])) and ((episode['event'] in event['strVenue']) or (venue.lower() in event['strVenue'].lower())):
            log.Log('Found perfect match: {0}'.format(event['idEvent']), pluginid, log.LL_INFO)
            return fetch_tsdb_data(str('/lookup/event/') + event['idEvent'])['lookup'][0]
            break
    log.Log('Trying to match on week/round or event year and venue names', pluginid, log.LL_INFO)
    metrics = {}
    fileuni = unicodedata.normalize('NFD', unicode(episode['event']))
    filewords = re.sub(' [0-9]+', '', fileuni.lower()).split(' ')
    for idx, fw in enumerate(filewords):
        filewords[idx] = unicodedata.normalize('NFD', unicode(fw))
    for event in seasonevents:
        eventuni = event['strEvent'].replace('.', ' ')
        eventuni = unicodedata.normalize('NFD', eventuni)
        eventwords = re.sub(' [0-9]+', '', eventuni.lower()).split(' ')
        for idx, ew in enumerate(eventwords):
            eventwords[idx] = unicodedata.normalize('NFD', unicode(ew))
        matchedwords = []
        for eword in eventwords:
            for fword in filewords:
                wordmatch = jaro.jaro_winkler_metric(unicode(eword), unicode(fword))
                if wordmatch > 0.85:
                    matchedwords.append(wordmatch)
        totalscore = 0
        if (len(matchedwords) > 0):
            for score in matchedwords:
                totalscore += score * 4    
            metrics[event['idEvent']] = (totalscore + jaro.jaro_winkler_metric(unicode(eventname), unicode(event['strEvent']))) / ((len(matchedwords) * 4) + (len(filewords) - len(matchedwords)) + 1)
        else:
            metrics[event['idEvent']] = 0
    
    topevent = 0
    topscore = 0
    for event, score in metrics.iteritems():
        if metrics[event] > topscore:
            topevent = event
            topscore = metrics[event]
    for event in seasonevents:
        if (event['idEvent'] == topevent) and topscore > 0.8:
            matchevents.append(event)
    if len(matchevents) == 0 and venue == '*__*' and episode['week'] != 0: # If we don't have a venue, and haven't found one using event name matching, just use the week value if it's not 0.
        log.Log("No match yet found, searching without the venue", pluginid)
        for event in seasonevents:
            seasonmatch = False
            for season in seasons:
                if episode['year'] in season:
                    seasonmatch = True
            if (episode['week'] != 0) and (episode['week'] == int(event['intRound'])) and (seasonmatch or (episode['year'] == event['dateEvent'][:4])):
                log.Log('Found match: {0}'.format(event['idEvent']), pluginid, log.LL_INFO)
                matchevents.append(event)
    if len(matchevents) != 1:
        log.Log('Failed to find a singular correct match. Returning nothing.', pluginid, log.LL_INFO)
        return {}
    log.Log('Found a match in event {0}'.format(matchevents[0]['strEvent']), pluginid, log.LL_INFO)
    ret_event = fetch_tsdb_data(str('/lookup/event/') + matchevents[0]['idEvent'])['lookup'][0]
    return ret_event

