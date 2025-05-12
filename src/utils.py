import asyncio
import json
from collections import OrderedDict
from typing import Any, AsyncGenerator, Dict, List, Tuple

import aiohttp_client
import gradio as gr
from loguru import logger

from config import settings


class SSEClient:
    sem = asyncio.Semaphore(settings.semaphore)

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

                                if "content" in delta and delta["content"]:
                                    content_piece = delta["content"]
                                    yield content_piece
                                elif (
                                    "reasoning_content" in delta
                                    and delta["reasoning_content"]
                                ):
                                    reasoning_content_piece = delta["reasoning_content"]
                                    yield reasoning_content_piece

                            elif chunk.get("error"):
                                error_info = chunk["error"]
                                error_message = (
                                    error_info.get("message")
                                    if isinstance(error_info, dict)
                                    else str(error_info)
                                )
                                logger.error(f"API Error: {error_message}")
                                raise Exception(f"API Error: {error_message}")

                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"JSON decode error: {e}, data: {json_data_str}"
                            )
                            continue

            except Exception as e:
                logger.error(f"SSE request failed: {str(e)}")
                raise


if __name__ == "__main__":
    pass
