# -*- coding: utf-8 -*-
import re, os, os.path, random, urllib2
import datetime, titlecase, unicodedata, sys
import networks as tvnetworks
import plexlog as log

# CONSTANTS SPORTS SCANNER
pluginid = "NAME PARSER"
episode_regexes = {
    'dated': [ # NHL.2015.09.25.New-York-Islanders.vs.Philadelphia-Flyers.720p.HDTV.60fps.x264-Reborn4HD_h.mp4
        r'^(?P<show>.*?)[^0-9a-zA-Z]+(?P<year>[0-9]{4})[^0-9a-zA-Z]+(?P<month>[0-9]{2})[^0-9a-zA-Z]+(?P<day>[0-9]{2})[^0-9a-zA-Z]+(?P<event>.*)$'
        ],
    'single_event': [ # NCS.2024.Round.03.Watkins.Glen.Race.FoxSports.720p60.h264.English-egortech
        r'^(?P<show>[a-z]+.*?)[ ]+(?P<season>[0-9]{2,4})[ ]+(?P<preseason>(PS))?[ ]?[wekround]+[ ]?(?P<week>[0-9]+)[ ]+(?P<event>((?!(@|vs |at )).)*?)$'
        ],
    'match' : [ # NFL.2023.Week.01.New.Orleans.Saints.vs.Tennessee.Titans.1st.Half.FoxSports.720p60.h264.English-egortech
        r'^(?P<show>[^0-9]*?)[ ]+(?P<season>[0-9]{2,4})[ ]+(?P<preseason>(PS))?[ ]?[wekround]+[ ]?(?P<week>[0-9]+)[ ]+(?P<event>[a-z0-9 ]+[ ]+(@|vs|at)[ ]+[a-z0-9 ]*?[ ]*)$'
        ],
    'pack_event' : [ # 02.NASCAR.Cup.Series.2024.R13.Goodyear.400.Race.FS1.720P.mkv
        r'^(?P<ep>[0-9]*)[ ]+(?P<show>.+)[ ]+(?P<season>[0-9]{4})[ ]+(?P<preseason>(PS))?[ ]?[wekround]*[ ]*(?P<week>[0-9]+)[ ]+(?P<event>.*)$'
        ],
    'episodic' : [ # Euro 2024 - s06e01 - Groep F - Turkije - Georgie
        r'^(?P<show>.*?)[ ](?P<year>[0-9]{4})[ ]+s(?P<season>[0-9]+)[ ]*e(?P<ep>[0-9]+)[ ]*(?P<event>.*)$' 
        ]
}

session_regexes = {
    'match_split': [r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>half|period|quarter|inning|set)[ ]?)((?P<ses2nr>[0-9]+)[ ]?)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'], # 1st half, quarter 2, 9th inning
    'match_full' : [r' ((?P<sesname>((full[ ]?))?(game|match))[ ]?)(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'], # full game, match
    'match_extra': [r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>(o(ver)?|e(xtra)?)[ ]?(t(ime)?)(?![a-z])[ ]?))(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'], # overtime, extra time 2
                 
    'event_quali': [r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>q(ual(y|if(ying( practice)?|ication( practice)?|ier(s)?){1})?)?)[ ]?)(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'], # Qualy, Q3, Qualification Practice, Qualifying Practice 2, 2nd Qualy
    'event_pract': [r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>((f(ree))[ ]?)?practice|fp)[ ]?)(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'], # free practice, fp3
    'event_shtot': [r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>(top[ ]?([0-9]{1,2}[ ]?)|heat[ ]?)(races|shootout|q(ual(y|if(ying|ication|ier(s)?){1})?)?))[ ]?)(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'],
    'event_race' : [r' (((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>((full|sprint|feature|main)[ ]?)?(race((?=[^a-z])|$)([a-z ]*)|stage((?=[^a-z])|$)|day((?=[^a-z])|$)|finals((?=[^a-z])|$)|sprint((?=[^a-z])|$)))[ ]?)(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?']
    #'event_race' : [r'(((?P<ses1nr>[0-9]+)(?P<sestxt>(st|nd|rd|th)))[ ]?)?((?P<sesname>((full|sprint|feature|main)[ ]?)?(race((?=[^a-z])|$)|stage(?=[^a-z])|day(?=[^a-z])))[ ]?)(?P<ses2nr>[0-9]+)?[ ]?((?P<part>part)[ ]?)?(?P<ses3nr>[0-9]+)?'] # top 10 shootout, stage 3, day 2               
}

