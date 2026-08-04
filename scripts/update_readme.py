#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立更新README脚本
"""

import json
import os
import glob
import re
from datetime import datetime
from collections import defaultdict

def load_channels():
    """加载最新的频道数据"""
    patterns = [
        'output/valid_channels_latest.json',
        'output/all_channels.json',
    ]
    
    for pattern in patterns:
        if os.path.exists(pattern):
            with open(pattern, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    files = glob.glob('output/valid_channels_*.json')
    if files:
        with open(max(files), 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return []

def load_stats():
    """加载统计信息"""
    if os.path.exists('output/stats.json'):
        with open('output/stats.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def generate_stats_table(channels):
    """生成统计表格"""
    stats = defaultdict(lambda: {'count': 0, 'speed': 0, 'high': 0, 'mid': 0})
    
    for ch in channels:
        region = ch.get('region', 'other')
        speed = ch.get('speed', 0)
        
        stats[region]['count'] += 1
        stats[region]['speed'] += speed
        
        if speed >= 1000:
            stats[region]['high'] += 1
        elif speed >= 500:
            stats[region]['mid'] += 1
    
    region_order = ['china', 'hongkong', 'taiwan', 'macau', 'japan', 'korea', 'usa', 'southeast_asia', 'international', 'other']
    emoji_map = {
        'china': '🇨🇳', 'hongkong': '🇭🇰', 'taiwan': '🇹🇼', 'macau': '🇲🇴',
        'japan': '🇯🇵', 'korea': '🇰🇷', 'usa': '🇺🇸', 'southeast_asia': '🌏',
        'international': '🌍', 'other': '📡'
    }
    
    table = "| 地区 | 频道总数 | 平均速度 | 高速(>1MB) | 中速(>500KB) |\n"
    table += "|------|----------|----------|------------|-------------|\n"
    
    total = 0
    for region in region_order:
        if region in stats:
            data = stats[region]
            avg = data['speed'] / data['count'] if data['count'] > 0 else 0
            table += f"| {emoji_map.get(region, '📡')} {region} | {data['count']} | {avg:.0f} KB/s | {data['high']} | {data['mid']} |\n"
            total += data['count']
    
    table += f"| 📊 **总计** | **{total}** | - | - | - |\n"
    return table

def update_readme():
    """更新README中的统计信息"""
    channels = load_channels()
    stats = load_stats()
    total = len(channels)
    
    if not os.path.exists('README.md'):
        print("README.md 不存在，跳过更新")
        return
    
    with open('README.md', 'r', encoding='utf-8') as f:
        readme = f.read()
    
    # 更新统计表格
    stats_table = generate_stats_table(channels)
    pattern = r'<!-- STATS_START -->.*<!-- STATS_END -->'
    replacement = f'<!-- STATS_START -->\n{stats_table}\n<!-- STATS_END -->'
    readme = re.sub(pattern, replacement, readme, flags=re.DOTALL)
    
    # 更新最后更新时间
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    readme = re.sub(
        r'📅 最后更新: .*',
        f'📅 最后更新: {now}',
        readme
    )
    
    # 更新频道总数
    readme = re.sub(
        r'可用频道.*?\d+',
        f'可用频道-{total}',
        readme
    )
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"README已更新 - 总频道: {total}")

if __name__ == '__main__':
    update_readme()
