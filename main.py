import asyncio
import os

import nest_asyncio
from dotenv import load_dotenv

from modules.bot.indeed import IndeedBot, IndeedBotOptions
from modules.bot.linkedin import LinkedinBot, LinkedinBotOptions
from modules.configs.indeed_config import IndeedConfig
from modules.configs.jobot_config import JobotConfig
from modules.configs.linkedin_config import LinkedinConfig

nest_asyncio.apply()

load_dotenv("../")


async def indeed():
    bot = "indeedbot"
    configs = IndeedConfig()
    options = IndeedBotOptions(
        username=os.getenv("INDEED_USER"),
        password=os.getenv("INDEED_PASS"),
        searches=configs.get_searches(bot),
        filters=configs.get_filters(),
    )
    bot = IndeedBot(options)
    await bot.start()


# TODO: Em homologação (requer testes)
async def linkedin():
    bot = "linkedinbot"
    configs = LinkedinConfig()
    options = LinkedinBotOptions(
        username=os.getenv("LINKEDIN_USER"),
        password=os.getenv("LINKEDIN_PASS"),
        searches=configs.get_searches(bot),
        filters=configs.get_filters(bot),
    )
    bot = LinkedinBot(options)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(indeed())
