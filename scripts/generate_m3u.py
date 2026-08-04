#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分类M3U播放列表
"""

import json
import os
from datetime import datetime
import glob

class M3UGenerator:
    def __init__(self, channels_file=None):
        # 自动找到最新的测试结果文件
        if channels_file is None:
            files = glob.glob('output/valid_channels_*.json')
            if files:
                channels_file = max(files)  # 获取最新的文件
        
        with open(channels_file, 'r', encoding='utf-8') as f:
            self.channels = json.load(f)
    
    def generate_m3u_header(self, name):
        """生成M3U文件头"""
        return f'#EXTM3U\n#PLAYLIST:{name}\n# Generated at: {datetime.now().isoformat()}\n'
    
    def generate_channel_entry(self, channel):
        """生成单个频道条目"""
        name = channel['name']
        url = channel['url']
        logo = channel.get('logo', '')
        group = channel.get('group', channel.get('category', '综合'))
        
        extinf = f'#EXTINF:-1'
        if logo:
            extinf += f' tvg-logo="{logo}"'
        extinf += f' group-title="{group}",{name}'
        
        return f'{extinf}\n{url}\n'
    
    def generate_by_region(self):
        """按地区生成M3U文件"""
        regions = {
            'china': {'name': '中国大陆频道', 'channels': []},
            'hongkong': {'name': '香港频道', 'channels': []},
            'taiwan': {'name': '台湾频道', 'channels': []},
            'macau': {'name': '澳门频道', 'channels': []},
            'international': {'name': '国际频道', 'channels': []},
            'other': {'name': '其他频道', 'channels': []}
        }
        
        # 按地区分类
        for ch in self.channels:
            region = ch.get('region', 'other')
            if region in regions:
                regions[region]['channels'].append(ch)
        
        # 生成文件
        for region_key, region_data in regions.items():
            if not region_data['channels']:
                continue
            
            filename = f'output/{region_key}.m3u'
            content = self.generate_m3u_header(region_data['name'])
            
            for ch in region_data['channels']:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"生成 {filename}: {len(region_data['channels'])} 个频道")
    
    def generate_by_category(self):
        """按类别生成M3U文件"""
        categories = {}
        
        for ch in self.channels:
            cat = ch.get('category', '综合')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(ch)
        
        for cat_name, cat_channels in categories.items():
            filename = f'output/category_{cat_name}.m3u'
            content = self.generate_m3u_header(f'{cat_name}频道')
            
            for ch in cat_channels:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"生成 {filename}: {len(cat_channels)} 个频道")
    
    def generate_mainland_china(self):
        """生成中国大陆专用列表（CCTV+卫视+地方台）"""
        mainland_channels = []
        
        for ch in self.channels:
            name = ch['name'].upper()
            if any(keyword in name for keyword in ['CCTV', '卫视', '北京', '上海', '广东', '浙江', '江苏']):
                mainland_channels.append(ch)
        
        filename = 'output/china_mainland.m3u'
        content = self.generate_m3u_header('中国大陆电视频道')
        
        for ch in mainland_channels:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"生成 {filename}: {len(mainland_channels)} 个频道")
    
    def generate_all_in_one(self):
        """生成完整的播放列表"""
        filename = 'output/all_channels.m3u'
        content = self.generate_m3u_header('全部频道')
        
        for ch in self.channels:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"生成 {filename}: {len(self.channels)} 个频道")
    
    def generate_readme(self):
        """生成README统计信息"""
        stats = {}
        for ch in self.channels:
            region = ch.get('region', 'other')
            category = ch.get('category', '综合')
            
            stats.setdefault(region, {'count': 0, 'categories': {}})
            stats[region]['count'] += 1
            stats[region]['categories'].setdefault(category, 0)
            stats[region]['categories'][category] += 1
        
        readme = f"""# 📺 IPTV 直播源

> 自动更新于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 可用频道总数: {len(self.channels)}

## 📊 频道统计

| 地区 | 频道数 | 类别分布 |
|------|--------|----------|
"""
        
        for region, data in stats.items():
            categories_str = ', '.join([f'{k}({v})' for k, v in data['categories'].items()])
            readme += f"| {region} | {data['count']} | {categories_str} |\n"
        
        readme += """
## 📥 使用方法

### 飞牛影视配置
1. 打开飞牛影视 → 设置 → 直播源
2. 添加M3U8源，填入以下URL之一：
   - 全部频道: `https://raw.githubusercontent.com/你的用户名/仓库名/main/output/all_channels.m3u`
   - 中国大陆: `https://raw.githubusercontent.com/你的用户名/仓库名/main/output/china.m3u`
   - CCTV+卫视: `https://raw.githubusercontent.com/你的用户名/仓库名/main/output/china_mainland.m3u`

### 其他播放器
- VLC: 媒体 → 打开网络串流 → 粘贴M3U链接
- PotPlayer: 打开 → 打开链接 → 粘贴M3U链接
- Kodi: 安装IPTV Simple Client插件 → 配置M3U播放列表URL

## ⚠️ 免责声明
本项目仅供学习研究使用，所有源均来自网络公开资源。请勿用于商业用途，如有侵权请联系删除。
"""
        
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(readme)
        
        print("README.md 已更新")

if __name__ == '__main__':
    generator = M3UGenerator()
    generator.generate_by_region()
    generator.generate_by_category()
    generator.generate_mainland_china()
    generator.generate_all_in_one()
    generator.generate_readme()
