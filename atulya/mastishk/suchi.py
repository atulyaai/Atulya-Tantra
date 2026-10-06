"""Suchi (सूची): the provider catalog -- Spec, CATALOG and BY_ID."""
from __future__ import annotations

from dataclasses import dataclass




# ── suchi ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Spec:
    id: str
    label: str
    key_var: str
    model_var: str
    default_model: str
    base_url: str = ""          # OpenAI-style base (…/v1); empty for builtin classes
    free: str = "paid"          # "free" | "free tier" | "paid" | "local"
    docs: str = ""              # where to get a key
    builtin: bool = False


CATALOG: list[Spec] = [
    # Own classes
    Spec("anthropic", "Claude (Anthropic)", "ANTHROPIC_API_KEY", "ATULYA_CLAUDE_MODEL", "claude-haiku-4-5-20251001",
         free="paid", docs="https://console.anthropic.com/settings/keys", builtin=True),
    Spec("openai", "ChatGPT / OpenAI", "OPENAI_API_KEY", "ATULYA_OPENAI_MODEL", "gpt-4o-mini",
         free="paid", docs="https://platform.openai.com/api-keys", builtin=True),
    Spec("gemini", "Google Gemini", "GEMINI_API_KEY", "ATULYA_GEMINI_MODEL", "gemini-1.5-flash",
         free="free tier", docs="https://aistudio.google.com/app/apikey", builtin=True),
    Spec("groq", "Groq (very fast)", "GROQ_API_KEY", "ATULYA_GROQ_MODEL", "llama-3.3-70b-versatile",
         free="free tier", docs="https://console.groq.com/keys", builtin=True),
    Spec("nvidia", "NVIDIA NIM", "NVIDIA_API_KEY", "ATULYA_NVIDIA_MODEL", "meta/llama-3.1-8b-instruct",
         free="free tier", docs="https://build.nvidia.com/", builtin=True),
    Spec("openrouter", "OpenRouter (many models, free ones)", "OPENROUTER_API_KEY", "ATULYA_OPENROUTER_MODEL",
         "qwen/qwen3.8-27b:free", free="free tier", docs="https://openrouter.ai/keys", builtin=True),
    Spec("opencode", "OpenCode Go", "OPENCODE_API_KEY", "ATULYA_OPENCODE_MODEL", "deepseek-v4-flash",
         free="paid", docs="https://opencode.ai/auth", builtin=True),
    # One generic class, many providers
    Spec("mistral", "Mistral", "MISTRAL_API_KEY", "ATULYA_MISTRAL_MODEL", "mistral-small-latest",
         "https://api.mistral.ai/v1", "free tier", "https://console.mistral.ai/api-keys"),
    Spec("deepseek", "DeepSeek", "DEEPSEEK_API_KEY", "ATULYA_DEEPSEEK_MODEL", "deepseek-chat",
         "https://api.deepseek.com/v1", "paid", "https://platform.deepseek.com/api_keys"),
    Spec("qwen", "Qwen (Alibaba DashScope)", "DASHSCOPE_API_KEY", "ATULYA_QWEN_MODEL", "qwen-plus",
         "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "free tier", "https://bailian.console.alibabacloud.com/"),
    Spec("xai", "Grok (xAI)", "XAI_API_KEY", "ATULYA_XAI_MODEL", "grok-4",
         "https://api.x.ai/v1", "paid", "https://console.x.ai/"),
    Spec("together", "Together AI", "TOGETHER_API_KEY", "ATULYA_TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo",
         "https://api.together.xyz/v1", "free tier", "https://api.together.ai/settings/api-keys"),
    Spec("fireworks", "Fireworks AI", "FIREWORKS_API_KEY", "ATULYA_FIREWORKS_MODEL", "accounts/fireworks/models/llama-v3p3-70b-instruct",
         "https://api.fireworks.ai/inference/v1", "free tier", "https://fireworks.ai/account/api-keys"),
    Spec("cerebras", "Cerebras (very fast)", "CEREBRAS_API_KEY", "ATULYA_CEREBRAS_MODEL", "llama-3.3-70b",
         "https://api.cerebras.ai/v1", "free tier", "https://cloud.cerebras.ai/"),
    Spec("sambanova", "SambaNova", "SAMBANOVA_API_KEY", "ATULYA_SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct",
         "https://api.sambanova.ai/v1", "free tier", "https://cloud.sambanova.ai/apis"),
    Spec("perplexity", "Perplexity (web answers)", "PERPLEXITY_API_KEY", "ATULYA_PERPLEXITY_MODEL", "sonar",
         "https://api.perplexity.ai", "paid", "https://www.perplexity.ai/settings/api"),
    Spec("moonshot", "Kimi (Moonshot)", "MOONSHOT_API_KEY", "ATULYA_MOONSHOT_MODEL", "kimi-k2-0905-preview",
         "https://api.moonshot.ai/v1", "paid", "https://platform.moonshot.ai/console/api-keys"),
    Spec("zhipu", "GLM (Zhipu)", "ZHIPU_API_KEY", "ATULYA_ZHIPU_MODEL", "glm-4-flash",
         "https://open.bigmodel.cn/api/paas/v4", "free tier", "https://open.bigmodel.cn/usercenter/apikeys"),
    Spec("siliconflow", "SiliconFlow", "SILICONFLOW_API_KEY", "ATULYA_SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct",
         "https://api.siliconflow.com/v1", "free tier", "https://cloud.siliconflow.com/account/ak"),
    Spec("huggingface", "Hugging Face", "HF_TOKEN", "ATULYA_HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct",
         "https://router.huggingface.co/v1", "free tier", "https://huggingface.co/settings/tokens"),
    Spec("github", "GitHub Models", "GITHUB_MODELS_TOKEN", "ATULYA_GITHUB_MODEL", "openai/gpt-4o-mini",
         "https://models.github.ai/inference", "free tier", "https://github.com/settings/tokens"),
    Spec("custom", "Your own (LM Studio, vLLM, any OpenAI-style URL)", "ATULYA_CUSTOM_KEY", "ATULYA_CUSTOM_MODEL", "",
         "", "local", ""),
]
BY_ID = {s.id: s for s in CATALOG}


