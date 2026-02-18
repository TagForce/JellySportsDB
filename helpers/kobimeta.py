# -*- coding: utf-8 -*-
'''
Created on 25 jul. 2024

@author: Raymond
'''
import os.path, unicodedata, os
import plexlog as log
import jaro
from xml.etree import ElementTree as ET
from pickle import NONE, TRUE

pluginid = "KOBI PARSER"

def elem2dict(node):
    
    result = {}
    result[node.tag] = {}
    #x = {x.tag: node.find(x.tag).text  for x in node._children}
    for element in node:#_children:
        res = {}
        #result[node.tag][element.tag] = {}
        if len(element) > 0:
            res['children'] = elem2dict(element)[element.tag]
        else:
            res['children'] = None
        res['attrib'] = element.attrib
        if element.text == None and res['children'] == None:
            res['text'] = ''
        else:
            res['text'] = element.text
        if element.tag in result[node.tag]:
            if not isinstance(result[node.tag][element.tag], list):
                result[node.tag][element.tag] = [result[node.tag][element.tag]]
            result[node.tag][element.tag].append(res)
        else:
            result[node.tag][element.tag] = res
    return result

def d2e(tag, d):
    
    elem = ET.Element(tag)
    if (len(d['attrib']) > 0):
        for key, val in d['attrib'].items():
            elem.set(key, val)
    elem.text = str(d['text'])
    if not (isinstance(d['children'], type(None))):
        for key, val in d['children'].items():
            elem.append(d2e(key, val))
    return elem


def dict2elem(tag, d):
        
    elem = ET.Element(tag)
    for key, val in d.items():
        if isinstance(val, list):
            for v in val:
                child = elem.append(d2e(key, v))
        else:
            child = elem.append(d2e(key, val))
    return elem


def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i




def get_metadata(filename):
    
    log.Log("Fetching Kobi Metadata", pluginid)
    fname, ext = os.path.splitext(filename)
    fname = fname + '.nfo'
    fname = fname.decode('utf-8')
    episode_info = {}
    if os.path.exists(fname):
        log.Log("Kobi NFO file found. {0} - Parsing XML.".format(fname), pluginid)
        try:
            tree = ET.parse(fname)
            metadata = elem2dict(tree.getroot())['episodedetails']
        except Exception as e:
            log.LogExcept("Failed parsing XML", e, pluginid)
            return {}
        if 'season' in metadata.keys():
            episode_info['season'] = int(metadata['season']['text'])
        if 'episode' in metadata.keys():
            episode_info['episodenr'] = int(metadata['episode']['text'])
        if 'premiered' in metadata.keys():
            episode_info['airdate'] = metadata['premiered']['text']
        if 'title' in metadata.keys():
            episode_info['episodename'] = metadata['title']['text']
        if 'showtitle' in metadata.keys():    
            episode_info['show'] = metadata['showtitle']['text']
        else:
            log.Log("Show name not found in episode NFO, trying tvshow.nfo", pluginid)
            folder, fl = os.path.split(fname)
            if os.path.exists(os.path.join(folder, 'tvshow.nfo')):
                tvshow = os.path.join(folder, 'tvshow.nfo')
            else:
                folder, tl = os.path.split(folder)
                tvshow = os.path.join(folder, 'tvshow.nfo')
            if os.path.exists(tvshow):
                tvmeta = elem2dict(ET.parse(tvshow).getroot())['tvshow']
                if 'title' in tvmeta.keys():
                    episode_info['show'] = tvmeta['title']['text']
            if 'show' not in episode_info.keys():
                log.Log("Show name not found in either episode or tvshow NFO files", pluginid, log.LL_WARN)
                episode_info['show'] = ''
    else:
        folder, fl = os.path.split(fname)
        if os.path.exists(os.path.join(folder, 'tvshow.nfo')):
            tvshow = os.path.join(folder, 'tvshow.nfo')
        else:
            folder, tl = os.path.split(folder)
            tvshow = os.path.join(folder, 'tvshow.nfo')
        if os.path.exists(tvshow):
            tvmeta = elem2dict(ET.parse(tvshow).getroot())['tvshow']
            if 'title' in tvmeta.keys():
                episode_info['show'] = tvmeta['title']['text']
        if 'show' not in episode_info.keys():
            log.Log("Show name not found in either episode or tvshow NFO files", pluginid, log.LL_WARN)
            episode_info['show'] = ''
        if episode_info['show'] == '':
            log.Log("No Kobi NFO file found.", pluginid)
        else:
            log.Log("Only tvshow nfo found, show name read.", pluginid)
        
    log.Log("Exiting Kobi Metadata Fetcher.", pluginid)  
    return episode_info

