# -*- coding: utf-8 -*-
"""
基础分析器 - 所有分析器的基类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import logging
import requests
from bs4 import BeautifulSoup
import chardet

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """分析器基类"""

    def __init__(self, config):
        """
        初始化分析器

        Args:
            config: 配置对象
        """
        self.config = config
        self.timeout = config.REQUEST_TIMEOUT
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }

    @abstractmethod
    def analyze(self, url: str) -> Dict[str, Any]:
        """
        分析单个URL

        Args:
            url: 要分析的URL

        Returns:
            分析结果字典
        """
        pass

    @abstractmethod
    def batch_analyze(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量分析URLs

        Args:
            urls: URL列表

        Returns:
            批量分析结果字典 {url: result}
        """
        pass

    def fetch_content(self, url: str) -> tuple:
        """
        获取URL内容 - 通用方法

        Args:
            url: 目标URL

        Returns:
            (soup, text, encoding) BeautifulSoup对象、文本内容、编码
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            # 自动检测编码
            if response.encoding == 'ISO-8859-1':
                result = chardet.detect(response.content)
                response.encoding = result['encoding']

            soup = BeautifulSoup(response.text, 'html.parser')
            return soup, response.text, response.encoding

        except requests.exceptions.RequestException as e:
            logger.error(f"获取URL {url} 失败: {str(e)}")
            return None, None, None
        except Exception as e:
            logger.error(f"解析URL {url} 时出错: {str(e)}")
            return None, None, None

    def extract_publish_date(self, soup, url):
        """
        提取发布日期 - 通用方法

        Args:
            soup: BeautifulSoup对象
            url: 页面URL

        Returns:
            发布日期字符串
        """
        publish_date = None

        # 方法1: 通过元标签
        meta_date = (soup.find('meta', {'name': 'publishdate'}) or
                     soup.find('meta', {'name': 'pubdate'}) or
                     soup.find('meta', {'property': 'article:published_time'}))
        if meta_date and meta_date.get('content'):
            publish_date = meta_date.get('content')

        # 方法2: 通过time标签
        if not publish_date:
            time_tag = soup.find('time')
            if time_tag and time_tag.get('datetime'):
                publish_date = time_tag.get('datetime')

        # 方法3: 通过类名包含date的元素
        if not publish_date:
            date_elements = soup.find_all(class_=lambda x: x and 'date' in x.lower())
            if date_elements:
                publish_date = date_elements[0].get_text().strip()

        # 方法4: 针对东奥网站的日期提取
        if not publish_date and 'dongao.com' in url:
            if '/jxjy/' in url:
                date_span = soup.find('span', class_='sp_sj fl')
                if date_span:
                    publish_date = date_span.text.strip()
            else:
                h1_tag = soup.find('h1')
                if h1_tag:
                    div_tag = h1_tag.find_next('div')
                    if div_tag:
                        publish_date = div_tag.text.strip()

        return publish_date

    def clean_text(self, text: str) -> str:
        """
        清理文本内容

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        import re
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 去除特殊字符
        text = text.strip()
        return text
