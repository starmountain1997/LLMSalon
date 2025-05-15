import json
from typing import Any, AsyncGenerator, Dict, List, Tuple

from chatter import Chatter, Hoster
from config import settings
from utils import logger


class Salon:
    def __init__(self):
        chatters_cfg = settings.chatters
        self._chatters: Dict[str, Chatter] = {
            name: Chatter(
                provider=cfg.provider,
                model_name=cfg.model_name,
                system_prompt=self._genereate_chatter_system_prompt(name, chatters_cfg),
                **{
                    k: v
                    for k, v in cfg.items()
                    if k not in ["model_name", "system_prompt", "provider"]
                },
            )
            for name, cfg in chatters_cfg.items()
        }

        hoster_cfg = settings.hoster
        self._hoster = Hoster(
            provider=hoster_cfg.provider,
            model_name=hoster_cfg.model_name,
            system_prompt=self._generate_hoster_system_prompt(hoster_cfg, chatters_cfg),
            **{
                k: v
                for k, v in hoster_cfg.items()
                if k not in ["model_name", "system_prompt", "provider"]
            },
        )

    @property
    def chatter_list(self) -> List[str]:
        return list(self.chatters)

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def chatters(self) -> Dict[str, Chatter]:
        return self._chatters

    @property
    def hoster(self):
        return self._hoster

    @staticmethod
    def _generate_hoster_system_prompt(hoster_cfg: Dict, chatters_cfg: Dict):
        prompt_template = settings.template.hoster_prompt
        system_prompt = prompt_template.prefix.format(
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
    def _genereate_chatter_system_prompt(
        name: str,
        chatters_cfg: Dict,
    ) -> str:
        prompt_template = settings.template.chatter_prompt
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
        for i in range(settings.rounds):
            yield ("new_turn", i)
            async for piece in self.hoster.speaking(i):# FIXME: 这里不会有任何数据
                yield("hoster_determing",None)
            if self.hoster.function_called_name == "mark_task_as_completed":
                arguments = json.loads(self.hoster.function_called_arguments)
                if arguments["all_steps_done"] is True:
                    yield ("task_finish", None)
                    break
            elif self.hoster.function_called_name == "determine_next_speaker":
                arguments = json.loads(self.hoster.function_called_arguments)
                next_speaker_name = arguments["next_speaker_name"]
                reason=arguments.get("reason")
                next_speaker = self.chatters.get(next_speaker_name)
                if next_speaker is None:
                    raise Exception(f"{next_speaker} is not valid speaker")
                next_speaker.add_salon_cache("hoster",reason)
                yield("next_speaker",next_speaker_name)
                yield("next_speak_reason",reason)

            yield ("speaker_turn", next_speaker_name)
            current_utterance = ""
            async for piece in next_speaker.speaking(
                i,
            ):
                if piece["type"] == "content":
                    yield ("content_piece", piece["data"])
                    current_utterance += piece["data"]
                elif piece["type"] == "reasoning":
                    yield ("reasoning_piece", piece["data"])
            for k, v_chatter in self._chatters.items():
                if k == next_speaker_name:
                    continue
                v_chatter.add_salon_cache(next_speaker_name, current_utterance)
            self.hoster.add_salon_cache(next_speaker_name, current_utterance)


async def main():
    s = Salon()
    async for _ in s.chatting():
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
