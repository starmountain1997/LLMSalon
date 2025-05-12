from collections import OrderedDict
from chatter import Chatter
from typing import Dict, List
from config import settings
from loguru import logger


class Salon:
    def __init__(self):
        self._chatters: OrderedDict[str, Chatter] = OrderedDict()
        chatters_cfg = settings.chatters
        for name, cfg in chatters_cfg.items():
            self._chatters[name] = Chatter(
                provider=cfg.provider,
                model_name=cfg.model_name,
                system_prompt=cfg.system_prompt,
                temperature=cfg.temperature,
                top_p=cfg.top_p,
                max_tokens=cfg.max_tokens,
                presence_penalty=cfg.presence_penalty,
                frequency_penalty=cfg.frequency_penalty,
            )
            logger.info(
                f"Chatter {name} initialized with model {cfg.model_name} and provider {cfg.provider}"
            )
