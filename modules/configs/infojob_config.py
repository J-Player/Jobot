from modules.bot.infojob.infojob_bot import InfoJobJobFilterKey
from modules.configs.jobot_config import JobotConfig


class InfoJobConfig(JobotConfig):

    def __init__(self):
        super().__init__()

    def _get_filter_key(self, value: str) -> InfoJobJobFilterKey:
        return InfoJobJobFilterKey(value)
