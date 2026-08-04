#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高速测速脚本 - 优化版
- 使用 HEAD 请求快速检测可用性
- 仅对可用频道做简要速度测试
- 增加超时控制和早期退出
"""

import requests
import time
import json
import os
import sys
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FastIPTVSpeedTester:
    def __init__(self, config_path='config/sources.json'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.test_settings = self.config.get('test_settings', {})
        self.timeout = self.test_settings.get('timeout', 5)
        self.min_speed = self.test_settings.get('min_speed', 500)
        self.max_threads = self.test_settings.get('max_threads', 80)
        self.test_duration = self.test_settings.get('test_duration', 3)
        self.session = self._create_session()
    
    def _create_session(self):
        """创建优化的 requests session"""
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
            'Accept': '*/*',
            'Connection': 'close'  # 不保持连接
        })
        return session
    
    def quick_check(self, channel):
        """快速检查频道可用性（HEAD请求）"""
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
            # 先用 HEAD 快速检查
            try:
                head_resp = self.session.head(
                    url,
                    timeout=3,
                    allow_redirects=True
                )
                if head_resp.status_code >= 400:
                    return result
            except:
                # HEAD 失败，尝试 GET
                pass
            
            # 简单速度测试
            response = self.session.get(
                url,
                stream=True,
                timeout=(3, self.timeout),
            )
            
            if response.status_code == 200:
                content_length = 0
                test_start = time.time()
                
                # 只读取少量数据测试速度
                for chunk in response.iter_content(chunk_size=4096):
                    content_length += len(chunk)
                    if time.time() - test_start > self.test_duration:
                        break
                    if content_length > 512 * 1024:  # 最多读取512KB
                        break
                
                response.close()
                
                test_duration = time.time() - test_start
                speed = (content_length / 1024) / test_duration if test_duration > 0 else 0
                
                result['status'] = 'success'
                result['speed'] = round(speed, 2)
                result['latency'] = round((time.time() - start_time) * 1000, 2)
                
                if speed >= 1000:
                    logger.info(f"✓ {channel['name']}: {speed:.0f} KB/s")
                elif speed >= 500:
                    logger.info(f"○ {channel['name']}: {speed:.0f} KB/s")
                else:
                    logger.debug(f"△ {channel['name']}: {speed:.0f} KB/s")
            else:
                logger.debug(f"✗ {channel['name']}: HTTP {response.status_code}")
        
        except requests.exceptions.Timeout:
            logger.debug(f"⏱ {channel['name']}: 超时")
        except requests.exceptions.ConnectionError:
            logger.debug(f"🔌 {channel['name']}: 连接失败")
        except Exception as e:
            logger.debug(f"✗ {channel['name']}: {str(e)[:30]}")
        
        return result
    
    def batch_test(self, channels, max_workers=None):
        """批量快速测试"""
        if max_workers is None:
            max_workers = self.max_threads
        
        if not channels:
            return []
        
        results = []
        total = len(channels)
        completed = 0
        
        logger.info(f"快速测速 {total} 个频道，线程数: {max_workers}")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.quick_check, ch): ch for ch in channels}
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.timeout + 5)
                    results.append(result)
                except TimeoutError:
                    logger.debug("单个测试超时")
                except Exception:
                    pass
                
                completed += 1
                if completed % 100 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"进度: {completed}/{total} (耗时: {elapsed:.0f}s)")
        
        elapsed = time.time() - start_time
        logger.info(f"测速完成: {elapsed:.0f}秒")
        return results
    
    def filter_channels(self, results):
        """筛选可用频道"""
        valid = [ch for ch in results if ch['status'] == 'success' and ch['speed'] >= self.min_speed]
        failed = [ch for ch in results if ch not in valid]
        
        # 按速度排序
        valid.sort(key=lambda x: x['speed'], reverse=True)
        
        logger.info(f"有效: {len(valid)}, 失效: {len(failed)}, 成功率: {len(valid)/max(len(results),1)*100:.1f}%")
        
        # 速度分布统计
        high = len([ch for ch in valid if ch['speed'] >= 1000])
        mid = len([ch for ch in valid if 500 <= ch['speed'] < 1000])
        low = len([ch for ch in valid if 300 <= ch['speed'] < 500])
        logger.info(f"高速(>1MB): {high}, 中速(>500KB): {mid}, 低速(>300KB): {low}")
        
        return valid, failed
    
    def save_results(self, valid_channels, failed_channels):
        """保存测试结果"""
        os.makedirs('output', exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 只保存有效频道
        with open(f'output/valid_channels_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(valid_channels, f, ensure_ascii=False, indent=2)
        
        # 同时保存为最新文件
        with open('output/valid_channels_latest.json', 'w', encoding='utf-8') as f:
            json.dump(valid_channels, f, ensure_ascii=False, indent=2)
        
        # 统计信息
        stats = {
            'test_time': timestamp,
            'total_tested': len(valid_channels) + len(failed_channels),
            'valid_count': len(valid_channels),
            'failed_count': len(failed_channels),
            'success_rate': f"{len(valid_channels) / max(len(valid_channels) + len(failed_channels), 1) * 100:.1f}%",
            'avg_speed': sum(ch.get('speed', 0) for ch in valid_channels) / max(len(valid_channels), 1)
        }
        
        with open(f'output/stats_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        with open('output/stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存")

if __name__ == '__main__':
    try:
        # 查找频道数据
        channel_files = glob.glob('output/all_channels.json')
        if not channel_files:
            json_files = glob.glob('output/*.json')
            channel_files = [f for f in json_files if 'valid' not in f and 'stats' not in f]
        
        if not channel_files:
            logger.error("未找到频道数据")
            sys.exit(1)
        
        with open(channel_files[0], 'r', encoding='utf-8') as f:
            channels = json.load(f)
        
        logger.info(f"加载 {len(channels)} 个频道")
        
        # 预过滤：只测试可能有效的URL
        valid_urls = [ch for ch in channels if ch.get('url', '').startswith(('http://', 'https://'))]
        logger.info(f"有效URL: {len(valid_urls)}/{len(channels)}")
        
        # 去重（减少测试量）
        seen_urls = set()
        unique_channels = []
        for ch in valid_urls:
            url = ch['url']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_channels.append(ch)
        logger.info(f"去重后: {len(unique_channels)} 个频道")
        
        # 限制最大测试数量（如果太多）
        max_test = 3000
        if len(unique_channels) > max_test:
            logger.warning(f"频道过多，限制测试 {max_test} 个")
            unique_channels = unique_channels[:max_test]
        
        tester = FastIPTVSpeedTester()
        results = tester.batch_test(unique_channels)
        valid, failed = tester.filter_channels(results)
        tester.save_results(valid, failed)
        
    except Exception as e:
        logger.error(f"测速失败: {e}", exc_info=True)
        sys.exit(1)
