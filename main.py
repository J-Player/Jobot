import asyncio
import os

import nest_asyncio
from dotenv import load_dotenv

from modules.bot.indeed import IndeedBot, IndeedBotOptions
from modules.bot.infojob import InfoJobBot, InfoJobBotOptions
from modules.bot.linkedin import LinkedinBot, LinkedinBotOptions
from modules.configs.indeed_config import IndeedConfig
from modules.configs.infojob_config import InfoJobConfig
from modules.configs.linkedin_config import LinkedinConfig

nest_asyncio.apply()

load_dotenv("../")


async def infojob():
    bot = "infojobbot"
    configs = InfoJobConfig()
    options = InfoJobBotOptions(
        username=os.getenv("INFOJOB_USER"),
        password=os.getenv("INFOJOB_PASS"),
        searches=configs.get_searches(bot),
        filters=configs.get_filters(),
    )
    bot = InfoJobBot(options)
    await bot.start()


async def indeed():
    bot = "indeedbot"
    configs = IndeedConfig()
    options = IndeedBotOptions(
        username=os.getenv("INDEED_USER"),
        searches=configs.get_searches(bot),
        filters=configs.get_filters(),
    )
    bot = IndeedBot(options)
    await bot.start()


async def linkedin():
    bot = "linkedinbot"
    configs = LinkedinConfig()
    options = LinkedinBotOptions(
        username=os.getenv("LINKEDIN_USER"),
        password=os.getenv("LINKEDIN_PASS"),
        searches=configs.get_searches(bot),
        filters=configs.get_filters(),
    )
    bot = LinkedinBot(options)
    await bot.start()


if __name__ == "__main__":
    # Escolha um dos bots para executar
    # asyncio.run(infojob())
    # asyncio.run(indeed())
    # asyncio.run(linkedin())
    pass
