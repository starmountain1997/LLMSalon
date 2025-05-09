from typing import AsyncGenerator, Dict,List

from utils import SSEClient
from config import settings
from loguru import logger

class Chatter:
    def __init__(self, provider:str,model_name:str, system_prompt:str ):
        self._provider=settings.providers[provider]
        self._model_name=model_name
        self._system_prompt=system_prompt

        self._history :List[Dict[str,str]]= []
        self._salon_cache:List[Dict[str,str]]=[]
    
    @property
    def provider(self)->Dict[str,str]:
        return self._provider
    @property
    def model_name(self)->str:
        return self._model_name
    @property
    def system_prompt(self)->str:
        return self._system_prompt
    @property
    def history(self)->List[Dict[str,str]]:
        return self._history
    @property
    def salon_cache(self)->List[Dict[str,str]]:
        return self._salon_cache
    
    def add_salon_cache(self, speaker:str, message:str):
        self.salon_cache.append((speaker, message))

    def get_salon_cache(self) -> str:
        salon_cache_template=settings.chatter.salon_cache_template
        message_str = salon_cache_template.prefix
        for (speaker, message) in self._salon_cache:
            message_str += salon_cache_template.speaker.format(speaker=speaker,message=message)
        message_str += salon_cache_template.suffix
        logger.debug(f"salon cache:\n{message_str}")
        self._salon_cache.clear()
        return message_str

        
    async def speaking(self)->AsyncGenerator[str, None]:
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
        async for chunk in SSEClient.send_sse(
            url=self.provider["url"],
            payload=payload,
            api_key=self.provider["api_key"],
        ):
            yield chunk

if __name__ == "__main__":
    # Example usage
    chatter = Chatter(provider="deepseek", model_name="example_model", system_prompt="Hello!")
    chatter.add_salon_cache("user", "Hello, how are you?")
    chatter.get_salon_cache()