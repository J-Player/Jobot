import asyncio
import re
from dataclasses import dataclass

from modules.bot.linkedin.linkedin_job import LinkedinJob
from modules.core import JobBot, JobBotOptions
from modules.core.job_bot import JobFilterKey, JobSearch


class LinkedinJobFilterKey(JobFilterKey):
    TITLE = "title"
    DESCRIPTION = "description"
    LOCATION = "location"
    COMPANY = "company"


@dataclass
class LinkedinBotOptions(JobBotOptions):
    pass


@dataclass
class LinkedinSearch(JobSearch):
    pass


class LinkedinBot(JobBot):

    def __init__(self, options: LinkedinBotOptions):
        super().__init__(options)
        self._logged = False

    async def _setup(self):
        url = "https://www.linkedin.com/jobs/search"
        self._driver.uc_activate_cdp_mode(url)
        if self._username and self._password:
            self._logged = await self._login()
        else:
            await self._close_popup()

    async def _start(self):
        try:
            # CAPTCHA_SELECTOR = ""  # TODO: Descobrir o selector do linkedin para captcha
            # self._captcha_task = asyncio.create_task(self._captcha(CAPTCHA_SELECTOR))
            WRAPPER_SELECTOR = "//*[@class='two-pane-serp-page__detail-view']"
            if self._logged:
                WRAPPER_SELECTOR = "//*[contains(@class, 'jobs-details__main-content')]"
            for index, search in enumerate(self._searches, start=1):
                self._driver.cdp.sleep(5)
                self._search_job(search)
                self._logger.info(f"[{index} de {len(self._searches)}] Pesquisando vagas: {search.job} | Localização: {search.location}")
                async with self._captcha_condition:
                    await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                self._driver.cdp.sleep(5)
                if self._driver.cdp.is_element_present(WRAPPER_SELECTOR):
                    contador = 0
                    max_page = 5
                    current_page = 1
                    while True:
                        self._driver.cdp.sleep(10)
                        job_list_elements = self._get_job_list()
                        RESULT = len(job_list_elements)
                        if RESULT > 0:
                            self._logger.info(f"Página: {current_page} | Total de resultados encontrados: {RESULT}")
                            for i, job_element in enumerate(job_list_elements, start=1):
                                await asyncio.sleep(1.5)
                                async with self._captcha_condition:
                                    await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                job_element.click()
                                await asyncio.sleep(1)
                                async with self._captcha_condition:
                                    await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                CURRENT_URL = self._driver.cdp.get_current_url()
                                URL_PATTERN = r"currentJobId=(\d+)"
                                JOB_ID = re.search(URL_PATTERN, CURRENT_URL)[1]
                                if not await self._job_exists(JOB_ID):
                                    job = LinkedinJob(id=JOB_ID)
                                    job.url = f"https://www.linkedin.com/jobs/view/{JOB_ID}"
                                    if self._get_job_data(job) is None:
                                        self._logger.info(f"[{i} de {RESULT}] Job de ID {JOB_ID} expirou")
                                    elif self._filter_job(job):
                                        self._append_job(job)
                                        self._logger.info(f"[{i} de {RESULT}] {job.title}: {job.url}")
                                    else:
                                        self._logger.info(f"[{i} de {RESULT}] Job de ID {JOB_ID} foi descartado")
                                else:
                                    self._logger.info(f"[{i} de {RESULT}] Job de ID {JOB_ID} já foi extraído")
                            await self._save_jobs()
                        elif RESULT == 0:
                            self._logger.debug("Nenhum resultado encontrado para esta pesquisa")
                            break
                        if self._logged:
                            contador += 1
                            btn_next = self._next_page()
                            if btn_next is None:
                                break
                            if contador >= max_page:
                                self._logger.debug("LIMITE DE PÁGINAS ATINGIDO.")
                                break
                            btn_next.click()
                            current_page += 1
                        else:
                            break
        except Exception as err:
            self._logger.error(err)
            await self._save_jobs()
            raise err
        # finally:
            # if self._captcha_task:
            #     self._captcha_task.cancel()
            #     try:
            #         await self._captcha_task
            #     except asyncio.CancelledError:
            #         pass

    def _next_page(self):
        NEXT_BUTTON_SELECTOR = "//*[@id='main-content']/section[2]/button"
        if self._logged:
            NEXT_BUTTON_SELECTOR = "//*[@id='jobs-search-results-footer']/div[2]/button"
        if self._driver.cdp.is_element_present(NEXT_BUTTON_SELECTOR):
            return self._driver.cdp.find_element(NEXT_BUTTON_SELECTOR)

    async def _login(self):
        try:
            MODAL_SELECTOR = "//*[@id='base-contextual-sign-in-modal']"
            LOGIN_BUTTON_POPUP_SELECTOR = f"{MODAL_SELECTOR}//div[@class='sign-in-modal']/button"
            LOGIN_BUTTON_2 = f"/html/body/div[2]/a[1]"
            if self._driver.cdp.is_element_present(LOGIN_BUTTON_POPUP_SELECTOR):
                INPUT_USERNAME_SELECTOR = "//*[@id='base-sign-in-modal_session_key']"
                INPUT_PASSWORD_SELECTOR = "//*[@id='base-sign-in-modal_session_password']"
                BUTTON_SELECTOR = "//*[@id='base-sign-in-modal']/div/section/div/div/form/div[2]/button"
                self._driver.cdp.click(LOGIN_BUTTON_POPUP_SELECTOR)
            else:
                INPUT_USERNAME_SELECTOR = "//*[@id='username']"
                INPUT_PASSWORD_SELECTOR = "//*[@id='password']"
                BUTTON_SELECTOR = "//*[@id='organic-div']/form/div[4]/button"
                self._driver.cdp.click(LOGIN_BUTTON_2)
            self._logger.info("Inicializando processo de login no linkedin...")
            self._driver.cdp.type(INPUT_USERNAME_SELECTOR, self._username)
            self._driver.cdp.type(INPUT_PASSWORD_SELECTOR, self._password)
            self._driver.cdp.click(BUTTON_SELECTOR)
            self._logger.info("Login realizado com sucesso!")
            return True  # TODO: Usar um elemento para determina se o login foi bem sucedido
        except Exception as err:
            self._logger.error(f"Erro durante o login: {err}")
            raise err

    async def _close_popup(self):
        CLOSE_BUTTON_POPUP_SELECTOR = "//*[@id='base-contextual-sign-in-modal']/div/section/button"
        self._logger.debug(f"Aguardando popup inicial...")
        if self._driver.is_element_present(CLOSE_BUTTON_POPUP_SELECTOR):
            self._driver.cdp.click(CLOSE_BUTTON_POPUP_SELECTOR)
            self._logger.debug(f"Popup fechado com sucesso!")
            return
        self._logger.debug(f"Popup não encontrado")

    def _search_job(self, search: JobSearch):
        INPUT_JOB_ID = "#job-search-bar-keywords"
        INPUT_LOCATION_ID = "#job-search-bar-location"
        BUTTON_SEARCH_XPATH = "//*[@id='jobs-search-panel']/form/button"
        if self._logged:
            INPUT_JOB_ID = "//input[contains(@id, 'jobs-search-box-keyword')]"
            INPUT_LOCATION_ID = "//input[contains(@id, 'jobs-search-box-location')]"
            BUTTON_SEARCH_XPATH = "//*[@id='global-nav-search']/div/div[2]/button[1]"
        self._driver.cdp.type(INPUT_JOB_ID, search.job)
        self._driver.cdp.type(INPUT_LOCATION_ID, search.location)
        self._driver.cdp.click(BUTTON_SEARCH_XPATH)  # FIXME: Esse botão não tem efeito nenhum...

    def _get_job_list(self):
        SELECTORS = {
            "container": "//*[@id='main-content']/section[2]",
            "job_list": "//*[@class='jobs-search__results-list']//li/div",
        }
        if self._logged:
            SELECTORS["container"] = "//*[@id='main']/div/div[2]/div[1]/div"
            SELECTORS["job_list"] = SELECTORS["container"] + "/ul/li/div/div"
            SELECTORS["footer"] = "//*[@id='jobs-search-results-footer']"
            sort_by_date = "sortBy=DD"
            url = self._driver.cdp.get_current_url()
            if sort_by_date not in url:
                url = "&".join([self._driver.cdp.get_current_url(), sort_by_date])
                self._driver.cdp.get(url)
                self._driver.cdp.sleep(3)
            footer = self._driver.cdp.find_element(SELECTORS["footer"])
            footer.scroll_into_view()
            self._driver.cdp.sleep(3)
        last_count = 0
        stable_count = 0
        while True:
            elements = self._driver.cdp.find_elements(SELECTORS["job_list"], timeout=15)
            current_count = len(elements)
            if current_count == last_count:
                stable_count += 1
                if stable_count >= 3:
                    break
            else:
                stable_count = 0
                self._logger.debug(f"Carregando jobs... (jobs: {current_count})")
            if elements:
                for el in elements:
                    el.scroll_into_view()
            self._driver.cdp.sleep(3)
            last_count = current_count
        if elements:
            elements[0].scroll_into_view()
        return elements

    def _get_job_data(self, job: LinkedinJob, timeout=15):
        WRAPPER = "//*[contains(@class, 'details-pane__content')]"
        SELECTORS = {
            "title": f"{WRAPPER}//*[contains(@class, 'topcard__title')]",
            "company": f"{WRAPPER}//*[@class='topcard__flavor-row'][1]/span[1]",
            "location": f"{WRAPPER}//*[@class='topcard__flavor-row'][1]/span[2]",
            "button": f"{WRAPPER}//button[contains(@class, 'sign-up')]",
            "button_easy_application": f"{WRAPPER}//button[contains(@class, 'apply')]",
            "description": f"{WRAPPER}//*[contains(@class, 'description__text')]/section/div",
            "details": f"{WRAPPER}//*[@class='description__job-criteria-list']/li",
        }
        if self._logged:
            WRAPPER = "//*[contains(@class, 'jobs-details__main-content')]"
            SELECTORS["title"] = f"{WRAPPER}//h1/a"
            SELECTORS["company"] = f"{WRAPPER}/div[1]/div/div[1]/div/div[1]/div[1]/div"
            SELECTORS["location"] = f"{WRAPPER}/div[1]/div/div[1]/div/div[3]/div/span/span[1]"
            SELECTORS["button"] = f"{WRAPPER}//*[@id='jobs-apply-button-id']"
            SELECTORS["description"] = f"{WRAPPER}//*[@id='job-details']/div"
            SELECTORS["details"] = f"{WRAPPER}//ul/li//span[contains(@class, 'ui-label')]/span"
            SELECTORS["alert"] = f"{WRAPPER}//span[contains(@class, '__message')]"
        if self._driver.cdp.is_element_present(SELECTORS["button"]):
            BUTTON_ELEMENT = self._driver.cdp.find_element(SELECTORS["button"], timeout)
            job.easy_application = "simplificada" in BUTTON_ELEMENT.text
        elif self._driver.cdp.is_element_present(SELECTORS["button_easy_application"]):
            BUTTON_ELEMENT = self._driver.cdp.find_element(SELECTORS["button_easy_application"], timeout)
            job.easy_application = BUTTON_ELEMENT is not None
        else:
            self._driver.cdp.assert_element_present(SELECTORS["alert"], timeout)
            return None
        job.title = self._driver.cdp.find_element(SELECTORS["title"], timeout).text
        job.company = self._driver.cdp.find_element(SELECTORS["company"], timeout).text
        job.location = self._driver.cdp.find_element(SELECTORS["location"], timeout).text
        job.description = self._driver.cdp.find_element(SELECTORS["description"], timeout).text
        if self._driver.cdp.is_element_present(SELECTORS["details"]):
            details = dict()
            sections = self._driver.cdp.find_elements(SELECTORS["details"], timeout)
            for index in range(0, len(sections), 2 if self._logged else 1):
                if self._logged:
                    # TODO: Descobri o formato correto dos detalhes quando conectado
                    HIDDEN_VALUE = "Corresponde às suas preferências de vaga e o "
                    value = sections[index].text
                    key = sections[index + 1].text_fragment
                    key = key[len(HIDDEN_VALUE) : str(key).index(" é")]
                else:
                    key = self._driver.cdp.find_element(f"{SELECTORS['details']}[{index + 1}]/h3").text
                    value = self._driver.cdp.find_element(f"{SELECTORS['details']}[{index + 1}]/span").text
                details[key] = value
            job.details = details
        return job
