#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分类M3U播放列表 - 简化输出版
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
        with open('config/sources.json', 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        if channels_file is None:
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
            print(f"加载频道: {len(self.channels)} 个")
        else:
            print("警告: 未找到频道数据")
            self.channels = []
    
    def generate_m3u_header(self, name, count=0):
        header = f'#EXTM3U\n'
        header += f'#PLAYLIST:{name}\n'
        header += f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
        if count > 0:
            header += f'# Channels: {count}\n'
        return header
    
    def generate_channel_entry(self, channel):
        name = channel.get('name', 'Unknown')
        url = channel.get('url', '')
        logo = channel.get('logo', '')
        group = channel.get('group', channel.get('category', '综合'))
        speed = channel.get('speed', 0)
        region = channel.get('region', '')
        
        extinf = f'#EXTINF:-1'
        if logo:
            extinf += f' tvg-logo="{logo}"'
        extinf += f' group-title="{group}"'
        if speed > 0:
            extinf += f' tvg-speed="{speed:.0f}KB/s"'
        extinf += f',{name}'
        
        return f'{extinf}\n{url}\n'
    
    def normalize_channel_name(self, name):
        name = name.strip()
        name = re.sub(r'[【】\[\]\(\)（）]', '', name)
        name = re.sub(r'\s+', '', name)
        name = name.replace('CCTV-', 'CCTV').replace('CCTV ', 'CCTV')
        name = name.replace('HD', '').replace('高清', '').replace('标清', '')
        name = name.replace('超清', '').replace('4K', '').replace('1080P', '').replace('720P', '')
        name = re.sub(r'\[.*?\]', '', name)
        name = re.sub(r'【.*?】', '', name)
        name = re.sub(r'\(.*?\)', '', name)
        return name.upper().strip()
    
    def deduplicate_channels(self, channels):
        """智能去重，同名保留最快的"""
        channel_map = {}
        for ch in channels:
            norm = self.normalize_channel_name(ch.get('name', 'Unknown'))
            if norm not in channel_map or ch.get('speed', 0) > channel_map[norm].get('speed', 0):
                channel_map[norm] = ch
        deduped = list(channel_map.values())
        print(f"  去重: {len(channels)} -> {len(deduped)}")
        return deduped
    
    def get_speed_tier(self, speed):
        tiers = self.config.get('speed_tiers', {'high': 1000, 'medium': 500, 'low': 150})
        if speed >= tiers.get('high', 1000):
            return 'high'
        elif speed >= tiers.get('medium', 500):
            return 'medium'
        elif speed >= tiers.get('low', 150):
            return 'low'
        return 'failed'
    
    def filter_speed(self, channels, tiers):
        return [ch for ch in channels if self.get_speed_tier(ch.get('speed', 0)) in tiers]
    
    def save_m3u(self, filename, name, channels):
        """保存M3U文件，自动覆盖"""
        os.makedirs('output', exist_ok=True)
        filepath = f'output/{filename}'
        content = self.generate_m3u_header(name, len(channels))
        for ch in channels:
            content += self.generate_channel_entry(ch)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    # ==================== 完整版 ====================
    
    def generate_all(self):
        """完整版：去重 + 剔除低速(<150KB/s)"""
        deduped = self.deduplicate_channels(self.channels)
        filtered = self.filter_speed(deduped, ['high', 'medium', 'low'])
        filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        high = len([ch for ch in filtered if ch.get('speed', 0) >= 1000])
        mid = len([ch for ch in filtered if 500 <= ch.get('speed', 0) < 1000])
        low = len([ch for ch in filtered if 150 <= ch.get('speed', 0) < 500])
        
        self.save_m3u('all.m3u', '全部频道', filtered)
        print(f"  ✅ all.m3u: {len(filtered)} 个 (高速:{high} 中速:{mid} 低速:{low})")
    
    # ==================== 中国大陆 ====================
    
    def generate_china(self):
        """中国大陆：高速+中速"""
        china = [ch for ch in self.channels if ch.get('region') == 'china']
        deduped = self.deduplicate_channels(china)
        filtered = self.filter_speed(deduped, ['high', 'medium'])
        filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        self.save_m3u('china.m3u', '中国大陆频道', filtered)
        
        cctv = len([ch for ch in filtered if 'CCTV' in ch.get('name', '').upper()])
        sat = len([ch for ch in filtered if '卫视' in ch.get('name', '')])
        print(f"  ✅ china.m3u: {len(filtered)} 个 (CCTV:{cctv} 卫视:{sat})")
    
    # ==================== 东亚 ====================
    
    def generate_east_asia(self):
        """东亚：港澳台+韩国+日本+东南亚，仅高速"""
        east_asia_regions = ['hongkong', 'taiwan', 'macau', 'japan', 'korea', 'southeast_asia']
        
        east_asia = [ch for ch in self.channels if ch.get('region') in east_asia_regions]
        deduped = self.deduplicate_channels(east_asia)
        filtered = self.filter_speed(deduped, ['high'])
        filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        self.save_m3u('east_asia.m3u', '东亚频道', filtered)
        
        region_counts = defaultdict(int)
        for ch in filtered:
            region_counts[ch.get('region', 'other')] += 1
        detail = ', '.join([f'{r}:{c}' for r, c in sorted(region_counts.items())])
        print(f"  ✅ east_asia.m3u: {len(filtered)} 个 ({detail})")
    
    # ==================== 海外高速 ====================
    
    def generate_overseas_highspeed(self):
        """海外高速：除中国大陆外的所有地区，仅高速"""
        overseas = [ch for ch in self.channels if ch.get('region') != 'china']
        deduped = self.deduplicate_channels(overseas)
        filtered = self.filter_speed(deduped, ['high'])
        filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        self.save_m3u('overseas_highspeed.m3u', '海外高速频道', filtered)
        
        region_counts = defaultdict(int)
        for ch in filtered:
            region_counts[ch.get('region', 'other')] += 1
        detail = ', '.join([f'{r}:{c}' for r, c in sorted(region_counts.items())])
        print(f"  ✅ overseas_highspeed.m3u: {len(filtered)} 个 ({detail})")
    
    # ==================== 按类别 ====================
    
    def generate_by_category(self):
        """按类别生成"""
        deduped = self.deduplicate_channels(self.channels)
        filtered = self.filter_speed(deduped, ['high', 'medium', 'low'])
        
        categories = defaultdict(list)
        for ch in filtered:
            cat = ch.get('category', '综合')
            categories[cat].append(ch)
        
        emoji = {
            '新闻': '📰', '体育': '⚽', '影视': '🎬', '综艺': '🎭',
            '少儿': '🧒', '音乐': '🎵', '纪录片': '🎥', '教育': '📚', '综合': '📺'
        }
        
        for cat in sorted(categories.keys()):
            chs = categories[cat]
            chs.sort(key=lambda x: x.get('speed', 0), reverse=True)
            filename = f'category_{cat}.m3u'
            self.save_m3u(filename, f'{cat}频道', chs)
            print(f"  ✅ {filename}: {len(chs)} 个")
    
    # ==================== 飞牛优化版 ====================
    
    def generate_feiniu(self):
        """飞牛优化版：CCTV≤30, 卫视≤50, 海外≤170(每区3-20)"""
        cctv_max = 30
        satellite_max = 50
        overseas_max = 170
        per_min = 3
        per_max = 20
        
        overseas_regions = ['hongkong', 'taiwan', 'macau', 'southeast_asia', 'japan', 'korea', 'usa']
        
        deduped = self.deduplicate_channels(self.channels)
        
        # 中国大陆：高速+中速
        china = [ch for ch in deduped if ch.get('region') == 'china']
        china = self.filter_speed(china, ['high', 'medium'])
        
        cctv_list, satellite_list, other_list = [], [], []
        for ch in china:
            name = ch.get('name', '')
            if 'CCTV' in name.upper() or '央视' in name:
                cctv_list.append(ch)
            elif '卫视' in name:
                satellite_list.append(ch)
            else:
                other_list.append(ch)
        
        cctv_list.sort(key=lambda x: self._cctv_sort_key(x.get('name', '')))
        satellite_list.sort(key=lambda x: x.get('speed', 0), reverse=True)
        other_list.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        china_selected = cctv_list[:cctv_max] + satellite_list[:satellite_max] + other_list[:30]
        
        # 海外：仅高速，每区3-20个
        region_high = {}
        for region in overseas_regions:
            chs = [ch for ch in deduped if ch.get('region') == region]
            chs = self.filter_speed(chs, ['high'])
            chs = self._dedup_by_name(chs)
            chs.sort(key=lambda x: x.get('speed', 0), reverse=True)
            region_high[region] = chs
        
        # 第一轮：每区至少per_min
        round1 = {}
        for region in overseas_regions:
            take = min(per_min, len(region_high[region]))
            round1[region] = region_high[region][:take]
        
        used = sum(len(v) for v in round1.values())
        remaining = overseas_max - used
        
        # 第二轮：按速度分配
        candidates = []
        for region in overseas_regions:
            taken = len(round1[region])
            for ch in region_high[region][taken:per_max]:
                candidates.append((region, ch))
        candidates.sort(key=lambda x: x[1].get('speed', 0), reverse=True)
        
        round2 = defaultdict(list)
        for region, ch in candidates[:remaining]:
            round2[region].append(ch)
        
        overseas_selected = []
        for region in overseas_regions:
            region_chs = round1[region] + round2[region]
            overseas_selected.extend(region_chs[:per_max])
        
        if len(overseas_selected) > overseas_max:
            overseas_selected.sort(key=lambda x: x.get('speed', 0), reverse=True)
            overseas_selected = overseas_selected[:overseas_max]
        
        # 合并排序
        all_chs = china_selected + overseas_selected
        all_chs = self._final_sort(all_chs)
        
        self.save_m3u('feiniu.m3u', '飞牛影视专用精选', all_chs)
        
        # 统计
        china_count = len([ch for ch in all_chs if ch.get('region') == 'china'])
        overseas_count = len([ch for ch in all_chs if ch.get('region') != 'china'])
        print(f"  ✅ feiniu.m3u: {len(all_chs)} 个 (大陆:{china_count} 海外:{overseas_count})")
    
    # ==================== 辅助方法 ====================
    
    def _dedup_by_name(self, channels):
        name_map = {}
        for ch in channels:
            norm = self.normalize_channel_name(ch.get('name', ''))
            if norm not in name_map or ch.get('speed', 0) > name_map[norm].get('speed', 0):
                name_map[norm] = ch
        return list(name_map.values())
    
    def _cctv_sort_key(self, name):
        match = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
        if match:
            return (1, int(match.group(1)))
        return (2, 0) if 'CCTV' in name.upper() else (3, 0)
    
    def _final_sort(self, channels):
        region_order = {'china':1, 'hongkong':2, 'taiwan':3, 'macau':4,
                        'japan':5, 'korea':6, 'usa':7, 'southeast_asia':8}
        def key(ch):
            name = ch.get('name', '')
            region = ch.get('region', 'other')
            speed = ch.get('speed', 0)
            if 'CCTV' in name.upper():
                m = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
                return (0, int(m.group(1)) if m else 99, -speed)
            if '卫视' in name:
                return (1, region_order.get(region, 99), -speed)
            if region == 'china':
                return (2, 0, -speed)
            return (3, region_order.get(region, 99), -speed)
        return sorted(channels, key=key)
    
    # ==================== 主流程 ====================
    
    def run(self):
        print(f"\n{'='*60}")
        print(f"🚀 生成所有播放列表")
        print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        print("📦 完整版 (去重+剔除低速<150KB/s)...")
        self.generate_all()
        
        print("\n🇨🇳 中国大陆 (高速+中速>500KB/s)...")
        self.generate_china()
        
        print("\n🌏 东亚 (港澳台+日韩+东南亚, 仅高速>1MB/s)...")
        self.generate_east_asia()
        
        print("\n🌍 海外高速 (除大陆外所有地区, 仅高速>1MB/s)...")
        self.generate_overseas_highspeed()
        
        print("\n🎬 飞牛优化版...")
        self.generate_feiniu()
        
        print("\n📂 按类别分组...")
        self.generate_by_category()
        
        # 清理旧文件（保留需要的m3u文件）
        self._cleanup()
        
        print(f"\n{'='*60}")
        print(f"✅ 全部完成!")
        self._print_summary()
        print(f"{'='*60}\n")
    
    def _cleanup(self):
        """清理output目录，只保留需要的m3u文件和JSON数据文件"""
        keep_files = {
            'all.m3u', 'china.m3u', 'east_asia.m3u', 'overseas_highspeed.m3u',
            'feiniu.m3u',
            'category_新闻.m3u', 'category_体育.m3u', 'category_影视.m3u',
            'category_综艺.m3u', 'category_少儿.m3u', 'category_音乐.m3u',
            'category_纪录片.m3u', 'category_教育.m3u', 'category_综合.m3u',
            'all_channels.json', 'valid_channels_latest.json', 'stats.json'
        }
        
        for f in os.listdir('output'):
            if f not in keep_files and not f.startswith('valid_channels_'):
                os.remove(os.path.join('output', f))
    
    def _print_summary(self):
        """打印输出文件摘要"""
        print(f"\n📁 输出文件:")
        files = sorted([f for f in os.listdir('output') if f.endswith('.m3u')])
        for f in files:
            filepath = os.path.join('output', f)
            with open(filepath, 'r', encoding='utf-8') as fh:
                content = fh.read()
                count = content.count('#EXTINF:')
            size = os.path.getsize(filepath)
            print(f"   {f}: {count} 个频道 ({size/1024:.1f}KB)")


if __name__ == '__main__':
    try:
        generator = M3UGenerator()
        generator.run()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