session_episodes = {
    'match_split': 100,
    'match_full' : 100,
    'match_extra': 100,
                  
    'event_quali': 200,
    'event_pract': 100,
    'event_shtot': 300,
    'event_race' : 400
    }

session_types = {
    'match_split': 'event',
    'match_full' : 'event',
    'match_extra': 'event',
                  
    'event_quali': 'qualification',
    'event_pract': 'practice',
    'event_shtot': 'shootout',
    'event_race' : 'event'
    }
video_exts = ['3g2', '3gp', 'asf', 'asx', 'avc', 'avi', 'avs', 'bivx', 'bup', 'divx', 'dv', 'dvr-ms', 'evo', 'fli', 'flv',
              'm2t', 'm2ts', 'm2v', 'm4v', 'mkv', 'mov', 'mp4', 'mpeg', 'mpg', 'mts', 'nsv', 'nuv', 'ogm', 'ogv', 'tp',
              'pva', 'qt', 'rm', 'rmvb', 'sdp', 'svq3', 'strm', 'ts', 'ty', 'vdr', 'viv', 'vob', 'vp3', 'wmv', 'wtv', 'xsp', 'xvid', 'webm']

ignore_samples = ['[-\._]sample', 'sample[-\._]']
ignore_trailers = ['-trailer\.']
ignore_extras = ['^trailer.?$','-deleted\.', '-behindthescenes\.', '-interview\.', '-scene\.', '-featurette\.', '-short\.', '-other\.']
ignore_extras_startswith = ['^movie-trailer.*']
ignore_dirs =  ['\\bextras?\\b', '!?samples?', 'bonus', '.*bonus disc.*', 'bdmv', 'video_ts', '^interview.?$', '^scene.?$', '^trailer.?$', '^deleted.?(scene.?)?$', '^behind.?the.?scenes$', '^featurette.?$', '^short.?$', '^other.?$']
ignore_suffixes = ['.dvdmedia']


source_dict = {'bluray':['bdrc','bdrip','bluray','bd','brrip','hdrip','hddvd','hddvdrip'],'cam':['cam'],'dvd':['ddc','dvdrip','dvd','r1','r3','r5'],'retail':['retail'],
               'dtv':['dsr','dsrip','hdtv','pdtv','ppv'],'stv':['stv','tvrip'],'screener':['bdscr','dvdscr','dvdscreener','scr','screener'],
               'svcd':['svcd'],'vcd':['vcd'],'telecine':['tc','telecine'],'telesync':['ts','telesync'],'web':['webrip','web-dl'],'workprint':['wp','workprint']}
source = []
for d in source_dict:
    for s in source_dict[d]:
        if source != '':
            source.append(s)

audio = ['([^0-9])5\.1[ ]*ch(.)','([^0-9])5\.1([^0-9]?)','([^0-9])7\.1[ ]*ch(.)','([^0-9])7\.1([^0-9])']
subs = ['multi','multisubs']
misc = ['cd1','cd2','1cd','2cd','custom','internal','repack','read.nfo','readnfo','nfofix','proper','rerip','dubbed','subbed','extended','unrated','xxx','nfo','dvxa', 'web']
formt = ['ac3','divx','fragment','limited','ogg','ogm','ntsc','pal','ps3avchd','r1','r3','r5','720i','720p','1080i','1080p','remux','x264','xvid','vorbis','aac','dts','fs','ws','1920x1080','1280x720','h264','h','264','prores','uhd','2160p','truehd','atmos','hevc']
networks = tvnetworks.networks

reversed_tokens = set()
# use the values of 'format' and 'source' to generate the reversed tokens
for f in formt + source:
    if len(f) > 3:
        # only add token if length > 3, otherwise the reversed token can easily exists in a normal (not reversed) name
        reversed_tokens.add(f[::-1].lower())

