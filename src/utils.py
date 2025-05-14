import asyncio
import json
import os.path as osp
from typing import AsyncGenerator, Dict

import aiohttp_client
# import richuru
from loguru import logger

from config import settings

# richuru.install()


PROJECT_ROOT = osp.dirname(osp.dirname(osp.abspath(__file__)))


class SSEClient:
    sem = asyncio.Semaphore(settings.semaphore)
    tools = [
        { 
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
    ]

    @classmethod
    async def send_sse(
        cls, url: str, payload: Dict, api_key: str
    ) -> AsyncGenerator[str, None]:
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
