# coding=utf-8
"""
推送快照工具

为 daily 模式提供“前一日推送快照并集补齐”的最小辅助函数：

1. build_snapshot_payload: 把当前推送的 stats / rss_items 序列化为可持久化的快照
2. merge_with_snapshot:    把当前推送数据与历史快照按 url+title 去重并集
3. resolve_scope_key:      生成快照作用域 key（隔离不同筛选策略的快照）

设计原则：
- 只在“准备推送”那一刻起作用，绝不影响抓取、AI 分类、HTML 报告生成。
- 仅基于 url+title 去重，避免引入额外语义。
- 失败时静默回退到当前推送数据，绝不阻塞主流程。
"""

from typing import Any, Dict, List, Optional, Tuple


def resolve_scope_key(filter_method: str, interests_file: Optional[str], frequency_file: Optional[str]) -> str:
    """
    生成快照作用域 key

    AI 模式下按 interests_file 隔离，关键词模式下按 frequency_file 隔离。
    保证不同筛选源不会互相污染快照。
    """
    if filter_method == "ai":
        return f"ai:{interests_file or 'ai_interests.txt'}"
    return f"keyword:{frequency_file or 'frequency_words.txt'}"


def _title_dedupe_key(title_data: Dict[str, Any]) -> Optional[str]:
    """
    返回用于去重的 key：优先 url，否则 title。

    返回 None 表示该条记录无法可靠去重，调用方应原样保留以避免误删。
    """
    url = (title_data.get("url") or "").strip()
    if url:
        return f"url::{url}"
    title = (title_data.get("title") or "").strip()
    if title:
        return f"title::{title}"
    return None


def build_snapshot_payload(
    stats: Optional[List[Dict]],
    rss_items: Optional[List[Dict]],
) -> Dict[str, Any]:
    """
    构建可持久化的快照 payload

    只保留推送展示所需的最小字段，避免快照膨胀。
    """
    def _shrink_titles(titles: List[Dict]) -> List[Dict]:
        slim = []
        for t in titles or []:
            slim.append({
                "title": t.get("title", ""),
                "source_name": t.get("source_name", ""),
                "url": t.get("url", ""),
                "mobile_url": t.get("mobile_url", ""),
                "ranks": list(t.get("ranks", []) or []),
                "rank_threshold": t.get("rank_threshold", 0),
                "time_display": t.get("time_display", ""),
                "count": t.get("count", 1),
                "is_new": False,  # 来自快照的内容一律视为非新增
            })
        return slim

    def _shrink_groups(groups: Optional[List[Dict]]) -> List[Dict]:
        slim_groups = []
        for g in groups or []:
            slim_groups.append({
                "word": g.get("word", ""),
                "count": g.get("count", 0),
                "percentage": g.get("percentage", 0),
                "titles": _shrink_titles(g.get("titles", [])),
            })
        return slim_groups

    return {
        "stats": _shrink_groups(stats),
        "rss_items": _shrink_groups(rss_items),
    }


def _merge_groups(
    current_groups: List[Dict],
    snapshot_groups: List[Dict],
) -> Tuple[List[Dict], int]:
    """
    把快照中的分组合并入当前分组：

    - 完全新增的分组（word 在当前缺失）整组并入末尾
    - 已存在的分组按 url/title 去重补充缺失条目，不动顺序

    返回 (合并后分组列表, 实际新增条目数)
    """
    if not snapshot_groups:
        return current_groups or [], 0

    merged = [dict(g) for g in (current_groups or [])]
    word_to_index = {g.get("word", ""): i for i, g in enumerate(merged)}
    total_added = 0

    for snap_group in snapshot_groups:
        word = snap_group.get("word", "")
        snap_titles = snap_group.get("titles", []) or []
        if not snap_titles:
            continue

        if word not in word_to_index:
            new_group = {
                "word": word,
                "count": snap_group.get("count", len(snap_titles)),
                "percentage": snap_group.get("percentage", 0),
                "titles": [dict(t) for t in snap_titles],
            }
            merged.append(new_group)
            word_to_index[word] = len(merged) - 1
            total_added += len(snap_titles)
            continue

        idx = word_to_index[word]
        target = merged[idx]
        target_titles = list(target.get("titles", []) or [])
        existing_keys = set()
        for t in target_titles:
            key = _title_dedupe_key(t)
            if key:
                existing_keys.add(key)

        added_here = 0
        for snap_t in snap_titles:
            key = _title_dedupe_key(snap_t)
            if key is None:
                continue  # 无法去重的快照条目跳过，避免重复
            if key in existing_keys:
                continue
            target_titles.append(dict(snap_t))
            existing_keys.add(key)
            added_here += 1

        if added_here:
            target["titles"] = target_titles
            target["count"] = target.get("count", 0) + added_here
            total_added += added_here

    return merged, total_added


def merge_with_snapshot(
    stats: Optional[List[Dict]],
    rss_items: Optional[List[Dict]],
    snapshot_payload: Optional[Dict[str, Any]],
) -> Tuple[List[Dict], List[Dict], Dict[str, int]]:
    """
    用快照补齐当前推送数据。

    Returns:
        (merged_stats, merged_rss_items, summary)
        summary: {"stats_added": int, "rss_added": int, "snapshot_used": bool}
    """
    summary = {"stats_added": 0, "rss_added": 0, "snapshot_used": False}

    if not snapshot_payload:
        return list(stats or []), list(rss_items or []), summary

    snap_stats = snapshot_payload.get("stats") or []
    snap_rss = snapshot_payload.get("rss_items") or []

    merged_stats, stats_added = _merge_groups(list(stats or []), snap_stats)
    merged_rss, rss_added = _merge_groups(list(rss_items or []), snap_rss)

    summary["stats_added"] = stats_added
    summary["rss_added"] = rss_added
    summary["snapshot_used"] = bool(stats_added or rss_added)

    return merged_stats, merged_rss, summary
