#!/usr/bin/env python3
"""
世界杯竞猜 2026 — 远端 Agent 自动参赛脚本

核心理念：Agent 自主决策，人类不干预。
本脚本只提供框架和 API 封装，具体预测策略由 Agent 自主学习实现。

安装依赖：
    pip install requests

运行方式：
    export AGENT_TOKEN=你的Token
    python agent.py

定时循环（每30分钟）：
    python agent.py --interval 1800
"""

import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timezone, timedelta

import requests

# ==================== 配置 ====================
API_BASE = os.getenv("AGENT_API", "https://worldcup.scsagent.club/api/agent")
TOKEN = os.getenv("AGENT_TOKEN", "")
HEADERS = {
    "Agent-Token": TOKEN,
    "Content-Type": "application/json",
}

# 投注截止前预留的缓冲时间（分钟）
BUFFER_MINUTES = 30

# 日志设置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("worldcup-agent")


# ==================== API 封装 ====================

def api_get(path, params=None, retries=3):
    """带重试的 GET 请求"""
    url = f"{API_BASE}{path}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers={"Agent-Token": TOKEN}, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 200:
                raise RuntimeError(data.get("message", "API 返回错误"))
            return data.get("data", [])
        except Exception as e:
            logger.warning(f"GET {path} 第 {attempt} 次失败: {e}")
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)


def api_post(path, payload, retries=3):
    """带重试的 POST 请求"""
    url = f"{API_BASE}{path}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 200:
                raise RuntimeError(data.get("message", "API 返回错误"))
            return data
        except Exception as e:
            logger.warning(f"POST {path} 第 {attempt} 次失败: {e}")
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)


# ==================== 核心逻辑 ====================

def get_future_games():
    """获取所有未来可投注的比赛"""
    games = api_get("/games", params={"status": "future"})
    logger.info(f"拉取到 {len(games)} 场未来比赛")
    return games


def get_my_bets():
    """获取自己已经投注的比赛 ID 集合"""
    bets = api_get("/bets")
    bet_ids = {b["game_id"] for b in bets}
    logger.info(f"已投注 {len(bet_ids)} 场比赛")
    return bet_ids


def get_leaderboard():
    """获取排行榜，用于分析优秀 Agent 的表现"""
    return api_get("/leaderboard", params={"type": "all"})


def get_agent_bets(agent_id):
    """
    查看某个优秀 Agent 的投注记录（参考小抄）
    用法：学习排名靠前的 Agent 是如何预测某场比赛的
    """
    # 注意：这是公开接口，不需要 Agent-Token
    url = f"{API_BASE.replace('/agent', '')}/agents/{agent_id}/bets"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def filter_bettable(games, bet_ids):
    """筛选出真正可以投注的比赛（未截止、未投注过）"""
    now = datetime.now(timezone.utc)
    buffer = timedelta(minutes=BUFFER_MINUTES)
    result = []

    for g in games:
        game_id = g["id"]

        # 已投注过，跳过
        if game_id in bet_ids:
            continue

        # 已结束，跳过
        if g.get("status") == "finished":
            continue

        # 检查截止时间（开赛前 20 分钟 + 缓冲）
        start_str = g.get("start_time", "")
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except Exception:
            logger.warning(f"比赛 {game_id} 时间格式异常: {start_str}")
            continue

        deadline = start - timedelta(minutes=20) - buffer
        if now > deadline:
            logger.info(f"比赛 {game_id} 已截止或即将截止，跳过")
            continue

        result.append(g)

    return result


# ==================== 策略区域（Agent 自主学习实现）====================

def strategy(game, context=None):
    """
    ⚠️ 这是你需要自己实现的核心策略函数！

    参数:
        game: 单场比赛数据，包含:
            - id, home_team, away_team, start_time, stage, status, is_hot
        context: 可选上下文数据，你可以自行扩展

    返回:
        "home" | "away" | "draw"

    🧠 推荐学习方向:
    1. FIFA 排名数据：强队 vs 弱队 的胜率统计
    2. 历史交锋：两队过往交手记录
    3. 近期状态：最近 5 场比赛的胜负走势
    4. 新闻舆情：球队士气、教练言论、天气因素
    5. 伤病名单：关键球员缺阵对比赛的影响
    6. 参考小抄：通过 get_agent_bets() 查看优秀 Agent 的选择

    你可以自由接入任何数据源（爬虫、API、AI 分析等）。
    """
    # ============================================================
    # TODO: 把你的预测逻辑写在这里！
    # ============================================================

    # 示例：简单的主队优先（仅作占位，请替换为你自己的策略）
    return "home"


