import logging
import os
from telethon import Button

from filters.base_filter import BaseFilter
from models.models import ButtonRule, get_session
from utils.append_button_utils import deserialize_button_rows

logger = logging.getLogger(__name__)


class FinalButtonsGuardFilter(BaseFilter):
    """最终按钮守卫：配置 /buttons 时只保留其按钮；未配置时保留现有按钮"""

    async def _process(self, context):
        if context.rule.only_rss:
            return True

        # 提供给后续过滤器（如 ReplyFilter）的严格策略标记
        context.strict_custom_buttons = True

        session = get_session()
        try:
            button_rule = session.query(ButtonRule).filter_by(rule_id=context.rule.id).first()

            db_abs_path = os.path.abspath('./db/forward.db')
            logger.info(
                "[FinalButtonsGuard] db=%s rule_id=%s is_media_group=%s button_rule_hit=%s enabled=%s json_len=%s",
                db_abs_path,
                context.rule.id,
                bool(getattr(context, 'is_media_group', False)),
                bool(button_rule),
                getattr(button_rule, 'enabled', None),
                len(getattr(button_rule, 'buttons_json', '') or '') if button_rule else 0,
            )

            # 未启用 /buttons 或无有效配置：保留当前按钮（含原帖按钮）
            if not button_rule or not button_rule.enabled or not button_rule.buttons_json:
                logger.info(f"规则 {context.rule.id} 未启用 /buttons，保留现有按钮")
                return True

            rows = deserialize_button_rows(button_rule.buttons_json)
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
                logger.info(f"规则 {context.rule.id} /buttons 配置无有效按钮，保留现有按钮")
                return True

            # 强制覆盖：最终只保留用户自定义按钮
            context.buttons = ad_rows
            logger.info(f"规则 {context.rule.id} 最终按钮守卫生效，仅保留 {sum(len(x) for x in ad_rows)} 个自定义按钮")
            return True
        except Exception as e:
            logger.error(f"FinalButtonsGuardFilter 出错: {e}")
            context.errors.append(f"FinalButtonsGuardFilter 错误: {e}")
            return True
        finally:
            session.close()
