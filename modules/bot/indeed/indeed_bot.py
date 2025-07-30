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
        if self._username:
            await self._login()

    async def _start(self):
        try:
            CAPTCHA_SELECTOR = "#ovEdv1 div div"
            WRAPPER_SELECTOR = "//*[@id='jobsearch-ViewjobPaneWrapper']"
            self._captcha_task = asyncio.create_task(self._captcha(CAPTCHA_SELECTOR))
            await asyncio.sleep(1)  # Pequeno delay para permitir a criação da task
            async with self._captcha_condition:
                self._logger.debug(f"Total de pesquisas para realizar: {len(self._searches)}")
                for index, search in enumerate(self._searches, start=1):
                    await asyncio.sleep(5)  # Aguarda a lista carregar...
                    self._search_job(search)
                    self._logger.info(f"[{index} de {len(self._searches)}] Pesquisando vagas: {search.job} | Localização: {search.location}.")
                    await asyncio.sleep(3)
                    await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                    current_page = 1
                    if self._driver.cdp.is_element_present(WRAPPER_SELECTOR):
                        retry = True
                        while True:
                            await asyncio.sleep(5)
                            await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                            job_list_elements = self._get_job_list()
                            RESULT = len(job_list_elements)
                            self._logger.info(f"Página: {current_page} | Total de resultados encontrados: {RESULT}")
                            try:
                                for index, job_element in enumerate(job_list_elements, start=1):
                                    await asyncio.sleep(1)
                                    await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                    JOB_ID = job_element.get_attribute("id").split("_")[1]  # TODO: Verificar se problema dos ~1800 segundos foi corrigido
                                    if not await self._job_exists(JOB_ID):
                                        job = IndeedJob(id=JOB_ID)
                                        job.url = f"https://br.indeed.com/viewjob?jk={JOB_ID}"
                                        job_element.click()
                                        await asyncio.sleep(1)
                                        await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                        if not await self._get_job_data(job):
                                            retry = False
                                            raise Exception(f"Erro ao extrair dados do job de ID {JOB_ID}")
                                        if self._filter_job(job):
                                            self._append_job(job)
                                            self._logger.info(f"[{index} de {RESULT}] {job.title}: {job.url}")
                                        else:
                                            self._logger.info(f"[{index} de {RESULT}] Job de ID {JOB_ID} foi descartado")
                                        self._driver.cdp.go_back()
                                    else:
                                        self._logger.info(f"[{index} de {RESULT}] Job de ID {JOB_ID} já foi extraído")
                            except Exception as err:
                                if retry:
                                    retry = False
                                    self._logger.warning(f"Erro ao extrair jobs da página {current_page}: {err}")
                                    self._logger.warning(f"Realizando uma última tentativa...")
                                    continue
                                self._logger.error(f"Não foi possivel extrair jobs da página {current_page}: {err}")
                                raise err
                            await self._save_jobs()
                            next_button = self._next_page()
                            if next_button is None:
                                break
                            next_button.click()
                            retry = True
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
        LOGIN_BUTTON_SELECTOR = "//*[@id='gnav-main-container']/div/div/div[2]/div[2]/div[2]/a"
        EMAIL_INPUT_SELECTOR = "//input[@type='email']"
        CODE_INPUT_SELECTOR = "//*[@id='passcode-input']"
        BUTTON_SUBMIT_SELECTOR = "//*[@id='emailform']/button"
        ALERT_SELECTOR = "//*[@id='label-passcode-input-error']/div/div"
        try:
            async with self._captcha_condition:
                self._driver.cdp.click(LOGIN_BUTTON_SELECTOR)
                await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                self._driver.cdp.type(EMAIL_INPUT_SELECTOR, f"{self._username}\n")
                await asyncio.sleep(10)

                if self._driver.cdp.is_element_present(ALERT_SELECTOR):
                    text = (self._driver.cdp.find_element(ALERT_SELECTOR).text).strip()
                    if len(text) > 0:
                        url = self._driver.cdp.get_current_url()
                        self._logger.warning(f"Aviso detectado na página {url}: {text}")
                        raise Exception(text)

                if self._driver.cdp.is_element_present(BUTTON_SUBMIT_SELECTOR):
                    self._driver.cdp.click(BUTTON_SUBMIT_SELECTOR)

                await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                self._logger.info(f"Código enviado para o e-mail: {self._username} | Timeout: {timeout}s")
                code = await self._get_user_code_async(timeout)
                await self._submit_verification_code(CODE_INPUT_SELECTOR, code)
                if await self._is_login_successful():
                    self._logged = True
                else:
                    raise ValueError("Falha no login - código inválido ou tempo excedido")
        except Exception as err:
            self._logger.error(err)
            raise err

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

    async def _submit_verification_code(self, input_selector: str, code: str):
        """Submete o código de verificação."""
        BUTTON_SELECTOR = "//*[@id='passpage-container']/main/div/div/div[2]/div/button[1]"
        self._driver.cdp.type(input_selector, code)
        self._driver.cdp.click(BUTTON_SELECTOR)
        await asyncio.sleep(2)  # Aguarda possível redirecionamento

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
        self._driver.cdp.get(f"{url}&sort=date")

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

    async def _get_job_data(self, job: IndeedJob, backoff: int = 1):
        try:
            SELECTORS = {
                "title": "//*[@id='jobsearch-ViewjobPaneWrapper']//h2/span",
                "location": [
                    "//*[@id='jobsearch-ViewjobPaneWrapper']//div[contains(@data-testid, 'company')]/div",
                    "//*[@id='jobsearch-ViewjobPaneWrapper']/div[2]/div[3]/div/div/div[1]/div[3]/div[1]/div[2]/div/div/div/div",
                ],
                "company": "//*[@data-company-name]",
                "button": '//*[@id="jobsearch-ViewJobButtons-container"]//button',
                "details": "//*[@id='jobDetailsSection']",
                "benefits": "//*[@id='benefits']//li",
                "description": "//*[@id='jobDescriptionText']",
            }
            TIMEOUT = 15
            BUTTON_ELEMENT = self._driver.cdp.find_element(SELECTORS["button"], timeout=TIMEOUT)
            assert job.id in self._driver.cdp.get_current_url()
            job.easy_application = "indeedApplyButton" == BUTTON_ELEMENT.get_attribute("id")
            job.title = self._driver.cdp.find_element(SELECTORS["title"], timeout=TIMEOUT).text_fragment
            job.company = self._driver.cdp.find_element(SELECTORS["company"], timeout=TIMEOUT).text
            if self._driver.cdp.is_element_present(SELECTORS["location"][0]):
                elements_location = self._driver.cdp.find_elements(SELECTORS["location"][0], timeout=TIMEOUT)
            else:
                elements_location = self._driver.cdp.find_elements(SELECTORS["location"][1], timeout=TIMEOUT)
            job.location = " - ".join([el.text for el in elements_location[1:] if len(el.text) > 0])
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
            return True
        except Exception as err:
            EXPONENCIAL_BACKOFF = 5
            MAX_RETRIES = 3
            self._logger.warning(f"Erro durante a coleta de dados do job: {job.id}")
            if backoff < MAX_RETRIES:
                self._logger.warning(f"Tentando novamente em {EXPONENCIAL_BACKOFF ** backoff} segundos... (tentativas restantes: {MAX_RETRIES - backoff})")
                await asyncio.sleep(EXPONENCIAL_BACKOFF ** backoff)
                await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                return await self._get_job_data(job, backoff + 1)
            self._logger.error(f"Não foi possivel coletar os dados do job: {job.id} | Erro: {err}")
            return False
