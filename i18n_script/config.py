import os
from dataclasses import dataclass
from typing import List
import yaml
from dotenv import load_dotenv

load_dotenv()


# Configuration
@dataclass
class Config:
    project_path: str
    openai_api_key: str
    symbols_dict_path: str
    target_languages: List[str] = None
    default_language: str = "en"

    def __post_init__(self):
        if self.target_languages is None:
            self.target_languages = ["en", "es"]


def load_config(path: str = "config.yaml") -> Config:
    with open(path, "r") as f:
        raw_cfg = yaml.safe_load(f)

    # Resolve environment variable if used in YAML
    api_key = raw_cfg["openai_api_key"]
    if api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.getenv(env_var, "")

    return Config(
        project_path=raw_cfg["project_path"],
        openai_api_key=api_key,
        symbols_dict_path=raw_cfg["symbols_dict_path"],
        target_languages=raw_cfg.get("target_languages", ["en", "es"]),
        default_language=raw_cfg.get("default_language", "en"),
    )
