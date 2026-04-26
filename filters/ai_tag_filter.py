import logging
import re
from filters.base_filter import BaseFilter
from ai import get_ai_provider

logger = logging.getLogger(__name__)

# 检测文本中是否已有 Telegram 标签（#word 或 #中文）
_TAG_RE = re.compile(r'#[\w\u4e00-\u9fff]+')

# 清洗 AI 返回的单个标签词，去掉多余符号
_CLEAN_RE = re.compile(r'[#\s，,。.、！!？?:：]+')

# AI 返回错误字符串时的特征词（openai_base_provider 固定格式）
_ERROR_PREFIXES = ('AI处理失败', 'AI处理出错', '模型未能生成', 'Error', 'error')

# 标签词中不应出现的非法字符（数字冒号等单独出现说明是错误文本）
_INVALID_TAG_RE = re.compile(r'^[\d:：]+$')


def _is_error_response(text: str) -> bool:
    """判断 AI 返回的是否是错误字符串而非正常标签"""
    stripped = text.strip()
    for prefix in _ERROR_PREFIXES:
        if stripped.startswith(prefix):
            return True
    return False


class AITagFilter(BaseFilter):
    """
    AI 自动打标签过滤器。

    规则：
    1. 仅当规则开启 enable_ai_tag 时生效。
    2. 原文中已存在 #标签 → 跳过，直接使用原标签。
    3. 文本长度 < ai_tag_min_length（默认100）→ 不打标签。
    4. 否则调用 AI 生成最多 ai_tag_max_count 个标签，追加到消息末尾。
    5. AI 返回错误字符串或空结果 → 静默跳过，不修改消息。
    """

    async def _process(self, context):
        rule = context.rule

        if not rule.enable_ai_tag:
            return True

        message_text = context.message_text
        if not message_text:
            return True

        # 原文已有标签 → 无需 AI，直接跳过
        if _TAG_RE.search(message_text):
            logger.info(f'[AITagFilter] 规则 {rule.id}: 原文已含标签，跳过 AI 打标')
            return True

        min_len = rule.ai_tag_min_length or 100
        if len(message_text) < min_len:
            logger.info(f'[AITagFilter] 规则 {rule.id}: 文本长度 {len(message_text)} < {min_len}，跳过打标')
            return True

        max_count = rule.ai_tag_max_count or 3
        model = rule.ai_tag_model or None

        prompt = (
            f'请根据以下文本内容，提取最多 {max_count} 个最能概括主题的关键词作为标签。'
            '要求：\n'
            '1. 标签语言与原文语言保持一致。\n'
            '2. 每个标签用空格分隔，只输出标签词本身，不要 # 号，不要任何解释。\n'
            '3. 标签数量不超过规定数量。\n'
            '示例输出：人工智能 机器学习 深度学习'
        )

        try:
            provider = await get_ai_provider(model)
            raw = await provider.process_message(message_text, prompt=prompt)
            logger.info(f'[AITagFilter] AI 返回原始内容: {raw!r}')

            # AI 提供商返回错误字符串时静默跳过
            if _is_error_response(raw):
                logger.warning(f'[AITagFilter] 规则 {rule.id}: AI 返回错误，跳过打标: {raw!r}')
                return True

            # 解析标签：兼容空格/逗号/换行分隔
            parts = re.split(r'[\s,，\n]+', raw.strip())
            tags = []
            for p in parts:
                p = _CLEAN_RE.sub('', p).strip()
                # 过滤空词、纯数字/冒号（错误文本碎片）、过长的词（非正常标签）
                if not p or _INVALID_TAG_RE.match(p) or len(p) > 20:
                    continue
                tags.append(f'#{p}')
                if len(tags) >= max_count:
                    break

            if tags:
                tag_str = ' '.join(tags)
                context.message_text = f'{message_text}\n\n{tag_str}'
                logger.info(f'[AITagFilter] 规则 {rule.id}: 追加标签 {tag_str}')
            else:
                logger.warning(f'[AITagFilter] 规则 {rule.id}: AI 未返回有效标签，跳过')

        except Exception as e:
            logger.error(f'[AITagFilter] 规则 {rule.id}: 打标签时出错: {e}', exc_info=True)
            # 打标失败不中断消息转发，继续处理链

        return True
