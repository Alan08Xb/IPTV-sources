#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新README.md
读取output目录下的m3u文件统计信息，更新README
"""

import os
import re
import json
from datetime import datetime, timezone, timedelta

def count_channels(m3u_file):
    """统计m3u文件中的频道数"""
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return content.count('#EXTINF:')
    except:
        return 0

def get_file_size(m3u_file):
    """获取文件大小(KB)"""
    try:
        return os.path.getsize(m3u_file) / 1024
    except:
        return 0

def load_stats():
    """加载统计信息"""
    try:
        with open('output/stats.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def generate_stats_section():
    """生成统计表格"""
    output_dir = 'output'
    
    files = {
        'all.m3u': ('📦 完整版', '全部频道(>150KB/s)'),
        'china.m3u': ('🇨🇳 中国大陆', '高速+中速(>500KB/s)'),
        'east_asia.m3u': ('🌏 东亚', '港澳台+日韩+东南亚(>1MB/s)'),
        'overseas_highspeed.m3u': ('🌍 海外高速', '除大陆外所有地区(>1MB/s)'),
        'feiniu.m3u': ('🎬 飞牛优化版', '精选频道'),
        'category_新闻.m3u': ('📰 新闻', '新闻频道'),
        'category_体育.m3u': ('⚽ 体育', '体育频道'),
        'category_影视.m3u': ('🎬 影视', '影视频道'),
        'category_综艺.m3u': ('🎭 综艺', '综艺频道'),
        'category_少儿.m3u': ('🧒 少儿', '少儿频道'),
        'category_音乐.m3u': ('🎵 音乐', '音乐频道'),
        'category_纪录片.m3u': ('🎥 纪录片', '纪录片频道'),
        'category_教育.m3u': ('📚 教育', '教育频道'),
        'category_综合.m3u': ('📺 综合', '综合频道'),
    }
    
    lines = []
    lines.append("| 播放列表 | 说明 | 频道数 | 文件大小 |")
    lines.append("|----------|------|--------|----------|")
    
    total_channels = 0
    for filename, (emoji_name, desc) in files.items():
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            count = count_channels(filepath)
            size = get_file_size(filepath)
            total_channels += count
            link = f"[{emoji_name}](https://raw.githubusercontent.com/你的用户名/IPTV-sources/main/output/{filename})"
            lines.append(f"| {link} | {desc} | {count} | {size:.0f}KB |")
    
    stats = load_stats()
    if stats:
        lines.append(f"\n> 📊 测速统计: 总测试 {stats.get('total_tested', '?')} 个 | "
                     f"有效 {stats.get('valid_count', '?')} 个 | "
                     f"成功率 {stats.get('success_rate', '?')} | "
                     f"平均速度 {stats.get('avg_speed', 0):.0f}KB/s")
    
    return '\n'.join(lines)

def generate_usage_section():
    """生成使用说明"""
    return """## 📥 播放列表链接

| 类型 | 链接 | 适用场景 |
|------|------|----------|
| 🎬 飞牛优化版 | `https://raw.githubusercontent.com/你的用户名/IPTV-sources/main/output/feiniu.m3u` | **飞牛影视推荐** |
| 🇨🇳 中国大陆 | `https://raw.githubusercontent.com/你的用户名/IPTV-sources/main/output/china.m3u` | 国内频道 |
| 📦 完整版 | `https://raw.githubusercontent.com/你的用户名/IPTV-sources/main/output/all.m3u` | 全部可用频道 |
| 🌍 海外高速 | `https://raw.githubusercontent.com/你的用户名/IPTV-sources/main/output/overseas_highspeed.m3u` | 海外高速频道 |

### 🖥️ 飞牛影视配置
1. 打开飞牛影视 → 设置 → 直播源管理
2. 添加M3U8源，填入飞牛优化版链接
3. 保存刷新即可"""

def update_readme():
    """主函数：更新README"""
    readme_path = 'README.md'
    
    # 读取现有README
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme = f.read()
    else:
        readme = ""
    
    # 生成统计部分
    stats_section = generate_stats_section()
    usage_section = generate_usage_section()
    
    # 获取北京时间
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # 构建新README
    new_readme = f"""# 📺 IPTV 自动更新直播源

> 🌐 自动采集、筛选、测速的IPTV直播源合集  
> ⚡ 每日两次更新（08:00 快速测速 / 18:00 完整采集）  
> 📅 最后更新: {now} (北京时间)

## ✨ 特性

- 🔄 **全自动更新**：每天两次自动采集和测速
- 🧪 **自动测速**：多线程测速，剔除失效和低速节点
- 🧹 **智能去重**：同名频道只保留最快源
- 📊 **速度分层**：高速(>1MB/s)、中速(>500KB/s)、低速(>150KB/s)
- 🚀 **飞牛优化**：专为飞牛影视定制的精选列表

{usage_section}

## 📊 频道统计

{stats_section}

## ⚠️ 免责声明

> 本项目仅供学习研究使用，所有源均来自网络公开资源。请勿用于商业用途，如有侵权请联系删除。
"""
    
    # 写入README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_readme)
    
    print(f"✅ README.md 已更新 ({now})")

if __name__ == '__main__':
    update_readme()
