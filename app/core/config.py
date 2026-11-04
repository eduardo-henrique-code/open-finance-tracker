import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    pluggy_client_id: str
    pluggy_client_secret: str


def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    client_id = os.getenv("PLUGGY_CLIENT_ID", "").strip()
    client_secret = os.getenv("PLUGGY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET must be configured."
        )

    return Settings(
        pluggy_client_id=client_id,
        pluggy_client_secret=client_secret,
    )
