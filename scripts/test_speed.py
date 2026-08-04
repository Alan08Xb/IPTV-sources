#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV源测速脚本
功能：多线程测试频道可用性和速度
"""

import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IPTVSpeedTester:
    def __init__(self, config_path='config/sources.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.test_settings = self.config['test_settings']
        self.timeout = self.test_settings.get('timeout', 10)
        self.min_speed = self.test_settings.get('min_speed', 500)  # KB/s
        self.max_threads = self.test_settings.get('max_threads', 50)
        self.test_duration = self.test_settings.get('test_duration', 5)
        
    def test_single_channel(self, channel):
        """测试单个频道"""
        url = channel['url']
        result = {
            **channel,
            'status': 'failed',
            'speed': 0,
            'latency': 0,
            'tested_at': datetime.now().isoformat()
        }
        
        try:
            start_time = time.time()
            response = requests.get(
                url,
                stream=True,
                timeout=self.timeout,
                headers={'User-Agent': 'VLC/3.0.18'}
            )
            
            if response.status_code == 200:
                # 计算下载速度
                content_length = 0
                test_start = time.time()
                
                for chunk in response.iter_content(chunk_size=1024):
                    content_length += len(chunk)
                    if time.time() - test_start > self.test_duration:
                        break
                
                test_duration = time.time() - test_start
                speed = (content_length / 1024) / test_duration if test_duration > 0 else 0  # KB/s
                
                result['status'] = 'success'
                result['speed'] = round(speed, 2)
                result['latency'] = round((time.time() - start_time) * 1000, 2)  # ms
                result['content_type'] = response.headers.get('content-type', 'unknown')
                
                logger.info(f"✓ {channel['name']}: {speed:.2f} KB/s, 延迟 {result['latency']}ms")
            else:
                logger.warning(f"✗ {channel['name']}: HTTP {response.status_code}")
                
        except Exception as e:
            logger.debug(f"✗ {channel['name']}: {str(e)[:50]}")
        
        return result
    
    def batch_test(self, channels, max_workers=None):
        """批量测试频道"""
        if max_workers is None:
            max_workers = self.max_threads
        
        results = []
        total = len(channels)
        
        logger.info(f"开始测试 {total} 个频道，使用 {max_workers} 个线程")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.test_single_channel, ch): ch for ch in channels}
            
            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                results.append(result)
                
                if i % 50 == 0:
                    logger.info(f"进度: {i}/{total}")
        
        return results
    
    def filter_channels(self, results):
        """筛选可用频道"""
        valid_channels = []
        failed_channels = []
        
        for ch in results:
            if ch['status'] == 'success' and ch['speed'] >= self.min_speed:
                valid_channels.append(ch)
            else:
                failed_channels.append(ch)
        
        # 按速度排序
        valid_channels.sort(key=lambda x: x['speed'], reverse=True)
        
        logger.info(f"有效频道: {len(valid_channels)}, 失效频道: {len(failed_channels)}")
        return valid_channels, failed_channels
    
    def save_results(self, valid_channels, failed_channels):
        """保存测试结果"""
        os.makedirs('output', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存有效频道
        with open(f'output/valid_channels_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(valid_channels, f, ensure_ascii=False, indent=2)
        
        # 保存统计信息
        stats = {
            'test_time': timestamp,
            'total_tested': len(valid_channels) + len(failed_channels),
            'valid_count': len(valid_channels),
            'failed_count': len(failed_channels),
            'success_rate': f"{len(valid_channels) / (len(valid_channels) + len(failed_channels)) * 100:.2f}%",
            'regions': {},
            'categories': {}
        }
        
        for ch in valid_channels:
            region = ch.get('region', 'other')
            category = ch.get('category', '综合')
            
            stats['regions'][region] = stats['regions'].get(region, 0) + 1
            stats['categories'][category] = stats['categories'].get(category, 0) + 1
        
        with open(f'output/stats_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        return valid_channels

if __name__ == '__main__':
    # 加载频道列表
    with open('output/all_channels.json', 'r', encoding='utf-8') as f:
        channels = json.load(f)
    
    tester = IPTVSpeedTester()
    results = tester.batch_test(channels)
    valid, failed = tester.filter_channels(results)
    tester.save_results(valid, failed)
