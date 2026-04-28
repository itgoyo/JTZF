import json
import logging
import os

from filters.base_filter import BaseFilter
from ai import get_ai_provider
from utils.constants import DEFAULT_AI_MODEL, DEFAULT_AI_AD_REMOVAL_PROMPT, DEFAULT_AI_AD_REMOVAL_THRESHOLD

logger = logging.getLogger(__name__)


class AIAdRemovalFilter(BaseFilter):
    """
    AI去广告过滤器。
    使用 AI 分析消息文本，判断是否包含广告内容。
    - 若 AI 置信度 >= 阈值，则以去广告后的干净内容替换 context.message_text。
    - 若干净内容为空（整条消息都是广告），中断处理链（不转发）。
    - 若 AI 调用失败或置信度不足，放行原文，不影响后续处理。
    """

    async def _process(self, context):
        rule = context.rule

        if not getattr(rule, 'enable_ai_ad_removal', False):
            return True

        message_text = context.message_text
        if not message_text or not message_text.strip():
            # 无文本内容，跳过
            return True

        try:
            model = getattr(rule, 'ai_ad_removal_model', None) or os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)
            prompt = getattr(rule, 'ai_ad_removal_prompt', None) or DEFAULT_AI_AD_REMOVAL_PROMPT
            threshold = getattr(rule, 'ai_ad_removal_threshold', None)
            if threshold is None:
                threshold = DEFAULT_AI_AD_REMOVAL_THRESHOLD
            else:
                # DB stores 0-100 integer, convert to 0.0-1.0 float
                threshold = float(threshold) / 100.0

            provider = await get_ai_provider(model)

            logger.info(f"[AIAdRemoval] 开始分析消息，模型: {model}，阈值: {threshold}")
            logger.info(f"[AIAdRemoval] 消息内容（前100字）: {message_text[:100]}")
            response = await provider.process_message(
                message=f"消息内容：\n{message_text}",
                prompt=prompt
            )
            logger.info(f"[AIAdRemoval] AI原始响应: {response[:500]}")

            result = _parse_ad_response(response)
            if result is None:
                logger.warning(f"[AIAdRemoval] 解析AI响应失败，完整响应: {response[:500]}，放行原文")
                return True

            is_ad = result.get('is_ad', False)
            confidence = float(result.get('confidence', 0.0))
            clean_content = result.get('clean_content', message_text)

            logger.info(f"[AIAdRemoval] is_ad={is_ad}, confidence={confidence}, threshold={threshold}")

            if is_ad and confidence >= threshold:
                if not clean_content or not clean_content.strip():
                    logger.info("[AIAdRemoval] 整条消息为广告，中断转发")
                    context.should_forward = False
                    return False
                else:
                    logger.info(f"[AIAdRemoval] 去除广告，原文长度={len(message_text)}，清洁后长度={len(clean_content)}")
                    context.message_text = clean_content
            else:
                logger.info("[AIAdRemoval] 置信度不足或非广告，放行原文")

        except Exception as e:
            logger.warning(f"[AIAdRemoval] 处理出错，放行原文: {e}", exc_info=True)

        return True


def _parse_ad_response(response: str) -> dict | None:
    """
    从 AI 响应中解析 JSON 结果。
    支持响应中包含其他文字包裹 JSON 块的情况。
    """
    if not response:
        return None

    # 优先尝试直接解析
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    # 尝试提取 markdown 代码块中的 JSON
    import re
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'(\{[\s\S]*\})',
    ]
    for pattern in patterns:
        match = re.search(pattern, response)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    return None
