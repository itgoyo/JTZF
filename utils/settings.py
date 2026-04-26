import os
import json
import logging

from utils.file_creator import create_default_configs, AI_MODELS_CONFIG

logger = logging.getLogger(__name__)

def load_ai_models(type="list"):
    """
    加载AI模型配置
    
    参数:
        type (str): 返回类型
            - "list": 返回所有模型的平铺列表 [model1, model2, ...]
            - "dict"/"json": 返回原始配置格式 {provider: [model1, model2, ...]}
    
    返回值:
        根据type参数返回不同格式的模型配置
    """
    try:
        models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'ai_models.json')
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(models_path):
            create_default_configs()
            
        # 读取JSON配置文件
        with open(models_path, 'r', encoding='utf-8') as f:
            models_config = json.load(f)
            
            # 根据type参数返回不同格式
            if type.lower() in ["dict", "json"]:
                return models_config
            
            # 默认返回模型列表
            all_models = []
            for provider, models in models_config.items():
                all_models.extend(models)
                
            # 确保列表不为空
            if all_models:
                return all_models
                
    except (FileNotFoundError, IOError, json.JSONDecodeError) as e:
        logger.error(f"加载AI模型配置失败: {e}")
    
    # 如果出现任何问题，根据type返回默认值
    if type.lower() in ["dict", "json"]:
        return AI_MODELS_CONFIG
    
    # 默认返回模型列表
    return ["gpt-3.5-turbo", "gemini-1.5-flash", "claude-3-sonnet"]


def get_available_models():
    """
    返回已配置 API Key 的提供商的模型列表。
    只显示用户真正能用的模型，避免选了不支持的模型报错。

    特殊规则：
    - openai: 仅当 OPENAI_API_BASE 为空或指向 openai.com 时才显示 GPT 模型
    - groq_compatible: OPENAI_API_KEY 已设且 OPENAI_API_BASE 指向第三方（如 groq.com）时显示
    """
    OFFICIAL_OPENAI_BASES = ('', 'https://api.openai.com', 'https://api.openai.com/v1')

    try:
        models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'ai_models.json')
        with open(models_path, 'r', encoding='utf-8') as f:
            models_config = json.load(f)
    except Exception as e:
        logger.error(f"加载AI模型配置失败: {e}")
        default_model = os.getenv('DEFAULT_AI_MODEL', 'gpt-4o-mini')
        return [default_model]

    openai_key = os.getenv('OPENAI_API_KEY', '').strip()
    openai_base = os.getenv('OPENAI_API_BASE', '').strip().rstrip('/')

    available = []
    for provider_name, models in models_config.items():
        if provider_name == 'openai':
            # 只有真正的 OpenAI 接口才显示 GPT 模型
            if openai_key and not openai_key.lower().startswith('your_'):
                if openai_base in OFFICIAL_OPENAI_BASES or 'openai.com' in openai_base:
                    available.extend(models)
        elif provider_name == 'groq_compatible':
            # OPENAI_API_KEY 设置了第三方 Base（如 Groq）时显示这些模型
            if openai_key and not openai_key.lower().startswith('your_'):
                if openai_base and 'openai.com' not in openai_base:
                    available.extend(models)
        else:
            # 其他提供商：检查对应的 API Key
            key_map = {
                'gemini': 'GEMINI_API_KEY',
                'deepseek': 'DEEPSEEK_API_KEY',
                'qwen': 'QWEN_API_KEY',
                'grok': 'GROK_API_KEY',
                'claude': 'CLAUDE_API_KEY',
            }
            key_name = key_map.get(provider_name, '')
            if key_name:
                key_value = os.getenv(key_name, '').strip()
                if key_value and not key_value.lower().startswith('your_'):
                    available.extend(models)

    # 如果没有任何有效模型，回退到全量列表
    if not available:
        for models in models_config.values():
            available.extend(models)

    # DEFAULT_AI_MODEL 始终确保在列表顶部
    default_model = os.getenv('DEFAULT_AI_MODEL', '').strip()
    if default_model and default_model not in available:
        available.insert(0, default_model)

    return available


def load_summary_times():
    """加载总结时间列表"""
    try:
        times_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'summary_times.txt')
        if not os.path.exists(times_path):
            create_default_configs()
            
        with open(times_path, 'r', encoding='utf-8') as f:
            times = [line.strip() for line in f if line.strip()]
            if times:
                return times
    except (FileNotFoundError, IOError) as e:
        logger.warning(f"summary_times.txt 加载失败: {e}，使用默认时间列表")
    return ['00:00', '06:00', '12:00', '18:00']

def load_delay_times():
    """加载延迟时间列表"""
    try:
        times_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'delay_times.txt')
        if not os.path.exists(times_path):
            create_default_configs()
            
        with open(times_path, 'r', encoding='utf-8') as f:
            times = [line.strip() for line in f if line.strip()]
            if times:
                return times
    except (FileNotFoundError, IOError) as e:
        logger.warning(f"delay_times.txt 加载失败: {e}，使用默认时间列表")
    return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def load_max_media_size():
    """加载媒体大小限制"""
    try:
        size_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'max_media_size.txt')
        if not os.path.exists(size_path):
            create_default_configs()
            
        with open(size_path, 'r', encoding='utf-8') as f:
            size = [line.strip() for line in f if line.strip()]
            if size:
                return size
            
    except (FileNotFoundError, IOError) as e:
        logger.warning(f"max_media_size.txt 加载失败: {e}，使用默认大小限制")
    return [5,10,15,20,50,100,200,300,500,1024,2048]


def load_media_extensions():
    """加载媒体扩展名"""
    try:
        size_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'media_extensions.txt')
        if not os.path.exists(size_path):
            create_default_configs()
            
        with open(size_path, 'r', encoding='utf-8') as f:
            size = [line.strip() for line in f if line.strip()]
            if size:
                return size
            
    except (FileNotFoundError, IOError) as e:
        logger.warning(f"media_extensions.txt 加载失败: {e}，使用默认扩展名")
    return ['无扩展名','txt','jpg','png','gif','mp4','mp3','wav','ogg','flac','aac','wma','m4a','m4v','mov','avi','mkv','webm','mpg','mpeg','mpe','mp3','mp2','m4a','m4p','m4b','m4r','m4v','mpg','mpeg','mp2','mp3','mp4','mpc','oga','ogg','wav','wma','3gp','3g2','3gpp','3gpp2','amr','awb','caf','flac','m4a','m4b','m4p','oga','ogg','opus','spx','vorbis','wav','wma','webm','aac','ac3','dts','dtshd','flac','mp3','mp4','m4a','m4b','m4p','oga','ogg','wav','wma','webm','aac','ac3','dts','dtshd','flac','mp3','mp4','m4a','m4b','m4p','oga','ogg','wav','wma','webm']