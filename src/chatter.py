from typing import AsyncGenerator, Dict, List

from rich.markdown import Markdown

from config import settings
from utils import SSEClient, logger


class Chatter:
    def __init__(
        self,
        provider: str,
        model_name: str,
        system_prompt: str,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = None,
        *args,
        **kwargs,
    ):
        self._provider = settings.providers[provider]
        self._model_name = model_name
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._history: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        self._salon_cache: List[Dict[str, str]] = []
        self._function_calling: List[Dict] = []
        logger.info(
            f"initialized chatter with system prompt:\n{system_prompt}",
            rich=Markdown(system_prompt),
        )

    @property
    def provider(self) -> Dict[str, str]:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def history(self) -> List[Dict[str, str]]:
        return self._history

    @property
    def salon_cache(self) -> List[Dict[str, str]]:
        return self._salon_cache

    def add_salon_cache(self, speaker: str, message: str):
        self.salon_cache.append((speaker, message))

    def _add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    def _add_user_message(self, current_round: int, total_rounds: int):
        self.history.append(
            {
                "role": "user",
                "content": self.get_salon_cache(current_round, total_rounds),
            }
        )

    @property
    def url(self) -> str:
        return self.provider["url"]

    def get_salon_cache(self, current_round: int, total_rounds: int) -> str:
        salon_cache_template = settings.template.salon_cache
        message_str = salon_cache_template.prefix
        for speaker, message in self._salon_cache:
            message_str += salon_cache_template.speaker.format(
                speaker=speaker, message=message
            )
        message_str += salon_cache_template.suffix
        message_str += salon_cache_template.round_index.format(
            current_round=current_round + 1, total_rounds=total_rounds
        )

        self._salon_cache.clear()
        logger.info(f"salon cache:\n{message_str}", rich=Markdown(message_str))
        return message_str

    async def speaking(
        self, current_round: int, total_rounds: int, if_hoster: bool = False
    ) -> AsyncGenerator[str, None]:
        self._add_user_message(current_round, total_rounds)
        payload = {
            "model": self.model_name,
            "messages": self.history,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "max_tokens": self._max_tokens,
            "stream": True,
            "tools": SSEClient.tools if if_hoster else None,
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
            self._function_calling = tool_calls_response

        # 更新历史记录
        assistant_message = "".join(content_response)
        self._history.append(
            {
                "role": "assistant",
                "content": assistant_message,
            }
        )