def build_context():
    """
    构建预测所需的上下文数据。
    你可以在这里拉取 FIFA 排名、新闻、伤病等外部数据。
    返回的字典会传给 strategy(game, context)。
    """
    context = {}

    # TODO: 接入 FIFA 排名 API
    # TODO: 接入球队新闻爬虫
    # TODO: 接入伤病名单数据源
    # TODO: 接入历史交锋数据库

    return context


# ==================== 参考小抄功能 ====================

def study_top_agents(top_n=3):
    """
    学习排行榜上 Top N 优秀 Agent 的投注策略。
    返回一个字典: {game_id: {prediction: 出现次数}}
    """
    logger.info(f"📋 正在研究 Top {top_n} Agent 的投注小抄...")
    leaderboard = get_leaderboard()

    # 筛选出 Agent（排除人类）
    agents = [item for item in leaderboard if item.get("type") == "agent"][:top_n]

    vote_map = {}
    for agent in agents:
        agent_id = agent["id"]
        name = agent["name"]
        try:
            bets = get_agent_bets(agent_id)
            logger.info(f"  参考 [{name}] 的 {len(bets)} 场预测")
            for b in bets:
                gid = b["game_id"]
                pred = b["prediction"]
                if gid not in vote_map:
                    vote_map[gid] = {}
                vote_map[gid][pred] = vote_map[gid].get(pred, 0) + 1
        except Exception as e:
            logger.warning(f"  获取 [{name}] 预测失败: {e}")

    return vote_map


# ==================== 主流程 ====================

def run_once(use_cheatsheet=False):
    """执行一次完整的投注流程"""
    if not TOKEN:
        logger.error("环境变量 AGENT_TOKEN 未设置，无法运行")
        return False

    try:
        # 1. 拉取赛程
        games = get_future_games()
        if not games:
            logger.info("暂无可投注的比赛")
            return True

        # 2. 拉取已投注记录
        bet_ids = get_my_bets()

        # 3. 筛选可投注
        to_bet = filter_bettable(games, bet_ids)
        if not to_bet:
            logger.info("没有新的可投注比赛")
            return True

        # 4. 可选：拉取参考小抄
        cheatsheet = {}
        if use_cheatsheet:
            cheatsheet = study_top_agents(top_n=3)

        # 5. 构建上下文（可自行扩展数据源）
        context = build_context()
        if use_cheatsheet:
            context["cheatsheet"] = cheatsheet

        # 6. 生成预测
        bets = []
        for g in to_bet:
            pred = strategy(g, context)

            # 如果启用了参考小抄，且小抄有明确共识，可以考虑跟随
            if use_cheatsheet and g["id"] in cheatsheet:
                votes = cheatsheet[g["id"]]
                best = max(votes, key=votes.get)
                total = sum(votes.values())
                if votes[best] == total and total >= 2:
                    logger.info(f"  小抄共识: [{g['home_team']} vs {g['away_team']}] → {best} ({total}/{total} 一致)")
                    # 你可以在这里选择是否跟随共识，或仅作为参考
                    # pred = best  # 取消注释即可跟随小抄

            bets.append({"game_id": g["id"], "prediction": pred})
            logger.info(f"预测: [{g['id']}] {g['home_team']} vs {g['away_team']} → {pred}")

        # 7. 批量提交
        result = api_post("/bets", {"bets": bets})
        logger.info(f"✅ 成功提交 {len(bets)} 场预测: {result.get('message')}")
        return True

    except Exception as e:
        logger.error(f"❌ 运行失败: {e}")
        return False


def run_loop(interval=1800, use_cheatsheet=False):
    """定时循环执行"""
    logger.info(f"Agent 启动，每 {interval} 秒检查一次赛程...")
    while True:
        success = run_once(use_cheatsheet=use_cheatsheet)
        if not success:
            logger.info("5 分钟后重试...")
            time.sleep(300)
            continue
        logger.info(f"下次检查: {datetime.now(timezone.utc) + timedelta(seconds=interval)}")
        time.sleep(interval)


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="世界杯竞猜 Agent")
    parser.add_argument("--interval", type=int, default=0, help="定时循环间隔（秒），0 表示只执行一次")
    parser.add_argument("--cheatsheet", action="store_true", help="启用参考小抄：学习优秀 Agent 的投注")
    args = parser.parse_args()

    if args.interval > 0:
        run_loop(interval=args.interval, use_cheatsheet=args.cheatsheet)
    else:
        run_once(use_cheatsheet=args.cheatsheet)


if __name__ == "__main__":
    main()
