from .base import BaseAIProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .qwen_provider import QwenProvider
from .grok_provider import GrokProvider
from .claude_provider import ClaudeProvider
import os
import logging
from utils.settings import load_ai_models
from utils.constants import DEFAULT_AI_MODEL

# 获取日志记录器
logger = logging.getLogger(__name__)

async def get_ai_provider(model=None):
    """获取AI提供者实例"""
    if not model:
        model = DEFAULT_AI_MODEL
    
    # 加载提供商配置（使用dict格式）
    providers_config = load_ai_models(type="dict")
    
    # 根据模型名称选择对应的提供者
    provider = None
    
    # 遍历配置中的每个提供商
    for provider_name, models_list in providers_config.items():
        # 检查完全匹配
        if model in models_list:
            if provider_name == "openai":
                provider = OpenAIProvider()
            elif provider_name == "groq_compatible":
                # 通过 OPENAI 兼容接口访问的第三方模型（如 Groq）
                provider = OpenAIProvider()
            elif provider_name == "gemini":
                provider = GeminiProvider()
            elif provider_name == "deepseek":
                provider = DeepSeekProvider()
            elif provider_name == "qwen":
                provider = QwenProvider()
            elif provider_name == "grok":
                provider = GrokProvider()
            elif provider_name == "claude":
                provider = ClaudeProvider()
            break
    
    if provider:
        # 无论哪种提供商，都必须把实际请求的模型名设置进去
        provider.default_model = model
        logger.info(f"使用提供商处理模型: {model}")
    else:
        # 模型不在配置列表中，尝试用 OpenAI 兼容接口（支持 Groq/第三方 API）
        logger.warning(f"模型 {model} 未在配置列表中找到，尝试使用 OpenAI 兼容接口")
        provider = OpenAIProvider()
        provider.default_model = model

    return provider


__all__ = [
    'BaseAIProvider',
    'OpenAIProvider',
    'GeminiProvider',
    'DeepSeekProvider',
    'QwenProvider',
    'GrokProvider',
    'ClaudeProvider',
    'get_ai_provider'
]