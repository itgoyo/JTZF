"""
智能广告 Callback 处理器
"""
import logging
import os

from telethon import Button

from handlers.button.button_helpers import create_model_buttons
from models.models import ForwardRule, get_session
from utils.smart_ad_utils import smart_ad_config

logger = logging.getLogger(__name__)


# ── 设置页面文本 ──────────────────────────────────────────────────

async def get_smart_ad_settings_text(rule) -> str:
    """生成智能广告设置页面的文字内容"""
    enabled = getattr(rule, 'enable_smart_ad', False)
    threshold = getattr(rule, 'smart_ad_threshold', 0.7) or 0.7
    max_count = getattr(rule, 'smart_ad_max_count', 3) or 3
    cooldown = getattr(rule, 'smart_ad_cooldown', 30) or 30
    model = getattr(rule, 'smart_ad_model', None) or os.getenv('DEFAULT_AI_MODEL', '默认')
    ad_count = smart_ad_config.count()

    threshold_label = _threshold_label(threshold)

    return (
        f"💰 智能广告设置\n\n"
        f"状态：{'✅ 开启' if enabled else '❌ 关闭'}\n"
        f"AI模型：`{model}`\n"
        f"匹配阈值：`{threshold_label}`（{threshold}）\n"
        f"单条消息最多广告数：`{max_count}` 个\n"
        f"广告冷却时间：`{cooldown}` 分钟\n"
        f"当前广告库：`{ad_count}` 条有效广告\n\n"
        f"广告库配置文件：`config/ads_config.yaml`\n"
        f"修改文件后点击「重载配置」生效"
    )


def _threshold_label(threshold: float) -> str:
    if threshold >= 0.85:
        return "严格"
    elif threshold >= 0.7:
        return "正常"
    else:
        return "宽松"


# ── 按钮布局 ──────────────────────────────────────────────────────

async def create_smart_ad_settings_buttons(rule=None, rule_id=None):
    """创建智能广告设置页面的按钮"""
    if rule is None:
        session = get_session()
        try:
            rule = session.query(ForwardRule).get(int(rule_id))
        finally:
            session.close()

    rid = rule.id
    enabled = getattr(rule, 'enable_smart_ad', False)
    threshold = getattr(rule, 'smart_ad_threshold', 0.7) or 0.7
    max_count = getattr(rule, 'smart_ad_max_count', 3) or 3
    cooldown = getattr(rule, 'smart_ad_cooldown', 30) or 30
    model = getattr(rule, 'smart_ad_model', None) or os.getenv('DEFAULT_AI_MODEL', '默认')

    buttons = [
        # 总开关
        [Button.inline(
            f"{'✅ 智能广告：开启' if enabled else '❌ 智能广告：关闭'}",
            f"toggle_smart_ad:{rid}"
        )],

        # AI模型
        [Button.inline(
            f"🤖 AI模型：{model}",
            f"change_smart_ad_model:{rid}"
        )],

        # 匹配阈值
        [
            Button.inline(
                f"{'✅ ' if threshold >= 0.85 else ''}严格(0.85)",
                f"smart_ad_threshold:{rid}:0.85"
            ),
            Button.inline(
                f"{'✅ ' if 0.65 < threshold < 0.85 else ''}正常(0.70)",
                f"smart_ad_threshold:{rid}:0.70"
            ),
            Button.inline(
                f"{'✅ ' if threshold <= 0.65 else ''}宽松(0.50)",
                f"smart_ad_threshold:{rid}:0.50"
            ),
        ],

        # 最多广告数
        [
            Button.inline(f"{'✅ ' if max_count == 1 else ''}最多1个", f"smart_ad_max_count:{rid}:1"),
            Button.inline(f"{'✅ ' if max_count == 2 else ''}最多2个", f"smart_ad_max_count:{rid}:2"),
            Button.inline(f"{'✅ ' if max_count == 3 else ''}最多3个", f"smart_ad_max_count:{rid}:3"),
            Button.inline(f"{'✅ ' if max_count == 5 else ''}最多5个", f"smart_ad_max_count:{rid}:5"),
        ],

        # 冷却时间
        [
            Button.inline(f"{'✅ ' if cooldown == 10 else ''}10分钟", f"smart_ad_cooldown:{rid}:10"),
            Button.inline(f"{'✅ ' if cooldown == 30 else ''}30分钟", f"smart_ad_cooldown:{rid}:30"),
            Button.inline(f"{'✅ ' if cooldown == 60 else ''}60分钟", f"smart_ad_cooldown:{rid}:60"),
            Button.inline(f"{'✅ ' if cooldown == 120 else ''}120分钟", f"smart_ad_cooldown:{rid}:120"),
        ],

        # 操作按钮
        [
            Button.inline("🔄 重载广告配置", f"reload_smart_ad_config:{rid}"),
            Button.inline("📋 查看广告库", f"view_smart_ad_list:{rid}"),
        ],

        # 返回
        [
            Button.inline('👈 返回', f"rule_settings:{rid}"),
            Button.inline('❌ 关闭', "close_settings")
        ],
    ]

    return buttons


# ── Callback 处理函数 ─────────────────────────────────────────────

