"""
智能广告工具模块
- SmartAdConfig: 广告配置热加载
- SmartAdCooldown: 冷却记录（内存级）
"""
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 广告配置文件路径
ADS_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'ads_config.yaml')


class SmartAdConfig:
    """广告配置加载器，支持热重载"""

    def __init__(self):
        self._ads: List[dict] = []
        self._loaded = False
        self.reload()

    def reload(self) -> int:
        """重新加载广告配置，返回加载的广告条数"""
        try:
            import yaml
            if not os.path.exists(ADS_CONFIG_PATH):
                logger.warning(f"[SmartAd] 广告配置文件不存在: {ADS_CONFIG_PATH}")
                self._ads = []
                return 0

            with open(ADS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data or 'ads' not in data:
                logger.warning("[SmartAd] 广告配置文件格式错误，缺少 ads 字段")
                self._ads = []
                return 0

            # 只保留 enabled=true 的条目
            self._ads = [ad for ad in data['ads'] if ad.get('enabled', True)]
            self._loaded = True
            logger.info(f"[SmartAd] 广告配置加载完成，共 {len(self._ads)} 条有效广告")
            return len(self._ads)

        except Exception as e:
            logger.error(f"[SmartAd] 加载广告配置失败: {e}", exc_info=True)
            self._ads = []
            return 0

    def get_all_ads(self) -> List[dict]:
        """获取所有有效广告"""
        if not self._loaded:
            self.reload()
        return self._ads

    def get_ad_by_id(self, ad_id: str) -> Optional[dict]:
        """根据ID获取单条广告"""
        for ad in self._ads:
            if ad.get('id') == ad_id:
                return ad
        return None

    def count(self) -> int:
        return len(self._ads)


class SmartAdCooldown:
    """内存冷却记录器，记录每个 (rule_id, ad_id) 的上次投放时间"""

    def __init__(self):
        # key: (rule_id, ad_id) -> expire_timestamp
        self._cooldowns: Dict[Tuple, float] = {}

    def is_cooling(self, rule_id: int, ad_id: str) -> bool:
        """判断是否还在冷却中"""
        key = (rule_id, ad_id)
        expire_ts = self._cooldowns.get(key, 0)
        return time.time() < expire_ts

    def set_cooling(self, rule_id: int, ad_id: str, minutes: int):
        """设置冷却，minutes 分钟内不重复投放"""
        key = (rule_id, ad_id)
        self._cooldowns[key] = time.time() + minutes * 60
        logger.debug(f"[SmartAd] 设置冷却 rule={rule_id} ad={ad_id} 时长={minutes}min")

    def clear_rule(self, rule_id: int):
        """清除某个规则的所有冷却"""
        keys_to_del = [k for k in self._cooldowns if k[0] == rule_id]
        for k in keys_to_del:
            del self._cooldowns[k]

    def clear_all(self):
        self._cooldowns.clear()


# 全局单例
smart_ad_config = SmartAdConfig()
smart_ad_cooldown = SmartAdCooldown()
