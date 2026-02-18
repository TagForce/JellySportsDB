'''
Created on 4 jun. 2025

@author: Raymond
'''
import ssl, json, base64, os.path, time

try:                 from ssl import PROTOCOL_TLS    as SSL_PROTOCOL
except ImportError:  from ssl import PROTOCOL_SSLv23 as SSL_PROTOCOL
try:                 from urllib.request import urlopen, Request
except ImportError:  from urllib2        import urlopen, Request
import plexlog as log

pluginid = 'JELLYFIN API'
headers = {'Authorization': 'MediaBrowser Token="55321e3ed64c4f02b8c82a3283041003"'}
baseurl = 'http://192.168.2.20:8096/'
allfields = 'AirTime,CanDelete,CanDownload,ChannelInfo,Chapters,Trickplay,ChildCount,CumulativeRunTimeTicks,CustomRating,DateCreated,DateLastMediaAdded,DisplayPreferencesId,Etag,ExternalUrls,Genres,HomePageUrl,ItemCounts,MediaSourceCount,MediaSources,OriginalTitle,Overview,ParentId,Path,People,PlayAccess,ProductionLocations,ProviderIds,PrimaryImageAspectRatio,RecursiveItemCount,Settings,ScreenshotImageTags,SeriesPrimaryImage,SeriesStudio,SortName,SpecialEpisodeNumbers,Studios,Taglines,Tags,RemoteTrailers,MediaStreams,SeasonUserData,ServiceName,ThemeSongIds,ThemeVideoIds,ExternalEtag,PresentationUniqueKey,InheritedParentalRatingValue,ExternalSeriesId,SeriesPresentationUniqueKey,DateLastRefreshed,DateLastSaved,RefreshState,ChannelImage,EnableMediaSourceDisplay,Width,Height,ExtraIds,LocalTrailerCount,IsHD,SpecialFeatureCount'

def fetch_api(endpoint, param={}):
    
    try:
        querystr = ''
        if len(param) != 0:
            for key in param.keys():
                if '?' in querystr:
                    querystr += '&{0}={1}'.format(key, param[key])
                else:
                    querystr += '?{0}={1}'.format(key, param[key])
        fullrequest = baseurl + endpoint + querystr    
        request = Request(fullrequest, headers=headers)
        unverified = ssl._create_unverified_context()
        req_data = urlopen(request, context=unverified)
        
    except Exception as e:
        print(e)
        return {}
    return json.load(req_data)


def get_series(name):
    
    Items = fetch_api('Items', {'Recursive':'true', 'includeItemTypes':'Series'})
    if 'Items' not in Items.keys():
        return ''
    for item in Items['Items']:
        if item['Name'] == name:
            return item['Id']
    return ''

def get_seasons(parentId):
    
    Seasons = fetch_api('Items', {'ParentId':parentId, 'includeItemTypes':'Season'})
    if 'Items' not in Seasons.keys():
        return ''
    return Seasons['Items']

def get_episodes(parentId):
    
    Episodes = fetch_api('Items', {'Recursive': 'true', 'ParentId':parentId, 'includeItemTypes':'Episode', 'fields': allfields})
    if 'Items' not in Episodes.keys():
        return ''
    return Episodes['Items']

def get_all_items(parentId = None, recursive = False):
    
    params = {}
    params['fields'] = allfields
    if parentId is not None:
        params['ParentId'] = parentId
    if recursive:
        params['Recursive'] = 'true'
        
    items = fetch_api('Items', params)
    if 'Items' not in items.keys():
        return ''
    return items['Items']
        
def get_item(ids):
    
    params = {}
    params['fields'] = allfields
    params['ids'] = ids
    return fetch_api('Items', params)['Items'][0]


def push_api(endpoint, param={}, headers=headers, data=None):
    
    try:
        querystr = ''
        if len(param) != 0:
            for key in param.keys():
                if '?' in querystr:
                    querystr += '&{0}={1}'.format(key, param[key])
                else:
                    querystr += '?{0}={1}'.format(key, param[key])
        fullrequest = baseurl + endpoint + querystr
        if data is None:
            data = ''    
        request = Request(fullrequest, headers=headers, data=data)
        unverified = ssl._create_unverified_context()
        req_data = urlopen(request, context=unverified)
        
    except Exception as e:
        print(e)
        return {}
    return req_data


