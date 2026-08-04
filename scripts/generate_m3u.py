#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分类M3U播放列表
包含：完整版、分层版、去重版、飞牛影视优化版
"""

import json
import os
import re
import glob
from datetime import datetime
from collections import defaultdict

class M3UGenerator:
    def __init__(self, channels_file=None):
    with open('config/sources.json', 'r', encoding='utf-8') as f:
        self.config = json.load(f)
    
    if channels_file is None:
        # 优先使用 valid_channels_latest.json
        if os.path.exists('output/valid_channels_latest.json'):
            channels_file = 'output/valid_channels_latest.json'
        else:
            files = glob.glob('output/valid_channels_*.json')
            if files:
                channels_file = max(files)
            else:
                files = glob.glob('output/all_channels.json')
                if files:
                    channels_file = max(files)
    
    if channels_file and os.path.exists(channels_file):
        with open(channels_file, 'r', encoding='utf-8') as f:
            self.channels = json.load(f)
        print(f"加载: {channels_file} ({len(self.channels)} 个频道)")
    else:
        print("警告: 未找到频道数据")
        self.channels = []
    
    def generate_m3u_header(self, name):
        """生成M3U文件头"""
        return f'#EXTM3U\n#PLAYLIST:{name}\n# Generated at: {datetime.now().isoformat()}\n# Total channels: PLACEHOLDER\n'
    
    def generate_channel_entry(self, channel):
        """生成单个频道条目"""
        name = channel.get('name', 'Unknown')
        url = channel.get('url', '')
        logo = channel.get('logo', '')
        group = channel.get('group', channel.get('category', '综合'))
        speed = channel.get('speed', 0)
        
        extinf = f'#EXTINF:-1'
        if logo:
            extinf += f' tvg-logo="{logo}"'
        extinf += f' group-title="{group}"'
        if speed > 0:
            extinf += f' tvg-speed="{speed:.0f}KB/s"'
        extinf += f',{name}'
        
        return f'{extinf}\n{url}\n'
    
    # ==================== 智能去重 ====================
    
    def normalize_channel_name(self, name):
        """标准化频道名称，用于去重"""
        name = name.strip()
        # 移除特殊字符和多余空格
        name = re.sub(r'[【】\[\]\(\)（）]', '', name)
        name = re.sub(r'\s+', '', name)
        # 统一常见变体
        name = name.replace('CCTV-', 'CCTV')
        name = name.replace('CCTV ', 'CCTV')
        name = name.replace('HD', '')
        name = name.replace('高清', '')
        name = name.replace('标清', '')
        name = name.replace('超清', '')
        name = name.replace('4K', '')
        name = name.replace('1080', '')
        name = name.replace('720', '')
        # 移除源标签
        name = re.sub(r'\[.*?\]', '', name)
        name = re.sub(r'【.*?】', '', name)
        return name.upper().strip()
    
    def deduplicate_channels(self, channels):
        """智能去重，同名频道只保留最快的"""
        channel_map = {}
        
        for ch in channels:
            name = ch.get('name', 'Unknown')
            normalized_name = self.normalize_channel_name(name)
            
            if normalized_name in channel_map:
                # 比较速度，保留更快的
                existing_speed = channel_map[normalized_name].get('speed', 0)
                current_speed = ch.get('speed', 0)
                
                if current_speed > existing_speed:
                    channel_map[normalized_name] = ch
            else:
                channel_map[normalized_name] = ch
        
        deduped = list(channel_map.values())
        print(f"去重: {len(channels)} -> {len(deduped)} (减少 {len(channels) - len(deduped)} 个重复)")
        return deduped
    
    # ==================== 速度分层 ====================
    
    def get_speed_tier(self, speed):
        """获取速度层级"""
        tiers = self.config.get('speed_tiers', {
            'high': 1000,
            'medium': 500,
            'low': 300
        })
        
        if speed >= tiers.get('high', 1000):
            return 'high'
        elif speed >= tiers.get('medium', 500):
            return 'medium'
        elif speed >= tiers.get('low', 300):
            return 'low'
        else:
            return 'failed'
    
    def filter_by_speed_tiers(self, channels, tiers):
        """按速度层级过滤频道"""
        filtered = []
        for ch in channels:
            speed = ch.get('speed', 0)
            tier = self.get_speed_tier(speed)
            if tier in tiers:
                filtered.append(ch)
        return filtered
    
    # ==================== 完整版（保持不变） ====================
    
    def generate_all_in_one(self):
        """生成完整的播放列表（保持原有）"""
        if not self.channels:
            print("没有频道数据，跳过完整版生成")
            return
        
        filename = 'output/all_channels.m3u'
        content = self.generate_m3u_header('全部频道（完整版）')
        content = content.replace('PLACEHOLDER', str(len(self.channels)))
        
        for ch in self.channels:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 完整版: {filename} ({len(self.channels)} 个频道)")
    
    def generate_by_region(self):
        """按地区生成完整版M3U文件（保持原有）"""
        regions = defaultdict(list)
        
        for ch in self.channels:
            region = ch.get('region', 'other')
            regions[region].append(ch)
        
        region_names = {
            'china': '中国大陆频道',
            'hongkong': '香港频道',
            'taiwan': '台湾频道',
            'macau': '澳门频道',
            'japan': '日本频道',
            'korea': '韩国频道',
            'usa': '美国频道',
            'southeast_asia': '东南亚频道',
            'international': '国际频道',
            'other': '其他频道'
        }
        
        for region_key, region_channels in regions.items():
            if not region_channels:
                continue
            
            filename = f'output/{region_key}.m3u'
            region_name = region_names.get(region_key, f'{region_key}频道')
            content = self.generate_m3u_header(f'{region_name}（完整版）')
            content = content.replace('PLACEHOLDER', str(len(region_channels)))
            
            for ch in region_channels:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {region_name}: {filename} ({len(region_channels)} 个频道)")
    
    # ==================== 分层版（按优先级分层） ====================
    
    def generate_tiered_lists(self):
        """生成分层播放列表（按速度层级）"""
        # 先去重
        deduped = self.deduplicate_channels(self.channels)
        
        # 高速频道（>1000KB/s）
        high_speed = [ch for ch in deduped if ch.get('speed', 0) >= 1000]
        # 中速频道（500-1000KB/s）
        mid_speed = [ch for ch in deduped if 500 <= ch.get('speed', 0) < 1000]
        # 低速频道（300-500KB/s）
        low_speed = [ch for ch in deduped if 300 <= ch.get('speed', 0) < 500]
        
        tiers = {
            'tier1_highspeed': ('高速频道（>1MB/s）', high_speed),
            'tier2_midspeed': ('中速频道（>500KB/s）', mid_speed),
            'tier3_lowspeed': ('低速频道（>300KB/s）', low_speed),
            'tier_high_medium': ('高速+中速频道', high_speed + mid_speed)
        }
        
        for key, (name, channels) in tiers.items():
            filename = f'output/{key}.m3u'
            content = self.generate_m3u_header(name)
            content = content.replace('PLACEHOLDER', str(len(channels)))
            
            # 按速度降序排列
            channels_sorted = sorted(channels, key=lambda x: x.get('speed', 0), reverse=True)
            
            for ch in channels_sorted:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {name}: {filename} ({len(channels)} 个频道)")
        
        # 生成按地区分层版本
        self.generate_tiered_by_region(deduped)
    
    def generate_tiered_by_region(self, channels):
        """按地区生成分层版本"""
        regions = defaultdict(list)
        for ch in channels:
            region = ch.get('region', 'other')
            regions[region].append(ch)
        
        for region_key, region_channels in regions.items():
            if len(region_channels) < 5:
                continue
            
            # 按速度排序
            region_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
            
            # 高速版
            high = [ch for ch in region_channels if ch.get('speed', 0) >= 1000]
            if high:
                filename = f'output/{region_key}_highspeed.m3u'
                content = self.generate_m3u_header(f'{region_key} 高速频道')
                content = content.replace('PLACEHOLDER', str(len(high)))
                for ch in high:
                    content += self.generate_channel_entry(ch)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ {region_key}高速版: {len(high)} 个频道")
            
            # 高速+中速版
            high_med = [ch for ch in region_channels if ch.get('speed', 0) >= 500]
            if high_med:
                filename = f'output/{region_key}_stable.m3u'
                content = self.generate_m3u_header(f'{region_key} 稳定频道')
                content = content.replace('PLACEHOLDER', str(len(high_med)))
                for ch in high_med:
                    content += self.generate_channel_entry(ch)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ {region_key}稳定版: {len(high_med)} 个频道")
    
    # ==================== 飞牛影视优化版 ====================
    
    def generate_feiniu_optimized(self):
        """为飞牛影视生成优化精选版播放列表
        综合方案1（精选）、方案2（分层）、方案3（去重）
        """
        settings = self.config.get('feiniu_settings', {})
        target_regions = settings.get('target_regions', 
            ['china', 'hongkong', 'taiwan', 'macau', 'southeast_asia', 'japan', 'korea', 'usa'])
        max_total = settings.get('max_total_channels', 200)
        
        print(f"\n{'='*60}")
        print(f"🎬 开始生成飞牛影视优化版")
        print(f"   目标地区: {', '.join(target_regions)}")
        print(f"   频道上限: {max_total}")
        print(f"{'='*60}")
        
        # Step 1: 智能去重
        print("\n📋 Step 1: 智能去重...")
        deduped = self.deduplicate_channels(self.channels)
        
        # Step 2: 按目标地区筛选
        print(f"\n🌍 Step 2: 按地区筛选...")
        region_channels = {}
        for region in target_regions:
            region_channels[region] = [ch for ch in deduped if ch.get('region') == region]
            print(f"   {region}: {len(region_channels[region])} 个频道（去重后）")
        
        # Step 3: 应用速度分层和精选规则
        print(f"\n⚡ Step 3: 应用速度分层...")
        selected_channels = []
        
        # 中国地区特殊处理
        china_channels = region_channels.get('china', [])
        china_selected = self._process_china_channels(china_channels)
        selected_channels.extend(china_selected)
        print(f"   中国大陆: 精选 {len(china_selected)} 个频道")
        
        # 港澳台（高速+中速）
        for region in ['hongkong', 'taiwan', 'macau']:
            chs = region_channels.get(region, [])
            # 港澳台保留高速+中速
            filtered = self.filter_by_speed_tiers(chs, ['high', 'medium'])
            # 按速度排序
            filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
            selected_channels.extend(filtered)
            print(f"   {region}: 保留 {len(filtered)} 个频道（高速+中速）")
        
        # 海外地区（仅高速）
        for region in ['southeast_asia', 'japan', 'korea', 'usa']:
            chs = region_channels.get(region, [])
            # 海外只保留高速频道
            filtered = self.filter_by_speed_tiers(chs, ['high'])
            # 按速度排序
            filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
            selected_channels.extend(filtered)
            print(f"   {region}: 保留 {len(filtered)} 个频道（仅高速）")
        
        # Step 4: 总数控制
        print(f"\n🔢 Step 4: 总数控制...")
        total_before = len(selected_channels)
        
        if total_before > max_total:
            print(f"   当前 {total_before} 个频道，超过上限 {max_total}，进行精选...")
            
            # 按速度降序排列
            selected_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
            
            # 确保各类别都有代表性频道
            final_channels = []
            region_counts = defaultdict(int)
            category_counts = defaultdict(int)
            
            for ch in selected_channels:
                region = ch.get('region', 'other')
                category = ch.get('category', '综合')
                
                # 每个地区至少保留5个，每个类别至少保留3个
                if region_counts[region] < 5 or category_counts[category] < 3:
                    final_channels.append(ch)
                    region_counts[region] += 1
                    category_counts[category] += 1
                    continue
                
                if len(final_channels) < max_total:
                    final_channels.append(ch)
                    region_counts[region] += 1
                    category_counts[category] += 1
            
            selected_channels = final_channels[:max_total]
            print(f"   精选后: {len(selected_channels)} 个频道")
        else:
            print(f"   当前 {total_before} 个频道，未超过上限")
        
        # Step 5: 最终排序（CCTV优先，然后按地区+速度）
        print(f"\n📊 Step 5: 最终排序...")
        selected_channels = self._final_sort(selected_channels)
        
        # Step 6: 生成M3U文件
        print(f"\n💾 Step 6: 生成文件...")
        filename = 'output/feiniu.m3u'
        content = self.generate_m3u_header('飞牛影视专用精选')
        content = content.replace('PLACEHOLDER', str(len(selected_channels)))
        
        # 添加频道说明注释
        content += '# ====================\n'
        content += f'# 飞牛影视优化版\n'
        content += f'# 频道总数: {len(selected_channels)}\n'
        content += f'# 生成时间: {datetime.now().isoformat()}\n'
        content += f'# 覆盖地区: {", ".join(target_regions)}\n'
        content += f'# 中国大陆: 高速+中速（CCTV全保留+卫视精选）\n'
        content += f'# 港澳台: 高速+中速\n'
        content += f'# 海外: 仅高速频道\n'
        content += '# ====================\n\n'
        
        for ch in selected_channels:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 打印统计
        print(f"\n{'='*60}")
        print(f"✅ 飞牛影视优化版生成完成!")
        print(f"   文件: {filename}")
        print(f"   频道总数: {len(selected_channels)}")
        print(f"\n📊 地区分布:")
        for region in target_regions:
            count = len([ch for ch in selected_channels if ch.get('region') == region])
            if count > 0:
                print(f"   {region}: {count} 个")
        print(f"{'='*60}\n")
        
        return selected_channels
    
    def _process_china_channels(self, channels):
        """处理中国大陆频道：CCTV全保留 + 卫视精选
        速度限制：高速和中速，剔除低速
        """
        settings = self.config.get('feiniu_settings', {})
        satellite_selection = settings.get('china_satellite_selection', [])
        
        # 速度筛选：只保留高速和中速
        filtered = self.filter_by_speed_tiers(channels, ['high', 'medium'])
        
        cctv_channels = []
        satellite_channels = []
        local_channels = []
        other_channels = []
        
        for ch in filtered:
            name = ch.get('name', '')
            name_upper = name.upper()
            
            # CCTV全部保留
            if 'CCTV' in name_upper:
                cctv_channels.append(ch)
            # 卫视频道精选
            elif any(sat in name for sat in satellite_selection):
                satellite_channels.append(ch)
            # 其他地方频道
            elif ch.get('region') == 'china':
                local_channels.append(ch)
            else:
                other_channels.append(ch)
        
        # 排序
        cctv_channels.sort(key=lambda x: self._cctv_sort_key(x.get('name', '')))
        satellite_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
        local_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        # 合并：CCTV + 卫视精选 + 地方（按速度限制数量）
        result = cctv_channels + satellite_channels
        
        # 地方频道按速度取前N个（避免过多）
        max_local = 20
        if local_channels:
            result.extend(local_channels[:max_local])
        
        print(f"      CCTV: {len(cctv_channels)} 个")
        print(f"      卫视精选: {len(satellite_channels)} 个")
        print(f"      地方频道: {min(len(local_channels), max_local)} 个")
        
        return result
    
    def _cctv_sort_key(self, name):
        """CCTV频道排序"""
        match = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
        if match:
            num = int(match.group(1))
            return (1, num)
        # CCTV+、CCTV4K等放在后面
        if 'CCTV' in name.upper():
            return (2, 0)
        return (3, 0)
    
    def _final_sort(self, channels):
        """最终排序：CCTV优先，然后按地区+速度"""
        def sort_key(ch):
            name = ch.get('name', '')
            region = ch.get('region', 'other')
            speed = ch.get('speed', 0)
            
            # 排序优先级
            region_order = {
                'china': 1,
                'hongkong': 2,
                'taiwan': 3,
                'macau': 4,
                'japan': 5,
                'korea': 6,
                'usa': 7,
                'southeast_asia': 8
            }
            
            # CCTV最优先
            if 'CCTV' in name.upper():
                match = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
                cctv_order = int(match.group(1)) if match else 99
                return (0, cctv_order, -speed)
            
            # 卫视其次
            if '卫视' in name:
                return (1, region_order.get(region, 99), -speed)
            
            # 其他按地区+速度
            return (2, region_order.get(region, 99), -speed)
        
        return sorted(channels, key=sort_key)
    
    # ==================== README生成 ====================
    
    def generate_readme(self):
        """生成README统计信息"""
        stats = defaultdict(lambda: {'count': 0, 'speed': 0, 'categories': defaultdict(int)})
        
        for ch in self.channels:
            region = ch.get('region', 'other')
            category = ch.get('category', '综合')
            speed = ch.get('speed', 0)
            
            stats[region]['count'] += 1
            stats[region]['speed'] += speed
            stats[region]['categories'][category] += 1
        
        total = len(self.channels)
        
        readme = f"""# 📺 IPTV 自动更新直播源