def adddictelem(value, attrib = {}, children=None):
    
    result = {}
    result['text'] = value
    result['attrib'] = attrib
    result['children'] = children
    return result

def _pretty_print(current, parent=None, index=-1, depth=0):
    for i, node in enumerate(current):
        _pretty_print(node, current, i, depth + 1)
    if parent is not None:
        if index == 0:
            parent.text = '\n' + ('\t' * depth)
        else:
            parent[index - 1].tail = '\n' + ('\t' * depth)
        if index == len(parent) - 1:
            current.tail = '\n' + ('\t' * (depth - 1))
    
def makenfo(file, depth, event, artwork, showname, episodename, episodenr, season):
    
    # First get the proposed location for the <videofile>.nfo file
    dirname, filename = os.path.split(file)
    fname, ext = os.path.splitext(filename)
    fname = fname + ".nfo" # .nfo file has the same name as the video file itself.    
    
    log.Log("Reading existing tvshow.nfo", pluginid, 20)
    # Now we look for a tvshow nfo file.
    nforoot = 'tvshow'
    if depth == 2:
        # We're assuming to be in a season folder, so the tvshow.nfo file should be one up.
        sdir, tail = os.path.split(dirname)
        shownfo = os.path.join(sdir, "tvshow.nfo")
        if os.path.exists(shownfo):
            xmldata = ET.parse(shownfo)
        elif os.path.exists(os.path.join(dirname, "tvshow.nfo")):
            shownfo = os.path.join(dirname, "tvshow.nfo")
            xmldata = ET.parse(shownfo)
        else:
            root = ET.Element(nforoot)
            xmldata = ET.ElementTree(root)
    else:
        shownfo = os.path.join(dirname, "tvshow.nfo")
        if os.path.exists(os.path.join(dirname, "tvshow.nfo")):
            xmldata = ET.parse(shownfo)
        else:
            root = ET.Element(nforoot)
            xmldata = ET.ElementTree(root)
    
    nfodict = elem2dict(xmldata.getroot())
    
    # We now have a dict with the current NFO stuff. We need to add to the information, or update existing information if needed.
    changed = False
    # Sport title (includes year between parentheses and goes into the 'title' tags)
    if 'title' in nfodict[nforoot].keys():
        #title exists. Update it if it's not the same as our info.
        if nfodict[nforoot]['title']['text'] != showname:
            nfodict[nforoot]['title']['text'] = showname
            changed = True
    else:
        nfodict[nforoot]['title'] = adddictelem(showname)
        changed = True
    
    # Description (goes into the plot tags)
    if 'plot' in nfodict[nforoot].keys() and 'strDescriptionEN' in event['league'].keys():
        # Since there are multiple string conversions happening between getting it from tsdb and
        # loading it from the resultant XML file, even the same string will not match exactly.
        # That's why we're using the jaro-winkler fuzzy method to compare them. If they are 99+% similar
        # we can safely assume they are the same string.
        similarity = jaro.jaro_winkler_metric(unicode(nfodict[nforoot]['plot']['text']), unicode(event['league']['strDescriptionEN']))
        if similarity < 0.99:
            nfodict[nforoot]['plot']['text'] = event['league']['strDescriptionEN']
            changed = True
    else:
        if 'strDescriptionEN' in event['league'].keys():
            if event['league']['strDescriptionEN'] != '':
                nfodict[nforoot]['plot'] = adddictelem(event['league']['strDescriptionEN'])
                changed = True
    
    # SportsDB league ID (goes into the UniqueID tag with attributes)
    if not 'idLeague' in event['league'].keys():
        event['league']['idLeague'] = '0'
    if 'uniqueid' in nfodict[nforoot].keys():
        if nfodict[nforoot]['uniqueid']['text'] != event['league']['idLeague']:
            nfodict[nforoot]['uniqueid']['text'] = event['league']['idLeague']
            nfodict[nforoot]['uniqueid']['attrib'] = {'type':'tsdb', 'default':'false'}
            changed = True
    else:
        nfodict[nforoot]['uniqueid'] = adddictelem(event['league']['idLeague'], attrib={'type':'tsdb', 'default':'false'})
        changed = True
        
    # Sport Category (goes into the Genre tag, of which multiple may exist
    if 'genre' in nfodict[nforoot].keys() and 'strSport' in event['league'].keys():
        if not isinstance(nfodict[nforoot]['genre'], list):
            # It's going to be a list, so we can make it one and iterate over it.
            nfodict[nforoot]['genre'] = [nfodict[nforoot]['genre']]
        found = False
        for genre in nfodict[nforoot]['genre']:
            if genre['text'] == event['league']['strSport']:
                found = True
                break
        if not found:
            nfodict[nforoot]['genre'].append(adddictelem(event['league']['strSport']))
            changed = True
        
    else:
        if 'strSport' in event['league'].keys():
            nfodict[nforoot]['genre'] = adddictelem(event['league']['strSport'])
            changed = True
            
    # Event names (goes into the namedseason tags with the round number. Round 0 is named 'Non-Championship'
        
    if 'namedseason' in nfodict[nforoot].keys():
        if not isinstance(nfodict[nforoot]['namedseason'], list):
            nfodict[nforoot]['namedseason'] = [nfodict[nforoot]['namedseason']]
        found = False
        for namedseason in nfodict[nforoot]['namedseason']:
            # Since these are rounds, we can check for the correct season number
            if 'attrib' in namedseason.keys():
                if 'number' in namedseason['attrib'].keys():
                    if namedseason['attrib']['number'] == str(season):
                        if namedseason['text'] == event['event']['strEvent']:
                            found = True
                            break
                        elif season == 0:
                            if namedseason['text'] == 'Non-Championship':
                                found = True
                                break
                            else:
                                namedseason['text'] = 'Non-Championship'
                                changed = True
                        else:
                            namedseason['text'] = event['event']['strEvent']
                            found = True
        if not found:
            nfodict[nforoot]['namedseason'].append(adddictelem(event['event']['strEvent'], attrib={'number': str(season)}))
            found = True
    else:
        nfodict[nforoot]['namedseason'] = adddictelem(event['event']['strEvent'], attrib={'number': str(season)})
        changed = True
    
    # And finally check for artwork changes
    log.Log(nfodict, pluginid)
    if 'thumb' in nfodict[nforoot].keys():
        log.Log(nfodict[nforoot]['thumb'], pluginid, 10)
        if not isinstance(nfodict[nforoot]['thumb'], list):
            log.Log("Making a list of a non-list thumbnail tag", pluginid, 10)
            nfodict[nforoot]['thumb'] = [nfodict[nforoot]['thumb']]
        found = False
        foundshow = False
        for thumb in nfodict[nforoot]['thumb']:
            log.Log(thumb, pluginid)
            if 'season' in thumb['attrib']: # It's a season poster, not a sport poster.
                if thumb['attrib']['season'] == str(season) and thumb['attrib']['aspect'] == 'poster':
                    # We don't overwrite existing art, in case it's a local edit, so just say we found it
                    found = True
            else:
                if thumb['attrib']['aspect'] == 'poster':
                    # We don't overwrite existing art here either
                    foundshow = True        
        if not found:
            # If the season poster wasn't found create it.
            if artwork['season']['poster'] != '':
                nfodict[nforoot]['thumb'].append(adddictelem(artwork['season']['poster'], attrib={'aspect': 'poster', 'type': 'season', 'season': str(season), 'preview': ''}))
                changed = True
        if not foundshow:
            if artwork['sport']['poster'] != '':
                nfodict[nforoot]['thumb'].append(adddictelem(artwork['sport']['poster'], attrib={'aspect': 'poster', 'preview': ''}))
                changed = True
    else:
        if artwork['season']['poster'] != '' or artwork['sport']['poster'] != '':
            nfodict[nforoot]['thumb'] = []
            if artwork['season']['poster'] != '':
                nfodict[nforoot]['thumb'].append(adddictelem(artwork['season']['poster'], attrib={'aspect': 'poster', 'type': 'season', 'season': str(season), 'preview': ''}))
            if artwork['sport']['poster'] != '':
                nfodict[nforoot]['thumb'].append(adddictelem(artwork['sport']['poster'], attrib={'aspect': 'poster', 'preview': ''}))
            changed = True
    
    
    # If we applied changes to the information, save the NFO file.
    
    if changed:
        elements = dict2elem(nfodict.keys()[0], nfodict[nfodict.keys()[0]])
        _pretty_print(elements)
        tree = ET.ElementTree(elements)
        tree.write(shownfo, encoding='utf-8', xml_declaration=True)
    
    
    
    # And now we do the same with the episode data
    nforoot = 'episodedetails'
    epnfo = os.path.join(dirname, fname)
    if os.path.exists(epnfo):
        xmldata = ET.parse(epnfo)
    else:
        root = ET.Element(nforoot)
        xmldata = ET.ElementTree(root)
        
    nfodict = elem2dict(xmldata.getroot())
    changed = False
    
    # Episode name
    if 'title' in nfodict[nforoot].keys():
        #title exists. Update it if it's not the same as our info.
        if nfodict[nforoot]['title']['text'] != episodename:
            nfodict[nforoot]['title']['text'] = episodename
            changed = True
    else:
        nfodict[nforoot]['title'] = adddictelem(episodename)
        changed = True
    
    # Description
    if 'plot' in nfodict[nforoot].keys() and 'strDescriptionEN' in event['event'].keys():
        similarity = jaro.jaro_winkler_metric(unicode(nfodict[nforoot]['plot']['text']), unicode(event['event']['strDescriptionEN']))
        if similarity < 0.99:
            nfodict[nforoot]['plot']['text'] = event['event']['strDescriptionEN']
            changed = True
    else:
        if 'strDescriptionEN' in event['event'].keys():
            if event['event']['strDescriptionEN'] != '':
                nfodict[nforoot]['plot'] = adddictelem(event['event']['strDescriptionEN'])
                changed = True
    
    # UniqueID
    if not 'idEvent' in event['event'].keys():
        event['event']['idEvent'] = '0'
    if 'uniqueid' in nfodict[nforoot].keys():
        if nfodict[nforoot]['uniqueid']['text'] != event['event']['idEvent']:
            nfodict[nforoot]['uniqueid']['text'] = event['event']['idEvent']
            changed = True
    else:
        nfodict[nforoot]['uniqueid'] = adddictelem(event['event']['idEvent'], attrib={'type':'tsdb', 'default':'false'})
        changed = True
        
    # Date
    if 'aired' in nfodict[nforoot].keys() and 'dateEvent' in event['event'].keys():
        if nfodict[nforoot]['aired']['text'] != event['event']['dateEvent']:
            nfodict[nforoot]['aired']['text'] = event['event']['dateEvent']
            changed = True
    else:
        if 'dateEvent' in event['event'].keys():
            nfodict[nforoot]['aired'] = adddictelem(event['event']['dateEvent'])
            changed = True
    
    # Season
    if 'season' in nfodict[nforoot].keys():
        if nfodict[nforoot]['season']['text'] != str(season):
            nfodict[nforoot]['season']['text'] = str(season)
            changed = True
    else:
        nfodict[nforoot]['season'] = adddictelem(str(season))
        changed = True
    
    # Episode
    if 'episode' in nfodict[nforoot].keys():
        if nfodict[nforoot]['episode']['text'] != str(episodenr):
            nfodict[nforoot]['episode']['text'] = str(episodenr)
            changed = True
    else:
        nfodict[nforoot]['episode'] = adddictelem(str(episodenr))
        changed = True
    
    # Thumbnails
    if 'thumb' in nfodict[nforoot].keys():
        if not isinstance(nfodict[nforoot]['thumb'], list):
            nfodict[nforoot]['thumb'] = [nfodict[nforoot]['thumb']]
        found = False
        for thumb in nfodict[nforoot]['thumb']:
            if thumb['attrib']['aspect'] == 'thumb' and thumb['text'] == artwork['season']['thumb']:
                # We don't overwrite existing art here either
                found = True        
        if not found:
            # If the season poster wasn't found create it.
            if artwork['season']['thumb'] != '':
                nfodict[nforoot]['thumb'].append(adddictelem(artwork['season']['thumb'], attrib={'aspect': 'thumb', 'preview': ''}))
                changed = True
    else:
        if artwork['season']['thumb'] != '':
            nfodict[nforoot]['thumb'] = []
            nfodict[nforoot]['thumb'].append(adddictelem(artwork['season']['thumb'], attrib={'aspect': 'thumb', 'preview': ''}))
            changed = True
    
    
    if changed:
        elements = dict2elem(nfodict.keys()[0], nfodict[nfodict.keys()[0]])
        _pretty_print(elements)
        tree = ET.ElementTree(elements)
        tree.write(epnfo, encoding='utf-8', xml_declaration=True)
    print(nfodict)
    
