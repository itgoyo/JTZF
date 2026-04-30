"""
智能广告过滤器
在消息转发时，根据内容智能匹配并追加广告按钮
"""
import asyncio
import logging
from telethon import Button

from filters.base_filter import BaseFilter
from utils.smart_ad_utils import smart_ad_config, smart_ad_cooldown
from ai.smart_ad_analyzer import smart_ad_analyzer

logger = logging.getLogger(__name__)


class SmartAdFilter(BaseFilter):
    """智能广告过滤器：AI语义分析帖子内容，自动追加匹配的广告按钮"""

    async def _process(self, context):
        rule = context.rule

        # 未启用则跳过
        if not getattr(rule, 'enable_smart_ad', False):
            return True

        if context.rule.only_rss:
            return True

        message_text = context.message_text
        if not message_text or not message_text.strip():
            return True

        try:
            # 获取配置参数
            threshold = getattr(rule, 'smart_ad_threshold', None)
            if not threshold:
                threshold = 0.7
            max_count = getattr(rule, 'smart_ad_max_count', None) or 3
            cooldown_minutes = getattr(rule, 'smart_ad_cooldown', None) or 30

            # 获取所有广告
            all_ads = smart_ad_config.get_all_ads()
            if not all_ads:
                logger.info(f"[SmartAd] 规则 {rule.id} 广告库为空，跳过")
                return True

            # AI分析匹配
            matched_ads = await smart_ad_analyzer.analyze(
                text=message_text,
                rule=rule,
                ads=all_ads,
                threshold=threshold,
            )

            if not matched_ads:
                logger.info(f"[SmartAd] 规则 {rule.id} 未命中任何广告")
                return True

            # 过滤冷却中的广告
            available_ads = [
                ad for ad in matched_ads
                if not smart_ad_cooldown.is_cooling(rule.id, ad['id'])
            ]

            if not available_ads:
                logger.info(f"[SmartAd] 规则 {rule.id} 所有命中广告均在冷却中")
                return True

            # 限制最大数量
            selected_ads = available_ads[:max_count]

            # 并发生成所有广告的动态文案（避免串行 AI 调用）
            copywrite_tasks = [
                smart_ad_analyzer.generate_copywrite(
                    text=message_text, ad=ad, rule=rule
                )
                for ad in selected_ads
            ]
            copywrite_results = await asyncio.gather(*copywrite_tasks, return_exceptions=True)

            # 构建广告按钮
            ad_buttons = []
            for ad, copywrite in zip(selected_ads, copywrite_results):
                # generate_copywrite 失败时返回 Exception，视为 None
                if isinstance(copywrite, Exception) or not copywrite:
                    btn_text = f"{ad.get('emoji', '')} {ad.get('name', '')}".strip()
                else:
                    btn_text = f"{ad.get('emoji', '')} {copywrite}".strip()

                url = ad.get('url', '')
                if btn_text and url:
                    ad_buttons.append([Button.url(btn_text, url)])
                    smart_ad_cooldown.set_cooling(rule.id, ad['id'], cooldown_minutes)
                    logger.info(f"[SmartAd] 规则 {rule.id} 追加广告按钮: {btn_text}")

            if not ad_buttons:
                return True

            # 追加到 context.buttons
            if context.buttons:
                context.buttons.extend(ad_buttons)
            else:
                context.buttons = ad_buttons

            logger.info(f"[SmartAd] 规则 {rule.id} 共追加 {len(ad_buttons)} 个智能广告按钮")

        except Exception as e:
            logger.error(f"[SmartAd] SmartAdFilter 出错: {e}", exc_info=True)
            # 出错不影响正常转发

        return True
