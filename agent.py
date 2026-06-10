#!/usr/bin/env python3
"""
世界杯竞猜 2026 — 远端 Agent 自动参赛脚本

功能：
- 自动拉取未来可投注的比赛
- 根据策略生成预测
- 批量提交投注
- 避免重复投注
- 错误自动重试
- 定时循环执行

安装依赖：
    pip install requests

运行方式：
    export AGENT_TOKEN=你的Token
    python agent.py

或者定时执行（每30分钟检查一次）：
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


# ==================== 策略函数（可自由替换）====================

def strategy_random(game):
    """随机策略"""
    import random
    return random.choice(["home", "draw", "away"])


def strategy_home_always(game):
    """永远押主队"""
    return "home"


def strategy_hot_favorite(game):
    """
    简单策略：热门球队主场押 home，否则随机
    可扩展为调用 FIFA 排名、历史数据等
    """
    hot_teams = {
        "阿根廷", "巴西", "法国", "英格兰", "西班牙",
        "葡萄牙", "德国", "荷兰", "比利时",
    }
    home = game.get("home_team", "")
    away = game.get("away_team", "")

    if home in hot_teams:
        return "home"
    if away in hot_teams:
        return "away"
    return "draw"


# 默认使用的热门球队策略
DEFAULT_STRATEGY = strategy_hot_favorite


# ==================== 主流程 ====================

def run_once(strategy=None):
    """执行一次完整的投注流程"""
    if not TOKEN:
        logger.error("环境变量 AGENT_TOKEN 未设置，无法运行")
        return False

    strategy = strategy or DEFAULT_STRATEGY

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

        # 4. 生成预测
        bets = []
        for g in to_bet:
            pred = strategy(g)
            bets.append({
                "game_id": g["id"],
                "prediction": pred,
            })
            logger.info(f"预测: [{g['id']}] {g['home_team']} vs {g['away_team']} → {pred}")

        # 5. 批量提交
        result = api_post("/bets", {"bets": bets})
        logger.info(f"✅ 成功提交 {len(bets)} 场预测: {result.get('message')}")
        return True

    except Exception as e:
        logger.error(f"❌ 运行失败: {e}")
        return False


def run_loop(interval=1800, strategy=None):
    """定时循环执行"""
    logger.info(f"Agent 启动，每 {interval} 秒检查一次赛程...")
    while True:
        success = run_once(strategy)
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
    parser.add_argument("--strategy", type=str, default="hot", choices=["hot", "home", "random"], help="投注策略")
    args = parser.parse_args()

    strategy_map = {
        "hot": strategy_hot_favorite,
        "home": strategy_home_always,
        "random": strategy_random,
    }
    strategy = strategy_map[args.strategy]

    if args.interval > 0:
        run_loop(interval=args.interval, strategy=strategy)
    else:
        run_once(strategy=strategy)


if __name__ == "__main__":
    main()
