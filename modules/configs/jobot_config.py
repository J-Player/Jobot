import os
from abc import ABC, abstractmethod
from multiprocessing import RLock

import yaml

from modules.core.job_bot import JobFilter, JobFilterKey, JobSearch
from modules.meta.singleton import SingletonMeta


class SingletonABCMeta(SingletonMeta, type(ABC)):
    pass


class JobotConfig(ABC, metaclass=SingletonABCMeta):
    # Variáveis de classe com lock separado
    _shared_config = None
    _shared_config_loaded = False
    _shared_config_lock = RLock()  # Usando RLock que suporta context manager

    def __init__(self):
        self._load_shared_config()
        self.bots = {}

    def _load_shared_config(self):
        # Usando gerenciador de contexto com RLock
        with JobotConfig._shared_config_lock:
            if JobotConfig._shared_config_loaded:
                self.config = JobotConfig._shared_config
                return
            file = os.getenv("BOT_CONFIG_YML", "configs.yml")
            if not os.path.exists(file):
                raise Exception(f"Arquivo {file} não encontrado.")
            with open(file, "r", encoding="utf-8") as f:
                JobotConfig._shared_config = yaml.safe_load(f)
            JobotConfig._shared_config_loaded = True
            self.config = JobotConfig._shared_config

    def get_searches(self, bot: str):
        search_list = self.__get_bot(bot)
        searches: list[JobSearch] = []
        assert type(search_list) == list
        for s in search_list:
            for location in s["locations"]:
                searches.append(JobSearch(s["job"], location))
        return searches

    def get_filters(self):
        filters: list[JobFilter] = []
        for f in self.config.get("filters", []):
            key = f["key"]
            includes = []
            excludes = []
            for include_list in f.get("include", []):
                for l in include_list.values():
                    includes += l
            for exclude_list in f.get("exclude", []):
                for l in exclude_list.values():
                    excludes += l
            full_match = f.get("full_match", False)
            filters.append(JobFilter(self._get_filter_key(key), keywords=includes, exclude_keywords=excludes, full_match=full_match))
        return filters

    @abstractmethod
    def _get_filter_key(self, value: str) -> JobFilterKey:
        raise NotImplementedError(f"The method {self._get_filter_key.__name__} must be implemented.")

    def __get_bot(self, bot: str):
        try:
            return self.config["searches"][bot[:-3]]
        except AttributeError as err:
            raise Exception(f'Chave "{bot[:-3]}" não encontrado no arquivo de configuração.')
