from seleniumbase import Driver
from abc import ABC, abstractmethod
from enum import Enum
from time import time
from datetime import datetime
import asyncio
import logging
import os
import time

from modules.utils import get_logger, camel_case_split


class BotState(Enum):
    READY = 1
    RUNNING = 2
    STOPPED = 3


class Bot(ABC):

    def __init__(self):
        self.__driver = None
        self.__state = BotState.READY
        self.__options: dict = {"binary_location": os.getenv("SB_BINARY_LOCATION")}
        self._captcha_task = None
        self._captcha_active = False  # Controle de estado do captcha
        self.__captcha_condition = asyncio.Condition()
        self._logger: logging.Logger = get_logger(
            self.__class__.__name__,
            level=logging.DEBUG,
            file_name=f"./logs/{self.__class__.__name__}/{self.__class__.__name__}_{datetime.now().strftime("%d_%m_%Y")}.log",
        )

    @property
    def _captcha_condition(self):
        return self.__captcha_condition

    @property
    def _driver(self):
        return self.__driver

    @property
    def state(self):
        return self.__state

    async def _setup(self):
        pass

    async def _teardown(self):
        pass

    @abstractmethod
    async def _start(self):
        raise NotImplementedError("O método _start deve ser implementado.")

    async def start(self):
        if self.__state == BotState.READY:
            try:
                binary_location = self.__options["binary_location"]
                self.__driver = Driver(uc=True, binary_location=binary_location)
                if self.__driver is None:
                    self._logger.critical("O driver não pôde ser inicializado.")
                    return
                self.__state = BotState.RUNNING
                self._logger.debug(f"Inicializando a execução do bot...")
                START_TIME = time.time()
                await self._setup()
                await self._start()
                await self._teardown()
            except Exception as err:
                data = datetime.fromtimestamp(time.time())
                dir_name = f"./screenshots/{self.__class__.__name__}"
                os.makedirs(dir_name, exist_ok=True)
                self._driver.cdp.save_screenshot(f"{dir_name}/{data.strftime("%d_%m_%Y_%H_%M_%S")}_ERROR.png")
                self._logger.error(err)
            else:
                self._logger.debug(f"Bot executado com sucesso!")
            finally:
                self._logger.debug(f"Finalizando a execução do bot.")
                END_TIME = time.time()
                DURATION = END_TIME - START_TIME
                self._logger.debug(f"Duração total de execução: {DURATION:.2f} segundos")
                await self.stop()

    async def stop(self):
        if self.__state == BotState.RUNNING:
            self.__driver.quit()
            self.__state = BotState.STOPPED

    async def reset(self):
        if self.__state == BotState.STOPPED:
            self.__driver = None
            self.__state = BotState.READY

    async def _captcha(self, selector_captcha: str):
        try:
            self._logger.debug("▶ Task de captcha inicializada.")
            while True:
                await asyncio.sleep(0.5)  # Verificação periódica
                # Verificação mais robusta do elemento
                if not self._driver.cdp.is_element_present(selector_captcha):
                    # Garante que _captcha_active seja False quando não há captcha
                    if self._captcha_active:
                        async with self._captcha_condition:
                            self._captcha_active = False
                            self._captcha_condition.notify_all()
                    continue
                self._logger.debug("🔍 Captcha detectado! Pausando processamento...")
                # Ativação do estado de captcha
                async with self._captcha_condition:
                    self._captcha_active = True
                    self._captcha_condition.notify_all()
                # Resolução com tratamento de erro
                try:
                    await self._captcha_resolve(selector_captcha)
                except Exception as e:
                    self._logger.warning(f"⚠️ Erro ao resolver captcha: {str(e)}")
                    # Continue sem resetar _captcha_active aqui - será resetado na próxima verificação
                    continue
                # Só reseta se chegou até aqui (resolução bem-sucedida)
                async with self._captcha_condition:
                    self._captcha_active = False
                    self._logger.debug("✅ Captcha resolvido! Retomando processamento...\n")
                    self._captcha_condition.notify_all()
        except asyncio.CancelledError:
            self._logger.warning(f"✖ Task de captcha foi cancelada")
        except Exception as e:
            self._logger.error(f"Erro inesperado na task de captcha: {str(e)}", exc_info=True)
        finally:
            self._logger.debug("🛑 Captcha task finalizada")

    async def _captcha_resolve(self, captcha_selector: str):
        """
        Fluxo inteligente de resolução:
        1. Aguarda um tempo razoável para a resolução automática
        2. Verifica discretamente se foi resolvido
        3. Se persistir, aciona seu fallback personalizado
        """
        # Tempos configuráveis (em segundos)
        WAIT_AUTO_RESOLUTION = 25  # Tempo máximo para a solução automática
        POLLING_INTERVAL = 3  # Intervalo entre verificações
        FALLBACK_TIMEOUT = 40  # Tempo máximo para o fallback
        try:
            # 1. Espera pela resolução automática (com polling discreto)
            start_time = time.time()
            while (time.time() - start_time) < WAIT_AUTO_RESOLUTION:
                if not self._driver.cdp.is_element_present(captcha_selector):
                    self._logger.debug("✅ Captcha resolvido automaticamente!")
                    return
                await asyncio.sleep(POLLING_INTERVAL)
            # 2. Se chegou aqui, a solução automática falhou
            self._logger.debug("⏳ Solução automática falhou - Acionando fallback...")
            start_time = time.time()
            while (time.time() - start_time) < FALLBACK_TIMEOUT:
                try:
                    # Exemplo: Recarregar o captcha e tentar novamente
                    self._driver.cdp.gui_click_element(captcha_selector)
                    await asyncio.sleep(5)  # Tempo para recarregar
                    # Verifique se o captcha persiste
                    if not self._driver.cdp.is_element_present(captcha_selector):
                        self._logger.debug("🎉 Fallback resolveu o captcha!")
                        return
                    # Implemente aqui alternativas como:
                    # - Mudar de proxy/endereço IP
                    # - Usar outra conta/sessão
                    # - Solicitar intervenção manual
                except Exception as e:
                    self._logger.debug(f"⚠️ Tentativa de fallback falhou: {str(e)}")
                    await asyncio.sleep(10)  # Intervalo entre tentativas
        except Exception as e:
            self._logger.debug(f"🚨 Erro no processo de resolução: {str(e)}")
            raise
