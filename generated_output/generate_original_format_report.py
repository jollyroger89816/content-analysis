#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用原有报告格式生成SEO综合报告
保持原有项目的报告结构和样式
"""
import sys
import os
import json
from datetime import datetime

# 添加路径（使用相对路径）
script_dir = os.path.dirname(os.path.abspath(__file__))
platform_dir = os.path.join(script_dir, 'seo_unified_platform')
sys.path.insert(0, platform_dir)

from config import config
from core.quality_analyzer import QualityAnalyzer
from core.duplicate_analyzer import DuplicateAnalyzer
from core.seo_analyzer import SEOAnalyzer

# 导入原有报告生成器
from services.generate_comprehensive_report import generate_html_report, merge_data

print("\n" + "="*80)
print("📊 生成SEO内容质量综合报告（原有格式）")
print("="*80 + "\n")

# 准备测试URL
urls = [
    "http://example.com",
    "http://example.org",
    "http://example.net",
    "https://httpbin.org/html",
    "https://www.python.org/",
    "https://github.com",
]

print(f"📋 分析URL列表 ({len(urls)}个):")
for i, url in enumerate(urls):
    print(f"   {i+1}. {url}")

# 加载配置
app_config = config['default']

# 初始化分析器
print("\n⚙️  初始化分析器...")
quality_analyzer = QualityAnalyzer(app_config, qianfan_client=None)
duplicate_analyzer = DuplicateAnalyzer(app_config)
seo_analyzer = SEOAnalyzer(app_config, quality_analyzer, duplicate_analyzer)

# 步骤1: 执行质量分析
print("\n📝 步骤1: 执行质量分析...")
quality_results = quality_analyzer.batch_analyze(urls)
print(f"✅ 质量分析完成")

# 步骤2: 执行重复检测
print("\n🔍 步骤2: 执行重复检测...")
duplicate_results = duplicate_analyzer.batch_analyze(urls)
print(f"✅ 重复检测完成")

# 步骤3: 转换数据格式为原报告格式
print("\n🔄 步骤3: 转换数据格式...")

def convert_to_original_format(quality_results, duplicate_results):
    """将新分析器的结果转换为原报告生成器期望的格式"""

    # 构建类似原项目的SEO数据结构
    seo_data = {
        "url_info": {},
        "duplicate_rates": {},
        "paragraph_stats": {},
        "duplicate_paragraphs": {},
        "directory_groups": {},
        "config": {
            "duplicate_threshold": 15.0
        }
    }

    # 提取重复检测数据
    if duplicate_results and 'url_data' in duplicate_results:
        for url, data in duplicate_results['url_data'].items():
            if data.get('success'):
                seo_data["url_info"][url] = {
                    "publish_date": data.get('publish_date'),
                    "directory": data.get('directory', 'unknown')
                }
                seo_data["paragraph_stats"][url] = {
                    "total": data.get('total_paragraphs', 0),
                    "duplicate": 0  # 稍后计算
                }

    # 提取重复率
    if duplicate_results and 'similarities' in duplicate_results:
        seo_data["duplicate_rates"] = duplicate_results['similarities'].get('duplicate_rates', {})
        seo_data["duplicate_paragraphs"] = duplicate_results['similarities'].get('duplicate_paragraphs', {})

        # 更新段落统计
        for url, dup_paragraphs in seo_data["duplicate_paragraphs"].items():
            if url in seo_data["paragraph_stats"]:
                seo_data["paragraph_stats"][url]["duplicate"] = len(dup_paragraphs)

    # 构建质量数据（CSV格式模拟）
    quality_data = {}
    for url, result in quality_results.items():
        if result.get('success'):
            analysis = result.get('analysis', {})
            quality_data[url] = {
                "has_implicit": analysis.get('has_implicit', False),
                "score": analysis.get('score', 0),
                "result": analysis.get('result', '')
            }

    return seo_data, quality_data

# 转换数据
seo_data, quality_data = convert_to_original_format(quality_results, duplicate_results)
print(f"✅ 数据格式转换完成")

# 步骤4: 合并数据
print("\n🔗 步骤4: 合并数据...")
merged_data = merge_data(seo_data, quality_data)
print(f"✅ 数据合并完成")

# 显示统计
stats = merged_data.get('stats', {})
quality_stats = stats.get('quality_stats', {})
print(f"\n📊 合并后统计:")
print(f"   总URL数: {stats.get('total_urls', 0)}")
print(f"   优: {quality_stats.get('excellent', 0)}")
print(f"   良: {quality_stats.get('good', 0)}")
print(f"   差: {quality_stats.get('fair', 0)}")
print(f"   极差: {quality_stats.get('poor', 0)}")

# 步骤5: 生成HTML报告
print("\n📝 步骤5: 生成HTML报告...")
# 报告生成到content_analysis/reports目录
output_dir = "/Users/tang/Desktop/python/content_analysis/reports"

report_dir = generate_html_report(merged_data, output_dir)

print(f"\n✅ 报告生成成功!")
print(f"   报告目录: {report_dir}")

# 打开索引页面
import subprocess
index_path = os.path.join(report_dir, "index.html")
try:
    subprocess.run(['open', index_path])
    print(f"   ✅ 报告已在浏览器中打开")
except Exception as e:
    print(f"   ⚠️  请手动打开: {index_path}")

# 列出生成的文件
print(f"\n📂 生成的文件:")
if os.path.exists(report_dir):
    for file in sorted(os.listdir(report_dir)):
        file_path = os.path.join(report_dir, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            print(f"   • {file} ({size} bytes)")

print("\n" + "="*80)
print("✅ 原有格式的SEO综合报告生成完成！")
print("="*80 + "\n")
