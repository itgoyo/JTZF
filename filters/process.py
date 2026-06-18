import logging
from filters.filter_chain import FilterChain
from filters.keyword_filter import KeywordFilter
from filters.delete_filter import DeleteFilter
from filters.replace_filter import ReplaceFilter
from filters.append_filter import AppendFilter
from filters.ai_tag_filter import AITagFilter
from filters.ai_filter import AIFilter
from filters.ai_translate_filter import AITranslateFilter
from filters.ai_ad_removal_filter import AIAdRemovalFilter
from filters.ai_rewrite_filter import AIRewriteFilter
from filters.info_filter import InfoFilter
from filters.media_filter import MediaFilter
from filters.sender_filter import SenderFilter
from filters.delete_original_filter import DeleteOriginalFilter
from filters.delay_filter import DelayFilter
from filters.edit_filter import EditFilter
from filters.comment_button_filter import CommentButtonFilter
from filters.custom_buttons_filter import CustomButtonsFilter
from filters.smart_ad_filter import SmartAdFilter
from filters.init_filter import InitFilter
from filters.reply_filter import ReplyFilter
from filters.rss_filter import RSSFilter
from filters.push_filter import PushFilter
from filters.final_buttons_guard_filter import FinalButtonsGuardFilter

logger = logging.getLogger(__name__)


async def process_forward_rule(client, event, chat_id, rule):
    """
    处理转发规则

    Args:
        client: 机器人客户端
        event: 消息事件
        chat_id: 聊天ID
        rule: 转发规则

    Returns:
        bool: 处理是否成功
    """
    logger.info(f'使用过滤器链处理规则 ID: {rule.id}')

    # 创建过滤器链
    filter_chain = FilterChain()

    # 添加初始化过滤器
    filter_chain.add_filter(InitFilter())

    # AI增强过滤器：自动翻译（最先执行，先把非中文翻译成中文）
    filter_chain.add_filter(AITranslateFilter())

    # AI增强过滤器：去广告（在翻译后执行）
    filter_chain.add_filter(AIAdRemovalFilter())

    # AI增强过滤器：改写（去广告之后执行）
    filter_chain.add_filter(AIRewriteFilter())

    # 延迟处理过滤器（如果启用了延迟处理）
    filter_chain.add_filter(DelayFilter())

    # 添加去重过滤器（相同内容在时间窗口内只转发一次，通过 DEDUP_ENABLED=true 开启）
    from filters.dedup_filter import DedupFilter
    filter_chain.add_filter(DedupFilter())

    # 添加关键字过滤器（如果消息不匹配关键字，会中断处理链）
    filter_chain.add_filter(KeywordFilter())

    # 添加删除过滤器（删除指定关键字及其后的所有内容）
    filter_chain.add_filter(DeleteFilter())

    # 添加替换过滤器
    filter_chain.add_filter(ReplaceFilter())

    # 添加媒体过滤器（处理媒体内容）
    filter_chain.add_filter(MediaFilter())

    # 添加AI处理过滤器（如果启用了AI处理后的关键字检查，可能会中断处理链）
    filter_chain.add_filter(AIFilter())

    # 添加AI自动打标签过滤器（必须在AIFilter之后，避免被覆盖）
    filter_chain.add_filter(AITagFilter())

    # 添加追加文本过滤器（/append），放在AI标签之后，确保标签出现在追加内容前面
    filter_chain.add_filter(AppendFilter())

    # 添加信息过滤器（处理原始链接和发送者信息）
    filter_chain.add_filter(InfoFilter())

    # 添加评论区按钮过滤器
    filter_chain.add_filter(CommentButtonFilter())

    # 添加自定义广告按钮过滤器（/buttons）
    filter_chain.add_filter(CustomButtonsFilter())

    # 添加智能广告过滤器（AI语义匹配，自动追加广告按钮）
    filter_chain.add_filter(SmartAdFilter())

    # 最终按钮守卫：
    # - 配置了 /buttons => 仅保留 /buttons
    # - 未配置 /buttons => 保留当前按钮（含原帖按钮）
    filter_chain.add_filter(FinalButtonsGuardFilter())

    # 添加RSS过滤器
    filter_chain.add_filter(RSSFilter())

    # 添加编辑过滤器（编辑原始消息）
    filter_chain.add_filter(EditFilter())

    # 添加发送过滤器（发送消息）
    filter_chain.add_filter(SenderFilter())

    # 添加回复过滤器（处理媒体组消息的评论区按钮）
    filter_chain.add_filter(ReplyFilter())

    # 添加推送过滤器
    filter_chain.add_filter(PushFilter())

    # 添加删除原始消息过滤器（最后执行）
    filter_chain.add_filter(DeleteOriginalFilter())

    # 执行过滤器链
    result = await filter_chain.process(client, event, chat_id, rule)

    return result
