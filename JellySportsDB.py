#!/usr/bin/env python3
"""
JellySportsDB – Modern object-oriented filesystem watcher + metadata agent
"""

import sys
import time
from pathlib import Path
from importlib import reload

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from helpers.config import AppConfig
from helpers.plexlog import log, setup as setup_logging, LL_INFO
from helpers.jellyfin_client import JellyfinClient
from helpers.sportsdb_client import TheSportsDBClient
from helpers.process import process_file, set_clients  # We'll add set_clients

class SportsVideoHandler(FileSystemEventHandler):
    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".ts", ".m2ts", ".mpg", ".webm"}

    def __init__(self, root_path: Path, processor):
        self.root = root_path.resolve()
        self.processor = processor

    def on_created(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).suffix.lower() in self.VIDEO_EXTENSIONS:
            self._handle_file(event.src_path, "created")

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).suffix.lower() in self.VIDEO_EXTENSIONS:
            self._handle_file(event.src_path, "modified")

    def on_moved(self, event):
        if event.is_directory:
            return
        if Path(event.dest_path).suffix.lower() in self.VIDEO_EXTENSIONS:
            self._handle_file(event.dest_path, "moved →")

    def _handle_file(self, filepath: str, action: str):
        path = Path(filepath)
        try:
            rel = path.parent.relative_to(self.root)
            depth = 0 if str(rel) == "." else len(rel.parts)
            log(f"[{action.upper()}] {filepath}  (depth={depth})", "FS", LL_INFO)
            process_file(str(path), depth)
        except Exception as e:
            log(f"Processing failed for {filepath}: {e}", "FS", level=40)


class JellySportsDBApp:
    def __init__(self):
        self.config = AppConfig()
        setup_logging(level=self.config.log_level)

        log("JellySportsDB starting...", "MAIN")

        self.jellyfin = JellyfinClient(self.config.jellyfin_url, self.config.jellyfin_token)
        self.sportsdb = TheSportsDBClient(self.config.sportsdb_apikey_file)

        # Inject clients into process module
        set_clients(self.jellyfin, self.sportsdb)

        self.library_paths = self._get_library_paths()
        self.observer = Observer()

    def _get_library_paths(self):
        try:
            vf_data = self.jellyfin._request("GET", "Library/VirtualFolders")
            paths = []
            for folder in vf_data if isinstance(vf_data, list) else vf_data.get("Items", []):
                for loc in folder.get("Locations", []):
                    p = Path(loc)
                    if p.is_dir():
                        paths.append(p)
            unique = {p.resolve() for p in paths}
            return sorted(unique)
        except Exception as e:
            log(f"Could not fetch libraries: {e} → using current directory", "MAIN", 40)
            return [Path(".")]

    def run(self):
        for path in self.library_paths:
            handler = SportsVideoHandler(path, self)
            self.observer.schedule(handler, str(path), recursive=True)
            log(f"Watching → {path}", "MAIN")

        self.observer.start()
        log("Monitoring active. Press Ctrl+C to stop.", "MAIN")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log("Shutting down...", "MAIN")
        finally:
            self.observer.stop()
            self.observer.join()
            log("Stopped.", "MAIN")


if __name__ == "__main__":
    reload(sys)
    app = JellySportsDBApp()
    app.run()