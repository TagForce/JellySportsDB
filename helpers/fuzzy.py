'''
Created on 12 jun. 2025

@author: Raymond
'''
import re, unicodedata, jaro

lw = 2
mw = 2
sw = 2
lm = 0.85
mm = 0.85
sm = 0.85

def compare(s1, s2):
    
    s1 = unicode(s1)
    s2 = unicode(s2)
    # Turn s1 into an array of words
    src = re.sub(' [0-9]+', '', s1.lower()).split(' ')
    # And convert each word into unicode
    for idx, fw in enumerate(src):
        src[idx] = unicodedata.normalize('NFC', unicode(fw))
    
    # Remove any periods from the destination string (the one we're comparing to)
    dest = s2.replace('.', ' ')
    # And convert it to unicode
    dest = unicodedata.normalize('NFC', dest)
    # Turn it into an array of words
    eventwords = re.sub(' [0-9]+', '', dest.lower()).split(' ')
    # Turn each word into unicode
    for idx, ew in enumerate(eventwords):
        eventwords[idx] = unicodedata.normalize('NFC', unicode(ew))
    
    # Compare each word to every word in the destination. And add matches to an array
    matchedwords = []
    for eword in eventwords:
        for fword in src:
            wordmatch = jaro.jaro_winkler_metric(unicode(eword), unicode(fword))
            if len(fword) >= lw and wordmatch > lm:
                matchedwords.append(wordmatch)
            elif len(fword) >= mw and wordmatch > mm:
                matchedwords.append(wordmatch)
            elif len(fword) >= sw and wordmatch > sm:
                matchedwords.append(wordmatch)
                
    
    totalscore = 0
    if (len(matchedwords) > 0):
        for score in matchedwords:
            totalscore += score * 4    
        return (totalscore + jaro.jaro_winkler_metric(s1, s2)) / ((len(matchedwords) * 4) + abs(len(src) - len(matchedwords)) + 1)
    else:
        return 0