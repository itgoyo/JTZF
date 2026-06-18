"""
智能广告 AI 分析器
- 双轨制：AI语义分析 + 关键词兜底匹配
- AI失败时自动降级为关键词匹配
- 支持动态生成广告推荐文案
"""
import json
import logging
import os
import re
from typing import List, Optional

from ai import get_ai_provider
from utils.constants import DEFAULT_AI_MODEL

logger = logging.getLogger(__name__)

# 分析提示词
SMART_AD_ANALYZE_PROMPT = """你是一个广告投放助手。请分析以下帖子内容，判断哪些广告适合在帖子末尾投放。

可用广告列表（JSON格式）：
{ads_json}

请严格按照以下JSON格式返回结果（只返回JSON，不要其他内容）：
[
  {{"ad_id": "广告ID", "score": 0.0到1.0的置信度, "reason": "匹配原因简述"}},
  ...
]

判断规则：
1. 仔细阅读帖子内容，理解其主题和场景
2. 对比每个广告的适用场景描述，判断是否与帖子内容高度相关
3. 只返回真正相关的广告，不要强行关联
4. score 表示相关程度：0.9+ 强相关，0.7-0.9 中度相关，低于0.7 不相关（不要返回）
5. 如果没有任何广告与帖子相关，返回空数组 []

帖子内容：
{message_text}"""

# 文案生成提示词
SMART_AD_COPYWRITE_PROMPT = """你是一个擅长写广告软文的文案助手，风格口语化、自然、简短。

请根据以下帖子内容，为指定广告生成一句自然衔接的推荐语（15字以内，不要生硬，像朋友推荐那种语气）。

帖子内容：{message_text}

广告信息：{ad_name} - {ad_description}

要求：
- 只输出推荐语本身，不要加引号、不要解释
- 口语化，简短有力
- 与帖子内容有自然衔接感
- 不要以"如果"开头
"""


class SmartAdAnalyzer:
    """智能广告分析器"""

    async def analyze(
        self,
        text: str,
        rule,
        ads: list,
        threshold: float = 0.7,
    ) -> List[dict]:
        """
        分析帖子内容，返回命中的广告列表（已过冷却过滤）

        Returns:
            List[dict]: 命中的广告信息列表，每项包含 ad 原始数据 + score
        """
        if not ads or not text or not text.strip():
            return []

        # 1. 先尝试 AI 语义分析
        ai_results = await self._ai_analyze(text, rule, ads, threshold)

        # 2. 关键词辅助匹配（不在AI结果中的，补充进来）
        keyword_results = self._keyword_match(text, ads)

        # 3. 合并结果（AI优先，关键词补充）
        merged = {r['ad_id']: r for r in keyword_results}
        for r in ai_results:
            merged[r['ad_id']] = r  # AI结果覆盖关键词结果

        # 4. 过滤阈值
        matched_ids = [ad_id for ad_id, r in merged.items() if r.get('score', 0) >= threshold]

        # 5. 构建最终结果，附上原始广告数据
        ad_map = {ad['id']: ad for ad in ads}
        result = []
        for ad_id in matched_ids:
            ad = ad_map.get(ad_id)
            if ad:
                result.append({
                    **ad,
                    'match_score': merged[ad_id].get('score', 0.7),
                    'match_reason': merged[ad_id].get('reason', '关键词匹配'),
                })

        # 6. 按 priority 排序（数字越小越优先）
        result.sort(key=lambda x: x.get('priority', 99))

        logger.info(f"[SmartAd] 分析完成，命中 {len(result)} 条广告: {[r['id'] for r in result]}")
        return result

    async def _ai_analyze(
        self,
        text: str,
        rule,
        ads: list,
        threshold: float,
    ) -> List[dict]:
        """AI语义分析，失败时返回空列表（自动降级）"""
        try:
            model = os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)

            # 构建广告摘要给AI（只传id、name、ai_description，节省token）
            ads_summary = [
                {
                    'id': ad['id'],
                    'name': ad['name'],
                    'description': ad.get('ai_description', ''),
                }
                for ad in ads
            ]

            prompt = SMART_AD_ANALYZE_PROMPT.format(
                ads_json=json.dumps(ads_summary, ensure_ascii=False, indent=2),
                message_text=text[:2000]  # 限制长度
            )

            provider = await get_ai_provider(model)
            response = await provider.process_message(
                message="请分析帖子内容并选择合适的广告。",
                prompt=prompt
            )

            logger.info(f"[SmartAd] AI响应（前200字）: {response[:200]}")

            results = _parse_json_response(response)
            if results is None:
                logger.warning("[SmartAd] AI响应解析失败，降级为关键词匹配")
                return []

            # 过滤阈值
            return [r for r in results if isinstance(r, dict) and r.get('score', 0) >= threshold]

        except Exception as e:
            logger.warning(f"[SmartAd] AI分析失败，降级为关键词匹配: {e}")
            return []

    def _keyword_match(self, text: str, ads: list) -> List[dict]:
        """关键词匹配（兜底），命中任意关键词即视为匹配，返回固定分数 0.75
        实际是否通过由 analyze() 中的 threshold 过滤决定。
        """
        results = []
        text_lower = text.lower()

        for ad in ads:
            categories = ad.get('categories', [])
            if not categories:
                continue

            matched_keywords = []
            for kw in categories:
                if kw.lower() in text_lower:
                    matched_keywords.append(kw)

            if matched_keywords:
                # 关键词匹配给 0.75 固定分数
                results.append({
                    'ad_id': ad['id'],
                    'score': 0.75,
                    'reason': f"关键词匹配: {', '.join(matched_keywords[:3])}"
                })

        logger.info(f"[SmartAd] 关键词匹配命中 {len(results)} 条")
        return results

    async def generate_copywrite(
        self,
        text: str,
        ad: dict,
        rule,
    ) -> Optional[str]:
        """为命中广告生成自然衔接的推荐文案，失败时返回None（使用默认文案）"""
        try:
            model = os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)

            prompt = SMART_AD_COPYWRITE_PROMPT.format(
                message_text=text[:500],
                ad_name=ad.get('name', ''),
                ad_description=ad.get('ai_description', '')[:200]
            )

            provider = await get_ai_provider(model)
            response = await provider.process_message(
                message="请生成广告推荐语。",
                prompt=prompt
            )

            copywrite = response.strip().strip('"').strip("'")
            if copywrite and len(copywrite) <= 50:
                return copywrite
            return None

        except Exception as e:
            logger.warning(f"[SmartAd] 生成文案失败: {e}")
            return None


def _parse_json_response(response: str):
    """从AI响应中提取JSON数组"""
    if not response:
        return None

    # 直接解析
    try:
        data = json.loads(response.strip())
        if isinstance(data, list):
            return data
    except Exception:
        pass

    # 提取 markdown 代码块
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'(\[[\s\S]*\])',
    ]
    for pattern in patterns:
        match = re.search(pattern, response)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if isinstance(data, list):
                    return data
            except Exception:
                continue

    return None


# 全局单例
smart_ad_analyzer = SmartAdAnalyzer()
