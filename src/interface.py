import html
import os
import pickle
from datetime import datetime

import gradio as gr
from loguru import logger

from config import settings
from salon import Salon

stop_flag = False


async def run_salon_gradio():
    global stop_flag
    stop_flag = False
    salon = Salon()
    chat_history = []
    current_speaker = None
    current_cot = ""
    current_turn = 0
    hoster_info = ""

    try:
        async for event_type, data in salon.chatting():
            if event_type == "hoster_determing":
                hoster_info = "主持人正在决定下一位发言者..."
            elif event_type == "next_speaker":
                hoster_info = f"下一位发言者: {data}"
            elif event_type == "next_speak_reason" and data:
                hoster_info += f"\n选择理由: {data}"
            
            if stop_flag or event_type == "task_finish":
                yield (chat_history, "# LLM 沙龙已停止", hoster_info)
                return
            if event_type == "speaker_turn":
                current_speaker = str(data)
                speaker_label = f"✨ **{current_speaker}** ✨"
                chat_history.append((speaker_label, ""))
                yield (
                    chat_history,
                    f"# LLM 沙龙（{current_turn}/{settings.rounds}）讨论中...🤖💬",
                    hoster_info
                )
            elif event_type == "content_piece" and current_speaker:
                current_cot = ""
                if (
                    not chat_history
                    or chat_history[-1][0] != f"✨ **{current_speaker}** ✨"
                ):
                    chat_history.append((f"✨ **{current_speaker}** ✨", None))

                last_message = chat_history[-1][1] or ""
                chat_history[-1] = (chat_history[-1][0], last_message + str(data))
                yield (
                    chat_history,
                    f"# LLM 沙龙（{current_turn}/{settings.rounds}）讨论中...🤖💬",
                    hoster_info
                )
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
                yield (
                    chat_history,
                    f"# LLM 沙龙（{current_turn}/{settings.rounds}）讨论中...🤖💬",
                    hoster_info
                )
            elif event_type == "new_turn":
                current_turn = data + 1
                yield (
                    chat_history,
                    f"# LLM 沙龙（{current_turn}/{settings.rounds}）讨论中...🤖💬",
                    hoster_info
                )

    except Exception as e:
        logger.error(f"Discussion failed: {str(e)}")
        raise


def save_chat_history(history):
    """保存聊天历史到pkl文件"""
    if not history:
        return "没有聊天历史可保存"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_history_{timestamp}.pkl"

    # 确保history目录存在
    os.makedirs("history", exist_ok=True)
    filepath = os.path.join("history", filename)

    with open(filepath, "wb") as f:
        pickle.dump(history, f)

    return f"聊天历史已保存到 {filepath}"


with gr.Blocks(theme=gr.themes.Soft(), css="""
    .hoster-info {
        padding: 15px;
        margin: 10px 0;
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 5px;
        font-weight: bold;
        color: #495057;
    }
    .hoster-info:hover {
        background: #e9ecef;
    }
""") as demo:
    title = gr.Markdown(f"# LLM 沙龙（0/{settings.rounds}）讨论中...🤖💬")
    gr.Markdown(settings.topic)

    chatbot_display = gr.Chatbot(
        label="Conversation Log",
        height=800,
        show_copy_button=True,
        bubble_full_width=False,
    )

    with gr.Row():
        run_button = gr.Button(
            "开始讨论",
            variant="primary",
        )
        stop_button = gr.Button(
            "停止讨论",
            variant="stop",
        )
        save_button = gr.Button(
            "保存历史",
            variant="secondary",
        )

    save_status = gr.Markdown()
    hoster_info_display = gr.Markdown(
        "主持人信息将显示在这里",
        elem_classes=["hoster-info"]
    )

    run_button.click(
        fn=run_salon_gradio,
        outputs=[chatbot_display, title, hoster_info_display],
        show_progress="hidden",
    )
    save_button.click(
        fn=lambda history: save_chat_history(history),
        inputs=[chatbot_display],
        outputs=[save_status],
    )

    def stop_discussion():
        global stop_flag
        stop_flag = True
        return "# LLM 沙龙已停止", "主持人信息将显示在这里"

    stop_button.click(
        fn=stop_discussion,
        outputs=[title, hoster_info_display],
    )


if __name__ == "__main__":
    demo.queue().launch()
