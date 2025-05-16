import asyncio
import json
from typing import AsyncGenerator, Dict

import aiohttp_client
import richuru
from loguru import logger

from config import settings

richuru.install()


class SSEClient:
    sem = asyncio.Semaphore(settings.semaphore)
    mark_task_as_completed = {
        "type": "function",
        "function": {
            "name": "mark_task_as_completed",
            "description": "Call this function when the task is fully completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "all_steps_done": {
                        "type": "boolean",
                        "description": "Confirms all steps are done.",
                    },
                },
                "required": ["all_steps_done"],
            },
        },
    }
    determine_next_speaker = {
        "type": "function",
        "function": {
            "name": "determine_next_speaker",
            "description": "Call this function to select which participant should speak next. You must choose a speaker from the list of participants provided in your role description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "next_speaker": {
                        "type": "string",
                        "description": "The exact name of the participant who should speak next. This name must be one of the participants listed in your initial role description.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "A brief explanation for choosing this particular speaker to speak next.",
                    },
                },
                "required": ["next_speaker", "reason"],
            },
        },
    }

    @classmethod
    async def send_sse(
        cls, url: str, payload: Dict, api_key: str
    ) -> AsyncGenerator[Dict[str, str], None]:
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        async with cls.sem:
            try:
                async with aiohttp_client.post(
                    url, json=payload, headers=headers
                ) as resp:
                    resp.raise_for_status()

                    async for line in resp.content:
                        if not line:
                            continue

                        decoded_line = line.decode("utf-8").strip()

                        if not decoded_line.startswith("data:"):
                            continue
                        json_data_str = decoded_line[len("data:") :].strip()
                        if json_data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(json_data_str)

                            if "choices" in chunk and chunk["choices"]:
                                delta = chunk["choices"][0].get("delta", {})

                                if "tool_calls" in delta and delta["tool_calls"]:
                                    yield {
                                        "type": "tool_calls",
                                        "data": delta["tool_calls"],
                                    }
                                elif delta.get("content"):
                                    yield {"type": "content", "data": delta["content"]}
                                elif (
                                    "reasoning_content" in delta
                                    and delta["reasoning_content"]
                                ):
                                    yield {
                                        "type": "reasoning",
                                        "data": delta["reasoning_content"],
                                    }

                            elif chunk.get("error"):
                                error_info = chunk["error"]
                                error_message = (
                                    error_info.get("message")
                                    if isinstance(error_info, dict)
                                    else str(error_info)
                                )
                                logger.error(
                                    f"API Error:\n{json.dumps(error_message, indent=4)}"
                                )
                                raise Exception(
                                    f"API Error:\n{json.dumps(error_message, indent=4)}"
                                )

                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"JSON decode error: {e}, data:\n{json.dumps(json_data_str, indent=4)}"
                            )
                            continue

            except Exception as e:
                logger.error(f"SSE request failed: {str(e)}")
                raise
