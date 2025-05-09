from modules.bot.linkedin.linkedin_bot import LinkedinJobFilterKey
from modules.configs.jobot_config import JobotConfig


class LinkedinConfig(JobotConfig):

    def __init__(self):
        super().__init__()

    def _get_filter_key(self, value: str) -> LinkedinJobFilterKey:
        return LinkedinJobFilterKey(value)
