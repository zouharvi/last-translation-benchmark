import os
import tomllib
from typing import Any

for config_file in ["config.toml", "config.template.toml"]:
    if os.path.exists(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/" + config_file
    ):
        break
else:
    raise FileNotFoundError("No config file found.")

with open(config_file, "rb") as f:
    config_data: dict[str, Any] = tomllib.load(f)


def get_config(key: str, default: Any = "") -> Any:
    return config_data.get(key) or os.getenv(key, default)


CONTRIBUTOR_QUOTA = get_config("CONTRIBUTOR_QUOTA", 10)
DATA_PATH = get_config("DATA_PATH", "data/db.json")
OPENAI_API_KEY = get_config("OPENAI_API_KEY", "")
