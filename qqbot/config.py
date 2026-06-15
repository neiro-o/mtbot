import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotConfig:
    appid: str
    secret: str


def load_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def load_config() -> BotConfig:
    load_dotenv()
    return BotConfig(
        appid=load_required_env("QQ_BOT_APPID"),
        secret=load_required_env("QQ_BOT_SECRET"),
    )
