#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速更新脚本
跳过采集，直接对已有频道测速并生成播放列表
"""

import json
import os
import sys
import glob
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_channel_file():
    """查找已有的频道文件"""
    # 优先使用之前采集的频道文件
    patterns = [
        'output/all_channels.json',
        'output/valid_channels_latest.json',
    ]
    
    for pattern in patterns:
        if os.path.exists(pattern):
            logger.info(f"找到频道文件: {pattern}")
            return pattern
    
    # 查找最新的 valid_channels 文件
    files = glob.glob('output/valid_channels_*.json')
    if files:
        latest = max(files)
        logger.info(f"使用最新测速结果: {latest}")
        return latest
    
    # 查找任意JSON文件
    json_files = glob.glob('output/*.json')
    valid_files = [f for f in json_files if 'stats' not in f]
    if valid_files:
        latest = max(valid_files)
        logger.info(f"使用备用文件: {latest}")
        return latest
    
    return None

def quick_update():
    """快速更新流程"""
    logger.info("="*60)
    logger.info("⚡ 快速更新模式")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info("="*60)
    
    # 1. 检查频道文件
    channel_file = find_channel_file()
    if not channel_file:
        logger.error("❌ 未找到任何频道文件，请先运行完整采集")
        sys.exit(1)
    
    # 2. 加载频道
    with open(channel_file, 'r', encoding='utf-8') as f:
        channels = json.load(f)
    logger.info(f"📋 加载 {len(channels)} 个频道")
    
    # 3. 快速测速
    logger.info("🚀 开始快速测速...")
    result = subprocess.run(
        [sys.executable, 'scripts/test_speed_fast.py'],
        capture_output=False,
        timeout=480  # 8分钟超时
    )
    
    if result.returncode != 0:
        logger.warning("⚠️ 测速部分失败，尝试继续生成")
    
    # 4. 生成播放列表
    logger.info("📝 生成播放列表...")
    result = subprocess.run(
        [sys.executable, 'scripts/generate_m3u.py'],
        capture_output=False,
        timeout=120
    )
    
    if result.returncode != 0:
        logger.warning("⚠️ 生成播放列表部分失败")
    
    # 5. 更新README
    logger.info("📖 更新README...")
    result = subprocess.run(
        [sys.executable, 'scripts/update_readme.py'],
        capture_output=False,
        timeout=60
    )
    
    logger.info("="*60)
    logger.info("✅ 快速更新完成")
    logger.info("="*60)

if __name__ == '__main__':
    try:
        quick_update()
    except subprocess.TimeoutExpired:
        logger.error("❌ 更新超时")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 更新失败: {e}", exc_info=True)
        sys.exit(1)