edition = ['se'] # se = special edition
yearRx = '([\(\[\.\-])([1-2][0-9]{3})([\.\-\)\]_,+])'
resRx = '(?P<res>(480|540|576|720|1080|2160|4320)[iIpP])[0-9]{1,3}'




def cleanfilenames(name):
    
    log.Log("Cleaning file name: " + name, pluginid)
    name_tokens_lowercase = set()
    for t in re.split('([^ \-_\.\(\)+]+)', name):
        t = t.strip()
        if not re.match('[\.\-_\(\)+]+', t) and len(t) > 0:
            name_tokens_lowercase.add(t.lower())

    if len(set.intersection(name_tokens_lowercase, reversed_tokens)) > 2:
        # if name contains more than two reversed tokens, mirror the name
        name = name[::-1]
    
    orig = name

    # Make sure we pre-compose.    Try to decode with reported filesystem encoding, then with UTF-8 since some filesystems lie.
    try:
        name = unicodedata.normalize('NFC', name)
    except:
        try:
            name = unicodedata.normalize('NFC', name)
        except:
            pass

    name = name.lower()

    # grab the year, if there is one. set ourselves up to ignore everything after the year later on.
    year = None
    yearMatch = re.search(yearRx, name)
    if yearMatch:
        yearStr = yearMatch.group(2)
        yearInt = int(yearStr)
        if yearInt > 1900 and yearInt < (datetime.date.today().year + 1):
            year = int(yearStr)
            #name = name.replace(yearMatch.group(1) + yearStr + yearMatch.group(3), ' *yearBreak* ')
        
    # Take out things in brackets. (sub acts weird here, so we have to do it a few times)
    done = False
    while done == False:
        (name, count) = re.subn(r'\[[^\]]+\]', '', name, re.IGNORECASE)
        if count == 0:
            done = True
    log.Log("Removed bracketed text: " + name, pluginid, log.LL_DEBUG)
    
    # Take out bogus suffixes.
    for suffix in ignore_suffixes:
        rx = re.compile(suffix + '$', re.IGNORECASE)
        name = rx.sub('', name)
    log.Log("Removed bogus suffixes: " + name, pluginid, log.LL_DEBUG)
    
    # Take out audio specs, after suffixing with space to simplify rx.
    name = name + ' '
    for s in audio:
        rx = re.compile(s, re.IGNORECASE)
        name = rx.sub(' ', name)
    log.Log("Removed audio specs: " + name, pluginid, log.LL_DEBUG)
    
    # Now tokenize.
    log.Log("Tokenizing name...", pluginid, log.LL_DEBUG)
    tokens = re.split('([^ \-_\.\(\)+]+)', name)
    
    # Process tokens.
    newTokens = []
    for t in tokens:
        t = t.strip()
        if not re.match('[\.\-_\(\)+]+', t) and len(t) > 0:
        #if t not in ('.', '-', '_', '(', ')') and len(t) > 0:
            newTokens.append(t)

    # Now build a bitmap of good and bad tokens.
    tokenBitmap = []
    log.Log("Building garbage token list...", pluginid, log.LL_DEBUG)

    garbage = subs
    garbage.extend(misc)
    garbage.extend(formt)
    garbage.extend(edition)
    garbage.extend(source)
    garbage.extend(video_exts)
    #garbage.extend(networks)
    garbage = set(garbage)
    
    # Keep track of whether we've encountered a garbage token since they shouldn't appear more than once.
    seenTokens = {}

    # Go through the tokens backwards since the garbage most likely appears at the end of the file name.
    # If we've seen a token already, don't consider it garbage the second time.    Helps cases like "Internal.Affairs.1990-INTERNAL.mkv"
    #
    log.Log("Build token bitmap...", pluginid, log.LL_DEBUG)
    for t in reversed(newTokens):
        # These days, resolution and framerates are often reported as 1, so we need to fix the token to match this in these
        # cases. eg. 720p60 is not a bad token, but it should be.
        resMatch = re.search(resRx, t)
        if resMatch:
            t = resMatch.group('res')
        if t.lower() in garbage and t.lower() not in seenTokens:
            tokenBitmap.insert(0, False)
            seenTokens[t.lower()] = True
        else:
            tokenBitmap.insert(0, True)

    
    # Now strip out the garbage, with one heuristic; if we encounter 2+ BADs after encountering
    # a GOOD, take out the rest (even if they aren't BAD). Special case for director's cut.
    log.Log("Stripping garbage...", pluginid, log.LL_DEBUG)
    numGood = 0
    numBad    = 0
    
    finalTokens = []
    
    for i in range(len(tokenBitmap)):
        good = tokenBitmap[i]
        
        # If we've only got one or two tokens, don't whack any, they might be part of
        # the actual name (e.g. "Internal Affairs" "XXX 2")
        #
        if len(tokenBitmap) <= 2:
            good = True
        
        if good and numBad < 2:
            finalTokens.append(newTokens[i])
        elif not good and newTokens[i].lower() == 'web':
            # We're checking here for the 'web-dl' or 'web-rip' case (have to do it in two pieces b/c it gets split).
            if i+1 < len(newTokens) and newTokens[i+1].lower() in ['dl', 'rip']:
                tokenBitmap[i+1] = False
        
        if good == True:
            numGood += 1
        else:
            numBad += 1

    # If we took *all* the tokens out, use the first one, otherwise we'll end up with no name at all.
    if len(finalTokens) == 0 and len(newTokens) > 0:
        finalTokens.append(newTokens[0])
        
    #print "CLEANED [%s] => [%s]" % (orig, u' '.join(finalTokens))
    #print "TOKENS: ", newTokens
    #print "BITMAP: ", tokenBitmap
    #print "FINAL:    ", finalTokens
    
    cleanedName = ' '.join(finalTokens)
    
    # Finally, check for the presence of broadcaster names in the filename and remove them.
    
    longestbroadcaster = ''
    for broadcaster in networks:
        if broadcaster == 'sky sports f1':
            pass
        if broadcaster in cleanedName:
            if len(broadcaster) > len(longestbroadcaster): # Make sure we only remove the longest match.
                longestbroadcaster = broadcaster
    cleanedName = cleanedName.replace(longestbroadcaster, "").strip()
            
    # If we failed to decode/encode above, we may still be dealing with a non-ASCII string here,
    # which will raise if we try to encode it, so let's just handle it and hope for the best!
    #
    try:
        cleanedName = cleanedName.encode('utf-8')
    except:
        pass
    
    log.Log("Finished cleaning, resulting name: " + cleanedName, pluginid)
    return unicodedata.normalize('NFC', unicode(titlecase.titlecase(cleanedName)))



    
