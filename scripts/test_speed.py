#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV源测速脚本
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class IPTVSpeedTester:
    def __init__(self, config_path='config/sources.json'):
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            sys.exit(1)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.test_settings = self.config.get('test_settings', {})
        self.timeout = self.test_settings.get('timeout', 10)
        self.min_speed = self.test_settings.get('min_speed', 500)
        self.max_threads = self.test_settings.get('max_threads', 50)
        self.test_duration = self.test_settings.get('test_duration', 5)
    
    # ... test_single_channel 方法保持不变 ...
    
    def batch_test(self, channels, max_workers=None):
        """批量测试频道"""
        if max_workers is None:
            max_workers = self.max_threads
        
        if not channels:
            logger.warning("没有频道需要测试")
            return []
        
        results = []
        total = len(channels)
        
        logger.info(f"开始测试 {total} 个频道，使用 {max_workers} 个线程")
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.test_single_channel, ch): ch for ch in channels}
                
                for i, future in enumerate(as_completed(futures), 1):
                    try:
                        result = future.result(timeout=self.timeout + 5)
                        results.append(result)
                    except Exception as e:
                        logger.debug(f"频道测试异常: {e}")
                    
                    if i % 50 == 0:
                        logger.info(f"进度: {i}/{total}")
        except Exception as e:
            logger.error(f"批量测试出错: {e}")
        
        return results
    
    # ... 其余方法保持不变 ...

if __name__ == '__main__':
    try:
        # 查找频道数据文件
        channel_files = glob.glob('output/all_channels.json')
        if not channel_files:
            # 尝试查找其他JSON文件
            json_files = glob.glob('output/*.json')
            if json_files:
                channel_files = [max(json_files)]  # 使用最新的
            else:
                logger.error("未找到频道数据文件")
                sys.exit(1)
        
        channel_file = channel_files[0]
        logger.info(f"加载频道数据: {channel_file}")
        
        with open(channel_file, 'r', encoding='utf-8') as f:
            channels = json.load(f)
        
        if not channels:
            logger.error("频道列表为空")
            sys.exit(1)
        
        tester = IPTVSpeedTester()
        results = tester.batch_test(channels)
        valid, failed = tester.filter_channels(results)
        tester.save_results(valid, failed)
        
        logger.info(f"测速完成: 有效 {len(valid)}, 失效 {len(failed)}")
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测速过程出错: {e}", exc_info=True)
        sys.exit(1)
