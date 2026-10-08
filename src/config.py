"""Application configuration loaded from environment variables and .env."""

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when required application configuration is missing."""


@dataclass(frozen=True)
class Config:
    faceit_api_key: str
    discord_token: str


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    if environ is None:
        load_dotenv()
        environ = os.environ
    missing = [name for name in ("FACEIT_API_KEY", "DISCORD_TOKEN") if not environ.get(name, "").strip()]
    if missing:
        raise ConfigurationError("Variables d'environnement manquantes : " + ", ".join(missing))
    return Config(faceit_api_key=environ["FACEIT_API_KEY"], discord_token=environ["DISCORD_TOKEN"])