def get_episode(filename):

    log.Log("Getting Episode from name: " + filename, pluginid)
    episode_info = {}
    episode_info['re_type'] = None
    episode_info['preseason'] = False
    log.Log("Trying to match regex", pluginid, log.LL_DEBUG)
    for re_type, rxs in episode_regexes.iteritems():
        for rx in rxs: 
            match = re.match(rx, filename, re.IGNORECASE)
            if match:
                log.Log("Matched regex: " + re_type, pluginid, log.LL_DEBUG)
                groups = match.groupdict()
                if re_type == 'dated':
                    episode_info['airdate']='' + groups['year'] + '-' + groups['month'] + '-' + groups['day']
                    episode_info['season'] = int(groups['year'])
                    episode_info['week'] = 9999
                    episode_info['preseason'] = False
                    episode_info['episodenr'] = NumberEpisode(groups['year'], int(groups['month']), int(groups['day']), abs(hash(filename)))
                    episode_info['show'] = groups['show']
                    episode_info['year'] = int(groups['year'])
                elif re_type == 'episodic':
                    episode_info['airdate'] = None
                    episode_info['season'] = int(groups['year'])
                    episode_info['week'] = int(groups['season'])
                    episode_info['preseason'] = False
                    episode_info['episodenr'] = int(groups['ep'])
                    episode_info['show'] = groups['show']
                    episode_info['year'] = groups['year']
                elif re_type == 'pack_event':
                    episode_info['airdate'] = None
                    episode_info['season'] = groups['season']
                    episode_info['week'] = int(groups['week'])
                    if groups['preseason'] != None:
                        episode_info['preseason'] = True
                    episode_info['episodenr'] = int(groups['ep'])
                    episode_info['show'] = groups['show']
                    episode_info['year'] = groups['season']
                else:
                    episode_info['airdate'] = None
                    episode_info['season'] = groups['season']
                    episode_info['week'] = int(groups['week'])
                    if groups['preseason'] != None:
                        episode_info['preseason'] = True
                    episode_info['episodenr'] = 0
                    episode_info['show'] = groups['show']
                    episode_info['year'] = groups['season']
                
                episode_info['event'] = groups['event']
                episode_info['retype'] = re_type
    log.Log("Finished extracting episode info from name: " + str(episode_info), pluginid)
    return episode_info



