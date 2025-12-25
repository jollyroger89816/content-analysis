# -*- coding: utf-8 -*-
"""
SEO分析报告生成器 - 生成HTML格式的质量报告
"""
import os
from datetime import datetime
from typing import Dict, List


class ReportGenerator:
    """SEO分析报告生成器"""

    def __init__(self, output_dir="reports"):
        """
        初始化报告生成器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_html_report(self, analysis_results: Dict, urls: List[str]) -> str:
        """
        生成HTML格式的SEO分析报告

        Args:
            analysis_results: 分析结果字典
            urls: 分析的URL列表

        Returns:
            生成的HTML报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"seo_report_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)

        # 提取数据
        seo_results = analysis_results.get('results', {})
        stats = analysis_results.get('stats', {})

        # 生成HTML内容
        html_content = self._generate_html_template(seo_results, stats, urls)

        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    def _generate_html_template(self, results: Dict, stats: Dict, urls: List[str]) -> str:
        """生成HTML模板"""

        # 计算统计信息
        total = len(results)
        successful = sum(1 for r in results.values() if r.get('success'))
        quality_dist = stats.get('quality_distribution', {})
        avg_score = stats.get('average_seo_score', 0)

        # 按质量等级分类
        excellent_urls = []
        good_urls = []
        fair_urls = []
        poor_urls = []

        for url, result in results.items():
            if result.get('success'):
                level = result.get('quality_level', '')
                data = {
                    'url': url,
                    'score': result.get('seo_score', 0),
                    'recommendations': result.get('recommendations', []),
                    'quality_info': result.get('quality_info', {}),
                    'duplicate_info': result.get('duplicate_info', {})
                }

                if level == '优':
                    excellent_urls.append(data)
                elif level == '良':
                    good_urls.append(data)
                elif level == '差':
                    fair_urls.append(data)
                else:
                    poor_urls.append(data)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量分析报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
            background: #f5f7fa;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header .meta {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px 40px;
            background: #f8f9fa;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .summary-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .summary-card .label {{
            color: #666;
            font-size: 0.9em;
        }}
        .content {{
            padding: 40px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        .quality-bar {{
            display: flex;
            height: 40px;
            border-radius: 8px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .quality-segment {{
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 0.9em;
        }}
        .excellent {{ background: #28a745; }}
        .good {{ background: #17a2b8; }}
        .fair {{ background: #ffc107; color: #333; }}
        .poor {{ background: #dc3545; }}
        .url-card {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            transition: transform 0.2s;
        }}
        .url-card:hover {{
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .url-card.excellent {{ border-left-color: #28a745; }}
        .url-card.good {{ border-left-color: #17a2b8; }}
        .url-card.fair {{ border-left-color: #ffc107; }}
        .url-card.poor {{ border-left-color: #dc3545; }}
        .url-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .url-title {{
            font-size: 1.1em;
            font-weight: bold;
            color: #333;
            flex: 1;
            word-break: break-all;
        }}
        .badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
            color: white;
            margin-left: 10px;
        }}
        .badge-excellent {{ background: #28a745; }}
        .badge-good {{ background: #17a2b8; }}
        .badge-fair {{ background: #ffc107; color: #333; }}
        .badge-poor {{ background: #dc3545; }}
        .score-display {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .recommendations {{
            margin-top: 15px;
            padding: 15px;
            background: white;
            border-radius: 5px;
        }}
        .recommendations h4 {{
            color: #555;
            margin-bottom: 10px;
            font-size: 1em;
        }}
        .recommendations ul {{
            list-style: none;
            padding: 0;
        }}
        .recommendations li {{
            padding: 5px 0;
            padding-left: 20px;
            position: relative;
        }}
        .recommendations li:before {{
            content: "•";
            position: absolute;
            left: 5px;
            color: #667eea;
            font-weight: bold;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            color: #666;
            border-top: 1px solid #e0e0e0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background: #667eea;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 SEO内容质量分析报告</h1>
            <div class="meta">
                <p>生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
                <p>分析URL数量: {total} 个 | 成功分析: {successful} 个</p>
            </div>
        </div>

        <div class="summary">
            <div class="summary-card">
                <div class="number">{total}</div>
                <div class="label">分析总数</div>
            </div>
            <div class="summary-card">
                <div class="number">{successful}</div>
                <div class="label">成功分析</div>
            </div>
            <div class="summary-card">
                <div class="number">{avg_score:.1f}</div>
                <div class="label">平均SEO评分</div>
            </div>
            <div class="summary-card">
                <div class="number">{quality_dist.get('优', 0)}</div>
                <div class="label">优秀页面</div>
            </div>
        </div>

        <div class="content">
            <div class="section">
                <h2 class="section-title">📈 质量等级分布</h2>
                <div class="quality-bar">
"""

        # 添加质量等级分布条
        excellent_pct = (quality_dist.get('优', 0) / total * 100) if total > 0 else 0
        good_pct = (quality_dist.get('良', 0) / total * 100) if total > 0 else 0
        fair_pct = (quality_dist.get('差', 0) / total * 100) if total > 0 else 0
        poor_pct = (quality_dist.get('极差', 0) / total * 100) if total > 0 else 0

        html += f"""
                    <div class="quality-segment excellent" style="width: {excellent_pct}%;">优 {quality_dist.get('优', 0)}</div>
                    <div class="quality-segment good" style="width: {good_pct}%;">良 {quality_dist.get('良', 0)}</div>
                    <div class="quality-segment fair" style="width: {fair_pct}%;">差 {quality_dist.get('差', 0)}</div>
                    <div class="quality-segment poor" style="width: {poor_pct}%;">极差 {quality_dist.get('极差', 0)}</div>
                </div>
            </div>
"""

        # 添加优秀URL详情
        if excellent_urls:
            html += self._generate_url_section("优秀页面 (优)", excellent_urls, "excellent")

        if good_urls:
            html += self._generate_url_section("良好页面 (良)", good_urls, "good")

        if fair_urls:
            html += self._generate_url_section("待改进页面 (差)", fair_urls, "fair")

        if poor_urls:
            html += self._generate_url_section("急需优化页面 (极差)", poor_urls, "poor")

        # 添加详细数据表格
        html += f"""
            <div class="section">
                <h2 class="section-title">📋 详细分析数据</h2>
                <table>
                    <thead>
                        <tr>
                            <th>URL</th>
                            <th>质量等级</th>
                            <th>SEO评分</th>
                            <th>暗示程度</th>
                            <th>重复率</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        for url, result in results.items():
            if result.get('success'):
                level = result.get('quality_level', '')
                score = result.get('seo_score', 0)
                quality_info = result.get('quality_info', {})
                duplicate_info = result.get('duplicate_info', {})

                implicit_level = quality_info.get('implicit_level', '无')
                duplicate_rate = duplicate_info.get('duplicate_rate', 0)

                html += f"""
                        <tr>
                            <td><a href="{url}" target="_blank" style="color: #667eea;">{url[:60]}...</a></td>
                            <td><span class="badge badge-{self._level_to_class(level)}">{level}</span></td>
                            <td>{score:.1f}</td>
                            <td>{implicit_level}</td>
                            <td>{duplicate_rate:.1f}%</td>
                        </tr>
"""

        html += """
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            <p>本报告由 统一SEO分析平台 自动生成</p>
            <p>生成时间: """ + datetime.now().strftime('%Y年%m月%d日 %H:%M:%S') + """</p>
            <p style="margin-top: 10px; font-size: 0.9em;">© 2024 SEO Analysis Platform</p>
        </div>
    </div>
</body>
</html>"""

        return html

    def _generate_url_section(self, title: str, urls: List[Dict], level_class: str) -> str:
        """生成URL分类区块"""
        html = f"""
            <div class="section">
                <h2 class="section-title">{title} - {len(urls)}个</h2>
"""

        for url_data in urls[:10]:  # 限制显示前10个
            url = url_data['url']
            score = url_data['score']
            recommendations = url_data.get('recommendations', [])

            html += f"""
                <div class="url-card {level_class}">
                    <div class="url-header">
                        <div class="url-title"><a href="{url}" target="_blank" style="color: #333;">{url}</a></div>
                        <div class="score-display">{score:.1f}</div>
                    </div>
                    <div class="recommendations">
                        <h4>💡 优化建议:</h4>
                        <ul>
"""

            for rec in recommendations[:5]:
                html += f"<li>{rec}</li>"

            html += """
                        </ul>
                    </div>
                </div>
"""

        if len(urls) > 10:
            html += f"<p style='text-align: center; color: #999; padding: 20px;'>... 还有 {len(urls) - 10} 个页面</p>"

        html += "</div>"

        return html

    def _level_to_class(self, level: str) -> str:
        """将质量等级转换为CSS类名"""
        mapping = {
            '优': 'excellent',
            '良': 'good',
            '差': 'fair',
            '极差': 'poor'
        }
        return mapping.get(level, 'good')
