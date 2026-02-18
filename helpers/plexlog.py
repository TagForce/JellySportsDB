# -*- coding: utf-8 -*-
import sys
import os
import time   
import logging, logging.handlers
import inspect


SetupDone              = False
Log                    = None
Handler                = None


def setup():
    global SetupDone
    if SetupDone:
        return
    else:
        SetupDone = True
    global PLEX_ROOT
    LOG_PATHS = { 'win32':  ['%LOCALAPPDATA%\\Plex Media Server',                                       #
                             '%USERPROFILE%\\Local Settings\\Application Data\\Plex Media Server' ],    #
                  'darwin': [ '$HOME/Library/Application Support/Plex Media Server' ],                    # LINE_FEED = "\r"
                  'linux':  [ '$PLEX_HOME/Library/Application Support/Plex Media Server',                 # Linux
                              '/var/lib/plexmediaserver/Library/Application Support/Plex Media Server',   # Debian, Fedora, CentOS, Ubuntu
                              '/usr/local/plexdata/Plex Media Server',                                    # FreeBSD
                              '/usr/pbi/plexmediaserver-amd64/plexdata/Plex Media Server',                # FreeNAS
                              '${JAIL_ROOT}/var/db/plexdata/Plex Media Server',                          # FreeNAS
                              '/c/.plex/Library/Application Support/Plex Media Server',                   # ReadyNAS
                              '/share/MD0_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server',          # QNAP
                              '/volume1/Plex/Library/Application Support/Plex Media Server',              # Synology, Asustor
                              '/volume2/Plex/Library/Application Support/Plex Media Server',              # Synology, if migrated a second raid volume as unique volume in new box         
                              '/raid0/data/module/Plex/sys/Plex Media Server',                            # Thecus
                              '/raid0/data/PLEX_CONFIG/Plex Media Server' ]}                              # Thecus Plex community version

    platform = sys.platform.lower() if "platform" in dir(sys) and not sys.platform.lower().startswith("linux") else "linux" if "platform" in dir(sys) else "unknown"
    for LOG_PATH in LOG_PATHS[platform] if platform in LOG_PATHS else [ os.path.join(os.getcwd(),"Logs"), '$HOME']:
        if '%' in LOG_PATH or '$' in LOG_PATH:
            LOG_PATH = os.path.expandvars(LOG_PATH)  # % on win only, $ on linux
        if os.path.isdir(LOG_PATH):
            break                                    # os.path.exists(LOG_PATH)
    else:
        LOG_PATH = os.path.expanduser('~')                       
    PLEX_ROOT = LOG_PATH
    
    global log
    log = logging.getLogger('SportsScanner')
    log.setLevel(logging.DEBUG)
    set_logging(backup_count=5)


LL_INFO = 20
LL_DEBUG= 10
LL_WARN = 30
LL_ERROR= 40
LL_CRIT = 50


# Setup logging

def set_logging(root='', foldername='', filename='', backup_count=0, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', mode='a'):#%(asctime)-15s %(levelname)s -
    foldername = os.path.join(PLEX_ROOT, 'Logs')
    filename = 'Plex Sports Scanner.log'
    log_file = os.path.join(foldername, filename)
    
    # Bypass DOS path MAX_PATH limitation (260 Bytes=> 32760 Bytes, 255 Bytes per folder unless UDF 127B ytes max)
    if os.sep=="\\":
        dos_path = os.path.abspath(log_file) if isinstance(log_file, unicode) else os.path.abspath(log_file.decode('utf-8'))
        log_file = u"\\\\?\\UNC\\" + dos_path[2:] if dos_path.startswith(u"\\\\") else u"\\\\?\\" + dos_path
    
    #if not mode:  mode = 'a' if os.path.exists(log_file) and os.stat(log_file).st_mtime + 3600 > time.time() else 'w' # Override mode for repeat manual scans or immediate rescans
    
    global Handler
    if Handler:       
        log.removeHandler(Handler)
    if backup_count:
        if not os.path.exists(log_file):
            open(log_file, 'a').close()
        Handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=backup_count, encoding='utf-8')
    else:             
        Handler = logging.FileHandler(log_file, mode=mode, encoding='utf-8')
    Handler.setFormatter(logging.Formatter(format))
    Handler.setLevel(logging.DEBUG)
    log.addHandler(Handler)



# Logging function
def Log(entry, pluginid="Undefined", loglevel=LL_INFO):
    
    log.log(loglevel, "{0} - [{1}]: {2}".format(pluginid, sys._getframe().f_back.f_code.co_name, entry))

    
def LogExcept(entry, e, pluginid="Undefined"):
    
    log.log(LL_CRIT, "{0} - [{1}]: {2}".format(pluginid, sys._getframe().f_back.f_code.co_name, entry))
    log.exception(e)
    
setup()
