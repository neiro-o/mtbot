import asyncio
import botpy
from qqbot.client import QQBotClient
from qqbot.config import load_config


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = load_config()
    intents = botpy.Intents(public_messages=True)
    client = QQBotClient(intents=intents)
    client.run(appid=config.appid, secret=config.secret)


if __name__ == "__main__":
    main()
