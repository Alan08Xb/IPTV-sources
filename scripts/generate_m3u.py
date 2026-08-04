#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成分类M3U播放列表 - 频道数量限定版
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
        tiers = self.config.get('speed_tiers', {'high': 1000, 'medium': 500, 'low': 300})
        if speed >= tiers.get('high', 1000):
            return 'high'
        elif speed >= tiers.get('medium', 500):
            return 'medium'
        elif speed >= tiers.get('low', 300):
            return 'low'
        return 'failed'
    
    def filter_by_speed_tiers(self, channels, tiers):
        return [ch for ch in channels if self.get_speed_tier(ch.get('speed', 0)) in tiers]
    
    # ==================== 飞牛影视优化版 ====================
    
    def generate_feiniu_optimized(self):
        """
        飞牛影视优化版频道数量规则：
        - CCTV频道: 不超过30个
        - 地方卫视频道: 不超过50个
        - 港澳台+韩国+日本+东南亚+美国: 总不超过170个，每个地区3-20个
        """
        
        target_regions = ['china', 'hongkong', 'taiwan', 'macau', 'southeast_asia', 'japan', 'korea', 'usa']
        
        # 数量限制
        cctv_max = 30          # CCTV频道上限
        satellite_max = 50     # 卫视频道上限
        overseas_total_max = 170  # 海外地区总上限
        overseas_per_min = 3      # 每个海外地区下限
        overseas_per_max = 20     # 每个海外地区上限
        
        print(f"\n{'='*60}")
        print(f"🎬 飞牛影视优化版")
        print(f"   目标地区: {', '.join(target_regions)}")
        print(f"   数量限制: CCTV≤{cctv_max}, 卫视≤{satellite_max}, 海外≤{overseas_total_max}")
        print(f"   海外每区: {overseas_per_min}-{overseas_per_max}个")
        print(f"{'='*60}")
        
        # Step 1: 去重
        print("\n📋 Step 1: 智能去重...")
        deduped = self.deduplicate_channels(self.channels)
        
        # Step 2: 按地区筛选
        print(f"\n🌍 Step 2: 按地区筛选...")
        region_channels = {}
        for region in target_regions:
            chs = [ch for ch in deduped if ch.get('region') == region]
            region_channels[region] = chs
            sample = [ch.get('name', '') for ch in chs[:5]]
            print(f"   {region}: {len(chs)} 个, 样本: {sample}")
        
        # Step 3: 中国大陆频道处理
        print(f"\n🇨🇳 Step 3: 中国大陆频道处理...")
        china_chs = region_channels.get('china', [])
        china_selected = self._process_china_channels_v2(
            china_chs, 
            cctv_max=cctv_max, 
            satellite_max=satellite_max
        )
        print(f"   中国大陆合计: {len(china_selected)} 个")
        
        # Step 4: 海外地区处理
        print(f"\n🌏 Step 4: 海外地区处理...")
        overseas_regions = ['hongkong', 'taiwan', 'macau', 'southeast_asia', 'japan', 'korea', 'usa']
        overseas_selected = self._process_overseas_channels(
            region_channels,
            overseas_regions,
            total_max=overseas_total_max,
            per_min=overseas_per_min,
            per_max=overseas_per_max
        )
        print(f"   海外合计: {len(overseas_selected)} 个")
        
        # Step 5: 合并
        print(f"\n📦 Step 5: 合并频道...")
        all_selected = china_selected + overseas_selected
        print(f"   总频道数: {len(all_selected)}")
        
        # Step 6: 最终排序
        print(f"\n📊 Step 6: 最终排序...")
        all_selected = self._final_sort(all_selected)
        
        # Step 7: 生成文件
        print(f"\n💾 Step 7: 生成文件...")
        filename = 'output/feiniu.m3u'
        content = self.generate_m3u_header(f'飞牛影视专用精选 ({len(all_selected)}个)')
        
        content += '# =========================================\n'
        content += '# 飞牛影视优化版\n'
        content += f'# 频道总数: {len(all_selected)}\n'
        content += f'# 生成时间: {datetime.now().isoformat()}\n'
        content += f'# 中国大陆: CCTV≤{cctv_max} + 卫视≤{satellite_max} (高速+中速)\n'
        content += f'# 海外地区: ≤{overseas_total_max}个，每区{overseas_per_min}-{overseas_per_max}个\n'
        content += '# 速度要求: 大陆高速+中速, 海外仅高速\n'
        content += '# =========================================\n\n'
        
        for ch in all_selected:
            content += self.generate_channel_entry(ch)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 打印详细统计
        print(f"\n{'='*60}")
        print(f"✅ 飞牛版完成! 共 {len(all_selected)} 个频道")
        print(f"\n📊 详细统计:")
        
        # 大陆统计
        china_in_result = [ch for ch in all_selected if ch.get('region') == 'china']
        cctv_in_result = [ch for ch in china_in_result if 'CCTV' in ch.get('name', '').upper()]
        satellite_in_result = [ch for ch in china_in_result if '卫视' in ch.get('name', '')]
        other_in_result = [ch for ch in china_in_result if ch not in cctv_in_result and ch not in satellite_in_result]
        
        print(f"   🇨🇳 中国大陆: {len(china_in_result)} 个")
        print(f"      - CCTV: {len(cctv_in_result)} 个")
        for ch in cctv_in_result[:10]:
            print(f"        {ch.get('name', '')} ({ch.get('speed', 0):.0f}KB/s)")
        if len(cctv_in_result) > 10:
            print(f"        ... 还有 {len(cctv_in_result)-10} 个")
        
        print(f"      - 卫视: {len(satellite_in_result)} 个")
        for ch in satellite_in_result[:15]:
            print(f"        {ch.get('name', '')} ({ch.get('speed', 0):.0f}KB/s)")
        if len(satellite_in_result) > 15:
            print(f"        ... 还有 {len(satellite_in_result)-15} 个")
        
        if other_in_result:
            print(f"      - 其他: {len(other_in_result)} 个")
        
        # 海外统计
        for region in ['hongkong', 'taiwan', 'macau', 'japan', 'korea', 'usa', 'southeast_asia']:
            region_chs = [ch for ch in all_selected if ch.get('region') == region]
            if region_chs:
                names = [ch.get('name', '')[:15] for ch in region_chs[:10]]
                print(f"   {'🇭🇰' if region=='hongkong' else '🇹🇼' if region=='taiwan' else '🇲🇴' if region=='macau' else '🇯🇵' if region=='japan' else '🇰🇷' if region=='korea' else '🇺🇸' if region=='usa' else '🌏'} {region}: {len(region_chs)} 个 -> {names}")
        
        print(f"{'='*60}\n")
        
        return all_selected
    
    def _process_china_channels_v2(self, channels, cctv_max=30, satellite_max=50):
        """
        处理中国大陆频道
        - CCTV: 不超过 cctv_max 个
        - 卫视: 不超过 satellite_max 个
        - 速度: 高速+中速
        """
        
        # 速度筛选：只保留高速和中速
        filtered = self.filter_by_speed_tiers(channels, ['high', 'medium'])
        print(f"   速度筛选后: {len(filtered)} 个 (高速+中速)")
        
        # 卫视关键词（扩展匹配）
        satellite_keywords = [
            '湖南卫视', '浙江卫视', '江苏卫视', '东方卫视', '北京卫视',
            '广东卫视', '深圳卫视', '山东卫视', '安徽卫视', '湖北卫视',
            '四川卫视', '重庆卫视', '天津卫视', '黑龙江卫视', '辽宁卫视',
            '江西卫视', '河南卫视', '河北卫视', '东南卫视', '吉林卫视',
            '贵州卫视', '云南卫视', '海南卫视', '广西卫视', '陕西卫视',
            '山西卫视', '甘肃卫视', '青海卫视', '新疆卫视', '西藏卫视',
            '宁夏卫视', '内蒙古卫视', '金鹰卡通', '卡酷少儿', '炫动卡通',
            '优漫卡通', '哈哈少儿', 'CCTV', '央视',
        ]
        
        cctv_list = []
        satellite_list = []
        other_china = []
        
        for ch in filtered:
            name = ch.get('name', '')
            name_upper = name.upper()
            
            # 判断CCTV
            if 'CCTV' in name_upper or '央视' in name or '中央' in name:
                cctv_list.append(ch)
                continue
            
            # 判断卫视（模糊匹配）
            is_satellite = False
            for kw in satellite_keywords:
                if kw in name:
                    is_satellite = True
                    break
            # 也匹配"XX卫视"格式
            if '卫视' in name:
                is_satellite = True
            
            if is_satellite:
                satellite_list.append(ch)
            else:
                other_china.append(ch)
        
        # CCTV去重并排序
        cctv_unique = self._dedup_by_name(cctv_list)
        cctv_unique.sort(key=lambda x: self._cctv_sort_key(x.get('name', '')))
        
        # 卫视去重并按速度排序
        satellite_unique = self._dedup_by_name(satellite_list)
        satellite_unique.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        # 其他频道去重并按速度排序
        other_unique = self._dedup_by_name(other_china)
        other_unique.sort(key=lambda x: x.get('speed', 0), reverse=True)
        
        # 应用数量限制
        cctv_final = cctv_unique[:cctv_max]
        satellite_final = satellite_unique[:satellite_max]
        
        # 计算剩余空间给其他大陆频道
        used = len(cctv_final) + len(satellite_final)
        other_slots = max(0, min(30, 250 - used))  # 其他频道最多30个
        other_final = other_unique[:other_slots]
        
        print(f"      CCTV: {len(cctv_unique)} -> 保留 {len(cctv_final)} 个")
        print(f"      卫视: {len(satellite_unique)} -> 保留 {len(satellite_final)} 个")
        if other_final:
            print(f"      其他: {len(other_unique)} -> 保留 {len(other_final)} 个")
        
        # 打印卫视列表
        if satellite_final:
            print(f"      卫视频道列表:")
            for ch in satellite_final[:15]:
                print(f"        - {ch.get('name', '')} ({ch.get('speed', 0):.0f}KB/s)")
            if len(satellite_final) > 15:
                print(f"        ... 还有 {len(satellite_final)-15} 个")
        
        result = cctv_final + satellite_final + other_final
        print(f"      大陆合计: {len(result)} 个")
        
        return result
    
    def _process_overseas_channels(self, region_channels, overseas_regions, total_max=170, per_min=3, per_max=20):
        """
        处理海外地区频道
        - 总数量: 不超过 total_max
        - 每个地区: per_min - per_max 个
        - 速度: 仅高速
        """
        
        print(f"   海外地区: {overseas_regions}")
        print(f"   每区限制: {per_min}-{per_max}个, 总计≤{total_max}个")
        
        # 每个地区先筛选高速频道
        region_highspeed = {}
        for region in overseas_regions:
            chs = region_channels.get(region, [])
            # 仅保留高速频道
            high_chs = self.filter_by_speed_tiers(chs, ['high'])
            # 去重并按速度排序
            high_chs = self._dedup_by_name(high_chs)
            high_chs.sort(key=lambda x: x.get('speed', 0), reverse=True)
            region_highspeed[region] = high_chs
            print(f"      {region}: {len(chs)} 个 -> 高速 {len(high_chs)} 个")
        
        # 第一轮：每个地区至少保留 per_min 个
        round1 = {}
        round1_total = 0
        for region in overseas_regions:
            chs = region_highspeed[region]
            take = min(per_min, len(chs))
            round1[region] = chs[:take]
            round1_total += take
            print(f"      第1轮 {region}: 保留 {take} 个 (最少保证)")
        
        # 第二轮的剩余配额
        remaining_quota = total_max - round1_total
        print(f"      第1轮合计: {round1_total} 个, 剩余配额: {remaining_quota} 个")
        
        # 第二轮：按速度从高到低，从所有地区中挑选
        all_remaining = []
        for region in overseas_regions:
            already_taken = len(round1[region])
            remaining_chs = region_highspeed[region][already_taken:per_max]  # 最多取到per_max
            for ch in remaining_chs:
                all_remaining.append((region, ch))
        
        # 按速度排序
        all_remaining.sort(key=lambda x: x[1].get('speed', 0), reverse=True)
        
        # 取前 remaining_quota 个
        round2_taken = defaultdict(list)
        for region, ch in all_remaining[:remaining_quota]:
            round2_taken[region].append(ch)
        
        # 合并结果
        result = []
        for region in overseas_regions:
            region_result = round1.get(region, []) + round2_taken.get(region, [])
            # 确保不超过 per_max
            region_result = region_result[:per_max]
            result.extend(region_result)
            print(f"      {region}: 最终 {len(region_result)} 个 (第1轮:{len(round1.get(region,[]))} + 第2轮:{len(round2_taken.get(region,[]))})")
        
        # 确保总数不超过 total_max
        if len(result) > total_max:
            result.sort(key=lambda x: x.get('speed', 0), reverse=True)
            result = result[:total_max]
            print(f"      总数超限，裁切至 {total_max} 个")
        
        print(f"      海外最终: {len(result)} 个")
        return result
    
    def _dedup_by_name(self, channels):
        """按名称去重，保留速度最快的"""
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
        if 'CCTV' in name.upper():
            return (2, 0)
        return (3, 0)
    
    def _final_sort(self, channels):
        """最终排序：CCTV -> 卫视 -> 大陆其他 -> 港澳台 -> 海外"""
        region_order = {
            'china': 1, 'hongkong': 2, 'taiwan': 3, 'macau': 4,
            'japan': 5, 'korea': 6, 'usa': 7, 'southeast_asia': 8
        }
        
        def sort_key(ch):
            name = ch.get('name', '')
            region = ch.get('region', 'other')
            speed = ch.get('speed', 0)
            
            # CCTV最优先
            if 'CCTV' in name.upper():
                match = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
                return (0, int(match.group(1)) if match else 99, -speed)
            
            # 卫视其次
            if '卫视' in name:
                return (1, region_order.get(region, 99), -speed)
            
            # 大陆其他
            if region == 'china':
                return (2, 0, -speed)
            
            # 海外按地区+速度
            return (3, region_order.get(region, 99), -speed)
        
        return sorted(channels, key=sort_key)
    
    # ==================== 其他生成方法 ====================
    
    def generate_all_in_one(self):
        if not self.channels:
            return
        filename = 'output/all_channels.m3u'
        content = self.generate_m3u_header(f'全部频道 ({len(self.channels)}个)')
        for ch in self.channels:
            content += self.generate_channel_entry(ch)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 完整版: {len(self.channels)} 个频道")
    
    def generate_by_region(self):
        regions = defaultdict(list)
        for ch in self.channels:
            regions[ch.get('region', 'other')].append(ch)
        
        for region, chs in regions.items():
            if not chs:
                continue
            filename = f'output/{region}.m3u'
            content = self.generate_m3u_header(f'{region} ({len(chs)}个)')
            for ch in chs:
                content += self.generate_channel_entry(ch)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ {region}: {len(chs)} 个频道")
    
    def generate_tiered_lists(self):
        deduped = self.deduplicate_channels(self.channels)
        
        tiers = {
            'tier1_highspeed': ('高速 >1MB/s', [ch for ch in deduped if ch.get('speed', 0) >= 1000]),
            'tier2_midspeed': ('中速 >500KB/s', [ch for ch in deduped if 500 <= ch.get('speed', 0) < 1000]),
            'tier_high_medium': ('高速+中速', [ch for ch in deduped if ch.get('speed', 0) >= 500]),
        }
        
        for key, (name, chs) in tiers.items():
            filename = f'output/{key}.m3u'
            content = self.generate_m3u_header(f'{name} ({len(chs)}个)')
            for ch in sorted(chs, key=lambda x: x.get('speed', 0), reverse=True):
                content += self.generate_channel_entry(ch)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ {name}: {len(chs)} 个频道")
    
    def generate_all(self):
        print(f"\n{'='*60}")
        print("🚀 生成所有播放列表")
        print(f"{'='*60}\n")
        
        self.generate_all_in_one()
        self.generate_by_region()
        self.generate_tiered_lists()
        self.generate_feiniu_optimized()
        
        print(f"\n✅ 全部完成!")


if __name__ == '__main__':
    try:
        generator = M3UGenerator()
        generator.generate_all()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
