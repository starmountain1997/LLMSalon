from typing import Any, AsyncGenerator, Dict, Tuple

from chatter import Chatter, Hoster
from config import settings


class Salon:
    def __init__(self):
        if "hoster" in settings.chatters.keys():
            raise ValueError("chatter id cannot be hoster")
        self._chatters: Dict[str, Chatter] = {
            role_id: Chatter(role_id) for role_id in settings.chatters.keys()
        }

        self._hoster = Hoster()

    @property
    def chatters(self) -> Dict[str, Chatter]:
        return self._chatters

    @property
    def hoster(self):
        return self._hoster

    async def rotation_chatting(self):
        current_utterance = ""
        yield ("speaker_turn", "hoster")
        async for piece in self.hoster.speaking(-1):
            if piece["type"] == "content":
                yield ("content_piece", piece["data"])
                current_utterance += piece["data"]
            elif piece["type"] == "reasoning":
                yield ("reasoning_piece", piece["data"])
        for chatter in self.chatters.values():
            chatter.add_salon_cache("hoster", current_utterance)

        for i in range(settings.rounds):
            yield ("new_turn", i)
            for speaker_name, speaker in self.chatters.items():
                current_utterance = ""
                yield ("speaker_turn", speaker_name)
                async for piece in speaker.speaking(i):
                    if piece["type"] == "content":
                        yield ("content_piece", piece["data"])
                        current_utterance += piece["data"]
                    elif piece["type"] == "reasoning":
                        yield ("reasoning_piece", piece["data"])
                for chatter_id, chatter in self.chatters.items():
                    if chatter_id == speaker_name:
                        continue
                    chatter.add_salon_cache(speaker_name, current_utterance)
                self.hoster.add_salon_cache(speaker_name, current_utterance)
            current_utterance = ""
            yield ("speaker_turn", "hoster")
            async for piece in self.hoster.speaking(i):
                if piece["type"] == "content":
                    yield ("content_piece", piece["data"])
                    current_utterance += piece["data"]
                elif piece["type"] == "reasoning":
                    yield ("reasoning_piece", piece["data"])
            for chatter in self.chatters.values():
                chatter.add_salon_cache("hoster", current_utterance)
            if self.hoster.if_mark_task_as_completed:
                yield ("task_completed", None)
                break

    async def assignment_chatting(self) -> AsyncGenerator[Tuple[str, Any], None]:
        current_utterance = ""
        yield ("speaker_turn", "hoster")
        async for piece in self.hoster.speaking(-1):
            if piece["type"] == "content":
                yield ("content_piece", piece["data"])
                current_utterance += piece["data"]
            elif piece["type"] == "reasoning":
                yield ("reasoning_piece", piece["data"])
        if current_utterance:
            for chatter in self.chatters.values():
                chatter.add_salon_cache("hoster", current_utterance)
        next_speaker_name, reason = self.hoster.determined_next_speaker_name()
        next_speaker = self.chatters[next_speaker_name]

        next_speaker_message=f"请{next_speaker_name}发言！理由是：{reason}"
        yield ("content_piece", next_speaker_message)

        for chatter in self.chatters.values():
            chatter.add_salon_cache(
                "hoster", next_speaker_message
            )

        for i in range(settings.rounds):
            yield ("new_turn", i)
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

            current_utterance = ""
            yield ("speaker_turn", "hoster")
            async for piece in self.hoster.speaking(i):
                if piece["type"] == "content":
                    yield ("content_piece", piece["data"])
                    current_utterance += piece["data"]
                elif piece["type"] == "reasoning":
                    yield ("reasoning_piece", piece["data"])
            if current_utterance:
                for chatter in self.chatters.values():
                    chatter.add_salon_cache("hoster", current_utterance)
            if self.hoster.if_mark_task_as_completed:
                yield ("task_completed", None)
                break
            next_speaker_name, reason = self.hoster.determined_next_speaker_name()
            next_speaker = self.chatters[next_speaker_name]
            next_speaker_message = f"请{next_speaker_name}发言！理由是：{reason}"
            yield ("content_piece", next_speaker_message)

            for chatter in self.chatters.values():
                chatter.add_salon_cache(
                    "hoster", next_speaker_message
                )


async def main():
    s = Salon()
    async for _ in s.assign_chatting():
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
