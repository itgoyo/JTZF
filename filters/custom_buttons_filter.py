import logging
from telethon import Button

from filters.base_filter import BaseFilter
from models.models import ButtonRule, get_session
from utils.append_button_utils import deserialize_button_rows

logger = logging.getLogger(__name__)


class CustomButtonsFilter(BaseFilter):
    """处理 /buttons：启用时强制覆盖按钮，未启用时保留原帖按钮"""

    async def _process(self, context):
        if context.rule.only_rss:
            return True

        # 默认不是严格自定义按钮模式
        context.strict_custom_buttons = False

        session = get_session()
        try:
            button_rule = session.query(ButtonRule).filter_by(rule_id=context.rule.id).first()
            if not button_rule or not button_rule.enabled or not button_rule.buttons_json:
                # 未配置 /buttons：保留已有按钮（原帖按钮/评论按钮等）
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

            # 开启 /buttons：强制覆盖，移除原帖自带及其它流程注入的按钮
            context.buttons = ad_rows
            context.strict_custom_buttons = True

            logger.info(f"规则 {context.rule.id} 启用 /buttons，已覆盖为 {sum(len(x) for x in ad_rows)} 个自定义按钮")
            return True
        except Exception as e:
            logger.error(f"CustomButtonsFilter 出错: {e}")
            context.errors.append(f"CustomButtonsFilter 错误: {e}")
            return True
        finally:
            session.close()
