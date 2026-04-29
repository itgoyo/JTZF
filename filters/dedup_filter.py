import hashlib
import logging
import os
import time

from filters.base_filter import BaseFilter

logger = logging.getLogger(__name__)

# 全局去重存储：{rule_id: {md5_hash: expire_timestamp}}
_DEDUP_STORE: dict[int, dict[str, float]] = {}


def _md5(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


class DedupFilter(BaseFilter):
    """
    重复消息去重过滤器。
    在同一时间窗口内，如果同一规则已转发过内容相同的消息，则跳过。
    通过环境变量控制：
        DEDUP_ENABLED=true/false  （默认 false，不启用）
        DEDUP_WINDOW_SECONDS=86400 （默认 24 小时）
    """

    async def _process(self, context):
        # 未启用则放行
        if os.getenv('DEDUP_ENABLED', 'false').lower() != 'true':
            return True

        message_text = (context.message_text or '').strip()
        if not message_text:
            # 纯媒体消息不做去重
            return True

        rule = context.rule
        rule_id = rule.id
        window = int(os.getenv('DEDUP_WINDOW_SECONDS', '86400'))
        now = time.time()
        content_hash = _md5(message_text)

        if rule_id not in _DEDUP_STORE:
            _DEDUP_STORE[rule_id] = {}

        store = _DEDUP_STORE[rule_id]

        # 清理过期条目
        expired = [h for h, exp in store.items() if exp <= now]
        for h in expired:
            del store[h]

        if content_hash in store:
            logger.info(
                f'[DedupFilter] rule_id={rule_id} 检测到重复消息，已跳过。'
                f' hash={content_hash} 文本前50字: {message_text[:50]!r}'
            )
            return False  # 阻断转发

        # 写入记录
        store[content_hash] = now + window
        logger.info(
            f'[DedupFilter] rule_id={rule_id} 新消息已记录，hash={content_hash}，'
            f'窗口={window}s，当前记录数={len(store)}'
        )
        return True