async def callback_smart_ad_settings(event, rule_id, session, message, data):
    """显示智能广告设置页面"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
    finally:
        session.close()


async def callback_toggle_smart_ad(event, rule_id, session, message, data):
    """切换智能广告开关"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            rule.enable_smart_ad = not getattr(rule, 'enable_smart_ad', False)
            session.commit()
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
            status = '开启' if rule.enable_smart_ad else '关闭'
            await event.answer(f"智能广告已{status}")
    finally:
        session.close()


async def callback_smart_ad_threshold(event, rule_id, session, message, data):
    """设置匹配阈值，格式: smart_ad_threshold:{rule_id}:{value}
    注意：router 会把 parts[1:] 全部 join 传来，所以 rule_id 参数是 "{rid}:{value}"
    必须从 data 直接解析。
    """
    parts = data.split(':', 2)  # ['smart_ad_threshold', rid, value]
    if len(parts) < 3:
        await event.answer("参数错误")
        return
    try:
        real_rule_id = int(parts[1])
        threshold = float(parts[2])
        rule = session.query(ForwardRule).get(real_rule_id)
        if rule:
            rule.smart_ad_threshold = threshold
            session.commit()
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
            await event.answer(f"阈值已设置为 {threshold}")
    except Exception as e:
        logger.error(f"[SmartAd] 设置阈值出错: {e}")
        await event.answer("设置失败")
    finally:
        session.close()


async def callback_smart_ad_max_count(event, rule_id, session, message, data):
    """设置最多广告数，格式: smart_ad_max_count:{rule_id}:{count}"""
    parts = data.split(':', 2)  # ['smart_ad_max_count', rid, count]
    if len(parts) < 3:
        await event.answer("参数错误")
        return
    try:
        real_rule_id = int(parts[1])
        count = int(parts[2])
        rule = session.query(ForwardRule).get(real_rule_id)
        if rule:
            rule.smart_ad_max_count = count
            session.commit()
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
            await event.answer(f"最多广告数已设置为 {count}")
    except Exception as e:
        logger.error(f"[SmartAd] 设置最多广告数出错: {e}")
        await event.answer("设置失败")
    finally:
        session.close()


async def callback_smart_ad_cooldown(event, rule_id, session, message, data):
    """设置冷却时间，格式: smart_ad_cooldown:{rule_id}:{minutes}"""
    parts = data.split(':', 2)  # ['smart_ad_cooldown', rid, minutes]
    if len(parts) < 3:
        await event.answer("参数错误")
        return
    try:
        real_rule_id = int(parts[1])
        minutes = int(parts[2])
        rule = session.query(ForwardRule).get(real_rule_id)
        if rule:
            rule.smart_ad_cooldown = minutes
            session.commit()
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
            await event.answer(f"冷却时间已设置为 {minutes} 分钟")
    except Exception as e:
        logger.error(f"[SmartAd] 设置冷却时间出错: {e}")
        await event.answer("设置失败")
    finally:
        session.close()


async def callback_change_smart_ad_model(event, rule_id, session, message, data):
    """进入模型选择页面"""
    try:
        await event.edit(
            "请选择智能广告使用的AI模型：",
            buttons=await create_model_buttons(rule_id, page=0, prefix='select_smart_ad_model')
        )
    finally:
        session.close()


async def callback_select_smart_ad_model(event, rule_id, session, message, data):
    """选择AI模型，格式: select_smart_ad_model:{rule_id}:{model}"""
    parts = data.split(':', 2)
    if len(parts) < 3:
        await event.answer("参数错误")
        return
    _, rid, model = parts
    try:
        rule = session.query(ForwardRule).get(int(rid))
        if rule:
            rule.smart_ad_model = model
            session.commit()
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
            await event.answer(f"已选择模型: {model}")
    except Exception as e:
        logger.error(f"[SmartAd] 选择模型出错: {e}")
        await event.answer("设置失败")
    finally:
        session.close()


async def callback_reload_smart_ad_config(event, rule_id, session, message, data):
    """热重载广告配置文件"""
    try:
        count = smart_ad_config.reload()
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(
                await get_smart_ad_settings_text(rule),
                buttons=await create_smart_ad_settings_buttons(rule)
            )
        await event.answer(f"✅ 广告配置已重载，共 {count} 条广告")
        logger.info(f"[SmartAd] 手动重载广告配置，共 {count} 条")
    except Exception as e:
        logger.error(f"[SmartAd] 重载配置出错: {e}")
        await event.answer("重载失败，请检查 ads_config.yaml 格式")
    finally:
        session.close()


async def callback_view_smart_ad_list(event, rule_id, session, message, data):
    """查看当前广告库列表"""
    try:
        ads = smart_ad_config.get_all_ads()
        if not ads:
            await event.answer("广告库为空，请检查 ads_config.yaml")
            return

        lines = ["📋 当前广告库\n"]
        for ad in ads:
            emoji = ad.get('emoji', '')
            name = ad.get('name', '')
            ad_id = ad.get('id', '')
            lines.append(f"{emoji} {name} `[{ad_id}]`")

        text = "\n".join(lines)
        await event.edit(
            text,
            buttons=[[
                Button.inline('👈 返回', f"smart_ad_settings:{rule_id}"),
                Button.inline('❌ 关闭', "close_settings")
            ]]
        )
    except Exception as e:
        logger.error(f"[SmartAd] 查看广告库出错: {e}")
        await event.answer("查看失败")
    finally:
        session.close()
