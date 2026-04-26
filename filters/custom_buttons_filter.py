import logging
from telethon import Button

from filters.base_filter import BaseFilter
from models.models import ButtonRule, get_session
from utils.append_button_utils import deserialize_button_rows

logger = logging.getLogger(__name__)


class CustomButtonsFilter(BaseFilter):
    """给转发消息追加自定义广告按钮"""

    async def _process(self, context):
        if context.rule.only_rss:
            return True

        session = get_session()
        try:
            button_rule = session.query(ButtonRule).filter_by(rule_id=context.rule.id).first()
            if not button_rule or not button_rule.enabled or not button_rule.buttons_json:
                return True

            rows = deserialize_button_rows(button_rule.buttons_json)
            if not rows:
                return True

            ad_rows = []
            for row in rows:
                line = []
                for btn in row:
                    text = (btn or {}).get("text", "").strip()
                    url = (btn or {}).get("url", "").strip()
                    if text and url:
                        line.append(Button.url(text, url))
                if line:
                    ad_rows.append(line)

            if not ad_rows:
                return True

            if context.buttons:
                context.buttons.extend(ad_rows)
            else:
                context.buttons = ad_rows

            logger.info(f"规则 {context.rule.id} 已追加 {sum(len(x) for x in ad_rows)} 个按钮")
            return True
        except Exception as e:
            logger.error(f"CustomButtonsFilter 出错: {e}")
            context.errors.append(f"CustomButtonsFilter 错误: {e}")
            return True
        finally:
            session.close()
