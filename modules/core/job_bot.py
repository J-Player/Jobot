import os
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pymongo import AsyncMongoClient, UpdateOne

from modules.core import Bot, Job
from modules.utils import normalize_string
from modules.utils.json_handler import load_json, save_json


class JobFilterKey(Enum):
    pass


@dataclass
class JobFilter:
    _key: JobFilterKey
    keywords: Optional[list[str]] = None
    full_match: bool = False
    exclude_keywords: Optional[list[str]] = None

    @property
    def key(self) -> str:
        """Retorna o valor (string) do Enum."""
        return self._key.value


@dataclass
class JobSearch:
    job: str
    location: str = None


@dataclass
class JobBotOptions:
    searches: list[JobSearch]
    filters: list[JobFilter] = None
    username: str = None
    password: str = None


class JobBot(Bot):

    def __init__(self, options: JobBotOptions):
        super().__init__()
        self._username = options.username
        self._password = options.password
        self._searches = options.searches
        self._logged: False
        self.__filters = options.filters or []
        self.__jobs: dict[str, Job] = defaultdict(Job)
        self.__jobs_inserted: int = 0
        self.__jobs_updated: int = 0
        host_name = os.getenv("DB_HOST", "mongodb://root:example@mongo:27017/")
        self.__client = AsyncMongoClient(host_name, connect=False)

    async def _setup(self):
        try:
            self._logger.debug("Estabelecendo conexão com banco de dados...")
            await self.__client.aconnect()
        except Exception as err:
            self._logger.error(f"Erro ao conectar ao banco de dados: {str(err)}", exc_info=True)
            raise err
        else:
            self._logger.debug(f"Conexão com banco de dados estabelecida com sucesso!")

    async def _teardown(self):
        try:
            if not self.__client._closed:
                self._logger.debug("Fechando conexões com banco de dados...")
                await self.__client.close()
                self._logger.debug(f"Conexão com banco de dados fechada com sucesso!")
        except Exception as err:
            self._logger.error(f"Erro ao fechar conexão ao banco de dados: {str(err)}", exc_info=True)
        finally:
            self._logger.info(f"Total de jobs adicionados: {self.__jobs_inserted}")
            self._logger.info(f"Total de jobs atualizados: {self.__jobs_updated}")

    async def _login(self):
        raise NotImplementedError(f"The method {self._login.__name__} must be implemented.")

    def _filter_job(self, job: Job):
        for index, job_filter in enumerate(self.__filters, start=1):
            passed = self.__filter_data(job, job_filter)
            if not passed:
                self._logger.debug(f"Job não passou pelo filtro Nº {index} de {len(self.__filters)} | ID: {job.id}")
                return False
        return True

    async def _job_exists(self, id: str):
        if id in [*self.__jobs.keys()]:
            return True
        else:
            job = await self.__client["job_db"][self.__class__.__name__].find_one({"_id": id})
            return job is not None

    def _append_job(self, job: Job):
        self.__jobs[job.id] = self.__jobs.get(job.id, job)

    async def _save_jobs(self):
        if len(self.__jobs) == 0:
            return
        try:
            DATABASE = self.__client["job_db"]
            COLLECTION = DATABASE[self.__class__.__name__]
            operations = []
            for job in self.__jobs.values():
                job_dict = vars(deepcopy(job))

                if "id" in job_dict:
                    job_dict["_id"] = job_dict.pop("id")

                # Remove 'updated_at' do dicionário para evitar conflito
                job_dict.pop("updated_at", None)

                now = datetime.now()
                operacao = UpdateOne(
                    {"_id": job.id},  # Filtro pelo ID
                    {
                        "$setOnInsert": {**job_dict, "created_at": now},
                        "$set": {"updated_at": now},
                    },
                    upsert=True,  # Cria documento se não existir
                )
                operations.append(operacao)
            result = await COLLECTION.bulk_write(operations, ordered=False)
            if result.upserted_count:
                self.__jobs_inserted += result.upserted_count
                self._logger.debug(f"Jobs inseridos no banco de dados: {result.upserted_count}")
            if result.modified_count:
                self.__jobs_updated += result.modified_count
                self._logger.debug(f"Jobs atualizados no banco de dados: {result.modified_count}")
        except Exception as err:
            self._logger.error(f"Ocorreu um erro ao salvar os jobs no banco de dados: {str(err)}", exc_info=True)
            self.__save_jobs_in_file()
        else:
            self.__jobs.clear()

    def __filter_data(self, job: Job, job_filter: JobFilter):
        key = job_filter.key
        keywords = job_filter.keywords
        exclude_keywords = job_filter.exclude_keywords
        full_match = job_filter.full_match
        INCLUDE_REGEX = [rf"\b{re.escape(word)}\b" for word in keywords] if keywords else []
        EXCLUDE_REGEX = [rf"\b{re.escape(word)}\b" for word in exclude_keywords] if exclude_keywords else []

        def verify(text: str) -> bool:
            text = normalize_string(text.lower().strip().replace(r"\s+", " "))
            include_condition = True
            if INCLUDE_REGEX:
                matches = (re.search(pattern, text, re.IGNORECASE) is not None for pattern in INCLUDE_REGEX)
                include_condition = all(matches) if full_match else any(matches)
            exclude_condition = False
            if EXCLUDE_REGEX:
                exclude_matches = (re.search(ex_pattern, text, re.IGNORECASE) is not None for ex_pattern in EXCLUDE_REGEX)
                exclude_condition = any(exclude_matches)
            return include_condition and not exclude_condition

        return verify(vars(job)[key])

    def __save_jobs_in_file(self):
        try:
            DIR_PATH = rf"jobs/{self.__class__.__name__.lower()}"
            self._logger.debug(f"Salvando arquivos em formato json no diretório: {DIR_PATH}")
            os.makedirs(DIR_PATH, exist_ok=True)
            files = []
            for id, job in self.__jobs.items():
                file_path = os.path.join(DIR_PATH, f"{id}.json")
                save_json(file_path, job)
                files.append(self.__jobs.pop(id))
            else:
                self._logger.debug(f"Total de arquivos salvos: {len(files)}")
        except Exception as err:
            self._logger.error(f"Erro ao salvar jobs em arquivos json: {str(err)}", exc_info=True)
            raise err

    def __load_jobs_files(self):
        DIR_PATH = rf"jobs/{self.__class__.__name__.lower()}"
        os.makedirs(DIR_PATH, exist_ok=True)
        for pos_json in os.listdir(DIR_PATH):
            job = Job(**load_json(os.path.join(DIR_PATH, pos_json)))
            self._append_job(job)
