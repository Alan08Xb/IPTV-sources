#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV源自动采集脚本 - 优化分类版
"""

import requests
import re
import json
import os
import sys
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IPTVCollector:
    def __init__(self, config_path='config/sources.json'):
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            sys.exit(1)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.channels = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_m3u(self, url):
        """获取M3U文件内容"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取失败 {url[:60]}: {e}")
            return None
    
    def parse_m3u(self, content):
        """解析M3U格式"""
        channels = []
        lines = content.split('\n')
        
        for i in range(len(lines)):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                # 尝试多种方式提取频道名称
                name = None
                
                # 方式1: tvg-name
                name_match = re.search(r'tvg-name="([^"]*)"', line)
                if name_match:
                    name = name_match.group(1)
                
                # 方式2: 逗号后面的内容
                if not name:
                    parts = line.split(',')
                    if len(parts) > 1:
                        name = parts[-1].strip()
                
                # 方式3: 最后一个引号后的内容
                if not name:
                    last_quote = line.rfind('"')
                    if last_quote > 0:
                        name = line[last_quote+1:].strip()
                
                if not name:
                    name = 'Unknown'
                
                # 清理名称
                name = name.strip()
                
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                group_match = re.search(r'group-title="([^"]*)"', line)
                
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and not url.startswith('#'):
                        channel = {
                            'name': name,
                            'url': url,
                            'logo': logo_match.group(1) if logo_match else '',
                            'group': group_match.group(1) if group_match else 'Undefined',
                            'source': 'collected'
                        }
                        channels.append(channel)
        
        return channels
    
    def parse_txt(self, content):
        """解析TXT格式"""
        channels = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    name, url = parts
                    channels.append({
                        'name': name.strip(),
                        'url': url.strip(),
                        'group': 'Undefined',
                        'source': 'collected'
                    })
        return channels
    
    def classify_channel(self, channel):
        """优化后的分类逻辑 - 中国大陆优先"""
        name = channel.get('name', '')
        name_upper = name.upper()
        group = channel.get('group', '')
        
        # 获取分类关键词
        cf = self.config.get('channels_filter', {})
        china_keywords = cf.get('china_keywords', [])
        hk_keywords = cf.get('hongkong_keywords', [])
        tw_keywords = cf.get('taiwan_keywords', [])
        mo_keywords = cf.get('macau_keywords', [])
        jp_keywords = cf.get('japan_keywords', [])
        kr_keywords = cf.get('korea_keywords', [])
        us_keywords = cf.get('usa_keywords', [])
        sea_keywords = cf.get('southeast_asia_keywords', [])
        
        # 中国大陆频道关键词（扩展）
        china_all_keywords = china_keywords + [
            '卫视', 'CCTV', '央视', '北京', '上海', '东方', '天津', '重庆',
            '河北', '山西', '辽宁', '吉林', '黑龙江', '江苏', '浙江',
            '安徽', '福建', '江西', '山东', '河南', '湖北', '湖南',
            '广东', '海南', '四川', '贵州', '云南', '陕西', '甘肃',
            '青海', '台湾', '内蒙古', '广西', '西藏', '宁夏', '新疆',
            '深圳', '厦门', '大连', '青岛', '宁波', '珠江',
            '金鹰', '纪实', '财富', '少儿', '新闻', '体育', '电影',
            '电视剧', '综艺', '音乐', '戏曲', '法制', '教育', '农业',
            '军事', '环球', '纪录', '发现', '探索',
        ]
        
        # 央视关键词
        cctv_keywords = ['CCTV', '央视', '中央']
        
        # 判断顺序：中国大陆优先
        # 1. 先检查是否为央视
        if any(kw in name_upper for kw in cctv_keywords):
            channel['region'] = 'china'
            channel['is_cctv'] = True
        # 2. 检查中国大陆频道
        elif any(kw in name for kw in china_all_keywords):
            channel['region'] = 'china'
            channel['is_cctv'] = False
        # 3. 检查港澳台
        elif any(kw in name for kw in hk_keywords):
            channel['region'] = 'hongkong'
        elif any(kw in name for kw in tw_keywords):
            channel['region'] = 'taiwan'
        elif any(kw in name for kw in mo_keywords):
            channel['region'] = 'macau'
        # 4. 检查海外
        elif any(kw in name for kw in jp_keywords):
            channel['region'] = 'japan'
        elif any(kw in name for kw in kr_keywords):
            channel['region'] = 'korea'
        elif any(kw in name for kw in us_keywords):
            channel['region'] = 'usa'
        elif any(kw in name for kw in sea_keywords):
            channel['region'] = 'southeast_asia'
        # 5. 通过 group 再次判断
        elif '卫视' in group or 'CCTV' in group.upper():
            channel['region'] = 'china'
        elif '香港' in group or 'HK' in group.upper():
            channel['region'] = 'hongkong'
        elif '台湾' in group or 'TW' in group.upper():
            channel['region'] = 'taiwan'
        elif '日本' in group or 'JP' in group.upper():
            channel['region'] = 'japan'
        elif '韩国' in group or 'KR' in group.upper():
            channel['region'] = 'korea'
        elif '美国' in group or 'US' in group.upper():
            channel['region'] = 'usa'
        else:
            channel['region'] = 'other'
        
        channel['category'] = self.get_category(name)
        return channel
    
    def get_category(self, name):
        """获取类别"""
        name_upper = name.upper()
        categories = {
            '新闻': ['新闻', 'NEWS', '资讯', '财经', 'BLOOMBERG', 'CNN'],
            '体育': ['体育', 'SPORT', '足球', '篮球', 'NBA', 'ESPN', '高尔夫', '网球'],
            '影视': ['电影', '影视', 'MOVIE', '剧场', '影院', 'HBO', '好莱坞'],
            '综艺': ['综艺', '娱乐', 'ENTERTAINMENT', '喜剧'],
            '少儿': ['少儿', '卡通', '儿童', '动漫', 'ANIME', 'ANIMATION', 'KIDS'],
            '音乐': ['音乐', 'MUSIC', 'MV', '演唱会'],
            '纪录片': ['纪录', '探索', 'DISCOVERY', 'DOCUMENTARY', '国家地理', '历史'],
            '教育': ['教育', '学习', '英语', '公开课'],
        }
        for cat, keywords in categories.items():
            if any(kw in name_upper for kw in keywords):
                return cat
        return '综合'
    
    def collect_all(self):
        """采集所有源"""
        all_channels = []
        
        sources = self.config.get('sources', [])
        sorted_sources = sorted(sources, key=lambda x: x.get('priority', 3))
        
        for source in sorted_sources:
            name = source.get('name', 'unknown')
            url = source.get('url', '')
            source_type = source.get('type', 'm3u')
            
            logger.info(f"[P{source.get('priority', 3)}] 采集: {name}")
            content = self.fetch_m3u(url)
            
            if content:
                if source_type == 'm3u':
                    channels = self.parse_m3u(content)
                else:
                    channels = self.parse_txt(content)
                
                for channel in channels:
                    channel = self.classify_channel(channel)
                    channel['source_name'] = name
                    channel['source_priority'] = source.get('priority', 3)
                
                all_channels.extend(channels)
                logger.info(f"  -> {len(channels)} 个频道")
        
        # 去重（按URL）
        seen_urls = {}
        for ch in all_channels:
            url = ch.get('url', '')
            if url in seen_urls:
                existing_priority = seen_urls[url].get('source_priority', 3)
                current_priority = ch.get('source_priority', 3)
                if current_priority < existing_priority:
                    seen_urls[url] = ch
            else:
                seen_urls[url] = ch
        
        unique_channels = list(seen_urls.values())
        
        # 过滤排除关键词
        exclude_keywords = self.config.get('channels_filter', {}).get('exclude_keywords', [])
        unique_channels = [
            ch for ch in unique_channels
            if not any(kw in ch.get('name', '').upper() for kw in exclude_keywords)
        ]
        
        # 统计
        region_stats = defaultdict(int)
        for ch in unique_channels:
            region_stats[ch.get('region', 'other')] += 1
        
        logger.info(f"总计: {len(unique_channels)} 个频道")
        for region, count in sorted(region_stats.items()):
            logger.info(f"  {region}: {count}")
        
        return unique_channels
    
    def save_channels(self, channels, filename='output/all_channels.json'):
        """保存频道"""
        os.makedirs('output', exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存: {filename} ({len(channels)} 个频道)")


if __name__ == '__main__':
    try:
        from collections import defaultdict
        collector = IPTVCollector()
        channels = collector.collect_all()
        collector.save_channels(channels)
        logger.info(f"✅ 采集完成，共 {len(channels)} 个频道")
    except Exception as e:
        logger.error(f"❌ 采集失败: {e}", exc_info=True)
        sys.exit(1)
