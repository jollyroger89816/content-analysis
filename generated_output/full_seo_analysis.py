#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的SEO分析流程 - 模拟原有项目的工作方式
1. 同时启动质量检测和重复检测（并行）
2. 等待两个脚本都完成
3. 合并结果生成综合报告

使用方法:
    python full_seo_analysis.py [url_file]

示例:
    python full_seo_analysis.py urls.txt
"""
import sys
import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加路径（使用相对路径）
script_dir = os.path.dirname(os.path.abspath(__file__))
platform_dir = os.path.join(script_dir, 'seo_unified_platform')
sys.path.insert(0, platform_dir)

from config import config
from core.quality_analyzer import QualityAnalyzer
from core.duplicate_analyzer import DuplicateAnalyzer
from services.generate_comprehensive_report import generate_html_report, merge_data

print("\n" + "="*80)
print("🚀 完整SEO分析流程（原有工作方式）")
print("="*80)

# 加载URL列表（支持命令行参数）
if len(sys.argv) > 1:
    url_file = sys.argv[1]
elif os.path.exists("/tmp/test_urls_clean.txt"):
    url_file = "/tmp/test_urls_clean.txt"
else:
    print("\n❌ 错误: 请指定URL文件")
    print("\n使用方法:")
    print("  python full_seo_analysis.py <url_file>")
    print("\n示例:")
    print("  python full_seo_analysis.py urls.txt")
    sys.exit(1)

print(f"\n📂 从文件加载URL: {url_file}")

with open(url_file, 'r', encoding='utf-8') as f:
    urls = [line.strip() for line in f if line.strip()]

print(f"✅ 加载了 {len(urls)} 个URL")

# 配置
app_config = config['default']
# 报告生成到content_analysis/reports目录
output_dir = "/Users/tang/Desktop/python/content_analysis/reports"

# 创建临时目录保存中间结果
temp_dir = os.path.join(output_dir, "temp_analysis")
os.makedirs(temp_dir, exist_ok=True)

quality_json_path = os.path.join(temp_dir, "quality_results.json")
duplicate_json_path = os.path.join(temp_dir, "duplicate_results.json")

# 用于存储结果
results = {
    'quality': None,
    'duplicate': None,
    'quality_time': 0,
    'duplicate_time': 0
}
lock = threading.Lock()

def run_quality_analysis(urls):
    """运行质量分析"""
    print("\n" + "-"*80)
    print("📝 【任务1】启动质量检测脚本...")
    print("-"*80)

    start_time = time.time()

    # 初始化分析器
    analyzer = QualityAnalyzer(app_config, qianfan_client=None)

    # 执行分析
    quality_results = analyzer.batch_analyze(urls)

    elapsed = time.time() - start_time

    # 保存结果到JSON
    with open(quality_json_path, 'w', encoding='utf-8') as f:
        json.dump(quality_results, f, ensure_ascii=False, indent=2)

    with lock:
        results['quality'] = quality_results
        results['quality_time'] = elapsed

    successful = sum(1 for r in quality_results.values() if r.get('success'))

    print(f"\n✅ 【任务1完成】质量检测脚本执行完成")
    print(f"   分析URL数: {len(quality_results)}")
    print(f"   成功: {successful}")
    print(f"   失败: {len(quality_results) - successful}")
    print(f"   耗时: {elapsed:.2f}秒")
    print(f"   结果已保存到: {quality_json_path}")

    return quality_results

def run_duplicate_analysis(urls):
    """运行重复检测"""
    print("\n" + "-"*80)
    print("🔍 【任务2】启动重复检测脚本...")
    print("-"*80)

    start_time = time.time()

    # 初始化分析器
    analyzer = DuplicateAnalyzer(app_config)

    # 执行分析
    duplicate_results = analyzer.batch_analyze(urls)

    elapsed = time.time() - start_time

    # 保存结果到JSON
    with open(duplicate_json_path, 'w', encoding='utf-8') as f:
        json.dump(duplicate_results, f, ensure_ascii=False, indent=2)

    with lock:
        results['duplicate'] = duplicate_results
        results['duplicate_time'] = elapsed

    if duplicate_results and 'url_data' in duplicate_results:
        successful = sum(1 for r in duplicate_results['url_data'].values() if r.get('success'))
        stats = duplicate_results.get('stats', {})

        print(f"\n✅ 【任务2完成】重复检测脚本执行完成")
        print(f"   分析URL数: {len(duplicate_results['url_data'])}")
        print(f"   成功: {successful}")
        print(f"   失败: {len(duplicate_results['url_data']) - successful}")
        print(f"   高重复URL: {stats.get('high_duplicate_count', 0)}")
        print(f"   平均重复率: {stats.get('avg_duplicate_rate', 0)}%")
        print(f"   耗时: {elapsed:.2f}秒")
        print(f"   结果已保存到: {duplicate_json_path}")

    return duplicate_results

# 步骤1: 并行启动两个分析脚本
print("\n" + "="*80)
print("🔄 步骤1: 同时启动质量检测和重复检测脚本（并行执行）")
print("="*80)

overall_start = time.time()

# 使用线程池并行执行
with ThreadPoolExecutor(max_workers=2) as executor:
    # 提交两个任务
    future_quality = executor.submit(run_quality_analysis, urls)
    future_duplicate = executor.submit(run_duplicate_analysis, urls)

    # 等待两个任务都完成
    print("\n⏳ 等待两个脚本完成...")
    futures = {future_quality: 'quality', future_duplicate: 'duplicate'}

    for future in as_completed(futures):
        task_name = futures[future]
        try:
            future.result()
        except Exception as e:
            print(f"\n❌ {task_name} 任务失败: {str(e)}")
            import traceback
            traceback.print_exc()

parallel_time = time.time() - overall_start

# 步骤2: 等待并确认两个脚本都完成
print("\n" + "="*80)
print("⏸️  步骤2: 两个脚本都已执行完成")
print("="*80)

print(f"\n📊 执行统计:")
print(f"   质量检测耗时: {results['quality_time']:.2f}秒")
print(f"   重复检测耗时: {results['duplicate_time']:.2f}秒")
print(f"   总耗时（并行）: {parallel_time:.2f}秒")
print(f"   节省时间: {results['quality_time'] + results['duplicate_time'] - parallel_time:.2f}秒")

# 步骤3: 合并数据
print("\n" + "="*80)
print("🔗 步骤3: 合并两个脚本的输出数据")
print("="*80)

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
                    "duplicate": 0
                }

    # 提取重复率
    if duplicate_results and 'similarities' in duplicate_results:
        seo_data["duplicate_rates"] = duplicate_results['similarities'].get('duplicate_rates', {})
        seo_data["duplicate_paragraphs"] = duplicate_results['similarities'].get('duplicate_paragraphs', {})

        # 更新段落统计
        for url, dup_paragraphs in seo_data["duplicate_paragraphs"].items():
            if url in seo_data["paragraph_stats"]:
                seo_data["paragraph_stats"][url]["duplicate"] = len(dup_paragraphs)

    # 构建质量数据
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

# 转换数据格式
seo_data, quality_data = convert_to_original_format(results['quality'], results['duplicate'])

print(f"✅ 数据格式转换完成")

# 使用原有的merge_data函数
merged_data = merge_data(seo_data, quality_data)

# 显示统计
stats = merged_data.get('stats', {})
quality_stats = stats.get('quality_stats', {})

print(f"\n📊 合并后统计:")
print(f"   总URL数: {stats.get('total_urls', 0)}")
print(f"   优: {quality_stats.get('excellent', 0)}")
print(f"   良: {quality_stats.get('good', 0)}")
print(f"   差: {quality_stats.get('fair', 0)}")
print(f"   极差: {quality_stats.get('poor', 0)}")
print(f"   高重复URL: {stats.get('high_duplicate', 0)}")
print(f"   暗示语言URL: {stats.get('has_implicit', 0)}")
print(f"   双重问题URL: {stats.get('both_issues', 0)}")

# 步骤4: 生成综合报告
print("\n" + "="*80)
print("📝 步骤4: 生成SEO内容质量综合报告")
print("="*80)

report_start = time.time()

report_dir = generate_html_report(merged_data, output_dir)

report_time = time.time() - report_start

total_time = time.time() - overall_start

print(f"\n✅ 综合报告生成成功!")
print(f"   报告目录: {report_dir}")
print(f"   报告生成耗时: {report_time:.2f}秒")

# 打开报告
import subprocess
index_path = os.path.join(report_dir, "index.html")
try:
    subprocess.run(['open', index_path])
    print(f"   ✅ 报告已在浏览器中打开")
except Exception as e:
    print(f"   请手动打开: {index_path}")

# 总结
print("\n" + "="*80)
print("🎉 完整SEO分析流程总结")
print("="*80)

print(f"\n⏱️  时间统计:")
print(f"   质量检测: {results['quality_time']:.2f}秒")
print(f"   重复检测: {results['duplicate_time']:.2f}秒")
print(f"   并行执行: {parallel_time:.2f}秒")
print(f"   报告生成: {report_time:.2f}秒")
print(f"   总耗时: {total_time:.2f}秒")

print(f"\n📊 分析结果:")
print(f"   总URL数: {len(urls)}")
print(f"   质量分布: 优{quality_stats.get('excellent', 0)} / 良{quality_stats.get('good', 0)} / 差{quality_stats.get('fair', 0)} / 极差{quality_stats.get('poor', 0)}")

print(f"\n💾 输出文件:")
print(f"   报告目录: {report_dir}")
print(f"   质量结果: {quality_json_path}")
print(f"   重复检测结果: {duplicate_json_path}")

print(f"\n✅ 分析完成！这是与原有项目完全一致的工作流程！")
print("="*80 + "\n")
