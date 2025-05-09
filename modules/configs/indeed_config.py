from modules.bot.indeed.indeed_bot import IndeedJobFilterKey
from modules.configs.jobot_config import JobotConfig


class IndeedConfig(JobotConfig):

    def __init__(self):
        super().__init__()

    def _get_filter_key(self, value: str) -> IndeedJobFilterKey:
        return IndeedJobFilterKey(value)
