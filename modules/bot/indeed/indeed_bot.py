import asyncio
from time import time

from modules.bot.indeed.indeed_job import IndeedJob
from modules.core import JobBot, JobBotOptions, JobFilterKey, JobSearch


class IndeedJobFilterKey(JobFilterKey):
    TITLE = "title"
    DESCRIPTION = "description"
    LOCATION = "location"
    COMPANY = "company"


class IndeedBotOptions(JobBotOptions):
    pass


class IndeedSearch(JobSearch):
    pass


class IndeedBot(JobBot):

    def __init__(self, options: IndeedBotOptions):
        super().__init__(options)

    async def _setup(self):
        await super()._setup()
        url = "https://br.indeed.com"
        self._driver.uc_activate_cdp_mode(url)
        self._close_cookie_popup()
        if self._username and self._password:
            await self._login()

    async def _start(self):
        try:
            CAPTCHA_SELECTOR = "#JnAv0 div div"
            WRAPPER_SELECTOR = "//*[@id='jobsearch-ViewjobPaneWrapper']"
            self._captcha_task = asyncio.create_task(self._captcha(CAPTCHA_SELECTOR))
            await asyncio.sleep(1)  # Pequeno delay para permitir a criação da task
            async with self._captcha_condition:
                self._logger.debug(f"Total de pesquisas para realizar: {len(self._searches)}")
                for index, search in enumerate(self._searches, start=1):
                    self._driver.cdp.sleep(5)  # Aguarda a lista carregar...
                    self._search_job(search)
                    self._logger.info(f"[{index} de {len(self._searches)}] Pesquisando vagas: {search.job} | Localização: {search.location}.")
                    await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                    self._driver.cdp.sleep(5)  # Aguarda a lista carregar...
                    current_page = 1
                    if self._driver.cdp.is_element_present(WRAPPER_SELECTOR):
                        while True:
                            TOTAL_PAGES = self._get_pages()
                            TOTAL_PAGES = len(TOTAL_PAGES) if TOTAL_PAGES else 1
                            self._driver.cdp.sleep(5)
                            job_list_elements = self._get_job_list()
                            RESULT = len(job_list_elements)
                            self._logger.info(f"Página: {current_page} | Total de resultados encontrados: {RESULT}")
                            for index, job_element in enumerate(job_list_elements, start=1):
                                JOB_ID = job_element.get_attribute("id").split("_")[1]  # TODO: Verificar se problema dos ~1800 segundos foi corrigido
                                job_element.click()
                                await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                if not await self._job_exists(JOB_ID):
                                    job = IndeedJob(id=JOB_ID)
                                    job.url = f"https://br.indeed.com/viewjob?jk={JOB_ID}"
                                    self._get_job_data(job)
                                    if self._filter_job(job):
                                        self._append_job(job)
                                        self._logger.info(f"[{index} de {RESULT}] {job.title}: {job.url}")
                                    else:
                                        self._logger.info(f"[{index} de {RESULT}] Job de ID {JOB_ID} foi descartado")
                                else:
                                    self._logger.info(f"[{index} de {RESULT}] Job de ID {JOB_ID} já foi extraído")
                            await self._save_jobs()
                            next_button = self._next_page()
                            if next_button is None:
                                break
                            next_button.click()
                            current_page += 1
                    else:
                        self._logger.debug(f"Nenhum resultado encontrado para essa pesquisa")
        except Exception as err:
            self._logger.error(err)
            await self._save_jobs()
            raise err
        finally:
            self._captcha_task.cancel()
            await self._captcha_task

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
        BUTTON_COOKIE_REJECT_ID = "#onetrust-reject-all-handler"
        self._logger.debug(f"Aguardando popup de cookies...")
        if self._driver.is_element_present(BUTTON_COOKIE_REJECT_ID):
            self._driver.cdp.click(BUTTON_COOKIE_REJECT_ID)
            self._logger.debug(f"Popup de cookies fechado")
            return
        self._logger.debug(f"Popup não encontrado")

    def _search_job(self, search: JobSearch):
        url = f"https://br.indeed.com/jobs?q={search.job}"
        if search.location is not None:
            url += f"&l={search.location}"
        self._driver.cdp.get(url)

    def _get_pages(self):
        SELECTOR_PAGINATION = "//*[@id='jobsearch-JapanPage']//nav//li/a"
        if self._driver.cdp.is_element_present(SELECTOR_PAGINATION):
            elements = self._driver.cdp.find_elements(SELECTOR_PAGINATION)
            return elements
        else:
            return []

    def _next_page(self):
        elements = self._get_pages()
        for i, el in enumerate(elements):
            if el.get_attribute("aria-current") == "page":
                if i < (len(elements) - 1):
                    return elements[i + 1]

    def _get_job_list(self):
        SELECTOR_JOB_LIST = "//*[@id='mosaic-jobResults']//ul//a"
        return [
            *filter(
                lambda el: el.get_attribute("id") is not None and el.get_attribute("id").startswith("job_"),
                self._driver.cdp.find_elements(SELECTOR_JOB_LIST, timeout=15),
            )
        ]

    def _get_job_data(self, job: IndeedJob):
        SELECTORS = {
            "title": "//*[contains(@class, 'jobsearch-HeaderContainer')]//h2/span",
            "location": "//*[contains(@data-testid, 'companyLocation')]",
            "company": "//*[@data-company-name]",
            "button": '//*[@id="jobsearch-ViewJobButtons-container"]//button',
            "details": "//*[@id='jobDetailsSection']",
            "benefits": "//*[@id='benefits']//li",
            "description": "//*[@id='jobDescriptionText']",
        }
        TIMEOUT = 15
        BUTTON_ELEMENT = self._driver.cdp.find_element(SELECTORS["button"])
        job.easy_application = "indeedApplyButton" == BUTTON_ELEMENT.get_attribute("id")
        job.title = self._driver.cdp.find_element(SELECTORS["title"], timeout=TIMEOUT).text_fragment
        job.company = self._driver.cdp.find_element(SELECTORS["company"], timeout=TIMEOUT).text
        job.location = self._driver.cdp.find_element(SELECTORS["location"], timeout=TIMEOUT).text
        job.description = self._driver.cdp.find_element(SELECTORS["description"], timeout=TIMEOUT).text
        if self._driver.cdp.is_element_present(SELECTORS["details"]):
            details = dict()
            sections = self._driver.cdp.find_elements(SELECTORS["details"] + '//div[@role="group"]', timeout=TIMEOUT)
            for section in sections:
                key = section.get_attribute("aria-label")
                SELECTOR_SECTION = f"{SELECTORS["details"]}//div[@aria-label='{key}']"
                values = self._driver.cdp.find_elements(SELECTOR_SECTION + "//ul/li//span")
                details[key] = [*map(lambda v: v.text, values)]
            job.details = details
        if self._driver.cdp.is_element_present(SELECTORS["benefits"]):
            BENEFIT_ELEMENTS = self._driver.cdp.find_elements(SELECTORS["benefits"])
            job.benefits = [*map(lambda s: s.text, BENEFIT_ELEMENTS)]
        return job