def get_session(epinfo, filename):
    
    log.Log("Getting session info from event: " + epinfo['event'], pluginid)
    session = "full game"
    episode_info = {}
    episode_info['episodenr'] = 101
    if epinfo['week'] != 0 and epinfo['preseason']:
        episode_info['episodenr'] = int(str(epinfo['week']) + str(episode_info['episodenr']) + str(abs(hash(epinfo['event'])) % (10 ** 3)))
    if epinfo['week'] == 0:
        episode_info['episodenr'] = int(str(abs(hash(filename)) % (10 ** 3)) + str(episode_info['episodenr']))
    episode_info['sessionname'] = session
    episode_info['session'] = ''
    episode_info['sessiontype'] = 'not found'
    episode_info['sessionnr'] = 1
    episode_info['eventname'] = epinfo['event']
    for re_type, rxs in session_regexes.iteritems():
        for rx in rxs: 
            match = re.search(rx, epinfo['event'], re.IGNORECASE)
            if match:
                log.Log("Matched session regex: " + re_type, pluginid, log.LL_DEBUG)
                #print "SS: matched regex | {0} |".format(rx)
                #Find out if there's a partnumber or session number
                groups = match.groupdict()
                ses1 = ('ses1nr' in groups) and groups['ses1nr'] != None
                ses2 = ('ses2nr' in groups) and groups['ses2nr'] != None
                ses3 = ('ses3nr' in groups) and groups['ses3nr'] != None
                part = ('part' in groups) and groups['part'] != None
                if part:
                    if ses1:
                        if ses2: #This really shouldn't happen, because it is bad numbering, but alas. We can kind of handle it.
                            session = groups['ses1nr'] + ' ' + groups['sesname'] + groups['ses2nr'] + ' part ' + groups['ses3nr']
                            episode = session_episodes[re_type] + 10 * int(groups['ses1nr']) + 20 * int(groups['ses2nr']) + int(groups['ses3nr'])
                            sesnr = int(groups['ses1nr'])
                            sesnm = groups['sesname'] + groups['ses2nr']
                        else:
                            session = groups['sesname'] + ' ' + groups['ses1nr'] + ' part ' + groups['ses3nr']
                            episode = session_episodes[re_type] + 10 * int(groups['ses1nr']) + int(groups['ses3nr'])
                            sesnr = int(groups['ses1nr'])
                            sesnm = groups['sesname']
                    elif ses2:
                        session = groups['sesname'] + ' ' + groups['ses2nr'] + ' part ' + groups['ses3nr']
                        episode = session_episodes[re_type] + 10 * int(groups['ses2nr']) + int(groups['ses3nr'])
                        sesnr = int(groups['ses2nr'])
                        sesnm = groups['sesname']
                    else:
                        session = groups['sesname'] + ' part ' + groups['ses3nr']
                        episode = session_episodes[re_type] + 10 + int(groups['ses3nr'])
                        sesnr = 1 
                        sesnm = groups['sesname']
                elif ses1:
                    if ses2 and ses3:
                        session = groups['ses1nr'] + groups['sestxt'] + ' ' + groups['sesname'] + groups['ses2nr'] + ' part ' + groups['ses3nr']
                        episode = session_episodes[re_type] + 10 * int(groups['ses1nr']) + 20 * int(groups['ses2nr']) + int(groups['ses3nr'])
                        sesnr = int(groups['ses1nr'])
                        sesnm = groups['sesname'] + groups['ses2nr']
                    elif ses2:
                        session = groups['ses1nr'] + groups['sestxt'] + ' ' + groups['sesname'] + ' part ' + groups['ses2nr']
                        episode = session_episodes[re_type] + 10 * int(groups['ses1nr']) + int(groups['ses2nr'])
                        sesnr = int(groups['ses1nr'])
                        sesnm = groups['sesname']
                    else:
                        session = groups['ses1nr'] + groups['sestxt'] + ' ' + groups['sesname']
                        episode = session_episodes[re_type] + 10 * int(groups['ses1nr']) + 1
                        sesnr = int(groups['ses1nr'])
                        sesnm = groups['sesname']
                elif ses2:
                    if ses3:
                        session = groups['sesname']  + ' ' + groups['ses2nr'] + ' part ' + groups['ses3nr']
                        episode = session_episodes[re_type] + 10 * int(groups['ses2nr']) + int(groups['ses3nr'])
                        sesnr = int(groups['ses2nr'])
                        sesnm = groups['sesname']
                    else:
                        session = groups['sesname']  + ' ' + groups['ses2nr']
                        episode = session_episodes[re_type] + 10 * int(groups['ses2nr']) + 1
                        sesnr = int(groups['ses2nr'])
                        sesnm = groups['sesname']
                else:
                    session = groups['sesname']
                    episode = session_episodes[re_type] + 10 + 1
                    sesnr = 1
                    sesnm = groups['sesname']
                    
                # When there's a Sprint (Race) then lower the episode number a bit, because Sprints generally occur before
                # the actual race, but both get assigned episode 411 by default. Lower it by 5, since if there's a session number, the sprint will fit
                # in between the previous and next race if there are multiple.
                if 'sprint' in groups['sesname'].lower():
                    episode -= 5                    
                if epinfo['week'] != 0 and epinfo['preseason']:
                    episode = int(str(epinfo['week']) + str(abs(hash(epinfo['event'].replace(match.group(0), '').strip())) % (10 ** 3)) + str(episode))
                elif epinfo['week'] == 0:
                    episode = int(str(abs(hash(epinfo['event'].replace(match.group(0), '').strip())) % (10 ** 3)) + str(episode))
                else:
                    episode = episode
                if epinfo['retype'] == 'episodic':
                    episode_info['episodenr'] = epinfo['episodenr']
                else:
                    episode_info['episodenr'] = episode
                episode_info['sessionname'] = session
                episode_info['session'] = sesnm
                episode_info['sessiontype'] = session_types[re_type]
                episode_info['sessionnr'] = sesnr
                #eventname = epinfo['event'].rsplit(match.group(0), 1)
                if epinfo['event'].count(match.group(0)) > 1:
                    episode_info['eventname'] = ''.join(epinfo['event'].rsplit(match.group(0), 1))
                else:
                    episode_info['eventname'] = epinfo['event'].replace(match.group(0), '').strip()
    log.Log("Finished extracting session info: " + str(episode_info), pluginid)
    return episode_info


def hasSession(instr):
    
    for re_type, rxs in session_regexes.iteritems():
        for rx in rxs: 
            match = re.search(rx, instr, re.IGNORECASE)
            if match:
                return True
    return False

def removeSession(instr):
    
    result = instr
    for re_type, rxs in session_regexes.iteritems():
        for rx in rxs: 
            match = re.search(rx, instr, re.IGNORECASE)
            if match:
                result = re.sub(rx, '', instr, flags=re.IGNORECASE).strip()
    return result            
    
    
def NumberEpisode(year,month,day,filehash):
    
    log.Log("Calculating Episode number from date", pluginid)
    if not re.match(r"^[0-9]{4}$", year):
        raise ValueError("Incorrectly formatted year. Must be 4 char str: {0}".format(year))
        log.Log("Incorrectly formatted year. Must be 4 char str: {0}".format(year), pluginid, log.LL_ERROR)
    ep = int('%s%02d%02d%03d' % (year[-2:],month, day, filehash % (10 ** 3)))
    log.Log("Episode found: " + str(ep), pluginid)   
    return ep
