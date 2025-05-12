from typing import AsyncGenerator, Dict, List

from utils import SSEClient
from config import settings
from loguru import logger


class Chatter:
    def __init__(
        self,
        provider: str,
        model_name: str,
        system_prompt: str,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 150,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
    ):
        self._provider = settings.providers[provider]
        self._model_name = model_name
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._presence_penalty = presence_penalty
        self._frequency_penalty = frequency_penalty
        self._history: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        self._salon_cache: List[Dict[str, str]] = []

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

    def add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    def get_salon_cache(self) -> str:
        salon_cache_template = settings.template.salon_cache
        message_str = salon_cache_template.prefix
        for speaker, message in self._salon_cache:
            message_str += salon_cache_template.speaker.format(
                speaker=speaker, message=message
            )
        message_str += salon_cache_template.suffix
        logger.debug(f"salon cache:\n{message_str}")
        self._salon_cache.clear()
        return message_str

    async def speaking(self) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model_name,
            "messages": self.history,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "max_tokens": self._max_tokens,
            "presence_penalty": self._presence_penalty,
            "frequency_penalty": self._frequency_penalty,
            "stream": True,
        }
        full_response = []
        async for chunk in SSEClient.send_sse(
            url=self.provider["url"],
            payload=payload,
            api_key=self.provider["api_key"],
        ):
            yield chunk
            full_response.append(chunk)
        full_response = "".join(full_response)
        self.add_assistant_message(full_response)
        logger.debug(f"assistant message:\n{full_response}")
        return full_response


if __name__ == "__main__":
    # Example usage
    chatter = Chatter(
        provider="deepseek", model_name="example_model", system_prompt="Hello!"
    )
    chatter.add_salon_cache("user", "Hello, how are you?")
    chatter.get_salon_cache()
