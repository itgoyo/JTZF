"""
到期规则清理调度器
每小时扫描一次 expire_at <= now 的转发规则，自动删除并通知管理员。
"""
import asyncio
import logging
import traceback
from datetime import datetime

from models.models import ForwardRule, get_session
from utils.common import get_admin_list, get_bot_client

logger = logging.getLogger(__name__)

# 默认检查间隔：3600 秒（1小时）
CHECK_INTERVAL = 3600


class ExpiryScheduler:
    """定期检查并删除已过期的转发规则"""

    def __init__(self):
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动调度器"""
        logger.info('[ExpiryScheduler] 启动到期规则清理调度器')
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        """停止调度器"""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info('[ExpiryScheduler] 已停止')

    async def _loop(self):
        """主循环：每小时检查一次"""
        while True:
            try:
                await self._check_and_delete_expired()
            except asyncio.CancelledError:
                logger.info('[ExpiryScheduler] 任务已取消')
                break
            except Exception as e:
                logger.error(f'[ExpiryScheduler] 检查出错: {e}\n{traceback.format_exc()}')
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_and_delete_expired(self):
        """扫描并删除所有已过期规则"""
        session = get_session()
        deleted_rules = []
        try:
            now = datetime.now()
            expired_rules = (
                session.query(ForwardRule)
                .filter(ForwardRule.expire_at != None)  # noqa: E711
                .filter(ForwardRule.expire_at <= now)
                .all()
            )

            if not expired_rules:
                logger.debug('[ExpiryScheduler] 无过期规则')
                return

            logger.info(f'[ExpiryScheduler] 发现 {len(expired_rules)} 条过期规则，开始删除')

            for rule in expired_rules:
                try:
                    src = rule.source_chat.name if rule.source_chat else str(rule.source_chat_id)
                    tgt = rule.target_chat.name if rule.target_chat else str(rule.target_chat_id)
                    expire_str = rule.expire_at.strftime('%Y-%m-%d %H:%M')
                    deleted_rules.append({
                        'id': rule.id,
                        'src': src,
                        'tgt': tgt,
                        'expire_str': expire_str,
                    })
                    session.delete(rule)
                    logger.info(f'[ExpiryScheduler] 删除规则 ID={rule.id} {src}→{tgt}，到期: {expire_str}')
                except Exception as e:
                    logger.error(f'[ExpiryScheduler] 删除规则 {rule.id} 时出错: {e}')

            session.commit()
            logger.info(f'[ExpiryScheduler] 成功删除 {len(deleted_rules)} 条过期规则')

        except Exception as e:
            session.rollback()
            logger.error(f'[ExpiryScheduler] 事务出错，已回滚: {e}')
            return
        finally:
            session.close()

        # 通知管理员
        if deleted_rules:
            await self._notify_admins(deleted_rules)

    async def _notify_admins(self, deleted_rules: list):
        """向所有管理员发送到期删除通知"""
        try:
            bot_client = await get_bot_client()
            admin_ids = get_admin_list()

            lines = ['🗑️ **以下转发规则已到期自动删除：**\n']
            for r in deleted_rules:
                lines.append(f"• 规则 ID `{r['id']}`：{r['src']} → {r['tgt']}（到期: {r['expire_str']}）")

            message = '\n'.join(lines)

            for admin_id in admin_ids:
                try:
                    await bot_client.send_message(admin_id, message, parse_mode='markdown')
                    logger.info(f'[ExpiryScheduler] 已通知管理员 {admin_id}')
                except Exception as e:
                    logger.warning(f'[ExpiryScheduler] 通知管理员 {admin_id} 失败: {e}')
        except Exception as e:
            logger.error(f'[ExpiryScheduler] 发送通知时出错: {e}')
