# -*- coding: utf-8 -*-
"""
文章质量分析器 - 基于千帆API的暗示性语言检测
"""
import re
import logging
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class QualityAnalyzer(BaseAnalyzer):
    """文章质量分析器"""

    def __init__(self, config, qianfan_client=None):
        """
        初始化质量分析器

        Args:
            config: 配置对象
            qianfan_client: 千帆API客户端（可选）
        """
        super().__init__(config)
        self.qianfan_client = qianfan_client

    def analyze(self, url: str) -> Dict[str, any]:
        """
        分析单个URL的文章质量

        Args:
            url: 要分析的URL

        Returns:
            分析结果字典
        """
        logger.info(f"分析URL质量: {url}")

        # 获取页面内容
        soup, _, _ = self.fetch_content(url)
        if not soup:
            return {
                'url': url,
                'success': False,
                'error': '无法获取页面内容'
            }

        # 提取段落
        paragraphs = self._extract_paragraphs(soup, url)
        if not paragraphs:
            return {
                'url': url,
                'success': False,
                'error': '未找到有效段落'
            }

        # 合并段落进行分析
        combined_text = " ".join(paragraphs)

        # 调用AI分析
        if self.qianfan_client:
            analysis_result = self._analyze_with_ai(combined_text)
        else:
            # 使用规则引擎作为备选方案
            analysis_result = self._analyze_with_rules(combined_text)

        return {
            'url': url,
            'success': True,
            'paragraphs_count': len(paragraphs),
            'content_preview': combined_text[:200] + '...' if len(combined_text) > 200 else combined_text,
            'analysis': analysis_result
        }

    def batch_analyze(self, urls: List[str]) -> Dict[str, Dict]:
        """
        批量分析URLs

        Args:
            urls: URL列表

        Returns:
            批量分析结果
        """
        results = {}

        with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
            futures = {executor.submit(self.analyze, url): url for url in urls}

            for future in tqdm(as_completed(futures), total=len(urls), desc="质量分析进度"):
                url = futures[future]
                try:
                    result = future.result()
                    results[url] = result
                except Exception as e:
                    logger.error(f"分析URL {url} 时出错: {str(e)}")
                    results[url] = {
                        'url': url,
                        'success': False,
                        'error': str(e)
                    }

        return results

    def _extract_paragraphs(self, soup, url: str) -> List[str]:
        """
        从BeautifulSoup对象中提取段落

        Args:
            soup: BeautifulSoup对象
            url: 页面URL（用于特殊处理）

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
            # 如果没找到特定容器，使用整个body
            container = soup.find('body')

        if container:
            # 移除无关内容
            for div_class in ['next-prev-Art clearfix', 'related-art', 'sidebar', 'footer']:
                for div in container.find_all('div', class_=div_class):
                    div.decompose()

            # 提取段落
            for p in container.find_all('p'):
                text = p.get_text().strip()
                if text and len(text) >= 3:
                    # 过滤掉无关内容
                    if any(keyword in text for keyword in [
                        '点击查看：', '推荐阅读', '本文由原创', '转载请注明出处',
                        '说明：', '免责声明'
                    ]):
                        continue

                    # 对于某些页面，遇到推荐阅读就停止
                    if "推荐阅读：" in text and '/jxjy/' not in url:
                        break

                    paragraphs.append(self.clean_text(text))

        return paragraphs

    def _analyze_with_ai(self, text: str) -> Dict:
        """
        使用千帆AI分析文本

        Args:
            text: 要分析的文本

        Returns:
            分析结果
        """
        try:
            question = f"""分析以下段落，识别属于暗示类语言的段落。暗示类语言是指没有明确答案关键字、建议类回答的内容。请评估暗示程度（轻微/中等/强烈），返回暗示类段落数和总段落数。

段落内容：{text}"""

            response = self.qianfan_client.chat.completions.create(
                model=self.config.QIANFAN_MODEL,
                messages=[{"role": "user", "content": question}]
            )

            # 提取AI回复
            if hasattr(response.choices[0], 'message'):
                ai_message = response.choices[0].message.content
            else:
                ai_message = response.choices[0].text

            # 解析AI回复
            return self._parse_ai_response(ai_message)

        except Exception as e:
            logger.error(f"AI分析失败: {str(e)}")
            return {
                'has_implicit': False,
                'score': 0,
                'result': f'AI分析失败: {str(e)}',
                'level': '未知'
            }

    def _analyze_with_rules(self, text: str) -> Dict:
        """
        使用规则引擎分析文本（备选方案）

        Args:
            text: 要分析的文本

        Returns:
            分析结果
        """
        # 简单的关键词匹配规则
        implicit_keywords = [
            '可能', '也许', '大概', '估计', '应该', '理论上',
            '某种程度上', '一定程度上', '一般来说', '通常',
            '可能存在', '不排除', '有可能'
        ]

        strong_keywords = [
            '强烈建议', '明确表示', '肯定', '必须', '务必'
        ]

        text_lower = text.lower()
        implicit_count = 0
        strong_count = 0

        for keyword in implicit_keywords:
            if keyword in text:
                implicit_count += text.count(keyword)

        for keyword in strong_keywords:
            if keyword in text:
                strong_count += text.count(keyword)

        # 计算评分
        if strong_count > 0:
            score = 7
            level = '强烈'
        elif implicit_count > 3:
            score = 5
            level = '中等'
        elif implicit_count > 0:
            score = 3
            level = '轻微'
        else:
            score = 0
            level = '无'

        return {
            'has_implicit': implicit_count > 0,
            'score': score,
            'result': f'规则分析: 发现{implicit_count}处暗示性语言, {strong_count}处强烈表达',
            'level': level
        }

    def _parse_ai_response(self, response: str) -> Dict:
        """
        解析AI响应

        Args:
            response: AI返回的文本

        Returns:
            解析后的结果
        """
        has_implicit = False
        score = 0
        level = '无'

        response_lower = response.lower()

        # 检查是否包含"无暗示"
        if re.search(r'无暗示|没有.*?暗示|不存在.*?暗示|暗示类段落数：0|暗示类段落数:0', response_lower):
            return {
                'has_implicit': False,
                'score': 0,
                'result': response,
                'level': '无'
            }

        # 检测是否存在暗示性语言
        if re.search(r'暗示类段落数[：:]\s*[1-9]|存在.*?暗示|有.*?暗示', response_lower):
            has_implicit = True

        # 检测暗示程度
        degree_pattern = re.search(r'程度[：:]\s*(轻微|中等|强烈)|暗示程度[：:]\s*(轻微|中等|强烈)', response_lower)
        if degree_pattern:
            degree = degree_pattern.group(1) or degree_pattern.group(2)
            level = degree
            if degree == '强烈':
                score = 7
            elif degree == '中等':
                score = 5
            elif degree == '轻微':
                score = 3
        else:
            # 根据关键词判断
            if re.search(r'强烈|明显|严重|高度', response_lower):
                score = 7
                level = '强烈'
            elif re.search(r'中等|适度|一定程度', response_lower):
                score = 5
                level = '中等'
            elif re.search(r'轻微|轻度|些许', response_lower):
                score = 3
                level = '轻微'
            elif has_implicit:
                score = 4
                level = '中等'

        return {
            'has_implicit': has_implicit,
            'score': score,
            'result': response,
            'level': level
        }