# Integrated the jellyfin API to handle the season images and season/episode numbering. No longer need a season.nfo
# And since it is a third party invention anyway, and not an original XMBC metadata solution, we should rid ourselves
# of it as quickly as possible.
    
'''    # And a season.nfo, which is an unsupported .nfo but Jellyfin uses it for season data.
    # It only supports 'seasonnumber', 'seasonname' and thumb posters/banners.
    nforoot = 'seasondetails' 
    
    # One caveat for season nfos. They must exist in a season folder.
    if depth == 2: # We are in a season folder
        senfo = os.path.join(dirname, "season.nfo")
        if os.path.exists(senfo):
            xmldata = ET.parse(senfo)
        else:
            root = ET.Element(nforoot)
            xmldata = ET.ElementTree(root)
    else: # We're in a series folder.
        found = False
        sfolder = 'season ' + str(season)
        if os.path.isdir(os.path.join(dirname, sfolder)):
            dirname = os.path.join(dirname, sfolder)
            found = True
        sfolder = 'season ' + str(season).zfill(2)
        if os.path.isdir(os.path.join(dirname, sfolder)):
            dirname = os.path.join(dirname, sfolder)
            found = True
        sfolder = 'season' + str(season)
        if os.path.isdir(os.path.join(dirname, sfolder)):
            dirname = os.path.join(dirname, sfolder)
            found = True
        sfolder = 'season' + str(season).zfill(2)
        if os.path.isdir(os.path.join(dirname, sfolder)):
            dirname = os.path.join(dirname, sfolder)
            found = True
        if not found:
            dirname = os.path.join(dirname, 'season ' + str(season).zfill(2))
            os.makedirs(dirname)
            
        senfo = os.path.join(dirname, "season.nfo")
        if os.path.exists(senfo):
            xmldata = ET.parse(senfo)
        else:
            root = ET.Element(nforoot)
            xmldata = ET.ElementTree(root)
    
      
    nfodict = elem2dict(xmldata.getroot())
    changed = False
    
    # Seasonnumber
    if 'seasonnumber' in nfodict[nforoot].keys():
        if int(nfodict[nforoot]['seasonnumber']['text']) != season:
            nfodict[nforoot]['seasonnumber']['text'] = str(season)
            changed = True
    else:
        nfodict[nforoot]['seasonnumber'] = adddictelem(str(season))
        changed = True
    
    
    # Seasonname
    if 'seasonname' in nfodict[nforoot].keys():
        if nfodict[nforoot]['seasonname']['text'] != sname:
            nfodict[nforoot]['seasonname'] = adddictelem(sname)
            changed = True
    else:
        nfodict[nforoot]['seasonname'] = adddictelem(sname)
        changed = True
    
    # Thumbnails 
    if 'thumb' in nfodict[nforoot].keys():
        if not isinstance(nfodict[nforoot]['thumb'], list):
            log.Log("Making a list of a non-list thumbnail tag", pluginid, 10)
            nfodict[nforoot]['thumb'] = [nfodict[nforoot]['thumb']]
        found = False
        for thumb in nfodict[nforoot]['thumb']:
            log.Log(thumb, pluginid)
            if (thumb['attrib']['aspect'] == 'poster') and (artwork['season']['poster'] == thumb['text']):
                # We don't overwrite existing art, in case it's a local edit, so just say we found it
                found = True
        if not found:
            # If the season poster wasn't found create it.
            if artwork['season']['poster'] != '':
                nfodict[nforoot]['thumb'].append(adddictelem(artwork['season']['poster'], attrib={'aspect': 'poster', 'preview': ''}))
                changed = True
    else:
        if artwork['season']['poster'] != '':
            nfodict[nforoot]['thumb'] = []
            nfodict[nforoot]['thumb'].append(adddictelem(artwork['season']['poster'], attrib={'aspect': 'poster', 'preview': ''}))
            changed = True
    
    if changed:
        elements = dict2elem(nfodict.keys()[0], nfodict[nfodict.keys()[0]])
        _pretty_print(elements)
        tree = ET.ElementTree(elements)
        tree.write(senfo, encoding='utf-8', xml_declaration=True)
'''            
    
    
    
    