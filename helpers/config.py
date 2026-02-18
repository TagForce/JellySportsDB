# helpers/config.py
import configparser
from pathlib import Path

class AppConfig:
    def __init__(self, path: str = "config.cfg"):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Config not found: {self.path}")

        self.parser = configparser.ConfigParser()
        self.parser.read(self.path)

    @property
    def jellyfin_url(self) -> str:
        return self.parser.get("jellyfin", "url", fallback="http://localhost:8096").rstrip("/")

    @property
    def jellyfin_token(self) -> str:
        return self.parser.get("jellyfin", "token", fallback="")

    @property
    def sportsdb_apikey_file(self) -> Path:
        fname = self.parser.get("thesportsdb", "apikey_file", fallback="tsdbapi.txt")
        return self.path.parent / fname

    @property
    def log_level(self) -> int:
        level_name = self.parser.get("logging", "level", fallback="INFO").upper()
        levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        return levels.get(level_name, 20)