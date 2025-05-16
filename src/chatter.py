import json
from typing import AsyncGenerator, Dict, List

from rich.markdown import Markdown

from config import settings
from sse_client import SSEClient, logger


class Chatter:
    def __init__(self, role_id: str):
        role_settings = settings.chatters.get(role_id, settings.hoster)
        self._provider = settings.providers[role_settings.provider]
        self._model_name = role_settings.model_name
        self._temperature = role_settings.temperature
        self._top_p = role_settings.top_p
        self._max_tokens = role_settings.get("max_tokens", None)
        self._history: List[Dict[str, str]] = [
            {"role": "system", "content": self._generate_system_prompt(role_id)}
        ]

        self._salon_cache: List[Dict[str, str]] = []
        self._function_calling: List[Dict] = []

    @staticmethod
    def _generate_system_prompt(
        role_id: str,
    ) -> str:
        prompt_template = settings.template.chatter_prompt
        chatter_list = [
            prompt_template.chatter_list.format(
                role=_role_id, role_prompt=role_settings.system_prompt
            )
            for _role_id, role_settings in settings.chatters.items()
            if _role_id != role_id
        ]
        chatter_list = "".join(chatter_list)

        system_prompt = prompt_template.salon_prompt.format(
            topic=settings.topic,
            role_id=role_id,
            role_prompt=settings.chatters[role_id].system_prompt,
            chatter_list=chatter_list,
        )
        logger.info(
            f"generate system_prompt for {role_id}:\n{system_prompt}",
            rich=Markdown(f"generate system_prompt for {role_id}:\n{system_prompt}"),
        )
        return system_prompt

    @property
    def tools(self) -> List[Dict]:
        return None

    @property
    def if_hoster(self) -> bool:
        return False

    @property
    def provider(self) -> Dict[str, str]:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def history(self) -> List[Dict[str, str]]:
        return self._history

    @property
    def function_calling(self) -> List[Dict]:
        return self._function_calling

    @property
    def salon_cache(self) -> List[Dict[str, str]]:
        return self._salon_cache

    def add_salon_cache(self, speaker: str, message: str):
        self.salon_cache.append((speaker, message))

    def _add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    def _add_user_message(self, current_round: int):
        self.history.append(
            {
                "role": "user",
                "content": self.get_salon_cache(current_round),
            }
        )

    @property
    def url(self) -> str:
        return self.provider["url"]

    def get_salon_cache(
        self,
        current_round: int,
    ) -> str:
        conversation_list = [
            self.conversation_list_template.format(
                speaker=speaker,
                message=message,
            )
            for speaker, message in self.salon_cache
        ]
        conversation_list = "".join(conversation_list)

        salon_cache = self.salon_cache_template.format(
            conversation_list=conversation_list,
            current_round=current_round,
            total_rounds=settings.rounds,
        )

        self._salon_cache.clear()
        logger.info(
            f"salon cache:\n{salon_cache}",
            rich=Markdown(f"salon cache:\n{salon_cache}"),
        )
        return salon_cache

    @property
    def salon_cache_template(self):
        return settings.template.chatter_prompt.salon_cache

    @property
    def conversation_list_template(self):
        return settings.template.chatter_prompt.conversation_list

    async def speaking(self, current_round: int) -> AsyncGenerator[str, None]:
        self._function_calling = []
        self._add_user_message(current_round)
        payload = {
            "model": self.model_name,
            "messages": self.history,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "max_tokens": self._max_tokens,
            "stream": True,
            "tools": self.tools,
        }
        content_response = []
        reasoning_response = []
        tool_calls_response: Dict = None

        async for chunk in SSEClient.send_sse(
            url=self.url,
            payload=payload,
            api_key=self.provider["api_key"],
        ):
            if chunk["type"] == "content":
                content_response.append(chunk["data"])
            elif chunk["type"] == "reasoning":
                reasoning_response.append(chunk["data"])
            elif chunk["type"] == "tool_calls":
                if not tool_calls_response:
                    tool_calls_response = chunk["data"][0]
                else:
                    tool_calls_response["function"]["arguments"] = tool_calls_response[
                        "function"
                    ].get("arguments", "") + chunk["data"][0]["function"].get(
                        "arguments", ""
                    )
            yield chunk

        if tool_calls_response:
            tool_calls_response["function"]["arguments"] = json.loads(
                tool_calls_response["function"]["arguments"]
            )
            self._function_calling = [tool_calls_response]

        assistant_message = "".join(content_response)
        self._history.append(
            {
                "role": "assistant",
                "content": assistant_message,
            }
        )


class Hoster(Chatter):
    def __init__(self):
        super().__init__(None)

    def get_salon_cache(
        self,
        current_round: int,
    ) -> str:
        if current_round == -1:
            return settings.template.hoster_prompt.opening_prompt
        else:
            return super().get_salon_cache(current_round)

    @property
    def if_hoster(self) -> bool:
        return True

    def _generate_system_prompt(self, role_id: str = None) -> str:
        prompt_template = settings.template.hoster_prompt
        chatter_list = [
            prompt_template.chatter_list.format(
                role=_role_id, role_prompt=role_settings.system_prompt
            )
            for _role_id, role_settings in settings.chatters.items()
            if _role_id != role_id
        ]
        chatter_list = "".join(chatter_list)

        system_prompt = prompt_template.salon_prompt.format(
            topic=settings.topic,
            chatter_list=chatter_list,
        )

        logger.info(
            f"generate system_prompt for hoster:\n{system_prompt}",
            rich=Markdown(f"generate system_prompt for hoster:\n{system_prompt}"),
        )
        return system_prompt

    @property
    def tools(self) -> List[Dict]:
        if settings.chat_mode.lower() == "rotation":
            return [SSEClient.mark_task_as_completed]
        elif settings.chat_mode.lower() == "assignment":
            return [
                SSEClient.mark_task_as_completed,
                SSEClient.determine_next_speaker,
            ]
        elif settings.chat_mode.lower() == "competition":
            return [SSEClient.mark_task_as_completed]
        else:
            raise ValueError(f"Unknown chat mode: {settings.chat_mode}")

    @property
    def if_mark_task_as_completed(self) -> bool:
        for fc in self.function_calling:
            logger.info(fc)
            if fc["function"]["name"] == "mark_task_as_completed":
                return fc["function"]["arguments"]["all_steps_done"] is True
        return False

    @property
    def salon_cache_template(self):
        return settings.template.hoster_prompt.salon_cache

    @property
    def conversation_list_template(self):
        return settings.template.hoster_prompt.conversation_list
