# LLMSalon: 大语言模型聊天沙龙

LLMSalon 是一个利用多个大型语言模型（LLM）进行模拟群聊或协作讨论的平台。它允许用户定义不同的角色（“发言者”或“chatter”）、一个主持人（“hoster”）以及一个讨论主题，然后观察这些由 LLM 驱动的角色如何围绕主题进行多轮对话。

## 如何运行

1.  **环境准备**:
    * 确保您已安装 Python 3.10 或更高版本。

2.  **克隆项目**:
    ```bash
    git clone https://github.com/starmountain1997/LLMSalon.git
    cd LLMSalon
    ```

3.  **安装依赖**:
    ```bash
    pip install .
    ```

4.  **配置API密钥**:
    * 打开 `src/settings.yaml` 文件。
    * 找到 `providers` 部分，例如 `deepseek`。
    * 将其中的 `api_key: sk-xxxxxxxx` 替换为您自己的有效 API 密钥。

5.  **运行应用**:
    推荐通过 `entry.py` 脚本启动，以启用配置文件热重载功能：
    ```bash
    python src/entry.py
    ```
    启动后，脚本会输出 Gradio 应用的访问地址，通常是 `http://127.0.0.1:7860`。在浏览器中打开此地址即可开始使用。

    **注意**: 当前版本的配置文件热重载机制（通过 `entry.py` 监控 `settings.yaml`）做得很烂……后面有时间再改。

## 项目特点

* **多角色对话**: 支持配置多个具有不同角色设定和指令的 LLM 参与者。
* **主持人引导**: 可以设定一个 LLM 主持人来引导讨论流程、总结观点并推动对话向目标前进。
* **动态配置**: 通过 `settings.yaml` 文件轻松配置模型、API、角色提示、讨论主题等。
* **热重载**: 修改 `settings.yaml` 后，应用会自动重启以应用新的配置，方便快速迭代和实验。（**注意：当前热重载机制尚不完善，详见“如何运行”部分**）
* **流式输出**: 对话内容实时流式显示在 Gradio 构建的 Web 界面上。
* **可扩展性**: 可以方便地添加新的 LLM 提供商或自定义角色行为。

## 运行原理

LLMSalon 的核心思想是模拟一个多方参与的、有结构的讨论会。其运行流程如下：

1.  **配置加载 (`config.py`, `settings.yaml`)**:
    * 应用启动时，首先通过 `config.py` 加载 `src/settings.yaml` 文件中的所有配置。这个 YAML 文件是整个沙龙的大脑，定义了参与者、讨论规则、API 密钥等。

2.  **沙龙初始化 (`salon.py` - `Salon` 类)**:
    * `Salon` 类根据 `settings.yaml` 中的配置，为每一个“发言者”（`chatters`）和“主持人”（`hoster`）创建一个 `Chatter` 实例 (`chatter.py`)。
    * **系统提示生成**: 对于每个 `Chatter` 实例（包括主持人），会动态构建一个详细的“系统提示”（System Prompt）。这个系统提示至关重要，它告诉 LLM 其扮演的角色、核心任务、行为准则、讨论的总主题以及其他参与者的角色信息。这些提示模板也存储在 `settings.yaml` 中。

3.  **对话流程 (`salon.py` - `Salon.chatting` 方法)**:
    * 讨论按预设的 `rounds`（轮次）进行。
    * **发言者轮流发言**:
        * 在每一轮中，`settings.yaml` 中定义的 `chatters` 会按顺序发言。
        * 轮到某个发言者时，其对应的 `Chatter` 实例会准备一个“用户消息”。此消息通常包含：
            * 最近的对话摘要（“沙龙缓存” - `salon_cache`），为 LLM 提供上下文。
            * 当前轮次和总轮次信息。
        * 这条用户消息，连同该 `Chatter` 实例的完整历史对话记录（包括其初始系统提示），会被发送到其配置的 LLM API（例如 DeepSeek API）。
        * API 的通信通过 `utils.py` 中的 `SSEClient` 实现，它使用服务器发送事件（SSE）来支持流式响应。这意味着 LLM 的回答会一个字一个字地显示出来，而不是等待完整回复。
        * 发言者的回复内容（`content`）、可能的思考过程（`reasoning`）或工具调用（`tool_calls`，主要由主持人使用）会被接收。
        * 该发言者的完整回复会被记录下来，并添加到其他所有发言者和主持人的“沙龙缓存”中，作为他们下一轮发言的上下文。
    * **主持人发言**:
        * 在一轮中所有普通发言者都发言完毕后，轮到主持人发言（如果 `show_hoster` 为 `true`）。
        * 主持人的角色是引导讨论、总结进展、在必要时进行干预，并可能使用预定义的“工具调用”（Function Calling），例如 `mark_task_as_completed` 来判断讨论是否达到预定目标，从而提前结束沙龙。
        * 主持人的发言同样会被添加到所有普通发言者的“沙龙缓存”中。
    * **循环与结束**: 这个“发言者发言 -> 主持人发言”的循环会持续进行，直到达到 `settings.yaml` 中设定的 `rounds` 数量，或者主持人通过工具调用明确表示任务已完成。

