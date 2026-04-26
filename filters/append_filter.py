import logging
from filters.base_filter import BaseFilter
from models.models import AppendRule, get_session

logger = logging.getLogger(__name__)


class AppendFilter(BaseFilter):
    """在消息末尾追加配置文本"""

    async def _process(self, context):
        if context.rule.only_rss:
            return True

        session = get_session()
        try:
            append_rule = session.query(AppendRule).filter_by(rule_id=context.rule.id).first()
            if not append_rule or not append_rule.enabled or not append_rule.content:
                return True

            base = context.message_text or ""
            if base:
                context.message_text = f"{base}\n\n{append_rule.content}"
            else:
                context.message_text = append_rule.content

            context.check_message_text = context.message_text
            context.append_parse_mode = append_rule.parse_mode  # None / Markdown / HTML
            logger.info(f"规则 {context.rule.id} 已追加文本")
            return True
        except Exception as e:
            logger.error(f"AppendFilter 出错: {e}")
            context.errors.append(f"AppendFilter 错误: {e}")
            return True
        finally:
            session.close()
