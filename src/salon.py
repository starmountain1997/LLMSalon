from collections import OrderedDict
from typing import Any, AsyncGenerator, Dict, Tuple

from chatter import Chatter
from config import settings


class Salon:
    def __init__(self):
        self._chatters: OrderedDict[str, Chatter] = OrderedDict()
        chatters_cfg = settings.chatters
        for name, cfg in chatters_cfg.items():
            system_prompt = self._genereate_system_prompt(name, chatters_cfg)

            self._chatters[name] = Chatter(
                provider=cfg.provider,
                model_name=cfg.model_name,
                system_prompt=system_prompt,
                **{
                    k: v
                    for k, v in cfg.items()
                    if k not in ["model_name", "system_prompt", "provider"]
                },
            )

        hoster_cfg = settings.hoster
        system_prompt = self._generate_hoster_system_prompt(hoster_cfg, chatters_cfg)
        self._hoster = (
            hoster_cfg.name,
            Chatter(
                provider=hoster_cfg.provider,
                model_name=hoster_cfg.model_name,
                system_prompt=system_prompt,
                **{
                    k: v
                    for k, v in cfg.items()
                    if k not in ["name", "model_name", "system_prompt", "provider"]
                },
            ),
        )

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def chatters(self) -> Dict[str, Chatter]:
        return self._chatters

    @property
    def hoster(self):
        return self._hoster[1]

    @property
    def hoster_name(self):
        return self._hoster[0]

    @staticmethod
    def _generate_hoster_system_prompt(hoster_cfg: Dict, chatters_cfg: Dict):
        prompt_template = settings.template.hoster_prompt
        system_prompt = prompt_template.prefix.format(
            role=hoster_cfg.name,
            role_prompt=hoster_cfg.system_prompt,
            topic=settings.topic,
        )
        participants = [
            prompt_template.chatter.format(role=role, role_prompt=cfg.system_prompt)
            for role, cfg in chatters_cfg.items()
        ]
        system_prompt += "".join(participants)
        system_prompt += prompt_template.suffix.format()
        return system_prompt

    @staticmethod
    def _genereate_system_prompt(
        name: str,
        chatters_cfg: Dict,
    ) -> str:
        prompt_template = settings.template.system_prompt
        system_prompt = prompt_template.prefix.format(
            role=name,
            role_prompt=chatters_cfg[name].system_prompt,
            topic=settings.topic,
        )
        participants = [
            prompt_template.chatter.format(role=role, role_prompt=cfg.system_prompt)
            for role, cfg in chatters_cfg.items()
            if role != name
        ]

        system_prompt += "".join(participants)
        system_prompt += prompt_template.suffix.format()
        return system_prompt

    async def chatting(self) -> AsyncGenerator[Tuple[str, Any], None]:
        # for _, chatter in self._chatters.items():
        #     chatter.add_salon_cache(self.hoster_name, settings.topic)

        for i in range(settings.rounds):
            yield ("new_turn", i)
            for speaker_name, speaker in self.chatters.items():
                yield ("speaker_turn", speaker_name)
                current_utterance = ""
                async for piece in speaker.speaking(i, settings.rounds):
                    if piece["type"] == "content":
                        yield ("content_piece", piece["data"])
                        current_utterance += piece["data"]
                    elif piece["type"] == "reasoning":
                        yield ("reasoning_piece", piece["data"])
                for k, v_chatter in self._chatters.items():
                    if k == speaker_name:
                        continue
                    v_chatter.add_salon_cache(speaker_name, current_utterance)
                self.hoster.add_salon_cache(speaker_name, current_utterance)
            hoster_utterance = ""
            if settings.show_hoster:
                yield ("speaker_turn", self.hoster_name)
            async for piece in self.hoster.speaking(i, settings.rounds):
                if piece["type"] == "content":
                    if settings.show_hoster:
                        yield ("content_piece", piece["data"])
                    hoster_utterance += piece["data"]
                elif piece["type"] == "reasoning":
                    if settings.show_hoster:
                        yield ("reasoning_piece", piece["data"])
            if "<|任务完成|>" in hoster_utterance:
                yield ("new_turn", -1)
                break
            for k, v_chatter in self._chatters.items():
                v_chatter.add_salon_cache(self.hoster_name, hoster_utterance)
