import html

import gradio as gr
from loguru import logger

from config import settings
from salon import Salon


async def run_salon_gradio(topic: str, rounds: int):
    salon = Salon()
    chat_history = []
    current_speaker = None
    current_cot = ""

    try:
        async for event_type, data in salon.chatting(topic, int(rounds)):
            if event_type == "speaker_turn":
                current_speaker = str(data)
                speaker_label = f"✨ **{current_speaker}** ✨"
                chat_history.append((speaker_label, ""))
                yield chat_history
            elif event_type == "content_piece" and current_speaker:
                current_cot = ""
                if (
                    not chat_history
                    or chat_history[-1][0] != f"✨ **{current_speaker}** ✨"
                ):
                    chat_history.append((f"✨ **{current_speaker}** ✨", None))

                last_message = chat_history[-1][1] or ""
                chat_history[-1] = (chat_history[-1][0], last_message + str(data))
                yield chat_history
            elif event_type == "reasoning_piece" and current_speaker:
                if (
                    not chat_history
                    or chat_history[-1][0] != f"✨ **{current_speaker}** ✨"
                ):
                    chat_history.append((f"✨ **{current_speaker}** ✨", None))
                current_cot += str(data)
                formatted_cot = f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{html.escape(current_cot)}</pre>"
                foldable_current_cot = f"""
<details open style="margin-top: 10px; border: 1px solid #eee; border-radius: 5px; padding: 5px;">
  <summary style="cursor: pointer; font-weight: bold; color: #555;">显示/隐藏 推理过程</summary>
  {formatted_cot}
</details>
"""
                chat_history[-1] = (chat_history[-1][0], foldable_current_cot)
                yield chat_history

    except Exception as e:
        logger.error(f"Discussion failed: {str(e)}")
        raise


def main():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# LLM 沙龙🤖💬")
        gr.Markdown(
            "输入一个主题，观看LLM讨论它。"
        )


        chatbot_display = gr.Chatbot(
            label="Conversation Log",
            height=600,
            show_copy_button=True,
            bubble_full_width=False,
        )

        with gr.Row():
            topic = gr.Textbox(
                label="讨论主题",
                lines=3,
                value=settings.topic,
                scale=3,
            )
            rounds = gr.Number(
                label="讨论轮次",
                value=settings.rounds,
                minimum=1,
                maximum=100,
                step=1,
                scale=1,
            )

            run_button = gr.Button("开始讨论", variant="primary", scale=1)

        run_button.click(
            fn=run_salon_gradio,
            inputs=[topic, rounds],
            outputs=chatbot_display,
            show_progress="hidden",
        )

    demo.queue().launch()


if __name__ == "__main__":
    main()
