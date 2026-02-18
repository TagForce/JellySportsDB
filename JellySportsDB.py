'''
Jellyfin Sports Monitor
Monitors Jellyfin library folders retrieved via the API and processes sports files.
'''

import sys
import time
import os
from importlib import reload

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileMovedEvent

# Existing helpers (unchanged)
import helpers.process as process
import helpers.jellyapi as jellyapi
import helpers.plexlog as log


class SportsFileHandler(FileSystemEventHandler):
    """Handles filesystem events for video files only."""

    VIDEO_EXTS = {
        'webm', 'mkv', 'flv', 'vob', 'ogv', 'ogg', 'mov', 'avi', 'qt', 'wmv',
        'asf', 'amv', 'mp4', 'm4p', 'm4v', 'mpg', 'mpeg', 'mpe', 'mpv', '3gp',
        '3g2', 'mxf', 'nsv', 'f4v', 'mod', 'rm', 'rmvb', 'ts', 'm2ts'
    }

    def __init__(self, base_path: str):
        super().__init__()
        self.base_path = os.path.abspath(base_path)

    def on_created(self, event):
        if not event.is_directory and self._is_video(event.src_path):
            self._process_file(event.src_path, "created")

    def on_modified(self, event):
        if not event.is_directory and self._is_video(event.src_path):
            self._process_file(event.src_path, "modified")

    def on_moved(self, event):
        # If a file is moved INTO a watched folder we treat it as created
        if not event.is_directory and self._is_video(event.dest_path):
            self._process_file(event.dest_path, "moved")

    def _is_video(self, filepath: str) -> bool:
        ext = os.path.splitext(filepath)[1].lstrip('.').lower()
        return ext in self.VIDEO_EXTS

    def _process_file(self, filepath: str, event_type: str):
        try:
            # Calculate depth relative to the library root (exactly what the old code expected)
            dirpath = os.path.dirname(filepath)
            rel = os.path.relpath(dirpath, self.base_path)
            depth = 0 if rel == '.' else len(rel.split(os.sep))

            log.Log(f"[{event_type.upper()}] Processing {filepath} (depth={depth})", "MONITOR")
            result = process.ProcessFile(filepath, depth)
            log.Log(f"Process result: {result}", "MONITOR", log.LL_INFO)

        except Exception as e:
            log.LogExcept(f"Failed to process {filepath}", e, "MONITOR")


class JellyfinSportsMonitor:
    """Main monitor class - fetches library paths from Jellyfin and starts watchers."""

    def __init__(self,
                 jellyfin_url: str = "http://192.168.2.20:8096/",
                 token: str = "55321e3ed64c4f02b8c82a3283041003"):
        self.jellyfin_url = jellyfin_url.rstrip('/')
        self.token = token

        # Configure the existing jellyapi module (it uses module-level globals)
        jellyapi.baseurl = self.jellyfin_url
        jellyapi.headers["Authorization"] = f'MediaBrowser Token="{self.token}"'

        self.library_paths = self._fetch_library_paths()
        self.observer = Observer()
        self.handlers = []

    def _fetch_library_paths(self) -> list[str]:
        """Retrieve every physical folder from Jellyfin VirtualFolders."""
        paths = []
        try:
            vfolders = jellyapi.fetch_api("Library/VirtualFolders")
            for vf in vfolders:
                for loc in vf.get("Locations", []):
                    abspath = os.path.abspath(loc)
                    if os.path.isdir(abspath):
                        paths.append(abspath)

            # Fallback to MediaFolders if VirtualFolders returned nothing
            if not paths:
                media = jellyapi.fetch_api("Library/MediaFolders")
                for item in media.get("Items", []):
                    # MediaFolders don't always expose paths, so we skip them
                    pass

        except Exception as e:
            log.LogExcept("Could not fetch Jellyfin libraries – falling back to current directory", e, "MONITOR")
            paths = ["."]

        unique_paths = sorted(set(paths))
        log.Log(f"Found {len(unique_paths)} library path(s) to monitor", "MONITOR")
        for p in unique_paths:
            log.Log(f"   → {p}", "MONITOR", log.LL_DEBUG)

        return unique_paths

    def start(self):
        """Schedule a handler for every library path and start the observer."""
        for path in self.library_paths:
            handler = SportsFileHandler(base_path=path)
            self.observer.schedule(handler, path, recursive=True)
            self.handlers.append(handler)
            log.Log(f"Started monitoring: {path}", "MONITOR")

        self.observer.start()
        log.Log("Jellyfin Sports Monitor is now running...", "MONITOR")

        try:
            while self.observer.is_alive():
                self.observer.join(1)
        except KeyboardInterrupt:
            log.Log("Received keyboard interrupt – shutting down", "MONITOR")
        finally:
            self.observer.stop()
            self.observer.join()
            log.Log("Observer stopped", "MONITOR")


if __name__ == "__main__":
    reload(sys)
    # sys.setdefaultencoding('utf-8')   # Python 3 no longer needs this

    # plexlog already does its own file logging on import
    log.setup()

    # Optional: pass URL / token via command line if you want
    url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.2.20:8096/"
    token = sys.argv[2] if len(sys.argv) > 2 else "55321e3ed64c4f02b8c82a3283041003"

    monitor = JellyfinSportsMonitor(jellyfin_url=url, token=token)
    monitor.start()
