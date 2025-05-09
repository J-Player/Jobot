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
            async with self._captcha_condition:
                for index, search in enumerate(self._searches, start=1):
                    self._driver.cdp.sleep(5)
                    self._search_job(search)
                    self._logger.info(
                        f"[{index} de {len(self._searches)}] Pesquisando vagas: {search.job} | Localização: {search.location}"
                    )
                    # await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                    self._driver.cdp.sleep(5)
                    if self._driver.cdp.is_element_present(WRAPPER_SELECTOR):
                        contador = 0
                        max_page = 5
                        current_page = 1
                        while True:
                            self._driver.cdp.sleep(10)
                            job_list_elements = self._get_job_list()
                            RESULT = len(job_list_elements)
                            self._logger.info(f"Página: {current_page} | Total de resultados encontrados: {RESULT}")
                            if RESULT > 0:
                                self._logger.debug(f"Total de vagas encontradas: {RESULT}")
                                for i, job_element in enumerate(job_list_elements, start=1):
                                    job_element.click()
                                    # await self._captcha_condition.wait_for(lambda: not self._captcha_active)
                                    CURRENT_URL = self._driver.cdp.get_current_url()
                                    URL_PATTERN = r"currentJobId=(\d+)"
                                    JOB_ID = re.search(URL_PATTERN, CURRENT_URL)[1]
                                    if not await self._job_exists(JOB_ID):
                                        job = LinkedinJob(id=JOB_ID)
                                        job.url = f"https://www.linkedin.com/jobs/view/{JOB_ID}"
                                        self._get_job_data(job)
                                        if self._filter_job(job):
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
        except Exception as err:
            self._logger.error(err)
            await self._save_jobs()
        finally:
            # self._captcha_task.cancel()
            # await self._captcha_task
            pass

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
            self._driver.cdp.click(LOGIN_BUTTON_POPUP_SELECTOR)
            INPUT_USERNAME_SELECTOR = "//*[@id='base-sign-in-modal_session_key']"
            INPUT_PASSWORD_SELECTOR = "//*[@id='base-sign-in-modal_session_password']"
            BUTTON_SELECTOR = "//*[@id='base-sign-in-modal']/div/section/div/div/form/div[2]/button"
            self._driver.cdp.type(INPUT_USERNAME_SELECTOR, self._username)
            self._driver.cdp.type(INPUT_PASSWORD_SELECTOR, self._password)
            self._driver.cdp.click(BUTTON_SELECTOR)
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
        self._driver.cdp.type(INPUT_LOCATION_ID, search.location)  # FIXME: Arruma um jeito
        self._driver.cdp.click(BUTTON_SEARCH_XPATH)  # FIXME: Esse botão não tem efeito nenhum...

    def _get_job_list(self):
        SELECTOR_CONTAINER = "//*[@id='main']/div/div[2]/div[1]/div"
        SELECTOR_JOB_LIST = f"{SELECTOR_CONTAINER}/ul//a"
        get_container = lambda: self._driver.cdp.find_element(SELECTOR_CONTAINER, timeout=15)
        LAST_HEIGHT = get_container().get_attribute("scrollHeight")
        while True:
            elements = self._driver.cdp.find_elements(SELECTOR_JOB_LIST, timeout=15)
            elements[-1].scroll_into_view()
            self._driver.cdp.sleep(1.5)
            current_height = get_container().get_attribute("scrollHeight")
            if current_height == LAST_HEIGHT:
                elements[0].scroll_into_view()
                break
            self._logger.debug(f"Carregando vagas...")
            LAST_HEIGHT = current_height
        return elements

    def _get_job_data(self, job: LinkedinJob, timeout=15):
        WRAPPER = "//*[@class='jobs-search__job-details--wrapper']"
        SELECTORS = {
            "title": f"{WRAPPER}//a[@class='topcard__link']",
            "company": f"{WRAPPER}//*[@class='topcard__flavor-row'][1]/span[1]",
            "location": f"{WRAPPER}//*[@class='topcard__flavor-row'][1]/span[2]",
            "button": f"{WRAPPER}//div/button[contains(@class, 'sign-up')]",
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
        BUTTON_ELEMENT = self._driver.cdp.find_element(SELECTORS["button"])
        job.easy_application = "simplificada" in BUTTON_ELEMENT.text
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
                    value = self._driver.cdp.find_element(f"{SELECTORS['details']}[{index + 1}]/h3").text
                    key = self._driver.cdp.find_element(f"{SELECTORS['details']}[{index + 1}]/span").text
                details[key] = value
            job.details = details
        return job
