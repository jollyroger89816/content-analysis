# -*- coding: utf-8 -*-
"""
SEO综合分析器 - 整合质量和重复度分析的综合评分系统
"""
import logging
from typing import Dict, List
from datetime import datetime

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class SEOAnalyzer(BaseAnalyzer):
    """SEO综合分析器"""

    def __init__(self, config, quality_analyzer=None, duplicate_analyzer=None):
        """
        初始化SEO综合分析器

        Args:
            config: 配置对象
            quality_analyzer: 质量分析器实例
            duplicate_analyzer: 重复分析器实例
        """
        super().__init__(config)
        self.quality_analyzer = quality_analyzer
        self.duplicate_analyzer = duplicate_analyzer

        # 评分权重
        self.implicit_language_weight = config.IMPLICIT_LANGUAGE_WEIGHT
        self.duplicate_content_weight = config.DUPLICATE_CONTENT_WEIGHT

    def analyze(self, url: str, quality_data: Dict = None, duplicate_data: Dict = None) -> Dict[str, any]:
        """
        分析单个URL的综合SEO表现

        Args:
            url: 要分析的URL
            quality_data: 质量分析数据（可选）
            duplicate_data: 重复度分析数据（可选）

        Returns:
            综合分析结果
        """
        logger.info(f"综合分析URL: {url}")

        # 如果没有提供数据，调用相应的分析器
        if quality_data is None and self.quality_analyzer:
            quality_data = self.quality_analyzer.analyze(url)

        if duplicate_data is None and self.duplicate_analyzer:
            duplicate_data = self.duplicate_analyzer.analyze(url)

        # 提取数据
        quality_info = self._extract_quality_info(quality_data)
        duplicate_info = self._extract_duplicate_info(duplicate_data)

        # 计算综合评分
        seo_score = self._calculate_seo_score(quality_info, duplicate_info)

        # 确定质量等级
        quality_level = self._determine_quality_level(seo_score)

        # 生成建议
        recommendations = self._generate_recommendations(quality_info, duplicate_info, seo_score)

        return {
            'url': url,
            'success': True,
            'publish_date': duplicate_info.get('publish_date'),
            'directory': duplicate_info.get('directory'),
            'quality_level': quality_level,
            'seo_score': seo_score,
            'quality_info': quality_info,
            'duplicate_info': duplicate_info,
            'recommendations': recommendations,
            'analyzed_at': datetime.now().isoformat()
        }

    def batch_analyze(self, urls: List[str], quality_results: Dict = None, duplicate_results: Dict = None) -> Dict:
        """
        批量综合分析

        Args:
            urls: URL列表
            quality_results: 质量分析结果（可选）
            duplicate_results: 重复度分析结果（可选）

        Returns:
            批量综合分析结果
        """
        logger.info(f"开始批量综合分析，共{len(urls)}个URL")

        results = {}

        for url in urls:
            quality_data = quality_results.get(url) if quality_results else None
            duplicate_data = duplicate_results.get(url, {}).get('url_data', {}).get(url) if duplicate_results else None

            try:
                result = self.analyze(url, quality_data, duplicate_data)
                results[url] = result
            except Exception as e:
                logger.error(f"综合分析URL {url} 时出错: {str(e)}")
                results[url] = {
                    'url': url,
                    'success': False,
                    'error': str(e)
                }

        # 生成汇总统计
        stats = self._generate_batch_stats(results)

        return {
            'results': results,
            'stats': stats
        }

    def _extract_quality_info(self, quality_data: Dict) -> Dict:
        """
        提取质量信息

        Args:
            quality_data: 质量分析数据

        Returns:
            质量信息字典
        """
        if not quality_data or not quality_data.get('success'):
            return {
                'has_implicit': False,
                'implicit_score': 0,
                'implicit_level': '未知',
                'paragraphs_count': 0
            }

        analysis = quality_data.get('analysis', {})

        return {
            'has_implicit': analysis.get('has_implicit', False),
            'implicit_score': analysis.get('score', 0),
            'implicit_level': analysis.get('level', '未知'),
            'paragraphs_count': quality_data.get('paragraphs_count', 0)
        }

    def _extract_duplicate_info(self, duplicate_data: Dict) -> Dict:
        """
        提取重复度信息

        Args:
            duplicate_data: 重复度分析数据

        Returns:
            重复度信息字典
        """
        if not duplicate_data or not duplicate_data.get('success'):
            return {
                'duplicate_rate': 0.0,
                'duplicate_paragraphs': 0,
                'total_paragraphs': 0,
                'publish_date': None,
                'directory': 'unknown'
            }

        # 如果是批量分析结果，提取URL特定数据
        if 'similarities' in duplicate_data:
            # 这是批量结果
            url = duplicate_data.get('url', '')
            duplicate_rates = duplicate_data.get('similarities', {}).get('duplicate_rates', {})
            duplicate_paragraphs = duplicate_data.get('similarities', {}).get('duplicate_paragraphs', {})

            return {
                'duplicate_rate': duplicate_rates.get(url, 0.0),
                'duplicate_paragraphs': len(duplicate_paragraphs.get(url, [])),
                'total_paragraphs': duplicate_data.get('url_data', {}).get(url, {}).get('total_paragraphs', 0),
                'publish_date': duplicate_data.get('url_data', {}).get(url, {}).get('publish_date'),
                'directory': duplicate_data.get('url_data', {}).get(url, {}).get('directory')
            }
        else:
            # 这是单个URL结果
            return {
                'duplicate_rate': 0.0,  # 单个分析无法计算重复率
                'duplicate_paragraphs': 0,
                'total_paragraphs': duplicate_data.get('total_paragraphs', 0),
                'publish_date': duplicate_data.get('publish_date'),
                'directory': duplicate_data.get('directory', 'unknown')
            }

    def _calculate_seo_score(self, quality_info: Dict, duplicate_info: Dict) -> float:
        """
        计算综合SEO评分

        评分公式:
        - 重复内容评分 = 100 - 重复率
        - 暗示性语言评分 = 100 - (暗示分数 * 10)
        - 综合评分 = 重复内容权重 * 重复评分 + 暗示语言权重 * 暗示评分

        Args:
            quality_info: 质量信息
            duplicate_info: 重复度信息

        Returns:
            综合SEO评分 (0-100)
        """
        # 1. 重复内容评分 (0-100，100最好)
        duplicate_rate = duplicate_info.get('duplicate_rate', 0.0)
        duplicate_score = max(0, 100 - duplicate_rate)

        # 2. 暗示性语言评分 (0-100，100最好)
        implicit_score = quality_info.get('implicit_score', 0)
        normalized_implicit_score = max(0, 100 - implicit_score * 10)

        # 3. 加权平均
        seo_score = (
            self.duplicate_content_weight * duplicate_score +
            self.implicit_language_weight * normalized_implicit_score
        )

        return round(seo_score, 2)

    def _determine_quality_level(self, seo_score: float) -> str:
        """
        根据SEO评分确定质量等级

        Args:
            seo_score: SEO综合评分

        Returns:
            质量等级 (优/良/差/极差)
        """
        if seo_score >= 85:
            return '优'
        elif seo_score >= 70:
            return '良'
        elif seo_score >= 50:
            return '差'
        else:
            return '极差'

    def _generate_recommendations(self, quality_info: Dict, duplicate_info: Dict, seo_score: float) -> List[str]:
        """
        生成优化建议

        Args:
            quality_info: 质量信息
            duplicate_info: 重复度信息
            seo_score: SEO评分

        Returns:
            建议列表
        """
        recommendations = []

        # 基于评分等级的建议
        if seo_score >= 85:
            recommendations.append("✅ 页面质量优秀，继续保持")
        elif seo_score >= 70:
            recommendations.append("⚠️ 页面质量良好，有优化空间")
        else:
            recommendations.append("❌ 页面质量需要优化")

        # 基于暗示性语言的建议
        if quality_info.get('has_implicit'):
            implicit_level = quality_info.get('implicit_level', '')
            implicit_score = quality_info.get('implicit_score', 0)

            if implicit_level == '强烈' or implicit_score >= 7:
                recommendations.append("🔴 检测到强烈暗示性语言，建议修改为明确表述")
            elif implicit_level == '中等' or implicit_score >= 5:
                recommendations.append("🟡 检测到中等程度暗示性语言，建议优化")
            elif implicit_level == '轻微' or implicit_score >= 3:
                recommendations.append("🟢 检测到轻微暗示性语言，可以适当改进")
        else:
            recommendations.append("✅ 未检测到暗示性语言，表述明确")

        # 基于重复度的建议
        duplicate_rate = duplicate_info.get('duplicate_rate', 0.0)
        duplicate_threshold = self.config.DUPLICATE_THRESHOLD

        if duplicate_rate > duplicate_threshold * 2:
            recommendations.append(f"🔴 内容重复率过高({duplicate_rate:.1f}%)，强烈建议重写")
        elif duplicate_rate > duplicate_threshold:
            recommendations.append(f"🟡 内容重复率较高({duplicate_rate:.1f}%)，建议修改")
        elif duplicate_rate > 0:
            recommendations.append(f"✅ 内容重复率在可接受范围({duplicate_rate:.1f}%)")
        else:
            recommendations.append("✅ 内容原创性良好")

        return recommendations

    def _generate_batch_stats(self, results: Dict) -> Dict:
        """
        生成批量分析统计信息

        Args:
            results: 分析结果字典

        Returns:
            统计信息
        """
        total_urls = len(results)
        successful = sum(1 for r in results.values() if r.get('success'))

        quality_levels = {}
        avg_score = 0
        has_implicit_count = 0
        high_duplicate_count = 0

        for result in results.values():
            if result.get('success'):
                # 质量等级统计
                level = result.get('quality_level', '未知')
                quality_levels[level] = quality_levels.get(level, 0) + 1

                # 平均评分
                avg_score += result.get('seo_score', 0)

                # 暗示性语言统计
                if result.get('quality_info', {}).get('has_implicit'):
                    has_implicit_count += 1

                # 高重复度统计
                if result.get('duplicate_info', {}).get('duplicate_rate', 0) > self.config.DUPLICATE_THRESHOLD:
                    high_duplicate_count += 1

        if successful > 0:
            avg_score = round(avg_score / successful, 2)

        return {
            'total_urls': total_urls,
            'successful_analyses': successful,
            'failed_analyses': total_urls - successful,
            'quality_distribution': quality_levels,
            'average_seo_score': avg_score,
            'has_implicit_count': has_implicit_count,
            'high_duplicate_count': high_duplicate_count
        }
