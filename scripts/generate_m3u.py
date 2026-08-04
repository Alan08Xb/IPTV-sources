#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分类M3U播放列表
包含：完整版、分层版、去重版、飞牛影视优化版
"""

import json
import os
import re
import sys
import glob
from datetime import datetime
from collections import defaultdict

class M3UGenerator:
    def __init__(self, channels_file=None):
        # 加载配置
        with open('config/sources.json', 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # 自动找到最新的测试结果文件
        if channels_file is None:
            # 优先使用最新的测速结果
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
            print(f"加载频道数据: {channels_file} ({len(self.channels)} 个频道)")
        else:
            print("警告: 未找到频道数据文件")
            self.channels = []
    
    def generate_m3u_header(self, name):
        """生成M3U文件头"""
        return f'#EXTM3U\n#PLAYLIST:{name}\n# Generated at: {datetime.now().isoformat()}\n'
    
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
        name = re.sub(r'[【】\[\]\(\)（）]', '', name)
        name = re.sub(r'\s+', '', name)
        name = name.replace('CCTV-', 'CCTV')
        name = name.replace('CCTV ', 'CCTV')
        name = name.replace('HD', '')
        name = name.replace('高清', '')
        name = name.replace('标清', '')
        name = name.replace('超清', '')
        name = name.replace('4K', '')
        name = name.replace('1080', '')
        name = name.replace('720', '')
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
    
    # ==================== 完整版 ====================
    
    def generate_all_in_one(self):
        """生成完整的播放列表"""
        if not self.channels:
            print("没有频道数据，跳过完整版生成")
            return
        
        filename = 'output/all_channels.m3u'
        content = self.generate_m3u_header(f'全部频道 ({len(self.channels)}个)')
        
        for ch in self.channels:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 完整版: {filename} ({len(self.channels)} 个频道)")
    
    def generate_by_region(self):
        """按地区生成完整版M3U文件"""
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
            content = self.generate_m3u_header(f'{region_name} ({len(region_channels)}个)')
            
            for ch in region_channels:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {region_name}: {filename} ({len(region_channels)} 个频道)")
    
    # ==================== 分层版 ====================
    
    def generate_tiered_lists(self):
        """生成分层播放列表"""
        # 先去重
        deduped = self.deduplicate_channels(self.channels)
        
        # 高速频道（>1000KB/s）
        high_speed = [ch for ch in deduped if ch.get('speed', 0) >= 1000]
        # 中速频道（500-1000KB/s）
        mid_speed = [ch for ch in deduped if 500 <= ch.get('speed', 0) < 1000]
        # 低速频道（300-500KB/s）
        low_speed = [ch for ch in deduped if 300 <= ch.get('speed', 0) < 500]
        
        tiers = {
            'tier1_highspeed': ('高速频道 >1MB/s', high_speed),
            'tier2_midspeed': ('中速频道 >500KB/s', mid_speed),
            'tier3_lowspeed': ('低速频道 >300KB/s', low_speed),
            'tier_high_medium': ('高速+中速频道', high_speed + mid_speed)
        }
        
        for key, (name, channels) in tiers.items():
            filename = f'output/{key}.m3u'
            content = self.generate_m3u_header(f'{name} ({len(channels)}个)')
            
            channels_sorted = sorted(channels, key=lambda x: x.get('speed', 0), reverse=True)
            
            for ch in channels_sorted:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {name}: {filename} ({len(channels)} 个频道)")
    
    # ==================== 飞牛影视优化版 ====================
    
    def generate_feiniu_optimized(self):
        """为飞牛影视生成优化精选版"""
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
            print(f"   {region}: {len(region_channels[region])} 个频道")
        
        # Step 3: 应用速度分层
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
            filtered = self.filter_by_speed_tiers(chs, ['high', 'medium'])
            filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
            selected_channels.extend(filtered)
            print(f"   {region}: 保留 {len(filtered)} 个频道（高速+中速）")
        
        # 海外地区（仅高速）
        for region in ['southeast_asia', 'japan', 'korea', 'usa']:
            chs = region_channels.get(region, [])
            filtered = self.filter_by_speed_tiers(chs, ['high'])
            filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
            selected_channels.extend(filtered)
            print(f"   {region}: 保留 {len(filtered)} 个频道（仅高速）")
        
        # Step 4: 总数控制
        print(f"\n🔢 Step 4: 总数控制...")
        total_before = len(selected_channels)
        
        if total_before > max_total:
            print(f"   当前 {total_before} 个频道，超过上限 {max_total}，进行精选...")
            selected_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
            selected_channels = selected_channels[:max_total]
            print(f"   精选后: {len(selected_channels)} 个频道")
        else:
            print(f"   当前 {total_before} 个频道，未超过上限")
        
        # Step 5: 最终排序
        print(f"\n📊 Step 5: 最终排序...")
        selected_channels = self._final_sort(selected_channels)
        
        # Step 6: 生成M3U文件
        print(f"\n💾 Step 6: 生成文件...")
        filename = 'output/feiniu.m3u'
        content = self.generate_m3u_header(f'飞牛影视专用精选 ({len(selected_channels)}个)')
        
        content += '# ====================\n'
        content += f'# 飞牛影视优化版\n'
        content += f'# 频道总数: {len(selected_channels)}\n'
        content += f'# 生成时间: {datetime.now().isoformat()}\n'
        content += f'# 覆盖地区: {", ".join(target_regions)}\n'
        content += f'# 规则: 中国大陆高速+中速(CCTV全+卫视精选), 港澳台高速+中速, 海外仅高速\n'
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
        """处理中国大陆频道：CCTV全保留 + 卫视精选"""
        settings = self.config.get('feiniu_settings', {})
        satellite_selection = settings.get('china_satellite_selection', [])
        
        # 速度筛选：只保留高速和中速
        filtered = self.filter_by_speed_tiers(channels, ['high', 'medium'])
        
        cctv_channels = []
        satellite_channels = []
        local_channels = []
        
        for ch in filtered:
            name = ch.get('name', '')
            name_upper = name.upper()
            
            if 'CCTV' in name_upper:
                cctv_channels.append(ch)
            elif any(sat in name for sat in satellite_selection):
                satellite_channels.append(ch)
            else:
                local_channels.append(ch)
        
        # 排序
        cctv_channels.sort(key=lambda x: self._cctv_sort_key(x.get('name', '')))
        satellite_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
        local_channels.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        # 合并：CCTV + 卫视精选 + 地方（限制数量）
        result = cctv_channels + satellite_channels
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
        if 'CCTV' in name.upper():
            return (2, 0)
        return (3, 0)
    
    def _final_sort(self, channels):
        """最终排序：CCTV优先，然后按地区+速度"""
        region_order = {
            'china': 1, 'hongkong': 2, 'taiwan': 3, 'macau': 4,
            'japan': 5, 'korea': 6, 'usa': 7, 'southeast_asia': 8
        }
        
        def sort_key(ch):
            name = ch.get('name', '')
            region = ch.get('region', 'other')
            speed = ch.get('speed', 0)
            
            if 'CCTV' in name.upper():
                match = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
                cctv_order = int(match.group(1)) if match else 99
                return (0, cctv_order, -speed)
            
            if '卫视' in name:
                return (1, region_order.get(region, 99), -speed)
            
            return (2, region_order.get(region, 99), -speed)
        
        return sorted(channels, key=sort_key)
    
    def generate_all(self):
        """生成所有类型的播放列表"""
        print(f"\n{'='*60}")
        print(f"🚀 开始生成所有播放列表")
        print(f"{'='*60}\n")
        
        # 1. 完整版
        print("📦 生成完整版播放列表...")
        self.generate_all_in_one()
        self.generate_by_region()
        
        # 2. 分层版
        print("\n📊 生成分层播放列表...")
        self.generate_tiered_lists()
        
        # 3. 飞牛影视优化版
        print("\n🎬 生成飞牛影视优化版...")
        self.generate_feiniu_optimized()
        
        print(f"\n{'='*60}")
        print(f"✅ 所有播放列表生成完成!")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    try:
        generator = M3UGenerator()
        generator.generate_all()
    except Exception as e:
        print(f"❌ 生成播放列表时出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
