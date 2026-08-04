#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测速脚本
"""

import requests
import time
import json
import os
import sys
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FastIPTVSpeedTester:
    def __init__(self, config_path='config/sources.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        settings = self.config.get('test_settings', {})
        self.timeout = settings.get('timeout', 5)
        self.min_speed = settings.get('min_speed', 500)
        self.max_threads = settings.get('max_threads', 80)
        self.test_duration = settings.get('test_duration', 3)
        self.session = self._create_session()
    
    def _create_session(self):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=1,
            pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': 'VLC/3.0.18',
            'Connection': 'close'
        })
        return session
    
    def quick_check(self, channel):
        url = channel['url']
        result = {**channel, 'status': 'failed', 'speed': 0, 'latency': 0, 'tested_at': datetime.now().isoformat()}
        
        try:
            # HEAD快速检测
            try:
                head_resp = self.session.head(url, timeout=3, allow_redirects=True)
                if head_resp.status_code >= 400:
                    return result
            except:
                pass
            
            start_time = time.time()
            response = self.session.get(url, stream=True, timeout=(3, self.timeout))
            
            if response.status_code == 200:
                content_length = 0
                test_start = time.time()
                
                for chunk in response.iter_content(chunk_size=4096):
                    content_length += len(chunk)
                    if time.time() - test_start > self.test_duration:
                        break
                    if content_length > 256 * 1024:
                        break
                
                response.close()
                
                test_duration = time.time() - test_start
                speed = (content_length / 1024) / test_duration if test_duration > 0 else 0
                
                result['status'] = 'success'
                result['speed'] = round(speed, 2)
                result['latency'] = round((time.time() - start_time) * 1000, 2)
        
        except:
            pass
        
        return result
    
    def batch_test(self, channels, max_workers=None):
        if max_workers is None:
            max_workers = self.max_threads
        
        if not channels:
            return []
        
        results = []
        total = len(channels)
        completed = 0
        start_time = time.time()
        
        logger.info(f"测速 {total} 个频道，线程: {max_workers}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.quick_check, ch): ch for ch in channels}
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.timeout + 5)
                    results.append(result)
                except:
                    pass
                
                completed += 1
                if completed % 200 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"进度: {completed}/{total} ({elapsed:.0f}s)")
        
        elapsed = time.time() - start_time
        logger.info(f"测速完成: {elapsed:.0f}秒")
        return results
    
    def filter_channels(self, results):
        valid = [ch for ch in results if ch['status'] == 'success' and ch['speed'] >= self.min_speed]
        failed = [ch for ch in results if ch not in valid]
        valid.sort(key=lambda x: x['speed'], reverse=True)
        
        high = len([ch for ch in valid if ch['speed'] >= 1000])
        mid = len([ch for ch in valid if 500 <= ch['speed'] < 1000])
        
        logger.info(f"有效: {len(valid)} (高速:{high} 中速:{mid}), 失效: {len(failed)}")
        return valid, failed
    
    def save_results(self, valid_channels, failed_channels):
        os.makedirs('output', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with open(f'output/valid_channels_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(valid_channels, f, ensure_ascii=False, indent=2)
        
        with open('output/valid_channels_latest.json', 'w', encoding='utf-8') as f:
            json.dump(valid_channels, f, ensure_ascii=False, indent=2)
        
        stats = {
            'test_time': timestamp,
            'total_tested': len(valid_channels) + len(failed_channels),
            'valid_count': len(valid_channels),
            'failed_count': len(failed_channels),
            'success_rate': f"{len(valid_channels)/max(len(valid_channels)+len(failed_channels),1)*100:.1f}%",
            'avg_speed': sum(ch.get('speed',0) for ch in valid_channels)/max(len(valid_channels),1)
        }
        
        with open('output/stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存")

if __name__ == '__main__':
    try:
        # 查找频道数据
        channel_files = glob.glob('output/all_channels.json')
        if not channel_files:
            json_files = [f for f in glob.glob('output/*.json') if 'valid' not in f and 'stats' not in f]
            channel_files = json_files
        
        if not channel_files:
            logger.error("未找到频道数据")
            sys.exit(1)
        
        with open(channel_files[0], 'r', encoding='utf-8') as f:
            channels = json.load(f)
        
        logger.info(f"加载 {len(channels)} 个频道")
        
        # 过滤有效URL
        channels = [ch for ch in channels if ch.get('url','').startswith(('http://','https://'))]
        
        # 去重
        seen = set()
        unique = []
        for ch in channels:
            if ch['url'] not in seen:
                seen.add(ch['url'])
                unique.append(ch)
        
        # 限制最大测试数
        if len(unique) > 3000:
            logger.warning(f"限制测试 3000 个")
            unique = unique[:3000]
        
        logger.info(f"去重后: {len(unique)} 个")
        
        tester = FastIPTVSpeedTester()
        results = tester.batch_test(unique)
        valid, failed = tester.filter_channels(results)
        tester.save_results(valid, failed)
        
    except Exception as e:
        logger.error(f"失败: {e}", exc_info=True)
        sys.exit(1)
