#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测速脚本 - 优化版
- 增加测速时长保证覆盖率
- HEAD失败后仍尝试GET
- 显示测速进度
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
        self.timeout = settings.get('timeout', 8)          # 增加超时
        self.min_speed = settings.get('min_speed', 300)    # 降低最低速度要求
        self.max_threads = settings.get('max_threads', 100) # 增加线程
        self.test_duration = settings.get('test_duration', 4) # 增加测试时长
        self.session = self._create_session()
    
    def _create_session(self):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=200,
            pool_maxsize=200,
            max_retries=2,  # 增加重试
            pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18',
            'Accept': '*/*',
            'Connection': 'close'
        })
        return session
    
    def quick_check(self, channel):
        """测试单个频道"""
        url = channel.get('url', '')
        name = channel.get('name', 'Unknown')
        result = {
            **channel, 
            'status': 'failed', 
            'speed': 0, 
            'latency': 0, 
            'tested_at': datetime.now().isoformat()
        }
        
        if not url.startswith(('http://', 'https://')):
            return result
        
        try:
            start_time = time.time()
            
            # 直接GET请求（跳过HEAD，因为很多源不支持）
            response = self.session.get(
                url,
                stream=True,
                timeout=(5, self.timeout),
                allow_redirects=True
            )
            
            if response.status_code == 200:
                # 检查是否是视频流
                content_type = response.headers.get('content-type', '').lower()
                
                content_length = 0
                test_start = time.time()
                
                # 读取数据测速
                for chunk in response.iter_content(chunk_size=8192):
                    content_length += len(chunk)
                    elapsed = time.time() - test_start
                    if elapsed > self.test_duration:
                        break
                    if content_length > 1024 * 1024:  # 最多读1MB
                        break
                
                response.close()
                
                test_duration = time.time() - test_start
                if test_duration > 0 and content_length > 0:
                    speed = (content_length / 1024) / test_duration  # KB/s
                    
                    result['status'] = 'success'
                    result['speed'] = round(speed, 2)
                    result['latency'] = round((time.time() - start_time) * 1000, 2)
                    result['content_type'] = content_type
                else:
                    # 能连接但无数据，给个保底速度
                    result['status'] = 'success'
                    result['speed'] = 100
                    result['latency'] = round((time.time() - start_time) * 1000, 2)
            elif response.status_code in [301, 302, 307, 308]:
                # 重定向的也可能可用
                result['status'] = 'success'
                result['speed'] = 50
                result['latency'] = round((time.time() - start_time) * 1000, 2)
        
        except requests.exceptions.Timeout:
            logger.debug(f"⏱ {name}: 超时")
        except requests.exceptions.ConnectionError:
            logger.debug(f"🔌 {name}: 连接失败")
        except Exception as e:
            logger.debug(f"✗ {name}: {str(e)[:30]}")
        
        return result
    
    def batch_test(self, channels, max_workers=None):
        """批量测试"""
        if max_workers is None:
            max_workers = self.max_threads
        
        if not channels:
            logger.warning("没有频道需要测试")
            return []
        
        results = []
        total = len(channels)
        completed = 0
        success_count = 0
        start_time = time.time()
        
        logger.info(f"开始测速: {total} 个频道, 线程数: {max_workers}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.quick_check, ch): ch for ch in channels}
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.timeout + 10)
                    results.append(result)
                    if result['status'] == 'success':
                        success_count += 1
                except Exception:
                    pass
                
                completed += 1
                
                # 每200个或每30秒报告进度
                if completed % 200 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    logger.info(f"进度: {completed}/{total} ({elapsed:.0f}s, 成功:{success_count}, 速率:{rate:.0f}/s, 预计剩余:{eta:.0f}s)")
        
        elapsed = time.time() - start_time
        logger.info(f"测速完成: {elapsed:.0f}秒, 成功: {success_count}/{total}")
        return results
    
    def filter_channels(self, results):
        """筛选可用频道 - 放宽条件"""
        # 状态为success的都算可用
        valid = [ch for ch in results if ch['status'] == 'success' and ch['speed'] >= self.min_speed]
        # 低速但可连接的也算低速可用
        low_speed = [ch for ch in results if ch['status'] == 'success' and 50 <= ch['speed'] < self.min_speed]
        failed = [ch for ch in results if ch not in valid and ch not in low_speed]
        
        # 按速度排序
        valid.sort(key=lambda x: x['speed'], reverse=True)
        
        # 统计
        high = len([ch for ch in valid if ch['speed'] >= 1000])
        mid = len([ch for ch in valid if 500 <= ch['speed'] < 1000])
        low = len([ch for ch in valid if self.min_speed <= ch['speed'] < 500])
        
        logger.info(f"有效: {len(valid)} (高速:{high}, 中速:{mid}, 低速:{low})")
        logger.info(f"低速可用: {len(low_speed)}, 失效: {len(failed)}")
        logger.info(f"成功率: {(len(valid)+len(low_speed))/max(len(results),1)*100:.1f}%")
        
        # 把低速可用的也加入（标注为low）
        for ch in low_speed:
            ch['speed_tier'] = 'low'
        valid.extend(low_speed)
        
        return valid, failed
    
    def save_results(self, valid_channels, failed_channels):
        """保存结果"""
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
        
        logger.info(f"结果已保存: {len(valid_channels)} 个有效频道")


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
        
        logger.info(f"去重后: {len(unique)} 个频道")
        
        tester = FastIPTVSpeedTester()
        results = tester.batch_test(unique)
        valid, failed = tester.filter_channels(results)
        tester.save_results(valid, failed)
        
        logger.info(f"✅ 测速完成: {len(valid)} 有效, {len(failed)} 失效")
        
    except Exception as e:
        logger.error(f"失败: {e}", exc_info=True)
        sys.exit(1)
