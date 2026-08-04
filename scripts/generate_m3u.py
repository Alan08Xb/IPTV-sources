#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分类M3U播放列表 - 完整版也去重限速
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
            print(f"加载频道: {channels_file} ({len(self.channels)} 个)")
        else:
            print("警告: 未找到频道数据")
            self.channels = []
    
    def generate_m3u_header(self, name):
        return f'#EXTM3U\n#PLAYLIST:{name}\n# Generated at: {datetime.now().isoformat()}\n'
    
    def generate_channel_entry(self, channel):
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
    
    def normalize_channel_name(self, name):
        """标准化频道名称"""
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
        name = name.replace('1080P', '')
        name = name.replace('720P', '')
        name = re.sub(r'\[.*?\]', '', name)
        name = re.sub(r'【.*?】', '', name)
        name = re.sub(r'\(.*?\)', '', name)
        return name.upper().strip()
    
    def deduplicate_channels(self, channels):
        """智能去重"""
        channel_map = {}
        
        for ch in channels:
            name = ch.get('name', 'Unknown')
            normalized = self.normalize_channel_name(name)
            
            if normalized in channel_map:
                if ch.get('speed', 0) > channel_map[normalized].get('speed', 0):
                    channel_map[normalized] = ch
            else:
                channel_map[normalized] = ch
        
        deduped = list(channel_map.values())
        print(f"去重: {len(channels)} -> {len(deduped)}")
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
    
    def filter_by_speed_tiers(self, channels, tiers):
        return [ch for ch in channels if self.get_speed_tier(ch.get('speed', 0)) in tiers]
    
    # ==================== 完整版（新增去重+限速） ====================
    
    def generate_all_in_one(self):
        """完整版：去重 + 剔除低速（<150KB/s）"""
        if not self.channels:
            return
        
        # 去重
        deduped = self.deduplicate_channels(self.channels)
        
        # 剔除低速频道（速度<150KB/s）
        filtered = [ch for ch in deduped if ch.get('speed', 0) >= 150]
        
        # 按速度排序
        filtered.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        filename = 'output/all_channels.m3u'
        content = self.generate_m3u_header(f'全部频道 ({len(filtered)}个)')
        content += f'# 去重并剔除低速频道(<150KB/s)\n'
        content += f'# 原始: {len(self.channels)} -> 去重: {len(deduped)} -> 过滤: {len(filtered)}\n'
        
        for ch in filtered:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 统计
        high = len([ch for ch in filtered if ch.get('speed', 0) >= 1000])
        mid = len([ch for ch in filtered if 500 <= ch.get('speed', 0) < 1000])
        low = len([ch for ch in filtered if 150 <= ch.get('speed', 0) < 500])
        
        print(f"✅ 完整版: {len(filtered)} 个 (高速:{high}, 中速:{mid}, 低速:{low})")
        print(f"   原始:{len(self.channels)} -> 去重:{len(deduped)} -> 过滤低速:{len(filtered)}")
    
    def generate_by_region(self):
        """按地区生成：去重 + 剔除低速"""
        # 先去重
        deduped = self.deduplicate_channels(self.channels)
        
        # 剔除低速
        filtered = [ch for ch in deduped if ch.get('speed', 0) >= 150]
        
        # 按地区分组
        regions = defaultdict(list)
        for ch in filtered:
            region = ch.get('region', 'other')
            regions[region].append(ch)
        
        region_emoji = {
            'china': '🇨🇳', 'hongkong': '🇭🇰', 'taiwan': '🇹🇼', 'macau': '🇲🇴',
            'japan': '🇯🇵', 'korea': '🇰🇷', 'usa': '🇺🇸', 'southeast_asia': '🌏',
            'international': '🌍', 'other': '📡'
        }
        
        for region, chs in sorted(regions.items()):
            if not chs:
                continue
            # 按速度排序
            chs.sort(key=lambda x: x.get('speed', 0), reverse=True)
            
            filename = f'output/{region}.m3u'
            content = self.generate_m3u_header(f'{region_emoji.get(region, "")} {region} ({len(chs)}个)')
            
            for ch in chs:
                content += self.generate_channel_entry(ch)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {region}: {len(chs)} 个频道")
    
    # ==================== 分层版 ====================
    
    def generate_tiered_lists(self):
        """分层版：去重 + 速度分层"""
        deduped = self.deduplicate_channels(self.channels)
        
        tiers = {
            'tier1_highspeed': ('高速 >1MB/s', [ch for ch in deduped if ch.get('speed', 0) >= 1000]),
            'tier2_midspeed': ('中速 500KB-1MB/s', [ch for ch in deduped if 500 <= ch.get('speed', 0) < 1000]),
            'tier3_lowspeed': ('低速 150-500KB/s', [ch for ch in deduped if 150 <= ch.get('speed', 0) < 500]),
            'tier_high_medium': ('高速+中速 >500KB/s', [ch for ch in deduped if ch.get('speed', 0) >= 500]),
            'tier_all_valid': ('全部可用 >150KB/s', [ch for ch in deduped if ch.get('speed', 0) >= 150]),
        }
        
        for key, (name, chs) in tiers.items():
            filename = f'output/{key}.m3u'
            content = self.generate_m3u_header(f'{name} ({len(chs)}个)')
            for ch in sorted(chs, key=lambda x: x.get('speed', 0), reverse=True):
                content += self.generate_channel_entry(ch)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ {name}: {len(chs)} 个频道")
    
    # ==================== 飞牛影视优化版 ====================
    
    def generate_feiniu_optimized(self):
        """
        飞牛版频道数量规则：
        - CCTV: ≤30个
        - 卫视: ≤50个
        - 港澳台+日韩+东南亚+美国: ≤170个，每区3-20个
        - 大陆高速+中速，海外仅高速
        """
        
        cctv_max = 30
        satellite_max = 50
        overseas_total_max = 170
        overseas_per_min = 3
        overseas_per_max = 20
        target_regions = ['china', 'hongkong', 'taiwan', 'macau', 'southeast_asia', 'japan', 'korea', 'usa']
        
        print(f"\n{'='*60}")
        print(f"🎬 飞牛影视优化版")
        print(f"   CCTV≤{cctv_max}, 卫视≤{satellite_max}, 海外≤{overseas_total_max}")
        print(f"   海外每区: {overseas_per_min}-{overseas_per_max}个")
        print(f"{'='*60}")
        
        # 去重
        deduped = self.deduplicate_channels(self.channels)
        
        # 按地区分组
        region_channels = {}
        for region in target_regions:
            chs = [ch for ch in deduped if ch.get('region') == region]
            region_channels[region] = chs
            print(f"   {region}: {len(chs)} 个")
        
        # 中国大陆处理
        china_chs = region_channels.get('china', [])
        china_selected = self._process_china_channels_v2(china_chs, cctv_max, satellite_max)
        print(f"   大陆: {len(china_selected)} 个")
        
        # 海外处理
        overseas_regions = ['hongkong', 'taiwan', 'macau', 'southeast_asia', 'japan', 'korea', 'usa']
        overseas_selected = self._process_overseas_channels(
            region_channels, overseas_regions, overseas_total_max, overseas_per_min, overseas_per_max
        )
        print(f"   海外: {len(overseas_selected)} 个")
        
        # 合并排序
        all_selected = china_selected + overseas_selected
        all_selected = self._final_sort(all_selected)
        
        # 生成文件
        filename = 'output/feiniu.m3u'
        content = self.generate_m3u_header(f'飞牛影视专用精选 ({len(all_selected)}个)')
        content += f'# CCTV≤{cctv_max}, 卫视≤{satellite_max}, 海外≤{overseas_total_max}\n'
        content += f'# 大陆:高速+中速, 海外:仅高速\n'
        
        for ch in all_selected:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 统计
        print(f"\n✅ 飞牛版: {len(all_selected)} 个频道")
        for region in target_regions:
            count = len([ch for ch in all_selected if ch.get('region') == region])
            if count > 0:
                print(f"   {region}: {count} 个")
        print()
        
        return all_selected
    
    def _process_china_channels_v2(self, channels, cctv_max, satellite_max):
        """中国大陆频道处理"""
        filtered = self.filter_by_speed_tiers(channels, ['high', 'medium'])
        
        satellite_keywords = [
            '湖南卫视', '浙江卫视', '江苏卫视', '东方卫视', '北京卫视',
            '广东卫视', '深圳卫视', '山东卫视', '安徽卫视', '湖北卫视',
            '四川卫视', '重庆卫视', '天津卫视', '黑龙江卫视', '辽宁卫视',
            '江西卫视', '河南卫视', '河北卫视', '东南卫视', '吉林卫视',
            '贵州卫视', '云南卫视', '海南卫视', '广西卫视', '陕西卫视',
            '山西卫视', '甘肃卫视', '青海卫视', '新疆卫视', '西藏卫视',
            '宁夏卫视', '内蒙古卫视', '金鹰卡通', '卡酷少儿', '炫动卡通',
        ]
        
        cctv_list, satellite_list, other_list = [], [], []
        
        for ch in filtered:
            name = ch.get('name', '')
            if 'CCTV' in name.upper() or '央视' in name:
                cctv_list.append(ch)
            elif '卫视' in name or any(kw in name for kw in satellite_keywords):
                satellite_list.append(ch)
            else:
                other_list.append(ch)
        
        cctv_unique = self._dedup_by_name(cctv_list)
        cctv_unique.sort(key=lambda x: self._cctv_sort_key(x.get('name', '')))
        
        satellite_unique = self._dedup_by_name(satellite_list)
        satellite_unique.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        other_unique = self._dedup_by_name(other_list)
        other_unique.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        result = cctv_unique[:cctv_max] + satellite_unique[:satellite_max]
        remaining = max(0, 200 - len(result))
        if remaining > 0 and other_unique:
            result.extend(other_unique[:min(remaining, 30)])
        
        print(f"      CCTV:{len(cctv_unique)}->{min(len(cctv_unique), cctv_max)}")
        print(f"      卫视:{len(satellite_unique)}->{min(len(satellite_unique), satellite_max)}")
        return result
    
    def _process_overseas_channels(self, region_channels, regions, total_max, per_min, per_max):
        """海外频道处理：仅高速，每区3-20个"""
        region_high = {}
        for region in regions:
            chs = region_channels.get(region, [])
            high = self.filter_by_speed_tiers(chs, ['high'])
            high = self._dedup_by_name(high)
            high.sort(key=lambda x: x.get('speed', 0), reverse=True)
            region_high[region] = high
        
        # 第一轮：每区至少per_min
        round1 = {}
        for region in regions:
            take = min(per_min, len(region_high[region]))
            round1[region] = region_high[region][:take]
        
        round1_total = sum(len(v) for v in round1.values())
        remaining = total_max - round1_total
        
        # 第二轮：按速度分配
        all_candidates = []
        for region in regions:
            taken = len(round1[region])
            for ch in region_high[region][taken:per_max]:
                all_candidates.append((region, ch))
        all_candidates.sort(key=lambda x: x[1].get('speed', 0), reverse=True)
        
        round2 = defaultdict(list)
        for region, ch in all_candidates[:remaining]:
            round2[region].append(ch)
        
        result = []
        for region in regions:
            region_result = round1[region] + round2[region]
            result.extend(region_result[:per_max])
        
        if len(result) > total_max:
            result.sort(key=lambda x: x.get('speed', 0), reverse=True)
            result = result[:total_max]
        
        return result
    
    def _dedup_by_name(self, channels):
        """按名称去重"""
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
        """排序：CCTV -> 卫视 -> 大陆其他 -> 海外"""
        region_order = {'china':1, 'hongkong':2, 'taiwan':3, 'macau':4, 'japan':5, 'korea':6, 'usa':7, 'southeast_asia':8}
        
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
    
    def generate_all(self):
        print(f"\n{'='*60}")
        print("🚀 生成所有播放列表")
        print(f"{'='*60}\n")
        
        print("📦 完整版 (去重+剔除低速)...")
        self.generate_all_in_one()
        
        print("\n🌍 地区版 (去重+剔除低速)...")
        self.generate_by_region()
        
        print("\n📊 分层版 (去重+速度分层)...")
        self.generate_tiered_lists()
        
        print("\n🎬 飞牛优化版...")
        self.generate_feiniu_optimized()
        
        print(f"\n✅ 全部完成!\n")


if __name__ == '__main__':
    try:
        generator = M3UGenerator()
        generator.generate_all()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
