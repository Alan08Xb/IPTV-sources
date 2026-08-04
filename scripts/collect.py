#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV源自动采集脚本
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
                name_match = re.search(r'tvg-name="([^"]*)"', line)
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                group_match = re.search(r'group-title="([^"]*)"', line)
                
                if name_match:
                    name = name_match.group(1)
                else:
                    parts = line.split(',')
                    name = parts[-1].strip() if len(parts) > 1 else 'Unknown'
                
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
        """分类频道"""
        name = channel['name'].upper()
        
        # 获取分类关键词
        china_keywords = self.config.get('channels_filter', {}).get('china_keywords', ['CCTV', '卫视'])
        hk_keywords = self.config.get('channels_filter', {}).get('hongkong_keywords', ['TVB', '凤凰'])
        tw_keywords = self.config.get('channels_filter', {}).get('taiwan_keywords', ['台视', '中视'])
        mo_keywords = self.config.get('channels_filter', {}).get('macau_keywords', ['澳亚', '澳门'])
        jp_keywords = self.config.get('channels_filter', {}).get('japan_keywords', ['NHK'])
        kr_keywords = self.config.get('channels_filter', {}).get('korea_keywords', ['KBS', 'MBC'])
        us_keywords = self.config.get('channels_filter', {}).get('usa_keywords', ['ABC', 'NBC', 'CNN'])
        sea_keywords = self.config.get('channels_filter', {}).get('southeast_asia_keywords', ['Channel 8'])
        
        region_map = [
            ('japan', jp_keywords),
            ('korea', kr_keywords),
            ('usa', us_keywords),
            ('southeast_asia', sea_keywords),
            ('macau', mo_keywords),
            ('hongkong', hk_keywords),
            ('taiwan', tw_keywords),
            ('china', china_keywords),
        ]
        
        region_found = 'other'
        for region, keywords in region_map:
            if any(kw in name for kw in keywords):
                region_found = region
                break
        
        channel['region'] = region_found
        channel['category'] = self.get_category(name)
        return channel
    
    def get_category(self, name):
        """获取类别"""
        categories = {
            '新闻': ['新闻', 'NEWS', '资讯', '财经'],
            '体育': ['体育', 'SPORT', '足球', '篮球'],
            '影视': ['电影', '影视', 'MOVIE', '剧场'],
            '综艺': ['综艺', '娱乐', 'ENTERTAINMENT'],
            '少儿': ['少儿', '卡通', '儿童', '动漫'],
            '音乐': ['音乐', 'MUSIC'],
            '纪录片': ['纪录', '探索', 'DISCOVERY'],
        }
        for cat, keywords in categories.items():
            if any(kw in name.upper() for kw in keywords):
                return cat
        return '综合'
    
    def collect_all(self):
        """采集所有源"""
        all_channels = []
        
        # 按优先级排序源
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
                # 保留优先级更高的源
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
        
        logger.info(f"总计: {len(unique_channels)} 个频道 (去重过滤后)")
        return unique_channels
    
    def save_channels(self, channels, filename='output/all_channels.json'):
        """保存频道"""
        os.makedirs('output', exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存: {filename} ({len(channels)} 个频道)")


if __name__ == '__main__':
    try:
        collector = IPTVCollector()
        channels = collector.collect_all()
        collector.save_channels(channels)
        logger.info(f"✅ 采集完成，共 {len(channels)} 个频道")
    except Exception as e:
        logger.error(f"❌ 采集失败: {e}", exc_info=True)
        sys.exit(1)
