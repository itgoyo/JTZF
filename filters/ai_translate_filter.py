import logging
import os
import re

from filters.base_filter import BaseFilter
from ai import get_ai_provider
from utils.constants import DEFAULT_AI_MODEL

logger = logging.getLogger(__name__)


class AITranslateFilter(BaseFilter):
    """
    AI 自动翻译过滤器。
    - 开关关闭时不处理。
    - 只要消息有文字，就先检测是否为中文。
    - 非中文则翻译为中文。
    - 翻译失败重试 1 次，仍失败则保留原文继续流程。
    """

    async def _process(self, context):
        rule = context.rule

        if not getattr(rule, 'enable_ai_translate', False):
            return True

        message_text = (context.message_text or '').strip()
        if not message_text:
            return True

        try:
            # 若文本中有明显中文，直接跳过翻译
            if self._contains_chinese(message_text):
                logger.info('[AITranslate] 检测到中文内容，跳过翻译')
                return True

            translated = await self._translate_with_retry(message_text, retries=1)
            if translated and translated.strip() and not self._is_ai_failure_text(translated):
                context.message_text = translated.strip()
                logger.info('[AITranslate] 翻译成功，已替换为中文文本')
            else:
                logger.warning('[AITranslate] 翻译失败，保留原文继续处理')

        except Exception as e:
            logger.warning(f'[AITranslate] 处理出错，保留原文: {e}', exc_info=True)

        return True

    async def _translate_with_retry(self, text: str, retries: int = 1) -> str:
        attempts = 0
        last_result = ''
        while attempts <= retries:
            attempts += 1
            result = await self._translate_once(text)
            last_result = result or ''
            if result and result.strip() and not self._is_ai_failure_text(result):
                return result
            logger.warning(f'[AITranslate] 第 {attempts} 次翻译失败')
        return last_result

    async def _translate_once(self, text: str) -> str:
        model = os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)
        provider = await get_ai_provider(model)
        prompt = (
            '你是一个专业翻译助手。请判断输入文本是否为中文。\n'
            '1) 如果已经是中文，原样返回，不要改写。\n'
            '2) 如果不是中文，准确翻译为简体中文后返回。\n'
            '3) 只返回最终文本本身，不要解释。'
        )
        logger.info(f'[AITranslate] 开始翻译，模型: {model}，文本长度: {len(text)}')
        return await provider.process_message(message=text, prompt=prompt)

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        return bool(re.search(r'[\u4e00-\u9fff]', text or ''))

    @staticmethod
    def _is_ai_failure_text(text):
        if not text:
            return True

        normalized = str(text).strip().lower()
        failure_markers = (
            'ai处理失败',
            'error code:',
            'forbidden',
            '初始化',
            'api 调用失败',
        )
        return any(marker in normalized for marker in failure_markers)