4.  **用户界面 (`interface.py`)**:
    * 使用 Gradio 库构建一个交互式的 Web 用户界面。
    * `run_salon_gradio` 函数负责调用 `salon.chatting()` 来驱动整个对话过程。
    * 它会监听从 `chatting` 方法产生的各种事件（如 `speaker_turn` - 轮到谁发言, `content_piece` - 发言内容片段, `reasoning_piece` - 思考过程片段, `new_turn` - 新一轮开始），并实时更新界面上的聊天记录。
    * 界面会清晰地展示当前发言者的名字、其发言内容，以及（如果 LLM 提供了）其“思考链”（Chain of Thought, CoT）或推理过程。
    * 提供“开始讨论”、“停止讨论”和“保存历史”等控制按钮。

5.  **入口与热重载 (`entry.py`)**:
    * `src/entry.py` 是项目的主入口脚本。
    * 它负责启动 `interface.py`（Gradio 应用）作为一个子进程。
    * 同时，它使用 `watchdog` 库监控 `src/settings.yaml` 文件的任何变动。
    * 如果 `settings.yaml` 文件被修改并保存，`entry.py` 会自动停止当前运行的 Gradio 进程，并重新启动一个新的 Gradio 进程。这使得用户可以动态修改沙龙的配置（如角色、提示、主题等）并立即看到效果，无需手动重启整个应用。（**注意：当前热重载机制尚不完善，详见“如何运行”部分**）

## `settings.yaml` 配置详解

`src/settings.yaml` 文件是 LLMSalon 的核心配置文件，用于定义沙龙的方方面面。

```yaml
# LLM Salon 的全局配置
semaphore: 30 # 最大并发 API 请求数，防止API过载或速率限制
show_hoster: true # 是否在输出中显示主持人的发言

# API 提供商配置
providers:
  deepseek: # 提供商名称，可以有多个 (例如 openai, anthropic 等)
    api_key: sk-xxxxxxxx # 您的 DeepSeek API 密钥 (需要替换)
    url: [https://api.deepseek.com/v1/chat/completions](https://api.deepseek.com/v1/chat/completions) # API 的聊天完成端点

# 构建提示的模板
template:
  # 用于总结最近对话内容，为 LLM 提供上下文的模板
  salon_cache:
    prefix: | # 对话摘要前的固定文本
      以下是最近的对话内容总结 (按发言顺序):
      ---
    speaker: | # 每条发言的格式
      {speaker} 说:
      {message}
      ---
    suffix: | # 对话摘要后的固定文本
      请基于以上对话和当前讨论主题进行发言。
    round_index: | # 显示当前轮次和总轮次的文本格式
      本次讨论共 {total_rounds} 轮，现在是第 {current_round} 轮。请确保讨论能在预定轮次内达成目标。

  # 通用发言者的基础系统提示模板
  system_prompt:
    prefix: | # 系统提示的前缀部分
      你是 {role}。

      本次群聊的核心目标是:
      {topic}

      你的角色设定如下:
      {role_prompt}

      其他参与者包括:
      ---
    chatter: | # 列出其他参与者及其角色设定的格式
      {role}: {role_prompt}
      ---
    suffix: | # 系统提示的后缀部分，包含核心指南
      核心指南:
      1. 你的回复必须简洁、专业，并严格符合你的角色设定。
      2. 始终围绕你的核心观点和任务进行。

  # 主持人的系统提示模板
  hoster_prompt: # 结构与 system_prompt 类似，但针对主持人的职责
    prefix: |
      你是 {role}。

      本次群聊的核心目标是:
      {topic}

      你的角色设定如下:
      {role_prompt}

      其他参与者包括:
      ---
    chatter: |
      {role}: {role_prompt}
      ---
    suffix: |
      核心指南:
      1. 你的回复必须简洁、公正，并严格符合你的角色设定。
      2. 你的主要职责是引导讨论、总结进展、并在适当时推动任务完成。

# 各个发言者的配置
chatters:
  学生: # 发言者的名称/角色，例如 "学生诗人"
    provider: deepseek # 使用哪个 API 提供商 (来自上面的 providers 定义)
    model_name: DeepSeek-V3-Fast # 使用的具体 LLM 模型名称
    system_prompt: | # 该角色的详细设定、任务和行为指令
      ===
      角色: 充满热情的青年诗人
      # ... (详细的角色描述和行为指令)
      ===
    temperature: 1.5 # LLM 的温度参数，控制输出的随机性。较高值更具创造性。
    top_p: 0.95 # LLM 的 top_p (nucleus sampling) 参数，控制输出的多样性。

  老师: # 另一个发言者的配置，例如 "诗歌评审专家"
    provider: deepseek
    model_name: DeepSeek-V3-Fast
    system_prompt: |
      ===
      角色: 汉语言文学教授 (诗歌评审专家)
      # ... (详细的角色描述和行为指令)
      ===
    temperature: 0.5 # 较低的温度，使输出更精确、分析性和一致。
    top_p: 0.9

# 主持人/协调者的配置
hoster:
  name: "主持人" # 主持人的显示名称
  provider: deepseek
  model_name: DeepSeek-V3-Fast
  system_prompt: | # 主持人的详细角色设定、核心任务和职责
    ===
    角色: 诗歌工作坊引导者 (主持人)
    # ... (详细的主持人职责和交互框架)
    成功标准 (主持人需确保最终成果满足以下所有条件):
    # ... (主持人需要确保达成的目标)
    ===
  temperature: 0.7 # 适中的温度，用于平衡引导的灵活性和一致性。
  top_p: 0.95

# LLM Salon 的中心主题/议题
topic: |
  请以“这么近，那么美，周末到河北”为主题，创作一首符合“江城子”词牌格律的词。

# 最大讨论轮次
rounds: 20