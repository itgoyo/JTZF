import logging
import os

from filters.base_filter import BaseFilter
from ai import get_ai_provider
from utils.constants import DEFAULT_AI_MODEL, DEFAULT_AI_REWRITE_PROMPT

logger = logging.getLogger(__name__)


class AIRewriteFilter(BaseFilter):
    """
    AI改写过滤器。
    使用 AI 对消息文本进行改写，以 AI 输出替换 context.message_text。
    - 仅处理有文本内容的消息。
    - 若 AI 调用失败，放行原文，不影响后续处理。
    - 执行顺序在 AIAdRemovalFilter 之后，在 AIFilter (is_ai) 之前。
    """

    async def _process(self, context):
        rule = context.rule

        if not getattr(rule, 'enable_ai_rewrite', False):
            return True

        message_text = context.message_text
        if not message_text or not message_text.strip():
            # 无文本内容，跳过
            return True

        try:
            model = os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)
            prompt = getattr(rule, 'ai_rewrite_prompt', None) or DEFAULT_AI_REWRITE_PROMPT

            provider = await get_ai_provider(model)

            logger.info(f"[AIRewrite] 开始改写消息，模型: {model}，原文长度: {len(message_text)}")
            logger.info(f"[AIRewrite] 消息内容（前100字）: {message_text[:100]}")
            rewritten = await provider.process_message(
                message=message_text,
                prompt=prompt
            )

            if self._is_ai_failure_text(rewritten):
                logger.warning(f"[AIRewrite] AI改写失败，保留原文: {rewritten}")
            elif rewritten and rewritten.strip():
                logger.info(f"[AIRewrite] 改写完成，新文本长度: {len(rewritten)}")
                logger.info(f"[AIRewrite] 改写结果（前200字）: {rewritten[:200]}")
                context.message_text = rewritten.strip()
            else:
                logger.warning("[AIRewrite] AI返回内容为空，保留原文")

        except Exception as e:
            logger.warning(f"[AIRewrite] 处理出错，放行原文: {e}", exc_info=True)

        return True

    @staticmethod
    def _is_ai_failure_text(text):
        """识别提供商返回的错误文本，避免把错误信息当正文发送。"""
        if not text:
            return False

        normalized = str(text).strip().lower()
        failure_markers = (
            'ai处理失败',
            'error code:',
            'forbidden',
            '初始化',
            'api 调用失败',
        )
        return any(marker in normalized for marker in failure_markers)
