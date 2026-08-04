#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV源自动采集脚本
功能：从多个公开源采集IPTV频道
"""

import requests
import re
import json
import os
from datetime import datetime
from urllib.parse import urlparse
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IPTVCollector:
    def __init__(self, config_path='config/sources.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.channels = []
        
    def fetch_m3u(self, url):
        """获取M3U文件内容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取 {url} 失败: {e}")
            return None
    
    def parse_m3u(self, content):
        """解析M3U格式"""
        channels = []
        lines = content.split('\n')
        
        for i in range(len(lines)):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                # 解析频道信息
                name_match = re.search(r'tvg-name="([^"]*)"', line)
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                group_match = re.search(r'group-title="([^"]*)"', line)
                
                # 获取频道名称
                if name_match:
                    name = name_match.group(1)
                else:
                    # 从逗号后获取名称
                    parts = line.split(',')
                    name = parts[-1].strip() if len(parts) > 1 else 'Unknown'
                
                # 获取URL（下一行）
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
        """解析TXT格式（名称,URL）"""
        channels = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    name, url = parts
                    channel = {
                        'name': name.strip(),
                        'url': url.strip(),
                        'group': 'Undefined',
                        'source': 'collected'
                    }
                    channels.append(channel)
        return channels
    
    def classify_channel(self, channel):
        """根据频道名称分类"""
        name = channel['name'].upper()
        
        # 中国大陆频道
        china_patterns = [
            'CCTV', '央视', '卫视', '北京', '上海', '广东', '深圳', '浙江',
            '江苏', '湖南', '湖北', '四川', '重庆', '天津', '山东', '安徽',
            '福建', '江西', '河南', '河北', '辽宁', '吉林', '黑龙江', '陕西',
            '山西', '甘肃', '青海', '云南', '贵州', '海南', '广西', '内蒙古',
            '新疆', '西藏', '宁夏', '澳门'
        ]
        
        # 港澳台频道
        hk_patterns = ['TVB', '凤凰', '香港', 'VIUTV', 'NOW', '有线']
        tw_patterns = ['台视', '中视', '华视', '民视', '公视', '三立', '东森', '中天', 'TVBS', '年代']
        mo_patterns = ['澳亚', '澳门', '莲花']
        
        # 国际频道
        intl_patterns = ['BBC', 'CNN', 'NHK', 'KBS', 'TVB', 'FRANCE', 'DW', 'RT']
        
        region = 'other'
        if any(pattern in name for pattern in china_patterns):
            region = 'china'
        elif any(pattern in name for pattern in hk_patterns):
            region = 'hongkong'
        elif any(pattern in name for pattern in tw_patterns):
            region = 'taiwan'
        elif any(pattern in name for pattern in mo_patterns):
            region = 'macau'
        elif any(pattern in name for pattern in intl_patterns):
            region = 'international'
        
        channel['region'] = region
        channel['category'] = self.get_category(name)
        return channel
    
    def get_category(self, name):
        """获取频道类别"""
        categories = {
            '新闻': ['新闻', 'NEWS', '资讯', '财经'],
            '体育': ['体育', 'SPORT', '足球', '篮球', 'NBA'],
            '影视': ['电影', '影视', 'MOVIE', '剧场', '戏剧'],
            '综艺': ['综艺', '娱乐', 'ENTERTAINMENT'],
            '少儿': ['少儿', '卡通', '儿童', '动漫', 'ANIME'],
            '音乐': ['音乐', 'MUSIC', 'MV'],
            '纪录片': ['纪录', '探索', 'DISCOVERY', 'DOCUMENTARY'],
            '教育': ['教育', '学习', '英语'],
        }
        
        for cat, keywords in categories.items():
            if any(keyword in name.upper() for keyword in keywords):
                return cat
        return '综合'
    
    def collect_all(self):
    """采集所有源，支持优先级"""
    all_channels = []
    
    # 按优先级排序源
    sorted_sources = sorted(self.config['sources'], 
                           key=lambda x: x.get('priority', 3))
    
    for source in sorted_sources:
        logger.info(f"[P{source.get('priority', 3)}] 采集: {source['name']}")
        
        # ... 原有采集代码 ...
        
        for channel in channels:
            channel = self.classify_channel(channel)
            channel['source_name'] = source['name']
            channel['source_priority'] = source.get('priority', 3)
    
    # 去重（按URL，保留高优先级源）
    seen_urls = {}
    for ch in all_channels:
        url = ch['url']
        if url in seen_urls:
            # 如果当前源的优先级更高，替换
            if ch.get('source_priority', 3) < seen_urls[url].get('source_priority', 3):
                seen_urls[url] = ch
        else:
            seen_urls[url] = ch
    
    unique_channels = list(seen_urls.values())
    
    # 过滤排除关键词
    exclude_keywords = self.config['channels_filter'].get('exclude_keywords', [])
    unique_channels = [
        ch for ch in unique_channels
        if not any(kw in ch['name'].upper() for kw in exclude_keywords)
    ]
    
    logger.info(f"去重过滤后: {len(unique_channels)} 个频道")
    return unique_channels
    
    def save_channels(self, channels, filename='output/all_channels.json'):
        """保存频道列表"""
        os.makedirs('output', exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
        logger.info(f"频道列表已保存到 {filename}")

if __name__ == '__main__':
    collector = IPTVCollector()
    channels = collector.collect_all()
    collector.save_channels(channels)
