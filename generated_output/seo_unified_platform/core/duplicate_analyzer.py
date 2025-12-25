# -*- coding: utf-8 -*-
"""
重复内容分析器 - 基于TF-IDF和余弦相似度的内容重复检测
"""
import re
import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import jieba

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class DuplicateAnalyzer(BaseAnalyzer):
    """重复内容分析器"""

    def __init__(self, config):
        """
        初始化重复分析器

        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.duplicate_threshold = config.DUPLICATE_THRESHOLD
        self.similarity_threshold = config.SIMILARITY_THRESHOLD

        # 初始化jieba分词
        jieba.initialize()

    def analyze(self, url: str) -> Dict[str, any]:
        """
        分析单个URL的重复内容

        Args:
            url: 要分析的URL

        Returns:
            分析结果字典
        """
        logger.info(f"分析URL重复度: {url}")

        # 获取页面内容
        soup, _, _ = self.fetch_content(url)
        if not soup:
            return {
                'url': url,
                'success': False,
                'error': '无法获取页面内容'
            }

        # 提取元数据
        publish_date = self.extract_publish_date(soup, url)
        directory = self._extract_directory(url)

        # 提取段落
        paragraphs = self._extract_paragraphs(soup, url)

        if not paragraphs:
            return {
                'url': url,
                'success': False,
                'error': '未找到有效段落'
            }

        return {
            'url': url,
            'success': True,
            'publish_date': publish_date,
            'directory': directory,
            'total_paragraphs': len(paragraphs),
            'paragraphs': paragraphs
        }

    def batch_analyze(self, urls: List[str]) -> Dict[str, Dict]:
        """
        批量分析URLs并计算相似度

        Args:
            urls: URL列表

        Returns:
            批量分析结果，包含相似度矩阵
        """
        # 第一步：提取所有URL的内容
        logger.info("步骤1: 提取URL内容")
        url_data = {}

        with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
            futures = {executor.submit(self.analyze, url): url for url in urls}

            for future in tqdm(as_completed(futures), total=len(urls), desc="提取内容"):
                url = futures[future]
                try:
                    result = future.result()
                    url_data[url] = result
                except Exception as e:
                    logger.error(f"分析URL {url} 时出错: {str(e)}")
                    url_data[url] = {
                        'url': url,
                        'success': False,
                        'error': str(e)
                    }

        # 第二步：计算相似度
        logger.info("步骤2: 计算内容相似度")
        similarity_results = self._calculate_similarities(url_data)

        # 第三步：生成统计报告
        logger.info("步骤3: 生成统计报告")
        stats = self._generate_stats(url_data, similarity_results)

        return {
            'url_data': url_data,
            'similarities': similarity_results,
            'stats': stats
        }

    def _extract_directory(self, url: str) -> str:
        """
        从URL中提取目录路径

        Args:
            url: 网页URL

        Returns:
            目录路径
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        parts = path.strip('/').split('/')

        if len(parts) >= 2:
            directory = '/'.join(parts[:-1])
        elif len(parts) == 1 and parts[0]:
            directory = parts[0]
        else:
            directory = 'root'

        return f"{parsed_url.netloc}/{directory}"

    def _extract_paragraphs(self, soup, url: str) -> List[str]:
        """
        从BeautifulSoup对象中提取段落

        Args:
            soup: BeautifulSoup对象
            url: 页面URL

        Returns:
            段落列表
        """
        paragraphs = []

        # 查找内容容器
        container = (soup.find('div', class_='content clearfix font16') or
                    soup.find('div', class_='content_main') or
                    soup.find('div', class_='content') or
                    soup.find('article'))

        if not container:
            container = soup.find('body')

        if container:
            # 移除无关内容
            for div in container.find_all(['script', 'style', 'nav', 'footer', 'header']):
                div.decompose()

            # 提取段落文本
            for p in container.find_all('p'):
                text = p.get_text().strip()
                # 过滤短段落和特定内容（与原项目一致：长度>30，且不包含"说明："）
                if len(text) > 30 and "说明：" not in text:
                    # 额外过滤无关内容
                    if any(keyword in text for keyword in [
                        '点击查看', '推荐阅读', '免责声明', '版权声明',
                        '本文由东奥会计在线原创', '转载请注明出处'
                    ]):
                        continue
                    paragraphs.append(self.clean_text(text))

        return paragraphs

    def _calculate_similarities(self, url_data: Dict) -> Dict:
        """
        计算URL之间的相似度

        Args:
            url_data: URL数据字典

        Returns:
            相似度结果
        """
        # 过滤出成功的URL
        valid_urls = [url for url, data in url_data.items() if data.get('success')]

        if len(valid_urls) < 2:
            return {
                'duplicate_rates': {},
                'duplicate_paragraphs': {},
                'similarity_matrix': {}
            }

        # 提取所有段落
        all_paragraphs = []
        url_to_paragraphs = {}

        for url in valid_urls:
            paragraphs = url_data[url].get('paragraphs', [])
            url_to_paragraphs[url] = paragraphs
            all_paragraphs.extend(paragraphs)

        if not all_paragraphs:
            return {
                'duplicate_rates': {},
                'duplicate_paragraphs': {},
                'similarity_matrix': {}
            }

        # 使用TF-IDF计算相似度
        try:
            # 中文分词
            tokenized_texts = [' '.join(jieba.cut(p)) for p in all_paragraphs]

            # 创建TF-IDF向量器
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform(tokenized_texts)

            # 计算余弦相似度
            similarity_matrix = cosine_similarity(tfidf_matrix)

            # 检测重复段落
            duplicate_paragraphs = self._find_duplicates(
                all_paragraphs, similarity_matrix, url_to_paragraphs
            )

            # 计算每个URL的重复率
            duplicate_rates = self._calculate_duplicate_rates(
                valid_urls, url_data, duplicate_paragraphs
            )

            return {
                'duplicate_rates': duplicate_rates,
                'duplicate_paragraphs': duplicate_paragraphs,
                'similarity_matrix': similarity_matrix.tolist()
            }

        except Exception as e:
            logger.error(f"计算相似度时出错: {str(e)}")
            return {
                'duplicate_rates': {},
                'duplicate_paragraphs': {},
                'error': str(e)
            }

    def _find_duplicates(self, paragraphs: List[str], similarity_matrix, url_to_paragraphs: Dict) -> Dict:
        """
        查找重复段落

        Args:
            paragraphs: 所有段落列表
            similarity_matrix: 相似度矩阵
            url_to_paragraphs: URL到段落的映射

        Returns:
            重复段落信息
        """
        duplicate_paragraphs = defaultdict(list)
        n = len(paragraphs)

        # 找出相似的段落对
        for i in range(n):
            for j in range(i + 1, n):
                if similarity_matrix[i][j] >= self.similarity_threshold:
                    # 找到对应的URL
                    url_i = self._find_url_for_paragraph(i, url_to_paragraphs)
                    url_j = self._find_url_for_paragraph(j, url_to_paragraphs)

                    duplicate_paragraphs[url_i].append({
                        'paragraph': paragraphs[i][:100] + '...',
                        'similar_to': url_j,
                        'similarity': round(similarity_matrix[i][j] * 100, 2)
                    })

        return dict(duplicate_paragraphs)

    def _find_url_for_paragraph(self, index: int, url_to_paragraphs: Dict) -> str:
        """
        根据段落索引找到对应的URL

        Args:
            index: 段落索引
            url_to_paragraphs: URL到段落的映射

        Returns:
            URL
        """
        count = 0
        for url, paragraphs in url_to_paragraphs.items():
            count += len(paragraphs)
            if index < count:
                return url
        return 'unknown'

    def _calculate_duplicate_rates(self, urls: List[str], url_data: Dict, duplicate_paragraphs: Dict) -> Dict:
        """
        计算每个URL的重复率

        Args:
            urls: URL列表
            url_data: URL数据
            duplicate_paragraphs: 重复段落信息

        Returns:
            每个URL的重复率
        """
        duplicate_rates = {}

        for url in urls:
            if not url_data[url].get('success'):
                duplicate_rates[url] = 0.0
                continue

            total_paragraphs = url_data[url].get('total_paragraphs', 0)
            duplicate_count = len(duplicate_paragraphs.get(url, []))

            if total_paragraphs > 0:
                duplicate_rate = (duplicate_count / total_paragraphs) * 100
            else:
                duplicate_rate = 0.0

            duplicate_rates[url] = round(duplicate_rate, 2)

        return duplicate_rates

    def _generate_stats(self, url_data: Dict, similarity_results: Dict) -> Dict:
        """
        生成统计信息

        Args:
            url_data: URL数据
            similarity_results: 相似度结果

        Returns:
            统计信息
        """
        duplicate_rates = similarity_results.get('duplicate_rates', {})

        # 计算统计
        total_urls = len(url_data)
        high_duplicate_urls = sum(1 for rate in duplicate_rates.values() if rate >= self.duplicate_threshold)
        avg_duplicate_rate = np.mean(list(duplicate_rates.values())) if duplicate_rates else 0

        return {
            'total_urls': total_urls,
            'high_duplicate_count': high_duplicate_urls,
            'avg_duplicate_rate': round(avg_duplicate_rate, 2),
            'threshold': self.duplicate_threshold
        }