[![Auto Update](https://github.com/Alan08Xb/iptv-sources/actions/workflows/update.yml/badge.svg)](https://github.com/Alan08Xb/iptv-sources/actions/workflows/update.yml)
[![Update](https://img.shields.io/badge/更新频率-每6小时-green)](https://github.com/Alan08Xb/iptv-sources/actions)

> 🌐 自动采集、筛选、测速的IPTV直播源合集  
> ⚡ 每日多次更新 | 🎯 多地区覆盖 | 🔍 智能筛选失效源  
> 📅 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## ✨ 特性

- 🔄 **全自动更新**：每6小时自动采集最新直播源
- 🧪 **自动测速**：多线程测速，剔除失效和低速节点
- 🧹 **智能去重**：同名频道只保留最快源
- 📊 **速度分层**：高速(>1MB/s)、中速(>500KB/s)、低速(>300KB/s)
- 🚀 **飞牛优化**：专为飞牛影视定制的精选列表
- 🌍 **多地区覆盖**：中国大陆、港澳台、东南亚、日韩、美国

## 📥 播放列表

### 🎬 飞牛影视专用（推荐）

| 播放列表 | 链接 | 说明 |
|---------|------|------|
| 🚀 **飞牛影视优化版** | [feiniu.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/feiniu.m3u) | **推荐** 精选≤200频道，CCTV全+卫视精选+海外高速 |

### 📊 分层播放列表

| 层级 | 链接 | 速度 | 适用场景 |
|------|------|------|----------|
| ⚡ 高速频道 | [tier1_highspeed.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/tier1_highspeed.m3u) | >1MB/s | 极速体验 |
| 🚀 高速+中速 | [tier_high_medium.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/tier_high_medium.m3u) | >500KB/s | 稳定观看 |
| ✅ 中速频道 | [tier2_midspeed.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/tier2_midspeed.m3u) | >500KB/s | 备用选择 |

### 🌍 地区频道

| 地区 | 完整版 | 高速版 | 稳定版 |
|------|--------|--------|--------|
| 🇨🇳 中国大陆 | [china.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/china.m3u) | [china_highspeed.m3u](https://raw.githubusercontent.com/你的用户名/iptv-sources/main/output/china_highspeed.m3u) | [china_stable.m3u](https://raw.githubusercontent.com/你的用户名/iptv-sources/main/output/china_stable.m3u) |
| 🇭🇰 香港 | [hongkong.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/hongkong.m3u) | - | - |
| 🇹🇼 台湾 | [taiwan.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/taiwan.m3u) | - | - |
| 🇲🇴 澳门 | [macau.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/macau.m3u) | - | - |
| 🇯🇵 日本 | [japan.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/japan.m3u) | - | - |
| 🇰🇷 韩国 | [korea.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/korea.m3u) | - | - |
| 🇺🇸 美国 | [usa.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/usa.m3u) | - | - |
| 🌏 东南亚 | [southeast_asia.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/southeast_asia.m3u) | - | - |

### 📦 完整合集

| 播放列表 | 链接 | 说明 |
|---------|------|------|
| 🔗 全部频道 | [all_channels.m3u](https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/all_channels.m3u) | 所有可用频道（完整版） |

## 📊 频道统计

| 地区 | 频道总数 | 平均速度 | 高速(>1MB) | 中速(>500KB) |
|------|----------|----------|------------|-------------|
"""
        
        region_order = ['china', 'hongkong', 'taiwan', 'macau', 'japan', 'korea', 'usa', 'southeast_asia', 'international', 'other']
        emoji_map = {
            'china': '🇨🇳', 'hongkong': '🇭🇰', 'taiwan': '🇹🇼', 'macau': '🇲🇴',
            'japan': '🇯🇵', 'korea': '🇰🇷', 'usa': '🇺🇸', 'southeast_asia': '🌏',
            'international': '🌍', 'other': '📡'
        }
        
        for region in region_order:
            if region in stats:
                data = stats[region]
                avg_speed = data['speed'] / data['count'] if data['count'] > 0 else 0
                high_count = len([ch for ch in self.channels if ch.get('region') == region and ch.get('speed', 0) >= 1000])
                mid_count = len([ch for ch in self.channels if ch.get('region') == region and 500 <= ch.get('speed', 0) < 1000])
                readme += f"| {emoji_map.get(region, '📡')} {region} | {data['count']} | {avg_speed:.0f} KB/s | {high_count} | {mid_count} |\n"
        
        readme += f"| 📊 **总计** | **{total}** | - | - | - |\n"
        
        readme += f"""
## 🚀 快速开始

### 🖥️ 飞牛影视（推荐）
1. 打开飞牛影视 → ⚙️ 设置 → 直播源管理
2. 点击 ➕ 添加 → 选择 **M3U8源**
3. 粘贴链接：`https://raw.githubusercontent.com/Alan08Xb/iptv-sources/main/output/feiniu.m3u`
4. 保存并刷新即可观看

### 📱 其他播放器

| 播放器 | 推荐播放列表 |
|--------|-------------|
| VLC | tier_high_medium.m3u（高速+中速） |
| PotPlayer | tier1_highspeed.m3u（仅高速） |
| Kodi | feiniu.m3u（飞牛优化版） |
| IPTV Pro | all_channels.m3u（完整版） |

## 📖 播放列表说明

### 分层逻辑
- **高速频道 (>1MB/s)**：最佳观看体验，秒开无缓冲
- **中速频道 (>500KB/s)**：流畅观看，偶有缓冲
- **低速频道 (>300KB/s)**：基本可看，适合备用

### 飞牛影视优化版规则
- 中国大陆：CCTV全部保留 + 卫视精选（高速+中速）
- 港澳台：全部高速+中速频道
- 海外（日韩美东南亚）：仅保留高速频道（>1MB/s）
- 总频道数：≤200个
- 智能去重：同名频道只保留最快源

## ⚠️ 免责声明

> 本项目仅供学习研究使用，所有源均来自网络公开资源。请勿用于商业用途，如有侵权请联系删除。

---
"""
        
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(readme)
        
        print("✅ README.md 已更新")
    
    def generate_all(self):
        """生成所有类型的播放列表"""
        print(f"\n{'='*60}")
        print(f"🚀 开始生成所有播放列表")
        print(f"{'='*60}\n")
        
        # 1. 完整版（保持不变）
        print("📦 生成完整版播放列表...")
        self.generate_all_in_one()
        self.generate_by_region()
        
        # 2. 分层版（去重+分层）
        print("\n📊 生成分层播放列表...")
        self.generate_tiered_lists()
        
        # 3. 飞牛影视优化版
        print("\n🎬 生成飞牛影视优化版...")
        self.generate_feiniu_optimized()
        
        # 4. README
        print("\n📝 更新README...")
        self.generate_readme()
        
        print(f"\n{'='*60}")
        print(f"✅ 所有播放列表生成完成!")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    try:
        generator = M3UGenerator()
        generator.generate_all()
    except Exception as e:
        print(f"生成播放列表时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
