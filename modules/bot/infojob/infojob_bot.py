import asyncio
from datetime import datetime
import re
from time import time

from modules.bot.infojob.infojob_job import InfoJobJob
from modules.core import JobBot, JobBotOptions, JobFilterKey, JobSearch
from modules.utils.string_handler import normalize_string


class InfoJobJobFilterKey(JobFilterKey):
    TITLE = "title"
    DESCRIPTION = "description"
    LOCATION = "location"
    COMPANY = "company"


class InfoJobBotOptions(JobBotOptions):
    pass


class InfoJobSearch(JobSearch):
    pass


class InfoJobBot(JobBot):

    def __init__(self, options: InfoJobBotOptions):
        super().__init__(options)

    async def _setup(self):
        await super()._setup()
        url = "https://www.infojobs.com.br"
        self._driver.uc_activate_cdp_mode(url)
        self._close_cookie_popup()
        if self._username and self._password:
            await self._login()

    async def _start(self):
        try:
            # CAPTCHA_SELECTOR = "#JnAv0 div div"
            WRAPPER_SELECTOR = "//*[@id='filterSideBar']"
            # self._captcha_task = asyncio.create_task(self._captcha(CAPTCHA_SELECTOR))
            # await asyncio.sleep(1)  # Pequeno delay para permitir a criação da task
            async with self._captcha_condition:
                self._logger.debug(f"Total de pesquisas para realizar: {len(self._searches)}")
                for index, search in enumerate(self._searches, start=1):
                    self._driver.cdp.sleep(5)  # Aguarda a lista carregar...
                    self._search_job(search)
                    self._logger.info(
                        f"[{index} de {len(self._searches)}] Pesquisando vagas: {search.job} | Localização: {search.location}."
                    )
                    # await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                    self._driver.cdp.sleep(5)  # Aguarda a lista carregar...
                    if self._driver.cdp.is_element_present(WRAPPER_SELECTOR):
                        OFFSET = 0
                        while True:
                            self._driver.cdp.sleep(5)
                            job_list_elements = self._get_job_list()[OFFSET:]
                            RESULT = len(job_list_elements)
                            if RESULT == 0:
                                break
                            self._logger.info(f"Total de resultados encontrados: {RESULT}")
                            for index, job_element in enumerate(job_list_elements, start=1):
                                JOB_ID = job_element.get_attribute("data-id")
                                job_element.click()
                                # await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                if not await self._job_exists(JOB_ID):
                                    job = InfoJobJob(id=JOB_ID)
                                    job.url = f"https://www.infojobs.com.br{job_element.get_attribute('data-href')}"
                                    posted_at = job_element.query_selector("div.d-flex > div.mr-8 > div:nth-child(1) > div")
                                    posted_at = posted_at.get_attribute("data-value")
                                    posted_at = datetime.strptime(posted_at, "%Y/%m/%d %H:%M:%S")
                                    job.posted_at = posted_at
                                    self._get_job_data(job)
                                    if self._filter_job(job):
                                        self._append_job(job)
                                        self._logger.info(f"[{index} de {RESULT}] {job.title}: {job.url}")
                                    else:
                                        self._logger.info(f"[{index} de {RESULT}] Job de ID {JOB_ID} foi descartado")
                                else:
                                    self._logger.info(f"[{index} de {RESULT}] Job de ID {JOB_ID} já foi extraído")
                            await self._save_jobs()
                            self._driver.cdp.scroll_to_bottom()
                            self._logger.debug("Carregando mais vagas...")
                            OFFSET += RESULT
                    else:
                        self._logger.debug(f"Nenhum resultado encontrado para essa pesquisa")
        except Exception as err:
            self._logger.error(err)
            await self._save_jobs()
        finally:
            # self._captcha_task.cancel()
            # await self._captcha_task
            pass

    async def _login(self, timeout: int = 30):
        """Realiza o login com autenticação de dois fatores.

        Args:
            timeout: Tempo máximo de espera para inserção do código (em segundos).

        Raises:
            TimeoutError: Se o tempo limite for excedido.
            ValueError: Se o código for inválido.
        """
        # Inicia o fluxo de login
        self._driver.cdp.click("//*[@class='css-7dcbld eu4oa1w0']//a")
        # Preenche o email
        EMAIL_INPUT_SELECTOR = "//input[@type='email']"
        BUTTON_SELECTOR = "//*[@id='emailform']/button"
        self._driver.cdp.type(EMAIL_INPUT_SELECTOR, f"{self._username}\n")
        self._driver.cdp.sleep(10)
        self._driver.cdp.click(BUTTON_SELECTOR)
        # Aguarda o campo de código
        CODE_INPUT_SELECTOR = "//*[@id='passcode-input']"
        if not self._driver.cdp.wait_for_element_visible(CODE_INPUT_SELECTOR, timeout=10):
            raise TimeoutError("Campo de código não apareceu após 10 segundos")
        # Processo de validação do código
        async with self._captcha_condition:
            await self._captcha_condition.wait_for(lambda: not self._captcha_active)
            self._logger.info(f"Código enviado para: {self._username} | Timeout: {timeout}s")
            code = await self._get_user_code_async(timeout)
            await self._submit_verification_code(CODE_INPUT_SELECTOR, code)
            # Verifica se o login foi bem sucedido
            if await self._is_login_successful():
                self._logged = True
            else:
                raise ValueError("Falha no login - código inválido ou tempo excedido")

    # TODO: Ainda não foi testado!
    async def _get_user_code_async(self, timeout: int):
        """Obtém o código de verificação do usuário via CLI de forma assíncrona com timeout.
        Args:
            timeout: Tempo máximo de espera em segundos.
        Returns:
            O código de 6 dígitos digitado pelo usuário.
        Raises:
            TimeoutError: Se o usuário não inserir o código a tempo.
        """
        loop = asyncio.get_running_loop()
        start_time = time()
        while (time() - start_time) <= timeout:
            try:
                # Usamos wait_for para não bloquear indefinidamente
                code = await asyncio.wait_for(
                    loop.run_in_executor(None, input, "Digite o código de 6 dígitos: "),
                    timeout=max(1, timeout - (time() - start_time)),
                )  # Tempo restante
                if code and code.isdigit() and len(code) == 6:
                    return code
                print("Código inválido! Deve conter exatamente 6 dígitos numéricos")
            except asyncio.TimeoutError:
                # Se o usuário não digitar nada no tempo restante
                continue
        raise TimeoutError("Tempo para inserção do código expirado")

    # TODO: Ainda não foi testado!
    async def _submit_verification_code(self, input_selector: str, code: str):
        """Submete o código de verificação."""
        BUTTON_SELECTOR = "//*[@id='passpage-container']/main/div/div/div[2]/div/button[1]"
        self._driver.cdp.type(input_selector, code)
        self._driver.cdp.click(BUTTON_SELECTOR)
        await asyncio.sleep(2)  # Aguarda possível redirecionamento

    # TODO: Ainda não foi testado!
    async def _is_login_successful(self):
        """Verifica se o login foi bem sucedido."""
        return not self._driver.cdp.is_element_present("//*[@class='css-1un0a8q e1wnkr790']")

    def _close_cookie_popup(self):
        BUTTON_COOKIE_LEARN_MORE_ID = "//*[@id='didomi-notice-learn-more-button']"
        BUTTON_COOKIE_REJECT_ID = "//*[@id='btn-toggle-disagree']"
        self._logger.debug(f"Aguardando popup de cookies...")
        try:
            self._driver.cdp.wait_for_element_visible(BUTTON_COOKIE_LEARN_MORE_ID, timeout=15)
        except:
            self._logger.debug(f"Popup não encontrado")
            return
        self._driver.cdp.click(BUTTON_COOKIE_LEARN_MORE_ID)
        self._driver.cdp.wait_for_element_visible(BUTTON_COOKIE_LEARN_MORE_ID, timeout=15)
        self._driver.cdp.click(BUTTON_COOKIE_REJECT_ID)
        self._logger.debug(f"Rejeitando cookies...")

    def _search_job(self, search: JobSearch):
        job = re.sub(r"\s+", "+", search.job)
        if search.location is not None:
            location = normalize_string(search.location).lower()
            if "-" in location:
                estado, uf = [*map(lambda s: re.sub(r"\s+", " ", s).strip(), location.rsplit("-", 1))]
                estado = "-".join([*filter(lambda x: x != "de", estado.split(" "))])
                location = f"{estado},-{uf}"
            else:
                location = re.sub(r"\s+", "-", location.strip())
            url = f"https://www.infojobs.com.br/empregos-em-{location}.aspx?palabra={job}"
        else:
            url = f"https://www.infojobs.com.br/empregos.aspx?palabra={job}"
        self._driver.cdp.get(url)

    def _get_pages(self):
        SELECTOR_PAGINATION = "//*[@id='jobsearch-JapanPage']//nav//li/a"
        if self._driver.cdp.is_element_present(SELECTOR_PAGINATION):
            elements = self._driver.cdp.find_elements(SELECTOR_PAGINATION)
            return elements

    def _next_page(self):
        elements = self._get_pages()
        for i, el in enumerate(elements):
            if el.get_attribute("aria-current") == "page":
                if i < (len(elements) - 1):
                    return elements[i + 1]

    def _get_job_list(self):
        SELECTOR_JOB_LIST = "/html/body/main/div[2]/form/div/div[1]/div[2]/div/div/div"
        return [
            *filter(
                lambda el: el.get_attribute("id") is not None and el.get_attribute("id").startswith("vacancy"),
                self._driver.cdp.find_elements(SELECTOR_JOB_LIST, timeout=15),
            )
        ]

    def _get_job_data(self, job: InfoJobJob):
        SELECTORS = {
            "title": "//*[@id='VacancyHeader']/div[1]/div/h2",
            "company": "//*[@id='VacancyHeader']/div[1]/div/div[1]/div[1]/a",
            "company_confidential": "//*[@id='VacancyHeader']/div[1]/div/div[1]/div",
            "location": "//*[@id='VacancyHeader']/div[1]/div[1]/div[2]/div[1]",
            "salary": "//*[@id='VacancyHeader']/div[1]/div[1]/div[2]/div[2]",
            "job_type": "//*[@id='VacancyHeader']/div[1]/div/div[2]/div[3]",
            "description": "//*[@id='vacancylistDetail']/div[2]/p[1]",
            "details": "//*[@id='vacancylistDetail']/div[2]/p",
            "details2": "//*[@id='vacancylistDetail']/div[2]/div",
        }
        TIMEOUT = 15

        job.title = self._driver.cdp.find_element(SELECTORS["title"], timeout=TIMEOUT).text_fragment
        if self._driver.cdp.is_element_present(SELECTORS["company"]):
            job.company = self._driver.cdp.find_element(SELECTORS["company"], timeout=TIMEOUT).text
        else:
            text = self._driver.cdp.find_element(SELECTORS["company_confidential"], timeout=TIMEOUT).text
            text = re.sub(r"\s+", " ", text).strip()
            assert text.upper() == "EMPRESA CONFIDENCIAL"
            job.company = self._driver.cdp.find_element(SELECTORS["company_confidential"], timeout=TIMEOUT).text

        job.location = self._driver.cdp.find_element(SELECTORS["location"], timeout=TIMEOUT).text_fragment
        job.description = self._driver.cdp.find_element(SELECTORS["description"], timeout=TIMEOUT).text

        # Tipos de jobs: Home office, hibrido, presencial
        type = self._driver.cdp.find_element(SELECTORS["job_type"], timeout=TIMEOUT).text_fragment
        assert normalize_string(type).lower() in ["home office", "hibrido", "presencial"]
        job.type = type

        job.salary = self._driver.cdp.find_element(SELECTORS["salary"], timeout=TIMEOUT).text
        job.salary = re.sub(r"\s+", " ", job.salary).strip()

        details = dict()
        elements = self._driver.cdp.find_elements(SELECTORS["details"], timeout=TIMEOUT)
        if len(elements) > 1:
            for element in elements[1:]:
                key, value = [*map(lambda e: e.strip(), element.text.split(":", 1))]
                details[key] = value
        elements = self._driver.cdp.find_elements(SELECTORS["details2"], timeout=TIMEOUT)
        if len(elements) > 0 and len(elements) % 2 == 0:
            for index in range(0, len(elements), 2):
                element = elements[index]
                SELECTOR_DETAILS_VALUE = f"//*[@id='vacancylistDetail']/div[2]/div[{index + 2}]"
                key = element.text_fragment
                if key == "Habilidades":
                    values = self._driver.cdp.find_elements(f"{SELECTOR_DETAILS_VALUE}//span", timeout=TIMEOUT)
                    values = [*map(lambda e: e.text.strip(), values)]
                    details[key] = values
                    continue
                values = self._driver.cdp.find_elements(f"{SELECTOR_DETAILS_VALUE}//ul/li", timeout=TIMEOUT)
                values = [*map(lambda e: e.text.strip(), values)]
                if all(":" in v for v in values):
                    for value in values:
                        k, v = [*map(lambda e: e.strip(), value.split(":", 1))]
                        details[key] = {k: v}
                    continue
                details[key] = values
        job.details = details
        return job