def push_json(endpoint, param={}, data={}):
    
    json_data = json.dumps(data)
    post_data = json_data.encode('utf-8')
    jsonhead = {}
    jsonhead["Content-Type"] = "application/json"
    for head in headers.keys():
        jsonhead[head] = headers[head]
    return push_api(endpoint, param, headers=jsonhead, data=post_data)
    

def push_image(endpoint, data=None):
    
    if data is None:
        return ''
    imagedata = base64.b64encode(data)
    imagehead = {}
    imagehead['Content-Type'] = "image/jpeg"
    for head in headers.keys():
        imagehead[head] = headers[head]
    return push_api(endpoint, headers=imagehead, data=imagedata)

def push_image_from_disk(filename, endpoint):
    
    if os.path.exists(filename):
        with open(filename, mode='rb') as fp:
            jpeg_data = fp.read()
        return push_image(endpoint, data=jpeg_data)
       

def dump_to_jelly(showname, backupshowname, dirname, filename, imageinfo, episodenr, episodename, seasonnr, seasonname):
    
    # First get the virtualfolders, and match it to a folder that our file is in.
    libraryid = ''
    virtualfolders = fetch_api('Library/VirtualFolders')
    if len(virtualfolders) > 0:
        for vf in virtualfolders:
            # Get the lowest level folders (because that should exist, all others may be mounted on different mountpoints)
            for folder in vf['Locations']:
                top, low = os.path.split(folder)
                if low in dirname:
                    libraryid=vf['ItemId']
                    break
            if libraryid != '':
                break
    if libraryid == '': # By default, if not found, take the last mediafolder in the list.
        mediafolders = fetch_api('Library/MediaFolders')
        if len(mediafolders) > 0:
            libraryid = mediafolders['Items'][len(mediafolders) - 1]['Id']
    if libraryid == '':
        return
    
    # Refresh the Racing library metadata to make sure we're seeing the latest version.
    push_api('Items/{0}/Refresh'.format(libraryid), {'Recursive': 'true'})
    log.Log('Refreshing Jellyfin Metadata for Library', pluginid)
    #time.sleep(3)
    
    # First, get the Show metadata
    seriesid = get_series(showname)
    if seriesid == '':            
        log.Log("Series {0} not found, trying to look it up from the actual episode".format(showname), pluginid)
        alleps = get_episodes('{0}'.format(libraryid))
        if len(alleps) == 0:
            log.Log("No episodes found at all", pluginid)
            return
        else:
            for episode in alleps:
                dirname, vidfile = os.path.split(episode['Path'])
                if filename == vidfile:
                    seriesid = episode['SeriesId']
    if seriesid == '':
        retrycount = 2
        retries = 0
        while retries <= retrycount and seriesid == '':
            retries += 1
            push_api('Items/{0}/Refresh'.format(libraryid), {'Recursive': 'true'})
            log.Log("Series not found, retrying metadata refresh. Retry number {0}".format(retries), pluginid)
            time.sleep(2)
            seriesid = get_series(showname)
    if seriesid == '':
        log.Log("Series {0} not found, trying {1}".format(showname, backupshowname), pluginid)
        showname = backupshowname
        retrycount = 2
        retries = 0
        while retries <= retrycount and seriesid == '':
            retries += 1
            push_api('Items/{0}/Refresh'.format(libraryid), {'Recursive': 'true'})
            log.Log("Series not found, retrying metadata refresh. Retry number {0}".format(retries), pluginid)
            time.sleep(2)
            seriesid = get_series(showname)
    log.Log("Series ID found: {0}".format(seriesid), pluginid)  
    retrycount = 10
    retries = 0
    episodeid = ''
    while retries <= retrycount and episodeid == '':
        retries += 1
        episodes = get_episodes(seriesid)
        if len(episodes) == 0:
            log.Log("No episodes found for show {0}".format(showname), pluginid)
        else:
            for episode in episodes:
                dirname, vidfile = os.path.split(episode['Path'])
                if filename == vidfile:
                    episodeid = episode['Id']
        if episodeid == '' and retries < retrycount:
            log.Log("Episode not found, retrying metadata refresh. Retry number {0}".format(retries), pluginid)
            push_api('Items/{0}/Refresh'.format(seriesid), {'Recursive': 'true'})
            time.sleep(2)
            
    if episodeid == '':
        log.Log("Episode for file {0} was not found in the Jellyfin database".format(filename), pluginid)
        return
    log.Log("Episode ID found: {0}".format(episodeid), pluginid)
    episode = get_item(episodeid)
    # Check if the season and episode numbers are correct, fix them if not.
    if 'IndexNumber' not in episode.keys(): # It has no episode number.
        log.Log("Episode had no episode number", pluginid)
        episode['IndexNumber'] = 0
    if 'ParentIndexNumber' not in episode.keys(): # It has no season number.
        log.Log("Episode had no season number", pluginid)
        episode['ParentIndexNumber'] = 0
    if (episode['IndexNumber'] != episodenr) or (episode['ParentIndexNumber'] != seasonnr) or episode['Name'] != episodename:
        log.Log("Fixing episode number, season number and episode name to Season {0}, Episode {1} and Name '{2}'".format(seasonnr, episodenr, episodename), pluginid)
        episode['IndexNumber'] = episodenr
        episode['ParentIndexNumber'] = seasonnr
        episode['Name'] = episodename
        result = push_json('Items/' + episodeid, data=episode)
        log.Log("Metadata push result: HTTP status {0}: {1}".format(result.code, result.msg), pluginid)
        # If there's a new season, it won't be available until we refresh the metadata, since seasons
        # are created upon finding a new season in an episode.
        result = push_api('Items/{0}/Refresh'.format(seriesid), {'Recursive': 'true'})
        log.Log("Metadata refresh result: HTTP status {0}: {1}".format(result.code, result.msg), pluginid)
        time.sleep(2)
    
    seasons = get_seasons(seriesid)
    if len(seasons) == 0:
        log.Log("No seasons found for {0}".format(showname), pluginid)
        return 
    seasonid = ''
    retrycount = 2
    retries = 0
    while retries < retrycount and seasonid == '':
        retries += 1
        for season in seasons:
            if 'IndexNumber' not in season.keys():
                continue
            if season['IndexNumber'] == seasonnr:
                seasonid = season['Id']
        if seasonid == '' and retries < retrycount:
            log.Log("Season not found, retrying metadata refresh. Retry number {0}".format(retries), pluginid)
            push_api('Items/{0}/Refresh'.format(seriesid), {'Recursive': 'true'})
            time.sleep(2)
    if seasonid == '':
        log.Log("Wanted season number '{0}' not found in database".format(seasonnr), pluginid)
        sepisode = get_item(episodeid)
        log.Log("Trying to fetch from updated episode", pluginid)
        sid = sepisode['parentId']
        epseason = get_item(sid)
        if epseason['IndexNumber'] == seasonnr:
            seasonid = sid
    if seasonid == '':        
        log.Log("Wanted season {0} not found in database".format(seasonnr), pluginid)
        return
    log.Log("Season ID found: {0}".format(seasonid), pluginid)
    season = get_item(seasonid)
    if season['Name'] != seasonname:
        log.Log("Changing season name for Season {0} to {1}".format(seasonnr, seasonname), pluginid)
        season['Name'] = seasonname
        result = push_json('Items/' + seasonid, data=season)
        log.Log("Metadata push result: HTTP status {0}: {1}".format(result.code, result.msg), pluginid)
        result = push_api('Items/{0}/Refresh'.format(seriesid), {'Recursive': 'true'})
        log.Log("Metadata refresh result: HTTP status {0}: {1}".format(result.code, result.msg), pluginid)
        time.sleep(2)
    result = push_image_from_disk(imageinfo['season']['poster'], 'Items/{0}/Images/Primary'.format(seasonid))
    if result is None:
        log.Log("Image upload failed for {0}".format(imageinfo['season']['poster']), pluginid)
    else:
        log.Log("Image push result: HTTP status {0}: {1}".format(result.code, result.msg), pluginid)
    push_api('Items/{0}/Refresh'.format(seriesid), {'Recursive': 'true'})
    log.Log("Metadata upload finished. Doing final metadata refresh for this series and its seasons and episodes.", pluginid)
    return
    
    
    
    
    
    
    