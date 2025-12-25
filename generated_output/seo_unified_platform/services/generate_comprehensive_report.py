#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import csv
import argparse
from datetime import datetime
import logging
from tqdm import tqdm
import shutil
import re
import math

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义工作目录
BASE_DIR = "/Users/tang/Desktop/python"
SEO_DIR = os.path.join(BASE_DIR, "线上检测/线上内容重复问题")
QUALITY_DIR = os.path.join(BASE_DIR, "线上检测/文章质量检测")
# 修改：使用新平台的报告目录，避免与原项目报告混淆
REPORT_DIR = "/Users/tang/Desktop/python/content_analysis/reports"

def load_seo_data(seo_json_path):
    """加载SEO内容重复分析的数据"""
    try:
        with open(seo_json_path, 'r', encoding='utf-8') as f:
            seo_data = json.load(f)
        return seo_data
    except Exception as e:
        logger.error(f"加载SEO数据失败: {str(e)}")
        return None

def load_quality_data(quality_csv_path):
    """加载文章质量检测的数据"""
    quality_data = {}
    try:
        with open(quality_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("URL", "").strip()
                if url:
                    quality_data[url] = {
                        "has_implicit": row.get("Has Implicit", "False").lower() == "true",
                        "score": int(row.get("Score", "0")),
                        "result": row.get("Analysis Result", "")
                    }
        return quality_data
    except Exception as e:
        logger.error(f"加载质量检测数据失败: {str(e)}")
        return {}

def merge_data(seo_data, quality_data):
    """合并SEO和质量检测数据"""
    if not seo_data:
        return None
    
    merged_results = {
        "urls": {},
        "directory_groups": seo_data.get("directory_groups", {}),
        "config": seo_data.get("config", {}),
        "stats": {
            "total_urls": 0,
            "high_duplicate": 0,
            "has_implicit": 0,
            "both_issues": 0,
            "quality_stats": {
                "excellent": 0,   # 优
                "good": 0,        # 良
                "fair": 0,        # 差
                "poor": 0         # 极差
            }
        }
    }
    
    # 处理URL数据
    duplicate_rates = seo_data.get("duplicate_rates", {})
    paragraph_stats = seo_data.get("paragraph_stats", {})
    url_info = seo_data.get("url_info", {})
    duplicate_paragraphs = seo_data.get("duplicate_paragraphs", {})
    
    # 设置重复率阈值和评分权重
    duplicate_threshold = seo_data.get("config", {}).get("duplicate_threshold", 15.0)
    
    # SEO评分权重配置 - 权重比例：重复度7:暗示语言3
    weights = {
        "duplicate_content": 0.7,  # 内容重复性权重 (70%)
        "implicit_language": 0.3    # 暗示性语言权重 (30%)
    }
    
    for url in url_info:
        # 获取SEO数据
        duplicate_rate = duplicate_rates.get(url, 0)
        stats = paragraph_stats.get(url, {})
        info = url_info.get(url, {})
        
        # 获取质量检测数据
        quality_info = quality_data.get(url, {
            "has_implicit": False,
            "score": 0,
            "result": "未进行质量检测"
        })
        
        # 计算SEO评分（仍然计算用于后续分级）
        # 1. 重复内容评分 (100-重复率)，100是最好的，0是最差的
        duplicate_score = max(0, 100 - duplicate_rate)
        
        # 2. 暗示性语言评分 (0-100，分数越低越好)
        # 因为暗示性语言评分是0-10，10分表示最严重，这里转换为0-100，并且反转使高分表示更好
        implicit_score = quality_info["score"]
        normalized_implicit_score = max(0, 100 - implicit_score * 10)
        
        # 3. 计算综合SEO评分 (权重加权平均)
        seo_score = (weights["duplicate_content"] * duplicate_score + 
                     weights["implicit_language"] * normalized_implicit_score)
        
        # 4. 转换为质量等级
        if seo_score >= 85:
            quality_level = "优"
            merged_results["stats"]["quality_stats"]["excellent"] += 1
        elif seo_score >= 70:
            quality_level = "良"
            merged_results["stats"]["quality_stats"]["good"] += 1
        elif seo_score >= 50:
            quality_level = "差"
            merged_results["stats"]["quality_stats"]["fair"] += 1
        else:
            quality_level = "极差"
            merged_results["stats"]["quality_stats"]["poor"] += 1
            
        # 合并数据
        merged_results["urls"][url] = {
            "publish_date": info.get("publish_date"),
            "directory": info.get("directory", ""),
            "total_paragraphs": stats.get("total", 0),
            "duplicate_paragraphs": stats.get("duplicate", 0),
            "duplicate_rate": duplicate_rate,
            "has_implicit": quality_info["has_implicit"],
            "implicit_score": quality_info["score"],
            "implicit_result": quality_info["result"],
            "duplicate_details": duplicate_paragraphs.get(url, []),
            "raw_seo_score": round(seo_score, 2),  # 原始SEO评分（隐藏）
            "quality_level": quality_level,  # 新增：质量等级
            "duplicate_score": round(duplicate_score, 2),  # 内容重复评分
            "normalized_implicit_score": round(normalized_implicit_score, 2)  # 暗示语言评分
        }
        
        # 更新统计信息
        merged_results["stats"]["total_urls"] += 1
        if duplicate_rate >= duplicate_threshold:
            merged_results["stats"]["high_duplicate"] += 1
        if quality_info["has_implicit"]:
            merged_results["stats"]["has_implicit"] += 1
        if duplicate_rate >= duplicate_threshold and quality_info["has_implicit"]:
            merged_results["stats"]["both_issues"] += 1
    
    return merged_results

def generate_html_report(merged_data, output_dir):
    """生成HTML格式的综合报告"""
    if not merged_data:
        logger.error("没有有效的合并数据，无法生成报告")
        return False
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = os.path.join(output_dir, f"comprehensive_report_{timestamp}")
    os.makedirs(report_dir, exist_ok=True)
    
    logger.info(f"正在生成索引页面...")
    index_path = generate_index_page(merged_data, report_dir)
    
    # 生成内容重复URL专用页面
    logger.info(f"正在生成内容重复URL页面...")
    generate_duplicate_page(merged_data, report_dir)
    
    # 生成暗示性语言URL专用页面
    logger.info(f"正在生成暗示性语言URL页面...")
    generate_implicit_page(merged_data, report_dir)

    # 生成目录统计页面
    logger.info(f"正在生成目录统计页面...")
    generate_directory_stats_page(merged_data, report_dir)
    
    # 定义各种类别的筛选函数
    filter_funcs = {
        "all": lambda data, threshold: True,
        "excellent": lambda data, threshold: data["quality_level"] == "优",
        "good": lambda data, threshold: data["quality_level"] == "良",
        "fair": lambda data, threshold: data["quality_level"] == "差",
        "poor": lambda data, threshold: data["quality_level"] == "极差",
        # "duplicate": lambda data, threshold: data["duplicate_rate"] >= threshold,  # 使用专用页面，不再在这里生成
        # "implicit": lambda data, threshold: data["has_implicit"]  # 使用专用页面，不再在这里生成
    }
    
    # 定义类别页面标题
    page_titles = {
        "all": "全部URL",
        "excellent": "优质内容",
        "good": "良好内容",
        "fair": "较差内容",
        "poor": "极差内容",
        # "duplicate": "内容重复URL",  # 移除，使用专用页面
        # "implicit": "暗示性语言URL"  # 移除，使用专用页面
    }
    
    # 生成各类别页面 - 使用改进版的页面生成函数
    for category, filter_func in filter_funcs.items():
        logger.info(f"正在生成{page_titles[category]}页面...")
        generate_improved_category_page(merged_data, report_dir, category, page_titles[category], filter_func)
        
        # 生成对应的CSV导出
        logger.info(f"正在生成{page_titles[category]}的CSV导出...")
        generate_csv_export(merged_data, report_dir, category, filter_func)
    
    # 生成内容重复和暗示性语言URL的CSV导出
    logger.info("正在生成内容重复URL的CSV导出...")
    generate_csv_export(merged_data, report_dir, "duplicate", lambda data, threshold: data["duplicate_rate"] >= threshold)
    
    logger.info("正在生成暗示性语言URL的CSV导出...")
    generate_csv_export(merged_data, report_dir, "implicit", lambda data, threshold: data["has_implicit"])
    
    # 单独生成双重问题URL的CSV导出
    logger.info("正在生成双重问题URL的CSV导出...")
    generate_csv_export(merged_data, report_dir, "both_issues", lambda data, threshold: data["duplicate_rate"] >= threshold and data["has_implicit"])
    
    # 保存合并数据的JSON文件以便后续分析
    json_path = os.path.join(report_dir, "merged_data.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    # 生成低质量目录页面（强制调用）
    directory_stats = {}
    for url, data in merged_data["urls"].items():
        directory = data.get("directory", "未分类")
        if directory not in directory_stats:
            directory_stats[directory] = {"total": 0, "excellent": 0, "good": 0, "fair": 0, "poor": 0, "high_duplicate": 0, "has_implicit": 0, "both_issues": 0, "avg_duplicate_rate": 0, "avg_implicit_score": 0, "urls": []}
        directory_stats[directory]["urls"].append(url)
        directory_stats[directory]["total"] += 1
        quality_level = data.get("quality_level", "")
        if quality_level == "优":
            directory_stats[directory]["excellent"] += 1
        elif quality_level == "良":
            directory_stats[directory]["good"] += 1
        elif quality_level == "差":
            directory_stats[directory]["fair"] += 1
        elif quality_level == "极差":
            directory_stats[directory]["poor"] += 1
        duplicate_threshold = merged_data.get("config", {}).get("duplicate_threshold", 15.0)
        if data.get("duplicate_rate", 0) >= duplicate_threshold:
            directory_stats[directory]["high_duplicate"] += 1
        if data.get("has_implicit", False):
            directory_stats[directory]["has_implicit"] += 1
        if data.get("duplicate_rate", 0) >= duplicate_threshold and data.get("has_implicit", False):
            directory_stats[directory]["both_issues"] += 1
        directory_stats[directory]["avg_duplicate_rate"] += data.get("duplicate_rate", 0)
        directory_stats[directory]["avg_implicit_score"] += data.get("implicit_score", 0)
    for directory in directory_stats:
        total = directory_stats[directory]["total"]
        if total > 0:
            directory_stats[directory]["avg_duplicate_rate"] = round(directory_stats[directory]["avg_duplicate_rate"] / total, 2)
            directory_stats[directory]["avg_implicit_score"] = round(directory_stats[directory]["avg_implicit_score"] / total, 2)
    generate_low_quality_directories_page(directory_stats, merged_data, report_dir)

    logger.info(f"综合报告已保存到: {report_dir}")
    logger.info(f"索引页面: {index_path}")
    return report_dir

def find_latest_file(directory, prefix, suffix=None):
    """查找指定目录下最新的文件或目录"""
    matching_items = []
    
    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            # 检查前缀和后缀匹配
            if item.startswith(prefix) and (suffix is None or item.endswith(suffix)):
                matching_items.append(item_path)
        
        if not matching_items:
            return None
        
        # 按修改时间排序，最新的在前
        matching_items.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return matching_items[0]
    except Exception as e:
        logger.error(f"查找文件失败: {str(e)}")
        return None

def find_seo_json():
    """自动查找最新的SEO分析JSON文件"""
    # 查找最新的analysis_output目录
    latest_analysis_dir = find_latest_file(SEO_DIR, "analysis_output_")
    if not latest_analysis_dir:
        logger.error(f"未找到SEO分析目录，请检查: {SEO_DIR}")
        return None
    
    # 获取该目录下的duplicate_analysis.json文件
    json_path = os.path.join(latest_analysis_dir, "duplicate_analysis.json")
    if os.path.exists(json_path):
        return json_path
    
    logger.error(f"在目录 {latest_analysis_dir} 中未找到duplicate_analysis.json文件")
    return None

def find_quality_csv():
    """自动查找文章质量检测CSV文件"""
    # 首先尝试查找带scores的版本
    csv_paths = [
        os.path.join(QUALITY_DIR, "output_final_with_scores.csv"),
        os.path.join(QUALITY_DIR, "output_with_scores.csv"),
        os.path.join(QUALITY_DIR, "output_final_with_scores_processed.csv")
    ]
    
    # 查找最新的可用文件
    latest_csv = None
    latest_time = 0
    
    for csv_path in csv_paths:
        if os.path.exists(csv_path):
            file_time = os.path.getmtime(csv_path)
            if file_time > latest_time:
                latest_time = file_time
                latest_csv = csv_path
    
    if latest_csv:
        return latest_csv
    
    # 如果没有找到预设文件名，则查找任何*with_scores*.csv文件
    any_scores_csv = find_latest_file(QUALITY_DIR, "", "_with_scores")
    if any_scores_csv:
        return any_scores_csv
    
    logger.error(f"未找到文章质量检测CSV文件，请检查: {QUALITY_DIR}")
    return None

def find_previous_report():
    """查找上一个报告的数据"""
    if not os.path.exists(REPORT_DIR):
        return None
    
    # 查找所有comprehensive_report目录
    report_dirs = []
    for item in os.listdir(REPORT_DIR):
        item_path = os.path.join(REPORT_DIR, item)
        if os.path.isdir(item_path) and item.startswith("comprehensive_report_"):
            # 提取时间戳
            timestamp_str = item.replace("comprehensive_report_", "")
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                report_dirs.append((item_path, timestamp))
            except ValueError:
                continue
    
    if len(report_dirs) < 2:
        return None
    
    # 按时间排序，获取第二新的报告（上一个报告）
    report_dirs.sort(key=lambda x: x[1], reverse=True)
    previous_report_dir = report_dirs[1][0]
    
    # 尝试读取上一个报告的merged_data.json
    merged_data_path = os.path.join(previous_report_dir, "merged_data.json")
    if os.path.exists(merged_data_path):
        try:
            with open(merged_data_path, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)
            logger.info(f"找到上一个报告数据: {previous_report_dir}")
            return previous_data
        except Exception as e:
            logger.warning(f"读取上一个报告数据失败: {e}")
    
    return None

def calculate_comparison_stats(current_data, previous_data):
    """计算当前报告与上一个报告的对比统计"""
    if not previous_data:
        return None
    
    current_stats = current_data["stats"]
    previous_stats = previous_data["stats"]
    
    # 计算当前报告的平均指标
    current_urls = current_data["urls"]
    current_total = len(current_urls)
    current_avg_duplicate = sum(url_data["duplicate_rate"] for url_data in current_urls.values()) / current_total if current_total > 0 else 0
    current_avg_seo = sum(url_data["raw_seo_score"] for url_data in current_urls.values()) / current_total if current_total > 0 else 0
    
    # 计算上一个报告的平均指标
    previous_urls = previous_data["urls"]
    previous_total = len(previous_urls)
    previous_avg_duplicate = sum(url_data["duplicate_rate"] for url_data in previous_urls.values()) / previous_total if previous_total > 0 else 0
    previous_avg_seo = sum(url_data["raw_seo_score"] for url_data in previous_urls.values()) / previous_total if previous_total > 0 else 0
    
    # 计算问题URL总数（避免重复计算双重问题URL）
    current_problem_urls = current_stats["high_duplicate"] + current_stats["has_implicit"] - current_stats["both_issues"]
    previous_problem_urls = previous_stats["high_duplicate"] + previous_stats["has_implicit"] - previous_stats["both_issues"]
    
    # 计算变化
    comparison = {
        "total_urls": {
            "current": current_total,
            "previous": previous_total,
            "change": current_total - previous_total,
            "change_percent": ((current_total - previous_total) / previous_total * 100) if previous_total > 0 else 0
        },
        "avg_seo_score": {
            "current": round(current_avg_seo, 2),
            "previous": round(previous_avg_seo, 2),
            "change": round(current_avg_seo - previous_avg_seo, 2),
            "change_percent": ((current_avg_seo - previous_avg_seo) / previous_avg_seo * 100) if previous_avg_seo > 0 else 0
        },
        "avg_duplicate_rate": {
            "current": round(current_avg_duplicate, 2),
            "previous": round(previous_avg_duplicate, 2),
            "change": round(current_avg_duplicate - previous_avg_duplicate, 2),
            "change_percent": ((current_avg_duplicate - previous_avg_duplicate) / previous_avg_duplicate * 100) if previous_avg_duplicate > 0 else 0
        },
        "problem_urls": {
            "current": current_problem_urls,
            "previous": previous_problem_urls,
            "change": current_problem_urls - previous_problem_urls,
            "change_percent": ((current_problem_urls - previous_problem_urls) / previous_problem_urls * 100) if previous_problem_urls > 0 else 0
        },
        "quality_distribution": {
            "current": current_stats["quality_stats"],
            "previous": previous_stats["quality_stats"],
            "changes": {}
        }
    }
    
    # 计算质量分布变化
    for quality in ["excellent", "good", "fair", "poor"]:
        current_count = current_stats["quality_stats"][quality]
        previous_count = previous_stats["quality_stats"][quality]
        comparison["quality_distribution"]["changes"][quality] = {
            "change": current_count - previous_count,
            "change_percent": ((current_count - previous_count) / previous_count * 100) if previous_count > 0 else 0
        }
    
    return comparison

def generate_index_page(merged_data, report_dir):
    """生成索引页面"""
    quality_stats = merged_data["stats"]["quality_stats"]
    total_urls = merged_data["stats"]["total_urls"]
    
    excellent_percent = quality_stats["excellent"] / total_urls * 100 if total_urls > 0 else 0
    good_percent = quality_stats["good"] / total_urls * 100 if total_urls > 0 else 0
    fair_percent = quality_stats["fair"] / total_urls * 100 if total_urls > 0 else 0
    poor_percent = quality_stats["poor"] / total_urls * 100 if total_urls > 0 else 0
    
    # 获取与上一个报告的对比数据
    previous_data = find_previous_report()
    comparison = calculate_comparison_stats(merged_data, previous_data)
    
    html_content = []
    html_content.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量综合报告 - 索引</title>
    <style>
        :root {{
            --primary-color: #3e8ed0;
            --primary-dark: #2c6aa0;
            --secondary-color: #6c757d;
            --success-color: #28a745;
            --warning-color: #fd7e14;
            --danger-color: #dc3545;
            --info-color: #17a2b8;
            --light-color: #f8f9fa;
            --dark-color: #222f3e;
            --box-shadow: 0 4px 25px 0 rgba(0, 0, 0, 0.1);
            --transition: all 0.3s ease;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background-color: #f7f9fc;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .dashboard-header {{
            position: relative;
            background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
            color: white;
            padding: 30px 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: var(--box-shadow);
            overflow: hidden;
        }}
        
        .dashboard-header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"><path fill="rgba(255, 255, 255, 0.05)" fill-opacity="1" d="M0,192L48,197.3C96,203,192,213,288,229.3C384,245,480,267,576,250.7C672,235,768,181,864,181.3C960,181,1056,235,1152,234.7C1248,235,1344,181,1392,154.7L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path></svg>');
            background-size: cover;
            background-position: center;
            opacity: 0.2;
        }}
        
        .dashboard-header h1 {{
            font-size: 2.2em;
            margin: 0;
            position: relative;
        }}
        
        .dashboard-header p {{
            opacity: 0.8;
            margin-top: 10px;
            position: relative;
        }}
        
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background-color: white;
            border-radius: 15px;
            box-shadow: var(--box-shadow);
            padding: 20px;
            transition: var(--transition);
            position: relative;
            overflow: hidden;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 30px 0 rgba(0, 0, 0, 0.12);
        }}
        
        .stat-card h3 {{
            font-size: 1.1em;
            margin-bottom: 15px;
            color: var(--secondary-color);
            display: flex;
            align-items: center;
        }}
        
        .stat-card .icon {{
            margin-right: 10px;
            height: 28px;
            width: 28px;
            line-height: 28px;
            text-align: center;
            border-radius: 50%;
            background-color: rgba(74, 108, 247, 0.1);
            color: var(--primary-color);
            display: inline-flex;
            justify-content: center;
            align-items: center;
        }}
        
        .stat-card.success .icon {{
            background-color: rgba(40, 199, 111, 0.1);
            color: var(--success-color);
        }}
        
        .stat-card.warning .icon {{
            background-color: rgba(243, 156, 18, 0.1);
            color: var(--warning-color);
        }}
        
        .stat-card.danger .icon {{
            background-color: rgba(234, 84, 85, 0.1);
            color: var(--danger-color);
        }}
        
        .stat-card .number {{
            font-size: 2.5em;
            font-weight: 700;
            margin: 10px 0;
            line-height: 1;
            color: var(--dark-color);
        }}
        
        .stat-card.success .number {{
            color: var(--success-color);
        }}
        
        .stat-card.warning .number {{
            color: var(--warning-color);
        }}
        
        .stat-card.danger .number {{
            color: var(--danger-color);
        }}
        
        .stat-card .percent {{
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.85em;
            font-weight: 600;
            border-radius: 20px;
            background-color: rgba(40, 199, 111, 0.1);
            color: var(--success-color);
        }}
        
        .stat-card.warning .percent {{
            background-color: rgba(243, 156, 18, 0.1);
            color: var(--warning-color);
        }}
        
        .stat-card.danger .percent {{
            background-color: rgba(234, 84, 85, 0.1);
            color: var(--danger-color);
        }}
        
        .section {{
            background-color: white;
            border-radius: 15px;
            box-shadow: var(--box-shadow);
            padding: 25px;
            margin-bottom: 30px;
        }}
        
        .section-title {{
            position: relative;
            margin-bottom: 20px;
            padding-bottom: 15px;
            font-size: 1.5em;
            color: var(--dark-color);
        }}
        
        .section-title::after {{
            content: '';
            position: absolute;
            left: 0;
            bottom: 0;
            height: 3px;
            width: 50px;
            background: linear-gradient(90deg, var(--primary-color), var(--primary-dark));
            border-radius: 10px;
        }}
        
        .chart-wrapper {{
            margin: 20px auto;
            max-width: 400px;
            height: 300px;
            position: relative;
        }}
        
        .card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .nav-card {{
            background-color: white;
            border-radius: 15px;
            box-shadow: var(--box-shadow);
            overflow: hidden;
            transition: var(--transition);
            position: relative;
        }}
        
        .nav-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 30px 0 rgba(0, 0, 0, 0.12);
        }}
        
        .nav-card-header {{
            padding: 20px;
            background: linear-gradient(to right, rgba(74, 108, 247, 0.1), rgba(74, 108, 247, 0.05));
            border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        }}
        
        .nav-card-header h3 {{
            margin: 0;
            color: var(--primary-color);
            font-size: 1.3em;
        }}
        
        .nav-card-excellent .nav-card-header {{
            background: linear-gradient(to right, rgba(40, 199, 111, 0.1), rgba(40, 199, 111, 0.05));
        }}
        
        .nav-card-excellent .nav-card-header h3 {{
            color: var(--success-color);
        }}
        
        .nav-card-good .nav-card-header {{
            background: linear-gradient(to right, rgba(74, 108, 247, 0.1), rgba(74, 108, 247, 0.05));
        }}
        
        .nav-card-good .nav-card-header h3 {{
            color: var(--primary-color);
        }}
        
        .nav-card-fair .nav-card-header {{
            background: linear-gradient(to right, rgba(243, 156, 18, 0.1), rgba(243, 156, 18, 0.05));
        }}
        
        .nav-card-fair .nav-card-header h3 {{
            color: var(--warning-color);
        }}
        
        .nav-card-poor .nav-card-header {{
            background: linear-gradient(to right, rgba(234, 84, 85, 0.1), rgba(234, 84, 85, 0.05));
        }}
        
        .nav-card-poor .nav-card-header h3 {{
            color: var(--danger-color);
        }}
        
        .nav-card-duplicate .nav-card-header {{
            background: linear-gradient(to right, rgba(0, 207, 232, 0.1), rgba(0, 207, 232, 0.05));
        }}
        
        .nav-card-duplicate .nav-card-header h3 {{
            color: var(--info-color);
        }}
        
        .nav-card-implicit .nav-card-header {{
            background: linear-gradient(to right, rgba(108, 117, 125, 0.1), rgba(108, 117, 125, 0.05));
        }}
        
        .nav-card-implicit .nav-card-header h3 {{
            color: var(--secondary-color);
        }}
        
        .nav-card-body {{
            padding: 20px;
        }}
        
        .nav-card-stats {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        
        .nav-card-stat-item {{
            text-align: center;
        }}
        
        .nav-card-stat-number {{
            font-size: 1.8em;
            font-weight: 700;
            display: block;
            color: var(--dark-color);
            line-height: 1.2;
        }}
        
        .nav-card-stat-label {{
            font-size: 0.85em;
            color: var(--secondary-color);
        }}
        
        .nav-card-btn {{
            display: block;
            text-align: center;
            padding: 12px 0;
            background-color: var(--primary-color);
            color: white;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            transition: var(--transition);
        }}
        
        .nav-card-btn:hover {{
            background-color: var(--primary-dark);
        }}
        
        .nav-card-excellent .nav-card-btn {{
            background-color: var(--success-color);
        }}
        
        .nav-card-excellent .nav-card-btn:hover {{
            background-color: #20a35d;
        }}
        
        .nav-card-good .nav-card-btn {{
            background-color: var(--primary-color);
        }}
        
        .nav-card-good .nav-card-btn:hover {{
            background-color: var(--primary-dark);
        }}
        
        .nav-card-fair .nav-card-btn {{
            background-color: var(--warning-color);
        }}
        
        .nav-card-fair .nav-card-btn:hover {{
            background-color: #d68910;
        }}
        
        .nav-card-poor .nav-card-btn {{
            background-color: var(--danger-color);
        }}
        
        .nav-card-poor .nav-card-btn:hover {{
            background-color: #d63030;
        }}
        
        .nav-card-duplicate .nav-card-btn {{
            background-color: var(--info-color);
        }}
        
        .nav-card-duplicate .nav-card-btn:hover {{
            background-color: #00a5bc;
        }}
        
        .nav-card-implicit .nav-card-btn {{
            background-color: var(--secondary-color);
        }}
        
        .nav-card-implicit .nav-card-btn:hover {{
            background-color: #5a6268;
        }}
        
        footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px 0;
            color: var(--secondary-color);
            font-size: 0.9em;
            border-top: 1px solid rgba(0, 0, 0, 0.05);
        }}
        
        /* 响应式表格样式 */
        @media screen and (max-width: 1024px) {{
            table {{
                display: block;
                overflow-x: auto;
                white-space: nowrap;
            }}
            th, td {{
                min-width: 100px;
            }}
            th:last-child, td:last-child {{
                min-width: 80px;
                max-width: 100px;
            }}
            .detail-content {{
                white-space: normal;
                min-width: 300px;
            }}
        }}
        
        .comparison-section {{
            background: rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .comparison-title {{
            font-size: 1.2em;
            margin-bottom: 15px;
            color: white;
            opacity: 0.9;
            display: flex;
            align-items: center;
        }}
        
        .comparison-title .icon {{
            margin-right: 8px;
            font-size: 1.1em;
        }}
        
        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        
        .comparison-item {{
            text-align: center;
        }}
        
        .comparison-label {{
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }}
        
        .comparison-value {{
            font-size: 1.5em;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .comparison-change {{
            font-size: 0.85em;
            padding: 3px 8px;
            border-radius: 12px;
            font-weight: 600;
            display: inline-block;
        }}
        
        .comparison-change.positive {{
            background-color: rgba(40, 199, 111, 0.2);
            color: #28c76f;
        }}
        
        .comparison-change.negative {{
            background-color: rgba(234, 84, 85, 0.2);
            color: #ea5455;
        }}
        
        .comparison-change.neutral {{
            background-color: rgba(108, 117, 125, 0.2);
            color: #6c757d;
        }}
        
        @media screen and (max-width: 768px) {{
            .navigation {{
                flex-direction: column;
                gap: 10px;
            }}
            .navigation a {{
                width: 100%;
                text-align: center;
            }}
            td {{
                vertical-align: top;
            }}
            .detail-content {{
                max-width: 300px;
                overflow-x: hidden;
            }}
            .implicit-result, .duplicate-detail {{
                max-width: 280px;
            }}
            .comparison-grid {{
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>SEO内容质量综合报告</h1>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 分析报告数量: {total_urls}个</p>
        {f'''
        <div class="comparison-section">
            <div class="comparison-title">
                <span class="icon">📊</span>
                整体统计概览
            </div>
            <div class="comparison-grid">
                <div class="comparison-item">
                    <div class="comparison-label">累计分析URL数量</div>
                    <div class="comparison-value">{comparison["total_urls"]["current"]:,}</div>
                    <div class="comparison-change {'positive' if comparison["total_urls"]["change"] > 0 else 'negative' if comparison["total_urls"]["change"] < 0 else 'neutral'}">
                        {'+' if comparison["total_urls"]["change"] > 0 else ''}{comparison["total_urls"]["change"]}
                    </div>
                </div>
                
                <div class="comparison-item">
                    <div class="comparison-label">平均SEO评分</div>
                    <div class="comparison-value">{comparison["avg_seo_score"]["current"]}</div>
                    <div class="comparison-change {'positive' if comparison["avg_seo_score"]["change"] > 0 else 'negative' if comparison["avg_seo_score"]["change"] < 0 else 'neutral'}">
                        {'+' if comparison["avg_seo_score"]["change"] > 0 else ''}{comparison["avg_seo_score"]["change"]}
                    </div>
                </div>
                
                <div class="comparison-item">
                    <div class="comparison-label">平均重复率</div>
                    <div class="comparison-value">{comparison["avg_duplicate_rate"]["current"]}%</div>
                    <div class="comparison-change {'negative' if comparison["avg_duplicate_rate"]["change"] > 0 else 'positive' if comparison["avg_duplicate_rate"]["change"] < 0 else 'neutral'}">
                        {'+' if comparison["avg_duplicate_rate"]["change"] > 0 else ''}{comparison["avg_duplicate_rate"]["change"]}%
                    </div>
                </div>
                
                <div class="comparison-item">
                    <div class="comparison-label">问题URL总数</div>
                    <div class="comparison-value">{comparison["problem_urls"]["current"]}</div>
                    <div class="comparison-change {'negative' if comparison["problem_urls"]["change"] > 0 else 'positive' if comparison["problem_urls"]["change"] < 0 else 'neutral'}">
                        {'+' if comparison["problem_urls"]["change"] > 0 else ''}{comparison["problem_urls"]["change"]}
                    </div>
                </div>
            </div>
        </div>
        ''' if comparison else ''}
    </div>
    
    <div class="container">
        <div class="section">
            <h2 class="section-title">统计摘要</h2>
            
            <div class="stat-grid">
                <div class="stat-card success">
                    <h3><span class="icon">✓</span>优质内容</h3>
                    <div class="number">{quality_stats["excellent"]}</div>
                    <div class="percent">占比 {excellent_percent:.1f}%</div>
                </div>
                
                <div class="stat-card">
                    <h3><span class="icon">●</span>良好内容</h3>
                    <div class="number">{quality_stats["good"]}</div>
                    <div class="percent">占比 {good_percent:.1f}%</div>
                </div>
                
                <div class="stat-card warning">
                    <h3><span class="icon">!</span>较差内容</h3>
                    <div class="number">{quality_stats["fair"]}</div>
                    <div class="percent">占比 {fair_percent:.1f}%</div>
                </div>
                
                <div class="stat-card danger">
                    <h3><span class="icon">×</span>极差内容</h3>
                    <div class="number">{quality_stats["poor"]}</div>
                    <div class="percent">占比 {poor_percent:.1f}%</div>
                </div>
            
                <div class="stat-card">
                    <h3><span class="icon">∑</span>总URL数</h3>
                    <div class="number">{merged_data["stats"]["total_urls"]}</div>
                </div>
                
                <div class="stat-card warning">
                    <h3><span class="icon">♺</span>内容重复URL</h3>
                    <div class="number">{merged_data["stats"]["high_duplicate"]}</div>
                    <div class="percent">占比 {merged_data["stats"]["high_duplicate"] / merged_data["stats"]["total_urls"] * 100 if merged_data["stats"]["total_urls"] > 0 else 0:.1f}%</div>
                </div>
                
                <div class="stat-card warning">
                    <h3><span class="icon">♯</span>暗示性语言URL</h3>
                    <div class="number">{merged_data["stats"]["has_implicit"]}</div>
                    <div class="percent">占比 {merged_data["stats"]["has_implicit"] / merged_data["stats"]["total_urls"] * 100 if merged_data["stats"]["total_urls"] > 0 else 0:.1f}%</div>
                </div>
                
                <div class="stat-card danger">
                    <h3><span class="icon">⚠</span>双重问题URL</h3>
                    <div class="number">{merged_data["stats"]["both_issues"]}</div>
                    <div class="percent">占比 {merged_data["stats"]["both_issues"] / merged_data["stats"]["total_urls"] * 100 if merged_data["stats"]["total_urls"] > 0 else 0:.1f}%</div>
                </div>
            </div>
            
            <div class="chart-wrapper">
                <canvas id="qualityPieChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">内容质量报告导航</h2>
            
            <div class="card-grid">
                <div class="nav-card">
                    <div class="nav-card-header">
                        <h3>全部URL</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["total_urls"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="all_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">问题内容分析</h2>
            
            <div class="card-grid">
                <div class="nav-card nav-card-duplicate">
                    <div class="nav-card-header">
                        <h3>内容重复URL</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["high_duplicate"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["high_duplicate"] / merged_data["stats"]["total_urls"] * 100 if merged_data["stats"]["total_urls"] > 0 else 0:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="duplicate_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
                
                <div class="nav-card nav-card-implicit">
                    <div class="nav-card-header">
                        <h3>暗示性语言URL</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["has_implicit"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["has_implicit"] / merged_data["stats"]["total_urls"] * 100 if merged_data["stats"]["total_urls"] > 0 else 0:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="implicit_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
                
                <div class="nav-card nav-card-both">
                    <div class="nav-card-header">
                        <h3>双重问题URL</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["both_issues"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{merged_data["stats"]["both_issues"] / merged_data["stats"]["total_urls"] * 100 if merged_data["stats"]["total_urls"] > 0 else 0:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="all_urls.html#both_issues" class="nav-card-btn" onclick="return filterBothIssues()">查看详情</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">内容质量分级</h2>
            
            <div class="card-grid">
                <div class="nav-card nav-card-excellent">
                    <div class="nav-card-header">
                        <h3>优质内容</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{quality_stats["excellent"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{excellent_percent:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="excellent_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
                
                <div class="nav-card nav-card-good">
                    <div class="nav-card-header">
                        <h3>良好内容</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{quality_stats["good"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{good_percent:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="good_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
                
                <div class="nav-card nav-card-fair">
                    <div class="nav-card-header">
                        <h3>较差内容</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{quality_stats["fair"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{fair_percent:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="fair_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
                
                <div class="nav-card nav-card-poor">
                    <div class="nav-card-header">
                        <h3>极差内容</h3>
                    </div>
                    <div class="nav-card-body">
                        <div class="nav-card-stats">
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{quality_stats["poor"]}</span>
                                <span class="nav-card-stat-label">条URL</span>
                            </div>
                            <div class="nav-card-stat-item">
                                <span class="nav-card-stat-number">{poor_percent:.1f}%</span>
                                <span class="nav-card-stat-label">占比</span>
                            </div>
                        </div>
                        <div class="nav-card-actions">
                            <a href="poor_urls.html" class="nav-card-btn">查看详情</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">高级分析</h2>
            
            <div class="card-grid">
                <div class="nav-card nav-card-directory-stats">
                    <div class="nav-card-header">
                        <h3>目录统计分析</h3>
                    </div>
                    <div class="nav-card-body">
                        <p class="nav-card-description">按目录查看内容质量、重复度和暗示性语言统计，了解不同目录的SEO表现情况。</p>
                        <div class="nav-card-actions">
                            <a href="directory_stats.html" class="nav-card-btn">查看分析</a>
                        </div>
                    </div>
                </div>
                <div class="nav-card nav-card-low-quality">
                    <div class="nav-card-header">
                        <h3>质量分布低的目录</h3>
                    </div>
                    <div class="nav-card-body">
                        <p class="nav-card-description">快速定位内容质量分布低于85%的目录，查看主要问题与优化建议。</p>
                        <div class="nav-card-actions">
                            <a href="low_quality_directories.html" class="nav-card-btn">查看目录</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <footer>
        <p>SEO内容质量综合分析工具 | 报告生成于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // 创建质量分布饼图
        document.addEventListener('DOMContentLoaded', function() {{
            const ctx = document.getElementById('qualityPieChart').getContext('2d');
            const qualityPieChart = new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: ['优质内容', '良好内容', '较差内容', '极差内容'],
                    datasets: [{{
                        data: [
                            {quality_stats["excellent"]}, 
                            {quality_stats["good"]}, 
                            {quality_stats["fair"]}, 
                            {quality_stats["poor"]}
                        ],
                        backgroundColor: [
                            '#28c76f',  // 优 - 绿色
                            '#4a6cf7',  // 良 - 蓝色
                            '#f39c12',  // 差 - 橙色
                            '#ea5455'   // 极差 - 红色
                        ],
                        borderWidth: 0,
                        hoverOffset: 4
                    }}]
                }},
                options: {{
                    cutout: '65%',
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                padding: 20,
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }}
                        }},
                        title: {{
                            display: true,
                            text: '内容质量分布',
                            font: {{
                                size: 16
                            }},
                            padding: {{
                                bottom: 10
                            }}
                        }}
                    }}
                }}
            }});
        }});
        
        // 跳转到全部URL页面并筛选双重问题
        function filterBothIssues() {{
            // 设置cookie标记，用于全部URL页面读取
            document.cookie = "filter_both_issues=true; path=/";
            return true;
        }}
    </script>
</body>
</html>
    """)
    
    # 写入HTML文件
    html_path = os.path.join(report_dir, "index.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_content))
    
    logger.info(f"索引页面已保存到: {html_path}")
    return html_path

def generate_category_page(merged_data, report_dir, category, page_title, filter_func):
    """生成特定类别的URL列表页面"""
    # 准备HTML内容
    html_content = []
    html_content.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量综合报告 - {page_title}</title>
    <style>
        body {{
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f8f9fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 30px;
            border-radius: 5px;
        }}
        h1, h2, h3 {{
            margin-top: 0;
        }}
        .section {{
            margin-bottom: 30px;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
            position: sticky;
            top: 0;
            cursor: pointer;
        }}
        th:hover {{
            background-color: #2c3e50;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .high-duplicate {{
            background-color: rgba(231, 76, 60, 0.1);
        }}
        .has-implicit {{
            background-color: rgba(46, 204, 113, 0.1);
        }}
        .both-issues {{
            background-color: rgba(243, 156, 18, 0.1);
        }}
        .url-cell {{
            max-width: 300px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 7px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 5px;
            color: white;
        }}
        .badge.duplicate {{
            background-color: #e74c3c;
        }}
        .badge.implicit {{
            background-color: #2ecc71;
        }}
        .badge.both {{
            background-color: #e67e22;
        }}
        .quality-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            color: white;
        }}
        .quality-excellent {{
            background-color: #2ecc71;
        }}
        .quality-good {{
            background-color: #3498db;
        }}
        .quality-fair {{
            background-color: #f39c12;
        }}
        .quality-poor {{
            background-color: #e74c3c;
        }}
        .duplicate-rate {{
            font-weight: bold;
            color: #e74c3c;
        }}
        .implicit-score {{
            font-weight: bold;
            color: #2ecc71;
        }}
        .search-container {{
            margin-bottom: 20px;
        }}
        #searchInput {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }}
        .collapsible {{
            cursor: pointer;
            color: #3498db;
            text-decoration: underline;
        }}
        .detail-content {{
            display: none;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
            margin-top: 10px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        .detail-section {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 4px;
        }}
        .duplicate-section {{
            background-color: rgba(231, 76, 60, 0.1);
            border-left: 3px solid #e74c3c;
        }}
        .implicit-section {{
            background-color: rgba(46, 204, 113, 0.1);
            border-left: 3px solid #2ecc71;
        }}
        .duplicate-detail, .implicit-result {{
            max-height: 250px;
            overflow-y: auto;
            padding: 10px;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 14px;
            line-height: 1.5;
        }}
        .implicit-result {{
            white-space: pre-wrap;
        }}
        .pagination {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
            flex-wrap: wrap;
            gap: 5px;
        }}
        .pagination a {{
            color: black;
            padding: 8px 14px;
            text-decoration: none;
            border: 1px solid #ddd;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .pagination a.active {{
            background-color: #3498db;
            color: white;
            border-color: #3498db;
        }}
        .pagination a:hover:not(.active) {{
            background-color: #f1f1f1;
        }}
        .pagination-info {{
            text-align: center;
            margin-top: 10px;
            color: #7f8c8d;
        }}
        .navigation {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        .navigation a {{
            display: inline-block;
            padding: 10px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .navigation a:hover {{
            background-color: #2980b9;
        }}
        footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .loader {{
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
            display: none;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* 响应式表格样式 */
        @media screen and (max-width: 1024px) {{
            table {{
                display: block;
                overflow-x: auto;
            }}
            .url-cell {{
                max-width: 200px;
            }}
            th, td {{
                min-width: 80px;
                vertical-align: top;
                word-break: break-word;
            }}
            th:first-child, td:first-child {{
                min-width: 200px;
            }}
            th:last-child, td:last-child {{
                min-width: 80px;
            }}
            .detail-content {{
                white-space: normal;
                min-width: 250px;
                max-width: 300px;
            }}
        }}
        
        @media screen and (max-width: 768px) {{
            .navigation {{
                flex-direction: column;
                gap: 10px;
            }}
            .navigation a {{
                width: 100%;
                text-align: center;
            }}
            td {{
                vertical-align: top;
            }}
            .detail-content {{
                max-width: 300px;
                overflow-x: hidden;
            }}
            .implicit-result, .duplicate-detail {{
                max-width: 280px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>SEO内容质量综合报告 - {page_title}</h1>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </header>
    <div class="container">
        <div class="navigation">
            <a href="index.html">返回首页</a>
            <a href="{category}_urls_export.csv" class="export-btn" download>导出CSV</a>
        </div>
        
        <div class="section">
            <h2>{page_title}</h2>
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="搜索URL...">
            </div>
            
            <table id="urlTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">URL</th>
                        <th onclick="sortTable(1)">目录</th>
                        <th onclick="sortTable(2)">重复率</th>
                        <th onclick="sortTable(3)">暗示评分</th>
                        <th onclick="sortTable(4)">质量等级</th>
                        <th>问题标签</th>
                        <th>详情</th>
                    </tr>
                </thead>
                <tbody>
    """)
    
    # 筛选并添加符合条件的URL
    filtered_urls = {}
    duplicate_threshold = merged_data.get("config", {}).get("duplicate_threshold", 15.0)
    
    for url, data in merged_data["urls"].items():
        if filter_func(data, duplicate_threshold):
            filtered_urls[url] = data
    
    # 添加URL详细信息行
    for url, data in filtered_urls.items():
        # 确定行的CSS类
        row_class = ""
        badges = []
        
        is_duplicate = data["duplicate_rate"] >= duplicate_threshold
        has_implicit = data["has_implicit"]
        
        if is_duplicate and has_implicit:
            row_class = "both-issues"
            badges.append('<span class="badge both">双重问题</span>')
        elif is_duplicate:
            row_class = "high-duplicate"
            badges.append('<span class="badge duplicate">内容重复</span>')
        elif has_implicit:
            row_class = "has-implicit"
            badges.append('<span class="badge implicit">暗示性语言</span>')
        
        # 设置质量等级样式
        quality_level = data["quality_level"]
        quality_class = ""
        if quality_level == "优":
            quality_class = "quality-excellent"
        elif quality_level == "良":
            quality_class = "quality-good"
        elif quality_level == "差":
            quality_class = "quality-fair"
        else:  # 极差
            quality_class = "quality-poor"
        
        # 确保暗示性语言分析结果不为空，并处理HTML特殊字符
        implicit_result = "无分析结果"
        if data['implicit_result']:
            # 转义HTML特殊字符
            implicit_result = data['implicit_result'].replace('<', '&lt;').replace('>', '&gt;')
        
        html_content.append(f"""
                <tr class="{row_class}">
                    <td class="url-cell"><a href="{url}" target="_blank">{url}</a></td>
                    <td>{data['directory']}</td>
                    <td><span class="duplicate-rate">{data['duplicate_rate']:.2f}%</span></td>
                    <td><span class="implicit-score">{data['implicit_score']}</span></td>
                    <td><span class="quality-badge {quality_class}">{quality_level}</span></td>
                    <td>{"".join(badges)}</td>
                    <td>
                        <span class="collapsible" onclick="toggleDetails(this)">查看详情</span>
                        <div class="detail-content">
                            <p><strong>发布日期:</strong> {data['publish_date'] or '未知'}</p>
                            <p><strong>质量等级:</strong> <span class="quality-badge {quality_class}">{quality_level}</span></p>
                            <p><strong>段落总数:</strong> {data['total_paragraphs']}</p>
                            
                            <div class="detail-section duplicate-section">
                                <h4>内容重复分析</h4>
                                <p><strong>重复段落数:</strong> {data['duplicate_paragraphs']}</p>
                                <p><strong>重复率:</strong> {data['duplicate_rate']:.2f}%</p>
                                <p><strong>重复评分:</strong> {data['duplicate_score']:.2f}</p>
                                {f"<p><strong>重复段落详情:</strong></p><div class='duplicate-detail'>" + "<br>".join([f"<p>{i+1}. {para[:100] if isinstance(para, str) else str(para)[:100]}..." for i, para in enumerate(data['duplicate_details'][:5])]) + ("..." if len(data['duplicate_details']) > 5 else "") + "</div>" if data['duplicate_details'] else "<p>无详细重复段落信息</p>"}
                            </div>
                            
                            <div class="detail-section implicit-section">
                                <h4>暗示性语言分析</h4>
                                <p><strong>暗示性评分:</strong> {data['implicit_score']} (0-10，越高越严重)</p>
                                <p><strong>标准化暗示评分:</strong> {data['normalized_implicit_score']:.2f}</p>
                                <p><strong>暗示性语言分析结果:</strong></p>
                                <div class="implicit-result">{implicit_result}</div>
                            </div>
                        </div>
                    </td>
                </tr>
        """)
    
    # 收尾HTML内容
    html_content.append("""
                </tbody>
            </table>
            <div id="pagination" class="pagination"></div>
            <div id="pagination-info" class="pagination-info"></div>
            <div id="loader" class="loader"></div>
        </div>
        
        <footer>
            <p>报告生成于 """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """ | SEO内容质量综合分析工具</p>
        </footer>
    </div>
    
    <script>
        // 全局变量
        const ITEMS_PER_PAGE = 25;
        let currentPage = 1;
        
        // 表格排序功能
        function sortTable(n, direction = null) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                let switching = true;
                let dir = direction || "asc"; 
                let switchcount = 0;
                let rows, shouldSwitch, x, y, i;
                
                while (switching) {
                    switching = false;
                    rows = table.rows;
                    
                    for (i = 1; i < (rows.length - 1); i++) {
                        shouldSwitch = false;
                        x = rows[i].getElementsByTagName("TD")[n];
                        y = rows[i + 1].getElementsByTagName("TD")[n];
                        
                        // 根据列内容类型确定比较方式
                        let xContent, yContent;
                        if (n === 2) { // 重复率列
                            xContent = parseFloat(x.textContent.replace('%', ''));
                            yContent = parseFloat(y.textContent.replace('%', ''));
                        } else if (n === 3) { // 暗示评分列
                            xContent = parseFloat(x.textContent);
                            yContent = parseFloat(y.textContent);
                        } else if (n === 4) { // 质量等级列
                            const qualityMap = {'优': 4, '良': 3, '差': 2, '极差': 1};
                            xContent = qualityMap[x.textContent.trim()] || 0;
                            yContent = qualityMap[y.textContent.trim()] || 0;
                        } else { // 文本列
                            xContent = x.textContent.toLowerCase();
                            yContent = y.textContent.toLowerCase();
                        }
                        
                        if (dir == "asc") {
                            if (xContent > yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        } else if (dir == "desc") {
                            if (xContent < yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        }
                    }
                    
                    if (shouldSwitch) {
                        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                        switching = true;
                        switchcount++;
                    } else {
                        if (switchcount == 0 && dir == "asc" && direction === null) {
                            dir = "desc";
                            switching = true;
                        }
                    }
                }
                
                // 重置分页并显示第一页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 分页功能
        function showPage(page) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
                const totalRows = rows.length;
                const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
                
                if (page < 1) page = 1;
                if (page > totalPages) page = totalPages;
                
                currentPage = page;
                
                // 隐藏所有行
                rows.forEach(row => {
                    row.style.display = 'none';
                });
                
                // 显示当前页的行
                const startIndex = (page - 1) * ITEMS_PER_PAGE;
                const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalRows);
                
                for (let i = startIndex; i < endIndex; i++) {
                    if (rows[i]) {
                        rows[i].style.display = '';
                    }
                }
                
                // 更新分页信息
                updatePaginationControls(totalRows, page, totalPages);
                hideLoader();
            }, 10);
        }
        
        // 更新分页控件
        function updatePaginationControls(totalRows, currentPage, totalPages) {
            const paginationDiv = document.getElementById('pagination');
            const paginationInfo = document.getElementById('pagination-info');
            
            paginationDiv.innerHTML = '';
            
            // 如果只有一页则不显示分页
            if (totalPages <= 1) {
                paginationDiv.style.display = 'none';
                paginationInfo.textContent = `显示 ${totalRows} 条记录`;
                return;
            }
            
            paginationDiv.style.display = 'flex';
            
            // 添加"上一页"按钮
            const prevPageLink = document.createElement('a');
            prevPageLink.href = 'javascript:void(0)';
            prevPageLink.textContent = '上一页';
            if (currentPage === 1) {
                prevPageLink.style.opacity = '0.5';
                prevPageLink.style.pointerEvents = 'none';
            } else {
                prevPageLink.onclick = () => showPage(currentPage - 1);
            }
            paginationDiv.appendChild(prevPageLink);
            
            // 确定要显示的页码范围
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + 4);
            
            if (endPage - startPage < 4) {
                startPage = Math.max(1, endPage - 4);
            }
            
            // 添加第一页
            if (startPage > 1) {
                const firstPageLink = document.createElement('a');
                firstPageLink.href = 'javascript:void(0)';
                firstPageLink.textContent = '1';
                firstPageLink.onclick = () => showPage(1);
                paginationDiv.appendChild(firstPageLink);
                
                if (startPage > 2) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
            }
            
            // 添加页码按钮
            for (let i = startPage; i <= endPage; i++) {
                const pageLink = document.createElement('a');
                pageLink.href = 'javascript:void(0)';
                pageLink.textContent = i;
                if (i === currentPage) {
                    pageLink.className = 'active';
                } else {
                    pageLink.onclick = () => showPage(i);
                }
                paginationDiv.appendChild(pageLink);
            }
            
            // 添加最后一页
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
                
                const lastPageLink = document.createElement('a');
                lastPageLink.href = 'javascript:void(0)';
                lastPageLink.textContent = totalPages;
                lastPageLink.onclick = () => showPage(totalPages);
                paginationDiv.appendChild(lastPageLink);
            }
            
            // 添加"下一页"按钮
            const nextPageLink = document.createElement('a');
            nextPageLink.href = 'javascript:void(0)';
            nextPageLink.textContent = '下一页';
            if (currentPage === totalPages) {
                nextPageLink.style.opacity = '0.5';
                nextPageLink.style.pointerEvents = 'none';
            } else {
                nextPageLink.onclick = () => showPage(currentPage + 1);
            }
            paginationDiv.appendChild(nextPageLink);
            
            // 更新页码信息
            const startRecord = (currentPage - 1) * ITEMS_PER_PAGE + 1;
            const endRecord = Math.min(currentPage * ITEMS_PER_PAGE, totalRows);
            paginationInfo.textContent = `显示 ${startRecord}-${endRecord} 条，共 ${totalRows} 条记录`;
        }
        
        // 重置分页器并显示第一页
        function resetPagination() {
            const table = document.getElementById('urlTable');
            if (!table) return;
            
            const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
            const totalRows = rows.length;
            const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
            
            showPage(1);
        }
        
        // 显示加载中
        function showLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'block';
        }
        
        // 隐藏加载中
        function hideLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'none';
        }
        
        // 搜索筛选功能
        function filterTable() {
            showLoader();
            
            setTimeout(() => {
                const input = document.getElementById('searchInput');
                const filter = input.value.toLowerCase();
                const table = document.getElementById('urlTable');
                const rows = table.getElementsByTagName("tr");
                
                // 用于标记行是否显示
                for (let i = 1; i < rows.length; i++) {
                    const td = rows[i].getElementsByTagName("td")[0]; // URL列
                    if (td) {
                        const txtValue = td.textContent || td.innerText;
                        if (txtValue.toLowerCase().indexOf(filter) > -1) {
                            rows[i].classList.remove('filtered-out');
                        } else {
                            rows[i].classList.add('filtered-out');
                        }
                    }
                }
                
                // 重新计算和显示分页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 为搜索框绑定事件
        document.getElementById('searchInput').addEventListener('keyup', filterTable);
        
        // 切换详情显示
        function toggleDetails(element) {
            const detailContent = element.nextElementSibling;
            if (detailContent.style.display === "block") {
                detailContent.style.display = "none";
                element.textContent = "查看详情";
            } else {
                detailContent.style.display = "block";
                element.textContent = "隐藏详情";
            }
        }
        
        // 页面加载完成后，设置默认排序并初始化分页
        window.addEventListener('DOMContentLoaded', function() {
            // 检查是否需要筛选双重问题
            if (document.location.hash === '#both_issues' || getCookie('filter_both_issues') === 'true') {
                // 如果需要，则自动筛选双重问题
                document.getElementById('searchInput').value = '双重问题';
                filterTable();
                // 清除cookie
                document.cookie = "filter_both_issues=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            }
            
            // 根据类别设置默认排序
            const category = '{category}';
            if (category === 'excellent' || category === 'good' || category === 'fair' || category === 'poor') {
                // 质量等级页面按质量等级降序排序
                sortTable(4, 'desc');
            } else if (category === 'duplicate') {
                // 内容重复页面按重复率降序排序
                sortTable(2, 'desc');
            } else if (category === 'implicit') {
                // 暗示性语言页面按暗示评分降序排序
                sortTable(3, 'desc');
            } else {
                // 默认按质量等级降序排序
                sortTable(4, 'desc');
            }
        });
        
        // 获取cookie值的辅助函数
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return '';
        }
    </script>
</body>
</html>
    """)
    
    # 写入HTML文件
    html_path = os.path.join(report_dir, f"{category}_urls.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_content))
    
    logger.info(f"{page_title}页面已保存到: {html_path}")
    return html_path

def generate_csv_export(merged_data, report_dir, category, filter_func):
    """为特定类别生成CSV导出文件"""
    import csv
    
    # 筛选符合条件的URL
    duplicate_threshold = merged_data.get("config", {}).get("duplicate_threshold", 15.0)
    filtered_urls = {}
    
    for url, data in merged_data["urls"].items():
        if filter_func(data, duplicate_threshold):
            filtered_urls[url] = data
    
    # 为不同类别定义不同的CSV头和数据选择方式
    if category == "duplicate":
        headers = ["URL", "目录", "重复率", "重复段落数", "段落总数", "质量等级", "发布日期"]
        csv_path = os.path.join(report_dir, f"duplicate_urls_export.csv")
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for url, data in filtered_urls.items():
                row = [
                    url,
                    data['directory'],
                    f"{data['duplicate_rate']:.2f}%",
                    data['duplicate_paragraphs'],
                    data['total_paragraphs'],
                    data['quality_level'],
                    data['publish_date'] or '未知'
                ]
                writer.writerow(row)
                
    elif category == "implicit":
        headers = ["URL", "目录", "暗示评分", "标准化评分", "质量等级", "发布日期"]
        csv_path = os.path.join(report_dir, f"implicit_urls_export.csv")
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for url, data in filtered_urls.items():
                row = [
                    url,
                    data['directory'],
                    data['implicit_score'],
                    f"{data['normalized_implicit_score']:.2f}",
                    data['quality_level'],
                    data['publish_date'] or '未知'
                ]
                writer.writerow(row)
    
    elif category == "both_issues":
        headers = ["URL", "目录", "重复率", "暗示评分", "质量等级", "发布日期"]
        csv_path = os.path.join(report_dir, f"both_issues_export.csv")
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            # 筛选同时存在内容重复和暗示性语言问题的URL
            both_issues_urls = {}
            for url, data in merged_data["urls"].items():
                if data["duplicate_rate"] >= duplicate_threshold and data["has_implicit"]:
                    both_issues_urls[url] = data
            
            for url, data in both_issues_urls.items():
                row = [
                    url,
                    data['directory'],
                    f"{data['duplicate_rate']:.2f}%",
                    data['implicit_score'],
                    data['quality_level'],
                    data['publish_date'] or '未知'
                ]
                writer.writerow(row)
    
    else:
        # 其他类型的导出（包括all和quality类别）
        headers = ["URL", "目录", "质量等级", "重复率", "暗示评分", "段落总数", "重复段落数", "发布日期"]
        csv_path = os.path.join(report_dir, f"{category}_urls_export.csv")
        
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for url, data in filtered_urls.items():
                row = [
                    url,
                    data['directory'],
                    data['quality_level'],
                    f"{data['duplicate_rate']:.2f}%",
                    data['implicit_score'],
                    data['total_paragraphs'],
                    data['duplicate_paragraphs'],
                    data['publish_date'] or '未知'
                ]
                writer.writerow(row)
    
    logger.info(f"已生成{category}类别的CSV导出文件: {csv_path}")
    return csv_path

def generate_duplicate_page(merged_data, report_dir):
    """生成内容重复URL列表专用页面"""
    # 准备HTML内容
    html_content = []
    html_content.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量综合报告 - 内容重复URL</title>
    <style>
        body {{
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f8f9fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 30px;
            border-radius: 5px;
        }}
        h1, h2, h3 {{
            margin-top: 0;
        }}
        .section {{
            margin-bottom: 30px;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
            position: sticky;
            top: 0;
            cursor: pointer;
        }}
        th:hover {{
            background-color: #2c3e50;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .high-duplicate {{
            background-color: rgba(231, 76, 60, 0.1);
        }}
        .url-cell {{
            max-width: 300px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .duplicate-rate {{
            font-weight: bold;
            color: #e74c3c;
        }}
        .quality-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            color: white;
        }}
        .quality-excellent {{
            background-color: #2ecc71;
        }}
        .quality-good {{
            background-color: #3498db;
        }}
        .quality-fair {{
            background-color: #f39c12;
        }}
        .quality-poor {{
            background-color: #e74c3c;
        }}
        .search-container {{
            margin-bottom: 20px;
        }}
        #searchInput {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }}
        .collapsible {{
            cursor: pointer;
            color: #3498db;
            text-decoration: underline;
        }}
        .detail-content {{
            display: none;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
            margin-top: 10px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        .detail-section {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 4px;
            background-color: rgba(231, 76, 60, 0.1);
            border-left: 3px solid #e74c3c;
        }}
        .duplicate-detail {{
            max-height: 200px;
            overflow-y: auto;
            padding: 10px;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 14px;
            line-height: 1.5;
        }}
        .pagination {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
            flex-wrap: wrap;
            gap: 5px;
        }}
        .pagination a {{
            color: black;
            padding: 8px 14px;
            text-decoration: none;
            border: 1px solid #ddd;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .pagination a.active {{
            background-color: #3498db;
            color: white;
            border-color: #3498db;
        }}
        .pagination a:hover:not(.active) {{
            background-color: #f1f1f1;
        }}
        .pagination-info {{
            text-align: center;
            margin-top: 10px;
            color: #7f8c8d;
        }}
        .navigation {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        .navigation a {{
            display: inline-block;
            padding: 10px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .navigation a:hover {{
            background-color: #2980b9;
        }}
        footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .loader {{
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
            display: none;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* 响应式表格样式 */
        @media screen and (max-width: 1024px) {{
            table {{
                display: block;
                overflow-x: auto;
            }}
            .url-cell {{
                max-width: 200px;
            }}
            th, td {{
                min-width: 80px;
                vertical-align: top;
                word-break: break-word;
            }}
            th:first-child, td:first-child {{
                min-width: 200px;
            }}
            th:last-child, td:last-child {{
                min-width: 80px;
            }}
            .detail-content {{
                white-space: normal;
                min-width: 250px;
                max-width: 300px;
            }}
        }}
        
        @media screen and (max-width: 768px) {{
            .navigation {{
                flex-direction: column;
                gap: 10px;
            }}
            .navigation a {{
                width: 100%;
                text-align: center;
            }}
            td {{
                vertical-align: top;
            }}
            .detail-content {{
                max-width: 300px;
                overflow-x: hidden;
            }}
            .duplicate-detail {{
                max-width: 280px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>SEO内容质量综合报告 - 内容重复URL</h1>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </header>
    <div class="container">
        <div class="navigation">
            <a href="index.html">返回首页</a>
            <a href="duplicate_urls_export.csv" class="export-btn" download>导出CSV</a>
        </div>
        
        <div class="section">
            <h2>内容重复URL</h2>
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="搜索URL...">
            </div>
            
            <table id="urlTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">URL</th>
                        <th onclick="sortTable(1)">目录</th>
                        <th onclick="sortTable(2)">重复率</th>
                        <th onclick="sortTable(3)">重复段落/总段落</th>
                        <th onclick="sortTable(4)">质量等级</th>
                        <th>详情</th>
                    </tr>
                </thead>
                <tbody>
    """)
    
    # 筛选并添加内容重复的URL
    duplicate_threshold = merged_data.get("config", {}).get("duplicate_threshold", 15.0)
    filtered_urls = {}
    
    for url, data in merged_data["urls"].items():
        if data["duplicate_rate"] >= duplicate_threshold:
            filtered_urls[url] = data
    
    # 添加URL详细信息行
    for url, data in filtered_urls.items():
        # 设置质量等级样式
        quality_level = data["quality_level"]
        quality_class = ""
        if quality_level == "优":
            quality_class = "quality-excellent"
        elif quality_level == "良":
            quality_class = "quality-good"
        elif quality_level == "差":
            quality_class = "quality-fair"
        else:  # 极差
            quality_class = "quality-poor"
        
        html_content.append(f"""
                <tr class="high-duplicate">
                    <td class="url-cell"><a href="{url}" target="_blank">{url}</a></td>
                    <td>{data['directory']}</td>
                    <td><span class="duplicate-rate">{data['duplicate_rate']:.2f}%</span></td>
                    <td>{data['duplicate_paragraphs']} / {data['total_paragraphs']}</td>
                    <td><span class="quality-badge {quality_class}">{quality_level}</span></td>
                    <td>
                        <span class="collapsible" onclick="toggleDetails(this)">查看详情</span>
                        <div class="detail-content">
                            <p><strong>发布日期:</strong> {data['publish_date'] or '未知'}</p>
                            <p><strong>质量等级:</strong> <span class="quality-badge {quality_class}">{quality_level}</span></p>
                            <p><strong>段落总数:</strong> {data['total_paragraphs']}</p>
                            <p><strong>重复评分:</strong> {data['duplicate_score']:.2f}</p>
                            
                            <div class="detail-section">
                                <h4>重复段落详情</h4>
                                {f"<div class='duplicate-detail'>" + "<br>".join([f"<p>{i+1}. {para[:100] if isinstance(para, str) else str(para)[:100]}..." for i, para in enumerate(data['duplicate_details'][:5])]) + ("..." if len(data['duplicate_details']) > 5 else "") + "</div>" if data['duplicate_details'] else "<p>无详细重复段落信息</p>"}
            </div>
                        </div>
                    </td>
                </tr>
        """)
    
    # 收尾HTML内容
    html_content.append("""
                </tbody>
            </table>
            <div id="pagination" class="pagination"></div>
            <div id="pagination-info" class="pagination-info"></div>
            <div id="loader" class="loader"></div>
        </div>
        
        <footer>
            <p>报告生成于 """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """ | SEO内容质量综合分析工具</p>
        </footer>
    </div>
    
    <script>
        // 全局变量
        const ITEMS_PER_PAGE = 25;
        let currentPage = 1;
        
        // 表格排序功能
        function sortTable(n, direction = null) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                let switching = true;
                let dir = direction || "asc"; 
                let switchcount = 0;
                let rows, shouldSwitch, x, y, i;
                
                while (switching) {
                    switching = false;
                    rows = table.rows;
                    
                    for (i = 1; i < (rows.length - 1); i++) {
                        shouldSwitch = false;
                        x = rows[i].getElementsByTagName("TD")[n];
                        y = rows[i + 1].getElementsByTagName("TD")[n];
                        
                        // 根据列内容类型确定比较方式
                        let xContent, yContent;
                        if (n === 2) { // 重复率列
                            xContent = parseFloat(x.textContent.replace('%', ''));
                            yContent = parseFloat(y.textContent.replace('%', ''));
                        } else if (n === 3) { // 重复段落/总段落列
                            const xParts = x.textContent.split('/');
                            const yParts = y.textContent.split('/');
                            const xRatio = parseInt(xParts[0].trim()) / parseInt(xParts[1].trim());
                            const yRatio = parseInt(yParts[0].trim()) / parseInt(yParts[1].trim());
                            xContent = xRatio;
                            yContent = yRatio;
                        } else if (n === 4) { // 质量等级列
                            const qualityMap = {'优': 4, '良': 3, '差': 2, '极差': 1};
                            xContent = qualityMap[x.textContent.trim()] || 0;
                            yContent = qualityMap[y.textContent.trim()] || 0;
                        } else { // 文本列
                            xContent = x.textContent.toLowerCase();
                            yContent = y.textContent.toLowerCase();
                        }
                        
                        if (dir == "asc") {
                            if (xContent > yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        } else if (dir == "desc") {
                            if (xContent < yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        }
                    }
                    
                    if (shouldSwitch) {
                        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                        switching = true;
                        switchcount++;
                    } else {
                        if (switchcount == 0 && dir == "asc" && direction === null) {
                            dir = "desc";
                            switching = true;
                        }
                    }
                }
                
                // 重置分页并显示第一页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 分页功能
        function showPage(page) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
                const totalRows = rows.length;
                const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
                
                if (page < 1) page = 1;
                if (page > totalPages) page = totalPages;
                
                currentPage = page;
                
                // 隐藏所有行
                rows.forEach(row => {
                    row.style.display = 'none';
                });
                
                // 显示当前页的行
                const startIndex = (page - 1) * ITEMS_PER_PAGE;
                const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalRows);
                
                for (let i = startIndex; i < endIndex; i++) {
                    if (rows[i]) {
                        rows[i].style.display = '';
                    }
                }
                
                // 更新分页信息
                updatePaginationControls(totalRows, page, totalPages);
                hideLoader();
            }, 10);
        }
        
        // 更新分页控件
        function updatePaginationControls(totalRows, currentPage, totalPages) {
            const paginationDiv = document.getElementById('pagination');
            const paginationInfo = document.getElementById('pagination-info');
            
            paginationDiv.innerHTML = '';
            
            // 如果只有一页则不显示分页
            if (totalPages <= 1) {
                paginationDiv.style.display = 'none';
                paginationInfo.textContent = `显示 ${totalRows} 条记录`;
                return;
            }
            
            paginationDiv.style.display = 'flex';
            
            // 添加"上一页"按钮
            const prevPageLink = document.createElement('a');
            prevPageLink.href = 'javascript:void(0)';
            prevPageLink.textContent = '上一页';
            if (currentPage === 1) {
                prevPageLink.style.opacity = '0.5';
                prevPageLink.style.pointerEvents = 'none';
            } else {
                prevPageLink.onclick = () => showPage(currentPage - 1);
            }
            paginationDiv.appendChild(prevPageLink);
            
            // 确定要显示的页码范围
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + 4);
            
            if (endPage - startPage < 4) {
                startPage = Math.max(1, endPage - 4);
            }
            
            // 添加第一页
            if (startPage > 1) {
                const firstPageLink = document.createElement('a');
                firstPageLink.href = 'javascript:void(0)';
                firstPageLink.textContent = '1';
                firstPageLink.onclick = () => showPage(1);
                paginationDiv.appendChild(firstPageLink);
                
                if (startPage > 2) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
            }
            
            // 添加页码按钮
            for (let i = startPage; i <= endPage; i++) {
                const pageLink = document.createElement('a');
                pageLink.href = 'javascript:void(0)';
                pageLink.textContent = i;
                if (i === currentPage) {
                    pageLink.className = 'active';
                } else {
                    pageLink.onclick = () => showPage(i);
                }
                paginationDiv.appendChild(pageLink);
            }
            
            // 添加最后一页
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
                
                const lastPageLink = document.createElement('a');
                lastPageLink.href = 'javascript:void(0)';
                lastPageLink.textContent = totalPages;
                lastPageLink.onclick = () => showPage(totalPages);
                paginationDiv.appendChild(lastPageLink);
            }
            
            // 添加"下一页"按钮
            const nextPageLink = document.createElement('a');
            nextPageLink.href = 'javascript:void(0)';
            nextPageLink.textContent = '下一页';
            if (currentPage === totalPages) {
                nextPageLink.style.opacity = '0.5';
                nextPageLink.style.pointerEvents = 'none';
            } else {
                nextPageLink.onclick = () => showPage(currentPage + 1);
            }
            paginationDiv.appendChild(nextPageLink);
            
            // 更新页码信息
            const startRecord = (currentPage - 1) * ITEMS_PER_PAGE + 1;
            const endRecord = Math.min(currentPage * ITEMS_PER_PAGE, totalRows);
            paginationInfo.textContent = `显示 ${startRecord}-${endRecord} 条，共 ${totalRows} 条记录`;
        }
        
        // 重置分页器并显示第一页
        function resetPagination() {
            const table = document.getElementById('urlTable');
            if (!table) return;
            
            const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
            const totalRows = rows.length;
            const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
            
            showPage(1);
        }
        
        // 显示加载中
        function showLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'block';
        }
        
        // 隐藏加载中
        function hideLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'none';
        }
        
        // 搜索筛选功能
        function filterTable() {
            showLoader();
            
            setTimeout(() => {
                const input = document.getElementById('searchInput');
                const filter = input.value.toLowerCase();
                const table = document.getElementById('urlTable');
                const rows = table.getElementsByTagName("tr");
                
                // 用于标记行是否显示
                for (let i = 1; i < rows.length; i++) {
                    const td = rows[i].getElementsByTagName("td")[0]; // URL列
                    if (td) {
                        const txtValue = td.textContent || td.innerText;
                        if (txtValue.toLowerCase().indexOf(filter) > -1) {
                            rows[i].classList.remove('filtered-out');
                        } else {
                            rows[i].classList.add('filtered-out');
                        }
                    }
                }
                
                // 重新计算和显示分页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 为搜索框绑定事件
        document.getElementById('searchInput').addEventListener('keyup', filterTable);
        
        // 切换详情显示
        function toggleDetails(element) {
            const detailContent = element.nextElementSibling;
            if (detailContent.style.display === "block") {
                detailContent.style.display = "none";
                element.textContent = "查看详情";
            } else {
                detailContent.style.display = "block";
                element.textContent = "隐藏详情";
            }
        }
        
        // 页面加载完成后，设置默认排序并初始化分页
        window.addEventListener('DOMContentLoaded', function() {
            // 默认按重复率降序排序
            sortTable(2, 'desc');
        });
    </script>
</body>
</html>
    """)
    
    # 写入HTML文件
    html_path = os.path.join(report_dir, "duplicate_urls.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_content))
    
    logger.info(f"内容重复URL页面已保存到: {html_path}")
    return html_path

def generate_implicit_page(merged_data, report_dir):
    """生成暗示性语言URL列表专用页面"""
    # 准备HTML内容
    html_content = []
    html_content.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量综合报告 - 暗示性语言URL</title>
    <style>
        body {{
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f8f9fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 30px;
            border-radius: 5px;
        }}
        h1, h2, h3 {{
            margin-top: 0;
        }}
        .section {{
            margin-bottom: 30px;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
            position: sticky;
            top: 0;
            cursor: pointer;
        }}
        th:hover {{
            background-color: #2c3e50;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .has-implicit {{
            background-color: rgba(46, 204, 113, 0.1);
        }}
        .url-cell {{
            max-width: 300px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .implicit-score {{
            font-weight: bold;
            color: #2ecc71;
        }}
        .quality-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            color: white;
        }}
        .quality-excellent {{
            background-color: #2ecc71;
        }}
        .quality-good {{
            background-color: #3498db;
        }}
        .quality-fair {{
            background-color: #f39c12;
        }}
        .quality-poor {{
            background-color: #e74c3c;
        }}
        .search-container {{
            margin-bottom: 20px;
        }}
        #searchInput {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }}
        .collapsible {{
            cursor: pointer;
            color: #3498db;
            text-decoration: underline;
        }}
        .detail-content {{
            display: none;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
            margin-top: 10px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        .detail-section {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 4px;
            background-color: rgba(46, 204, 113, 0.1);
            border-left: 3px solid #2ecc71;
        }}
        .implicit-result {{
            max-height: 300px;
            overflow-y: auto;
            padding: 10px;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
        }}
        .pagination {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
            flex-wrap: wrap;
            gap: 5px;
        }}
        .pagination a {{
            color: black;
            padding: 8px 14px;
            text-decoration: none;
            border: 1px solid #ddd;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .pagination a.active {{
            background-color: #3498db;
            color: white;
            border-color: #3498db;
        }}
        .pagination a:hover:not(.active) {{
            background-color: #f1f1f1;
        }}
        .pagination-info {{
            text-align: center;
            margin-top: 10px;
            color: #7f8c8d;
        }}
        .navigation {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        .navigation a {{
            display: inline-block;
            padding: 10px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .navigation a:hover {{
            background-color: #2980b9;
        }}
        footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .loader {{
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
            display: none;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* 响应式表格样式 */
        @media screen and (max-width: 1024px) {{
            table {{
                display: block;
                overflow-x: auto;
            }}
            .url-cell {{
                max-width: 200px;
            }}
            th, td {{
                min-width: 80px;
                vertical-align: top;
                word-break: break-word;
            }}
            th:first-child, td:first-child {{
                min-width: 200px;
            }}
            th:last-child, td:last-child {{
                min-width: 80px;
            }}
            .detail-content {{
                white-space: normal;
                min-width: 250px;
                max-width: 300px;
            }}
        }}
        
        @media screen and (max-width: 768px) {{
            .navigation {{
                flex-direction: column;
                gap: 10px;
            }}
            .navigation a {{
                width: 100%;
                text-align: center;
            }}
            td {{
                vertical-align: top;
            }}
            .detail-content {{
                max-width: 300px;
                overflow-x: hidden;
            }}
            .implicit-result {{
                max-width: 280px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>SEO内容质量综合报告 - 暗示性语言URL</h1>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </header>
    <div class="container">
        <div class="navigation">
            <a href="index.html">返回首页</a>
            <a href="implicit_urls_export.csv" class="export-btn" download>导出CSV</a>
        </div>
        
        <div class="section">
            <h2>暗示性语言URL</h2>
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="搜索URL...">
            </div>
            
            <table id="urlTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">URL</th>
                        <th onclick="sortTable(1)">目录</th>
                        <th onclick="sortTable(2)">暗示评分</th>
                        <th onclick="sortTable(3)">标准化评分</th>
                        <th onclick="sortTable(4)">质量等级</th>
                        <th>详情</th>
                    </tr>
                </thead>
                <tbody>
    """)
    
    # 筛选并添加有暗示性语言的URL
    filtered_urls = {}
    
    for url, data in merged_data["urls"].items():
        if data["has_implicit"]:
            filtered_urls[url] = data
    
    # 添加URL详细信息行
    for url, data in filtered_urls.items():
        # 设置质量等级样式
        quality_level = data["quality_level"]
        quality_class = ""
        if quality_level == "优":
            quality_class = "quality-excellent"
        elif quality_level == "良":
            quality_class = "quality-good"
        elif quality_level == "差":
            quality_class = "quality-fair"
        else:  # 极差
            quality_class = "quality-poor"
        
        # 确保暗示性语言分析结果不为空，并处理HTML特殊字符
        implicit_result = "无分析结果"
        if data['implicit_result']:
            # 转义HTML特殊字符
            implicit_result = data['implicit_result'].replace('<', '&lt;').replace('>', '&gt;')
        
        html_content.append(f"""
                <tr class="has-implicit">
                    <td class="url-cell"><a href="{url}" target="_blank">{url}</a></td>
                    <td>{data['directory']}</td>
                    <td><span class="implicit-score">{data['implicit_score']}</span></td>
                    <td>{data['normalized_implicit_score']:.2f}</td>
                    <td><span class="quality-badge {quality_class}">{quality_level}</span></td>
                    <td>
                        <span class="collapsible" onclick="toggleDetails(this)">查看详情</span>
                        <div class="detail-content">
                            <p><strong>发布日期:</strong> {data['publish_date'] or '未知'}</p>
                            <p><strong>质量等级:</strong> <span class="quality-badge {quality_class}">{quality_level}</span></p>
                            
                            <div class="detail-section">
                                <h4>暗示性语言分析</h4>
                                <p><strong>暗示性评分:</strong> {data['implicit_score']} (0-10，越高越严重)</p>
                                <p><strong>标准化暗示评分:</strong> {data['normalized_implicit_score']:.2f}</p>
                                <p><strong>暗示性语言分析结果:</strong></p>
                                <div class="implicit-result">{implicit_result}</div>
                            </div>
                        </div>
                    </td>
                </tr>
        """)
    
    # 收尾HTML内容
    html_content.append("""
                </tbody>
            </table>
            <div id="pagination" class="pagination"></div>
            <div id="pagination-info" class="pagination-info"></div>
            <div id="loader" class="loader"></div>
        </div>
        
        <footer>
            <p>报告生成于 """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """ | SEO内容质量综合分析工具</p>
        </footer>
    </div>
    
    <script>
        // 全局变量
        const ITEMS_PER_PAGE = 25;
        let currentPage = 1;
        
        // 表格排序功能
        function sortTable(n, direction = null) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                let switching = true;
                let dir = direction || "asc"; 
                let switchcount = 0;
                let rows, shouldSwitch, x, y, i;
                
                while (switching) {
                    switching = false;
                    rows = table.rows;
                    
                    for (i = 1; i < (rows.length - 1); i++) {
                        shouldSwitch = false;
                        x = rows[i].getElementsByTagName("TD")[n];
                        y = rows[i + 1].getElementsByTagName("TD")[n];
                        
                        // 根据列内容类型确定比较方式
                        let xContent, yContent;
                        if (n === 2 || n === 3) { // 数值列
                            xContent = parseFloat(x.textContent);
                            yContent = parseFloat(y.textContent);
                        } else if (n === 4) { // 质量等级列
                            const qualityMap = {'优': 4, '良': 3, '差': 2, '极差': 1};
                            xContent = qualityMap[x.textContent.trim()] || 0;
                            yContent = qualityMap[y.textContent.trim()] || 0;
                        } else { // 文本列
                            xContent = x.textContent.toLowerCase();
                            yContent = y.textContent.toLowerCase();
                        }
                        
                        if (dir == "asc") {
                            if (xContent > yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        } else if (dir == "desc") {
                            if (xContent < yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        }
                    }
                    
                    if (shouldSwitch) {
                        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                        switching = true;
                        switchcount++;
                    } else {
                        if (switchcount == 0 && dir == "asc" && direction === null) {
                            dir = "desc";
                            switching = true;
                        }
                    }
                }
                
                // 重置分页并显示第一页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 分页功能
        function showPage(page) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
                const totalRows = rows.length;
                const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
                
                if (page < 1) page = 1;
                if (page > totalPages) page = totalPages;
                
                currentPage = page;
                
                // 隐藏所有行
                rows.forEach(row => {
                    row.style.display = 'none';
                });
                
                // 显示当前页的行
                const startIndex = (page - 1) * ITEMS_PER_PAGE;
                const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalRows);
                
                for (let i = startIndex; i < endIndex; i++) {
                    if (rows[i]) {
                        rows[i].style.display = '';
                    }
                }
                
                // 更新分页信息
                updatePaginationControls(totalRows, page, totalPages);
                hideLoader();
            }, 10);
        }
        
        // 更新分页控件
        function updatePaginationControls(totalRows, currentPage, totalPages) {
            const paginationDiv = document.getElementById('pagination');
            const paginationInfo = document.getElementById('pagination-info');
            
            paginationDiv.innerHTML = '';
            
            // 如果只有一页则不显示分页
            if (totalPages <= 1) {
                paginationDiv.style.display = 'none';
                paginationInfo.textContent = `显示 ${totalRows} 条记录`;
                return;
            }
            
            paginationDiv.style.display = 'flex';
            
            // 添加"上一页"按钮
            const prevPageLink = document.createElement('a');
            prevPageLink.href = 'javascript:void(0)';
            prevPageLink.textContent = '上一页';
            if (currentPage === 1) {
                prevPageLink.style.opacity = '0.5';
                prevPageLink.style.pointerEvents = 'none';
            } else {
                prevPageLink.onclick = () => showPage(currentPage - 1);
            }
            paginationDiv.appendChild(prevPageLink);
            
            // 确定要显示的页码范围
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + 4);
            
            if (endPage - startPage < 4) {
                startPage = Math.max(1, endPage - 4);
            }
            
            // 添加第一页
            if (startPage > 1) {
                const firstPageLink = document.createElement('a');
                firstPageLink.href = 'javascript:void(0)';
                firstPageLink.textContent = '1';
                firstPageLink.onclick = () => showPage(1);
                paginationDiv.appendChild(firstPageLink);
                
                if (startPage > 2) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
            }
            
            // 添加页码按钮
            for (let i = startPage; i <= endPage; i++) {
                const pageLink = document.createElement('a');
                pageLink.href = 'javascript:void(0)';
                pageLink.textContent = i;
                if (i === currentPage) {
                    pageLink.className = 'active';
                } else {
                    pageLink.onclick = () => showPage(i);
                }
                paginationDiv.appendChild(pageLink);
            }
            
            // 添加最后一页
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
                
                const lastPageLink = document.createElement('a');
                lastPageLink.href = 'javascript:void(0)';
                lastPageLink.textContent = totalPages;
                lastPageLink.onclick = () => showPage(totalPages);
                paginationDiv.appendChild(lastPageLink);
            }
            
            // 添加"下一页"按钮
            const nextPageLink = document.createElement('a');
            nextPageLink.href = 'javascript:void(0)';
            nextPageLink.textContent = '下一页';
            if (currentPage === totalPages) {
                nextPageLink.style.opacity = '0.5';
                nextPageLink.style.pointerEvents = 'none';
            } else {
                nextPageLink.onclick = () => showPage(currentPage + 1);
            }
            paginationDiv.appendChild(nextPageLink);
            
            // 更新页码信息
            const startRecord = (currentPage - 1) * ITEMS_PER_PAGE + 1;
            const endRecord = Math.min(currentPage * ITEMS_PER_PAGE, totalRows);
            paginationInfo.textContent = `显示 ${startRecord}-${endRecord} 条，共 ${totalRows} 条记录`;
        }
        
        // 重置分页器并显示第一页
        function resetPagination() {
            const table = document.getElementById('urlTable');
            if (!table) return;
            
            const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
            const totalRows = rows.length;
            const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
            
            showPage(1);
        }
        
        // 显示加载中
        function showLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'block';
        }
        
        // 隐藏加载中
        function hideLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'none';
        }
        
        // 搜索筛选功能
        function filterTable() {
            showLoader();
            
            setTimeout(() => {
                const input = document.getElementById('searchInput');
                const filter = input.value.toLowerCase();
                const table = document.getElementById('urlTable');
                const rows = table.getElementsByTagName("tr");
                
                // 用于标记行是否显示
                for (let i = 1; i < rows.length; i++) {
                    const td = rows[i].getElementsByTagName("td")[0]; // URL列
                    if (td) {
                        const txtValue = td.textContent || td.innerText;
                        if (txtValue.toLowerCase().indexOf(filter) > -1) {
                            rows[i].classList.remove('filtered-out');
                        } else {
                            rows[i].classList.add('filtered-out');
                        }
                    }
                }
                
                // 重新计算和显示分页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 为搜索框绑定事件
        document.getElementById('searchInput').addEventListener('keyup', filterTable);
        
        // 切换详情显示
        function toggleDetails(element) {
            const detailContent = element.nextElementSibling;
            if (detailContent.style.display === "block") {
                detailContent.style.display = "none";
                element.textContent = "查看详情";
            } else {
                detailContent.style.display = "block";
                element.textContent = "隐藏详情";
            }
        }
        
        // 页面加载完成后，设置默认排序并初始化分页
        window.addEventListener('DOMContentLoaded', function() {
            // 默认按暗示评分降序排序
            sortTable(2, 'desc');
        });
    </script>
</body>
</html>
    """)
    
    # 写入HTML文件
    html_path = os.path.join(report_dir, "implicit_urls.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_content))
    
    logger.info(f"暗示性语言URL页面已保存到: {html_path}")
    return html_path

def generate_improved_category_page(merged_data, report_dir, category, page_title, filter_func):
    """生成改进版的类别页面，确保详情展示功能正常"""
    # 准备HTML内容
    html_content = []
    html_content.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量综合报告 - {page_title}</title>
    <style>
        body {{
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f8f9fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 30px;
            border-radius: 5px;
        }}
        h1, h2, h3 {{
            margin-top: 0;
        }}
        .section {{
            margin-bottom: 30px;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
            position: sticky;
            top: 0;
            cursor: pointer;
        }}
        th:hover {{
            background-color: #2c3e50;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .high-duplicate {{
            background-color: rgba(231, 76, 60, 0.1);
        }}
        .has-implicit {{
            background-color: rgba(46, 204, 113, 0.1);
        }}
        .both-issues {{
            background-color: rgba(243, 156, 18, 0.1);
        }}
        .url-cell {{
            max-width: 300px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 7px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 5px;
            color: white;
        }}
        .badge.duplicate {{
            background-color: #e74c3c;
        }}
        .badge.implicit {{
            background-color: #2ecc71;
        }}
        .badge.both {{
            background-color: #e67e22;
        }}
        .quality-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            color: white;
        }}
        .quality-excellent {{
            background-color: #2ecc71;
        }}
        .quality-good {{
            background-color: #3498db;
        }}
        .quality-fair {{
            background-color: #f39c12;
        }}
        .quality-poor {{
            background-color: #e74c3c;
        }}
        .duplicate-rate {{
            font-weight: bold;
            color: #e74c3c;
        }}
        .implicit-score {{
            font-weight: bold;
            color: #2ecc71;
        }}
        .search-container {{
            margin-bottom: 20px;
        }}
        #searchInput {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }}
        .collapsible {{
            cursor: pointer;
            color: #3498db;
            text-decoration: underline;
        }}
        .detail-content {{
            display: none;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
            margin-top: 10px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        .detail-section {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 4px;
        }}
        .duplicate-section {{
            background-color: rgba(231, 76, 60, 0.1);
            border-left: 3px solid #e74c3c;
        }}
        .implicit-section {{
            background-color: rgba(46, 204, 113, 0.1);
            border-left: 3px solid #2ecc71;
        }}
        .duplicate-detail, .implicit-result {{
            max-height: 250px;
            overflow-y: auto;
            padding: 10px;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 14px;
            line-height: 1.5;
        }}
        .implicit-result {{
            white-space: pre-wrap;
        }}
        .pagination {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
            flex-wrap: wrap;
            gap: 5px;
        }}
        .pagination a {{
            color: black;
            padding: 8px 14px;
            text-decoration: none;
            border: 1px solid #ddd;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .pagination a.active {{
            background-color: #3498db;
            color: white;
            border-color: #3498db;
        }}
        .pagination a:hover:not(.active) {{
            background-color: #f1f1f1;
        }}
        .pagination-info {{
            text-align: center;
            margin-top: 10px;
            color: #7f8c8d;
        }}
        .navigation {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        .navigation a {{
            display: inline-block;
            padding: 10px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background-color 0.3s;
        }}
        .navigation a:hover {{
            background-color: #2980b9;
        }}
        footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .loader {{
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
            display: none;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* 响应式表格样式 */
        @media screen and (max-width: 1024px) {{
            table {{
                display: block;
                overflow-x: auto;
            }}
            .url-cell {{
                max-width: 200px;
            }}
            th, td {{
                min-width: 80px;
                vertical-align: top;
                word-break: break-word;
            }}
            th:first-child, td:first-child {{
                min-width: 200px;
            }}
            th:last-child, td:last-child {{
                min-width: 80px;
            }}
            .detail-content {{
                white-space: normal;
                min-width: 250px;
                max-width: 300px;
            }}
        }}
        
        @media screen and (max-width: 768px) {{
            .navigation {{
                flex-direction: column;
                gap: 10px;
            }}
            .navigation a {{
                width: 100%;
                text-align: center;
            }}
            td {{
                vertical-align: top;
            }}
            .detail-content {{
                max-width: 300px;
                overflow-x: hidden;
            }}
            .duplicate-detail, .implicit-result {{
                max-width: 280px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>SEO内容质量综合报告 - {page_title}</h1>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </header>
    <div class="container">
        <div class="navigation">
            <a href="index.html">返回首页</a>
            <a href="{category}_urls_export.csv" class="export-btn" download>导出CSV</a>
        </div>
        
        <div class="section">
            <h2>{page_title}</h2>
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="搜索URL...">
            </div>
            
            <table id="urlTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">URL</th>
                        <th onclick="sortTable(1)">目录</th>
                        <th onclick="sortTable(2)">重复率</th>
                        <th onclick="sortTable(3)">暗示评分</th>
                        <th onclick="sortTable(4)">质量等级</th>
                        <th>问题标签</th>
                        <th>详情</th>
                    </tr>
                </thead>
                <tbody>
    """)
    
    # 筛选并添加符合条件的URL
    filtered_urls = {}
    duplicate_threshold = merged_data.get("config", {}).get("duplicate_threshold", 15.0)
    
    for url, data in merged_data["urls"].items():
        if filter_func(data, duplicate_threshold):
            filtered_urls[url] = data
    
    # 添加URL详细信息行
    for url, data in filtered_urls.items():
        # 确定行的CSS类
        row_class = ""
        badges = []
        
        is_duplicate = data["duplicate_rate"] >= duplicate_threshold
        has_implicit = data["has_implicit"]
        
        if is_duplicate and has_implicit:
            row_class = "both-issues"
            badges.append('<span class="badge both">双重问题</span>')
        elif is_duplicate:
            row_class = "high-duplicate"
            badges.append('<span class="badge duplicate">内容重复</span>')
        elif has_implicit:
            row_class = "has-implicit"
            badges.append('<span class="badge implicit">暗示性语言</span>')
        
        # 设置质量等级样式
        quality_level = data["quality_level"]
        quality_class = ""
        if quality_level == "优":
            quality_class = "quality-excellent"
        elif quality_level == "良":
            quality_class = "quality-good"
        elif quality_level == "差":
            quality_class = "quality-fair"
        else:  # 极差
            quality_class = "quality-poor"
        
        # 确保暗示性语言分析结果不为空，并处理HTML特殊字符
        implicit_result = "无分析结果"
        if data['implicit_result']:
            # 转义HTML特殊字符
            implicit_result = data['implicit_result'].replace('<', '&lt;').replace('>', '&gt;')
        
        html_content.append(f"""
                <tr class="{row_class}">
                    <td class="url-cell"><a href="{url}" target="_blank">{url}</a></td>
                    <td>{data['directory']}</td>
                    <td><span class="duplicate-rate">{data['duplicate_rate']:.2f}%</span></td>
                    <td><span class="implicit-score">{data['implicit_score']}</span></td>
                    <td><span class="quality-badge {quality_class}">{quality_level}</span></td>
                    <td>{"".join(badges)}</td>
                    <td>
                        <span class="collapsible" onclick="toggleDetails(this)">查看详情</span>
                        <div class="detail-content">
                            <p><strong>发布日期:</strong> {data['publish_date'] or '未知'}</p>
                            <p><strong>质量等级:</strong> <span class="quality-badge {quality_class}">{quality_level}</span></p>
                            <p><strong>段落总数:</strong> {data['total_paragraphs']}</p>
                            
                            <div class="detail-section duplicate-section">
                                <h4>内容重复分析</h4>
                                <p><strong>重复段落数:</strong> {data['duplicate_paragraphs']}</p>
                                <p><strong>重复率:</strong> {data['duplicate_rate']:.2f}%</p>
                                <p><strong>重复评分:</strong> {data['duplicate_score']:.2f}</p>
                                {f"<p><strong>重复段落详情:</strong></p><div class='duplicate-detail'>" + "<br>".join([f"<p>{i+1}. {para[:100] if isinstance(para, str) else str(para)[:100]}..." for i, para in enumerate(data['duplicate_details'][:5])]) + ("..." if len(data['duplicate_details']) > 5 else "") + "</div>" if data['duplicate_details'] else "<p>无详细重复段落信息</p>"}
                            </div>
                            
                            <div class="detail-section implicit-section">
                                <h4>暗示性语言分析</h4>
                                <p><strong>暗示性评分:</strong> {data['implicit_score']} (0-10，越高越严重)</p>
                                <p><strong>标准化暗示评分:</strong> {data['normalized_implicit_score']:.2f}</p>
                                <p><strong>暗示性语言分析结果:</strong></p>
                                <div class="implicit-result">{implicit_result}</div>
                            </div>
                        </div>
                    </td>
                </tr>
        """)
    
    # 收尾HTML内容
    html_content.append("""
                </tbody>
            </table>
            <div id="pagination" class="pagination"></div>
            <div id="pagination-info" class="pagination-info"></div>
            <div id="loader" class="loader"></div>
        </div>
        
        <footer>
            <p>报告生成于 """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """ | SEO内容质量综合分析工具</p>
        </footer>
    </div>
    
    <script>
        // 全局变量
        const ITEMS_PER_PAGE = 25;
        let currentPage = 1;
        
        // 表格排序功能
        function sortTable(n, direction = null) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                let switching = true;
                let dir = direction || "asc"; 
                let switchcount = 0;
                let rows, shouldSwitch, x, y, i;
                
                while (switching) {
                    switching = false;
                    rows = table.rows;
                    
                    for (i = 1; i < (rows.length - 1); i++) {
                        shouldSwitch = false;
                        x = rows[i].getElementsByTagName("TD")[n];
                        y = rows[i + 1].getElementsByTagName("TD")[n];
                        
                        // 根据列内容类型确定比较方式
                        let xContent, yContent;
                        if (n === 2) { // 重复率列
                            xContent = parseFloat(x.textContent.replace('%', ''));
                            yContent = parseFloat(y.textContent.replace('%', ''));
                        } else if (n === 3) { // 暗示评分列
                            xContent = parseFloat(x.textContent);
                            yContent = parseFloat(y.textContent);
                        } else if (n === 4) { // 质量等级列
                            const qualityMap = {'优': 4, '良': 3, '差': 2, '极差': 1};
                            xContent = qualityMap[x.textContent.trim()] || 0;
                            yContent = qualityMap[y.textContent.trim()] || 0;
                        } else { // 文本列
                            xContent = x.textContent.toLowerCase();
                            yContent = y.textContent.toLowerCase();
                        }
                        
                        if (dir == "asc") {
                            if (xContent > yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        } else if (dir == "desc") {
                            if (xContent < yContent) {
                                shouldSwitch = true;
                                break;
                            }
                        }
                    }
                    
                    if (shouldSwitch) {
                        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                        switching = true;
                        switchcount++;
                    } else {
                        if (switchcount == 0 && dir == "asc" && direction === null) {
                            dir = "desc";
                            switching = true;
                        }
                    }
                }
                
                // 重置分页并显示第一页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 分页功能
        function showPage(page) {
            showLoader();
            
            setTimeout(() => {
                const table = document.getElementById('urlTable');
                const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
                const totalRows = rows.length;
                const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
                
                if (page < 1) page = 1;
                if (page > totalPages) page = totalPages;
                
                currentPage = page;
                
                // 隐藏所有行
                rows.forEach(row => {
                    row.style.display = 'none';
                });
                
                // 显示当前页的行
                const startIndex = (page - 1) * ITEMS_PER_PAGE;
                const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalRows);
                
                for (let i = startIndex; i < endIndex; i++) {
                    if (rows[i]) {
                        rows[i].style.display = '';
                    }
                }
                
                // 更新分页信息
                updatePaginationControls(totalRows, page, totalPages);
                hideLoader();
            }, 10);
        }
        
        // 更新分页控件
        function updatePaginationControls(totalRows, currentPage, totalPages) {
            const paginationDiv = document.getElementById('pagination');
            const paginationInfo = document.getElementById('pagination-info');
            
            paginationDiv.innerHTML = '';
            
            // 如果只有一页则不显示分页
            if (totalPages <= 1) {
                paginationDiv.style.display = 'none';
                paginationInfo.textContent = `显示 ${totalRows} 条记录`;
                return;
            }
            
            paginationDiv.style.display = 'flex';
            
            // 添加"上一页"按钮
            const prevPageLink = document.createElement('a');
            prevPageLink.href = 'javascript:void(0)';
            prevPageLink.textContent = '上一页';
            if (currentPage === 1) {
                prevPageLink.style.opacity = '0.5';
                prevPageLink.style.pointerEvents = 'none';
            } else {
                prevPageLink.onclick = () => showPage(currentPage - 1);
            }
            paginationDiv.appendChild(prevPageLink);
            
            // 确定要显示的页码范围
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + 4);
            
            if (endPage - startPage < 4) {
                startPage = Math.max(1, endPage - 4);
            }
            
            // 添加第一页
            if (startPage > 1) {
                const firstPageLink = document.createElement('a');
                firstPageLink.href = 'javascript:void(0)';
                firstPageLink.textContent = '1';
                firstPageLink.onclick = () => showPage(1);
                paginationDiv.appendChild(firstPageLink);
                
                if (startPage > 2) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
            }
            
            // 添加页码按钮
            for (let i = startPage; i <= endPage; i++) {
                const pageLink = document.createElement('a');
                pageLink.href = 'javascript:void(0)';
                pageLink.textContent = i;
                if (i === currentPage) {
                    pageLink.className = 'active';
                } else {
                    pageLink.onclick = () => showPage(i);
                }
                paginationDiv.appendChild(pageLink);
            }
            
            // 添加最后一页
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) {
                    const ellipsis = document.createElement('a');
                    ellipsis.href = 'javascript:void(0)';
                    ellipsis.textContent = '...';
                    ellipsis.style.pointerEvents = 'none';
                    paginationDiv.appendChild(ellipsis);
                }
                
                const lastPageLink = document.createElement('a');
                lastPageLink.href = 'javascript:void(0)';
                lastPageLink.textContent = totalPages;
                lastPageLink.onclick = () => showPage(totalPages);
                paginationDiv.appendChild(lastPageLink);
            }
            
            // 添加"下一页"按钮
            const nextPageLink = document.createElement('a');
            nextPageLink.href = 'javascript:void(0)';
            nextPageLink.textContent = '下一页';
            if (currentPage === totalPages) {
                nextPageLink.style.opacity = '0.5';
                nextPageLink.style.pointerEvents = 'none';
            } else {
                nextPageLink.onclick = () => showPage(currentPage + 1);
            }
            paginationDiv.appendChild(nextPageLink);
            
            // 更新页码信息
            const startRecord = (currentPage - 1) * ITEMS_PER_PAGE + 1;
            const endRecord = Math.min(currentPage * ITEMS_PER_PAGE, totalRows);
            paginationInfo.textContent = `显示 ${startRecord}-${endRecord} 条，共 ${totalRows} 条记录`;
        }
        
        // 重置分页器并显示第一页
        function resetPagination() {
            const table = document.getElementById('urlTable');
            if (!table) return;
            
            const rows = table.querySelectorAll('tbody tr:not(.filtered-out)');
            const totalRows = rows.length;
            const totalPages = Math.ceil(totalRows / ITEMS_PER_PAGE);
            
            showPage(1);
        }
        
        // 显示加载中
        function showLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'block';
        }
        
        // 隐藏加载中
        function hideLoader() {
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'none';
        }
        
        // 搜索筛选功能
        function filterTable() {
            showLoader();
            
            setTimeout(() => {
                const input = document.getElementById('searchInput');
                const filter = input.value.toLowerCase();
                const table = document.getElementById('urlTable');
                const rows = table.getElementsByTagName("tr");
                
                // 用于标记行是否显示
                for (let i = 1; i < rows.length; i++) {
                    const td = rows[i].getElementsByTagName("td")[0]; // URL列
                    if (td) {
                        const txtValue = td.textContent || td.innerText;
                        if (txtValue.toLowerCase().indexOf(filter) > -1) {
                            rows[i].classList.remove('filtered-out');
                        } else {
                            rows[i].classList.add('filtered-out');
                        }
                    }
                }
                
                // 重新计算和显示分页
                resetPagination();
                hideLoader();
            }, 10);
        }
        
        // 为搜索框绑定事件
        document.getElementById('searchInput').addEventListener('keyup', filterTable);
        
        // 切换详情显示
        function toggleDetails(element) {
            const detailContent = element.nextElementSibling;
            if (detailContent.style.display === "block") {
                detailContent.style.display = "none";
                element.textContent = "查看详情";
            } else {
                detailContent.style.display = "block";
                element.textContent = "隐藏详情";
            }
        }
        
        // 页面加载完成后，设置默认排序并初始化分页
        window.addEventListener('DOMContentLoaded', function() {
            // 检查是否需要筛选双重问题
            if (document.location.hash === '#both_issues' || getCookie('filter_both_issues') === 'true') {
                // 如果需要，则自动筛选双重问题
                document.getElementById('searchInput').value = '双重问题';
                filterTable();
                // 清除cookie
                document.cookie = "filter_both_issues=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            }
            
            // 根据类别设置默认排序
            const category = '{category}';
            if (category === 'excellent' || category === 'good' || category === 'fair' || category === 'poor') {
                // 质量等级页面按质量等级降序排序
                sortTable(4, 'desc');
            } else if (category === 'duplicate') {
                // 内容重复页面按重复率降序排序
                sortTable(2, 'desc');
            } else if (category === 'implicit') {
                // 暗示性语言页面按暗示评分降序排序
                sortTable(3, 'desc');
            } else {
                // 默认按质量等级降序排序
                sortTable(4, 'desc');
            }
        });
        
        // 获取cookie值的辅助函数
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return '';
        }
    </script>
</body>
</html>
    """)
    
    # 写入HTML文件
    html_path = os.path.join(report_dir, f"{category}_urls.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_content))
    
    logger.info(f"{page_title}页面已保存到: {html_path}")
    return html_path

def generate_directory_stats_page(merged_data, report_dir):
    """生成目录统计页面，展示每个目录的综合评分情况"""
    logger.info("开始生成目录统计页面...")
    
    # 准备目录统计数据
    directory_stats = {}
    
    # 遍历所有URL，按目录分类统计
    for url, data in merged_data["urls"].items():
        directory = data.get("directory", "未分类")
        
        if directory not in directory_stats:
            directory_stats[directory] = {
                "total": 0,
                "excellent": 0,
                "good": 0,
                "fair": 0,
                "poor": 0,
                "high_duplicate": 0,
                "has_implicit": 0,
                "both_issues": 0,
                "avg_duplicate_rate": 0,
                "avg_implicit_score": 0,
                "urls": []
            }
        
        # 记录URL
        directory_stats[directory]["urls"].append(url)
        
        # 更新计数
        directory_stats[directory]["total"] += 1
        
        # 按质量等级统计
        quality_level = data.get("quality_level", "")
        if quality_level == "优":
            directory_stats[directory]["excellent"] += 1
        elif quality_level == "良":
            directory_stats[directory]["good"] += 1
        elif quality_level == "差":
            directory_stats[directory]["fair"] += 1
        elif quality_level == "极差":
            directory_stats[directory]["poor"] += 1
        
        # 重复度和暗示性语言统计
        duplicate_threshold = merged_data.get("config", {}).get("duplicate_threshold", 15.0)
        if data.get("duplicate_rate", 0) >= duplicate_threshold:
            directory_stats[directory]["high_duplicate"] += 1
        
        if data.get("has_implicit", False):
            directory_stats[directory]["has_implicit"] += 1
        
        if data.get("duplicate_rate", 0) >= duplicate_threshold and data.get("has_implicit", False):
            directory_stats[directory]["both_issues"] += 1
        
        # 累加评分用于后续计算平均值
        directory_stats[directory]["avg_duplicate_rate"] += data.get("duplicate_rate", 0)
        directory_stats[directory]["avg_implicit_score"] += data.get("implicit_score", 0)
    
    # 计算平均值
    for directory in directory_stats:
        total = directory_stats[directory]["total"]
        if total > 0:
            directory_stats[directory]["avg_duplicate_rate"] = round(directory_stats[directory]["avg_duplicate_rate"] / total, 2)
            directory_stats[directory]["avg_implicit_score"] = round(directory_stats[directory]["avg_implicit_score"] / total, 2)
    
    # 生成HTML内容
    html_content = []
    html_content.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO内容质量目录统计</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 5px solid #2c3e50;
        }
        .stats-card {
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #3498db;
        }
        .stats-card h2 {
            margin-top: 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }
        .stat-item {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            margin: 5px 0;
        }
        .stat-label {
            font-size: 14px;
            color: #666;
        }
        .excellent { background-color: #d4edda; border-left: 3px solid #28a745; }
        .good { background-color: #d1ecf1; border-left: 3px solid #17a2b8; }
        .fair { background-color: #fff3cd; border-left: 3px solid #ffc107; }
        .poor { background-color: #f8d7da; border-left: 3px solid #dc3545; }
        .high-duplicate { background-color: #fbf0ef; border-left: 3px solid #e74c3c; }
        .has-implicit { background-color: #f0f5fb; border-left: 3px solid #3498db; }
        .both-issues { background-color: #f5eef8; border-left: 3px solid #9b59b6; }
        
        .progress-container {
            width: 100%;
            background-color: #f1f1f1;
            border-radius: 5px;
            margin: 10px 0;
        }
        .progress-bar {
            height: 20px;
            border-radius: 5px;
            text-align: center;
            line-height: 20px;
            color: white;
        }
        .progress-excellent { background-color: #28a745; }
        .progress-good { background-color: #17a2b8; }
        .progress-fair { background-color: #ffc107; color: #333; }
        .progress-poor { background-color: #dc3545; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        
        .summary-box {
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            border-left: 4px solid #2c3e50;
        }
        
        .back-link {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
        .back-link:hover {
            background-color: #2980b9;
        }
        
        /* 低质量目录汇总样式 */
        .low-quality-summary {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 25px;
            margin: 30px 0;
            border-left: 5px solid #e74c3c;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .low-quality-summary h2 {
            color: #e74c3c;
            margin-top: 0;
            font-size: 1.8em;
            margin-bottom: 20px;
            border-bottom: 1px solid rgba(231, 76, 60, 0.2);
            padding-bottom: 10px;
        }
        .low-quality-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            box-shadow: 0 2px 3px rgba(0,0,0,0.1);
            border-radius: 5px;
            overflow: hidden;
            margin: 20px 0;
        }
        .low-quality-table th {
            background: linear-gradient(to bottom, #fadbd8, #f5b7b1);
            color: #c0392b;
            font-weight: 600;
            text-align: left;
            padding: 12px 15px;
            font-size: 1.05em;
            border-bottom: 2px solid #e74c3c;
        }
        .low-quality-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
            vertical-align: top;
        }
        .low-quality-table tr:last-child td {
            border-bottom: none;
        }
        .low-quality-table tr:nth-child(even) {
            background-color: rgba(248, 249, 250, 0.7);
        }
        .low-quality-table tr:hover {
            background-color: rgba(231, 76, 60, 0.05);
        }
        .summary-text {
            font-size: 16px;
            margin-bottom: 20px;
            line-height: 1.5;
            color: #555;
        }
        .improvement-tips {
            background-color: #eaf2f8;
            padding: 20px;
            border-radius: 8px;
            margin-top: 25px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border-left: 4px solid #3498db;
        }
        .improvement-tips h3 {
            margin-top: 0;
            color: #3498db;
            font-size: 1.4em;
            margin-bottom: 15px;
        }
        .improvement-tips ul {
            padding-left: 20px;
            margin-bottom: 0;
        }
        .improvement-tips li {
            margin-bottom: 10px;
            line-height: 1.5;
        }
        .improvement-tips strong {
            color: #2980b9;
        }
        
        /* 优化目标样式 */
        .summary-optimization-targets {
            background: linear-gradient(to right, #ebf5fb, #d6eaf8);
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
            border-left: 4px solid #3498db;
            box-shadow: 0 3px 8px rgba(52, 152, 219, 0.15);
        }
        
        .summary-optimization-targets h3 {
            margin-top: 0;
            color: #2980b9;
            font-size: 1.5em;
            margin-bottom: 15px;
            text-align: center;
            border-bottom: 1px solid rgba(52, 152, 219, 0.3);
            padding-bottom: 10px;
        }
        
        .summary-optimization-targets p {
            font-size: 1.1em;
            margin: 15px 0;
            text-align: center;
            padding: 10px;
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 5px;
        }
        
        .optimization-number {
            font-weight: 700;
            font-size: 1.3em;
            color: #e74c3c;
            background-color: rgba(255, 255, 255, 0.8);
            padding: 3px 8px;
            border-radius: 4px;
            margin: 0 5px;
            display: inline-block;
            min-width: 40px;
            text-align: center;
        }
        
        /* 表格中的优化目标列样式 */
        .optimization-target-cell {
            background-color: rgba(235, 245, 251, 0.4);
            width: 180px;
        }
        
        .optimization-target-cell p {
            margin: 8px 0;
            line-height: 1.4;
            padding: 5px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }
        
        .optimization-target-cell p:hover {
            background-color: rgba(255, 255, 255, 0.8);
        }
        
        .optimization-target-cell strong {
            color: #2980b9;
            display: inline-block;
            width: 120px;
        }
        
        .need-optimize {
            color: #e74c3c;
            font-weight: 700;
            background-color: rgba(255, 255, 255, 0.8);
            padding: 2px 6px;
            border-radius: 3px;
            display: inline-block;
            min-width: 25px;
            text-align: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        
        /* 质量分布信息 */
        .quality-distribution {
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }
        
        .quality-bar-container {
            flex-grow: 1;
            height: 20px;
            background-color: #f1f1f1;
            border-radius: 10px;
            overflow: hidden;
            margin: 0 10px;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .quality-bar {
            height: 100%;
            float: left;
            transition: width 0.5s;
        }
        
        .good-quality-bar {
            background: linear-gradient(to right, #2ecc71, #27ae60);
        }
        
        .poor-quality-bar {
            background: linear-gradient(to right, #e74c3c, #c0392b);
        }
        
        .quality-label {
            width: 80px;
            font-weight: 600;
            font-size: 0.9em;
        }
        
        @media screen and (max-width: 768px) {
            .low-quality-table {
                display: block;
                overflow-x: auto;
            }
            
            .optimization-target-cell {
                min-width: 180px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SEO内容质量目录统计</h1>
            <p>生成时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            <p>总URLs数量: """ + str(merged_data["stats"]["total_urls"]) + """</p>
            <a href="index.html" class="back-link">返回首页</a>
        </div>
        
        <h2>目录质量统计</h2>
        <table>
            <tr>
                <th>目录</th>
                <th>总URL数</th>
                <th>优质内容</th>
                <th>良好内容</th>
                <th>较差内容</th>
                <th>极差内容</th>
                <th>重复内容</th>
                <th>暗示性语言</th>
                <th>双重问题</th>
                <th>平均重复率</th>
                <th>平均暗示分</th>
            </tr>""")
    
    # 按URL总数排序目录
    sorted_directories = sorted(directory_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    
    # 为每个目录添加表格行
    for directory, stats in sorted_directories:
        html_content.append(f"""
            <tr>
                <td>{directory}</td>
                <td>{stats["total"]}</td>
                <td>{stats["excellent"]} ({round(stats["excellent"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["good"]} ({round(stats["good"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["fair"]} ({round(stats["fair"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["poor"]} ({round(stats["poor"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["high_duplicate"]} ({round(stats["high_duplicate"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["has_implicit"]} ({round(stats["has_implicit"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["both_issues"]} ({round(stats["both_issues"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)}%)</td>
                <td>{stats["avg_duplicate_rate"]}%</td>
                <td>{stats["avg_implicit_score"]}</td>
            </tr>""")
    
    html_content.append("""
        </table>
        
        <h2>目录详细分析</h2>""")
    
    # 为每个目录添加详细卡片
    for directory, stats in sorted_directories:
        # 只显示有5个以上URL的目录的详细卡片
        if stats["total"] >= 5:
            # 计算百分比
            excellent_percent = round(stats["excellent"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            good_percent = round(stats["good"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            fair_percent = round(stats["fair"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            poor_percent = round(stats["poor"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            high_duplicate_percent = round(stats["high_duplicate"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            has_implicit_percent = round(stats["has_implicit"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            both_issues_percent = round(stats["both_issues"]/stats["total"]*100 if stats["total"] > 0 else 0, 1)
            
            html_content.append(f"""
        <div class="stats-card">
            <h2>{directory}</h2>
            <p>包含 {stats["total"]} 个URL</p>
            
            <h3>质量分布</h3>
            <div class="progress-container">
                <div class="progress-bar progress-excellent" style="width: {excellent_percent}%;">{excellent_percent}%</div>
            </div>
            <p>优质内容: {stats["excellent"]} ({excellent_percent}%)</p>
            
            <div class="progress-container">
                <div class="progress-bar progress-good" style="width: {good_percent}%;">{good_percent}%</div>
            </div>
            <p>良好内容: {stats["good"]} ({good_percent}%)</p>
            
            <div class="progress-container">
                <div class="progress-bar progress-fair" style="width: {fair_percent}%;">{fair_percent}%</div>
            </div>
            <p>较差内容: {stats["fair"]} ({fair_percent}%)</p>
            
            <div class="progress-container">
                <div class="progress-bar progress-poor" style="width: {poor_percent}%;">{poor_percent}%</div>
            </div>
            <p>极差内容: {stats["poor"]} ({poor_percent}%)</p>
            
            <h3>问题分析</h3>
            <div class="stats-grid">
                <div class="stat-item high-duplicate">
                    <div class="stat-value">{high_duplicate_percent}%</div>
                    <div class="stat-label">重复内容</div>
                    <div>{stats["high_duplicate"]} 个URL</div>
                </div>
                
                <div class="stat-item has-implicit">
                    <div class="stat-value">{has_implicit_percent}%</div>
                    <div class="stat-label">暗示性语言</div>
                    <div>{stats["has_implicit"]} 个URL</div>
                </div>
                
                <div class="stat-item both-issues">
                    <div class="stat-value">{both_issues_percent}%</div>
                    <div class="stat-label">双重问题</div>
                    <div>{stats["both_issues"]} 个URL</div>
                </div>
                
                <div class="stat-item">
                    <div class="stat-value">{stats["avg_duplicate_rate"]}%</div>
                    <div class="stat-label">平均重复率</div>
                </div>
                
                <div class="stat-item">
                    <div class="stat-value">{stats["avg_implicit_score"]}</div>
                    <div class="stat-label">平均暗示分</div>
                </div>
            </div>
        </div>""")
    
    html_content.append("""
    <a href="index.html" class="back-link">返回首页</a>
</div>
</body>
</html>""")
    
    # 写入HTML文件
    html_path = os.path.join(report_dir, "directory_stats.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html_content))
    
    logger.info(f"目录统计页面已保存到: {html_path}")
    return html_path

def generate_low_quality_directories_section(directory_stats, merged_data):
    """生成质量分布低于85%的目录汇总和改进建议（含美观交互）"""
    import math

    low_quality_dirs = []
    # 查找质量分布低于85%的目录
    for directory, stats in directory_stats.items():
        directory = directory.strip()
        excellent_count = stats.get("excellent", 0)
        good_count = stats.get("good", 0)
        total_count = stats.get("total", 0)
        print(f"目录: {directory}, 总数: {total_count}, 优: {excellent_count}, 良: {good_count}, 差: {stats.get('fair', 0)}, 极差: {stats.get('poor', 0)}")
        if total_count > 0:
            quality_percent = round(excellent_count / total_count * 100, 1)
            current_quality_count = excellent_count  # 只用优内容
            needed_85_percent = int(math.ceil(total_count * 0.85))
            needed_90_percent = int(math.ceil(total_count * 0.90))
            to_optimize_85 = max(0, needed_85_percent - current_quality_count)
            to_optimize_90 = max(0, needed_90_percent - current_quality_count)
            
            if quality_percent < 85:
                low_quality_dirs.append({
                    "directory": directory,
                    "total": total_count,
                    "quality_percent": quality_percent,
                    "excellent": excellent_count,
                    "good": good_count,
                    "fair": stats.get("fair", 0),
                    "poor": stats.get("poor", 0),
                    "high_duplicate": stats.get("high_duplicate", 0),
                    "high_duplicate_percent": round(stats.get("high_duplicate", 0) / total_count * 100, 1) if total_count > 0 else 0,
                    "has_implicit": stats.get("has_implicit", 0),
                    "has_implicit_percent": round(stats.get("has_implicit", 0) / total_count * 100, 1) if total_count > 0 else 0,
                    "avg_duplicate_rate": stats.get("avg_duplicate_rate", 0),
                    "avg_implicit_score": stats.get("avg_implicit_score", 0),
                    "current_quality_count": current_quality_count,
                    "needed_85_percent": needed_85_percent,
                    "needed_90_percent": needed_90_percent,
                    "to_optimize_85": to_optimize_85,
                    "to_optimize_90": to_optimize_90
                })

    if not low_quality_dirs:
        return ""

    low_quality_dirs.sort(key=lambda x: x["quality_percent"])

    # 生成HTML内容
    html = """
    <style>
    .improve-interactive {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 12px;
        margin-bottom: 4px;
    }
    .improve-input {
        width: 70px;
        padding: 6px 8px;
        border: 1.5px solid #b2bec3;
        border-radius: 6px;
        font-size: 1em;
        transition: border 0.2s;
    }
    .improve-input:focus {
        border: 1.5px solid #4a6cf7;
        outline: none;
    }
    .improve-btn {
        padding: 6px 18px;
        background: linear-gradient(90deg, #4a6cf7 60%, #6dd5fa 100%);
        color: #fff;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        font-size: 1em;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(52,152,219,0.08);
        transition: background 0.2s, box-shadow 0.2s, transform 0.1s;
    }
    .improve-btn:hover {
        background: linear-gradient(90deg, #217dbb 60%, #3498db 100%);
        box-shadow: 0 4px 16px rgba(52,152,219,0.16);
        transform: translateY(-2px) scale(1.04);
    }
    .improve-result {
        margin-left: 0;
        margin-top: 8px;
        font-size: 0.98em;
        min-height: 1.5em;
        border-radius: 6px;
        padding: 6px 10px;
        background: #f8f9fa;
        color: #217dbb;
        box-shadow: 0 1px 4px rgba(52,152,219,0.06);
        word-break: break-all;
        max-width: 220px;
    }
    .improve-result.success {
        background: #eafaf1;
        color: #27ae60;
        font-weight: bold;
    }
    .improve-result.warning {
        background: #fff9e6;
        color: #e67e22;
        font-weight: bold;
    }
    .improve-result.error {
        background: #fff0f0;
        color: #e74c3c;
        font-weight: bold;
    }
    @media (max-width: 900px) {
        .improve-interactive { flex-direction: column; align-items: flex-start; gap: 4px;}
        .improve-result { max-width: 100%; }
    }
    </style>
    <div class="low-quality-summary">
        <h2>质量分布低于85%的目录</h2>
        <p class="summary-text">以下目录的内容质量分布低于85%，需要重点关注和改进。左侧红色部分表示较差/极差内容比例，右侧绿色部分表示优良内容比例。</p>
        <table class="low-quality-table">
            <tr>
                <th style="width:20%">目录</th>
                <th style="width:10%">URL总数</th>
                <th style="width:25%">质量分布</th>
                <th style="width:15%">重点问题</th>
                <th style="width:15%">改进建议</th>
                <th style="width:15%">优化目标</th>
            </tr>"""

    for idx, dir_info in enumerate(low_quality_dirs):
        good_quality_percent = dir_info["quality_percent"]
        poor_quality_percent = 100 - good_quality_percent

        # 主要问题
        main_issues = []
        if dir_info["high_duplicate_percent"] >= 20:
            main_issues.append(f"重复内容比例高({dir_info['high_duplicate_percent']}%)")
        if dir_info["has_implicit_percent"] >= 30:
            main_issues.append(f"暗示性语言比例高({dir_info['has_implicit_percent']}%)")
        if dir_info["poor"] / dir_info["total"] * 100 >= 15:
            main_issues.append("极差内容比例高")
        if not main_issues:
            main_issues = ["内容质量整体偏低"]
        main_issues_text = "、".join(main_issues)

        # 改进建议
        suggestions = []
        if dir_info["high_duplicate_percent"] >= 20:
            suggestions.append("减少内容重复度，增加原创内容比例")
        if dir_info["has_implicit_percent"] >= 30:
            suggestions.append("减少暗示性、营销性语言，提高内容客观性")
        if dir_info["poor"] / dir_info["total"] * 100 >= 15:
            suggestions.append("优先处理极差内容，提高内容深度和价值")
        if "资讯" in dir_info["directory"] or "新闻" in dir_info["directory"]:
            suggestions.append("增加新闻时效性和深度报道")
        elif "问答" in dir_info["directory"]:
            suggestions.append("提高问答内容的专业性和解决方案的实用性")
        elif "指南" in dir_info["directory"] or "攻略" in dir_info["directory"]:
            suggestions.append("增加实操步骤和案例分析")
        elif "专业" in dir_info["directory"] or "职业" in dir_info["directory"]:
            suggestions.append("增加行业专业知识和最新动态")
        else:
            suggestions.append("提高内容原创度和专业深度")
        suggestions_text = "；".join(suggestions) + "。"

        # 优化目标信息
        optimization_target = f"""
            <p><strong>当前优内容:</strong> <span class="need-optimize">{dir_info["excellent"]}</span> 条</p>
            <p><strong>达到85%需优化:</strong> <span class="need-optimize">{dir_info["to_optimize_85"]}</span> 条</p>
            <p><strong>达到90%需优化:</strong> <span class="need-optimize">{dir_info["to_optimize_90"]}</span> 条</p>
            <div class="improve-interactive">
                <input type='number' min='0' max='{dir_info["total"] - dir_info["excellent"]}' 
                    id='improve_input_{idx}' placeholder='优化条数' class='improve-input'
                    onkeydown="if(event.key==='Enter')calcImprove({idx}, {dir_info["excellent"]}, {dir_info["total"]})">
                <button class='improve-btn' onclick='calcImprove({idx}, {dir_info["excellent"]}, {dir_info["total"]})'>计算</button>
                <div id='improve_result_{idx}' class='improve-result'></div>
            </div>
        """

        # 质量分布可视化
        quality_distribution = f"""
            <div class="quality-distribution">
                <span class="quality-label">较差/极差:</span>
                <div class="quality-bar-container">
                    <div class="quality-bar poor-quality-bar" style="width: {poor_quality_percent}%;"></div>
                    <div class="quality-bar good-quality-bar" style="width: {good_quality_percent}%;"></div>
                </div>
                <span class="quality-label">优:</span>
            </div>
            <p>优内容: {dir_info["excellent"]} ({dir_info["quality_percent"]}%) |
               良内容: {dir_info["good"]} ({round(dir_info["good"] / dir_info["total"] * 100 if dir_info["total"] > 0 else 0, 1)}%) |
               较差/极差: {dir_info["fair"] + dir_info["poor"]} ({round(100 - dir_info["quality_percent"] - (dir_info["good"] / dir_info["total"] * 100 if dir_info["total"] > 0 else 0), 1)}%)</p>
        """

        html += f"""
            <tr>
                <td>{dir_info["directory"]}</td>
                <td>{dir_info["total"]}</td>
                <td>{quality_distribution}</td>
                <td>{main_issues_text}</td>
                <td>{suggestions_text}</td>
                <td class="optimization-target-cell">{optimization_target}</td>
            </tr>"""

    total_urls_to_optimize_85 = sum(d["to_optimize_85"] for d in low_quality_dirs)
    total_urls_to_optimize_90 = sum(d["to_optimize_90"] for d in low_quality_dirs)

    html += f"""
        </table>
        <div class="summary-optimization-targets">
            <h3>总优化需求</h3>
            <p>将所有低质量目录提升至85%优内容标准需要优化: <span class="optimization-number">{total_urls_to_optimize_85}</span> 条URL</p>
            <p>将所有低质量目录提升至90%优内容标准需要优化: <span class="optimization-number">{total_urls_to_optimize_90}</span> 条URL</p>
        </div>
        <div class="improvement-tips">
            <h3>通用改进策略</h3>
            <ul>
                <li><strong>内容深度提升</strong>：增加专业信息、数据支持和实用案例</li>
                <li><strong>减少重复内容</strong>：避免页面间内容大量重复，保持原创性</li>
                <li><strong>提高表达客观性</strong>：减少营销和推广性质的语言</li>
                <li><strong>优化内容结构</strong>：使用合理的标题层级和段落划分</li>
                <li><strong>增加内容时效性</strong>：定期更新与行业最新动态相关的内容</li>
            </ul>
        </div>
    </div>
    <script>
    function calcImprove(idx, current, total) {{
        var input = document.getElementById('improve_input_' + idx);
        var result = document.getElementById('improve_result_' + idx);
        var add = parseInt(input.value);
        if (isNaN(add)) add = 0;
        if (add < 0) add = 0;
        if (add > total - current) add = total - current;
        var new_quality = current + add;
        var percent = (new_quality / total * 100).toFixed(1);
        var msg = '';
        result.className = 'improve-result';
        if (add === 0) {{
            msg = '请输入大于0的优化条数';
            result.classList.add('error');
        }} else {{
            msg = '优化后优内容：' + new_quality + ' 条，优内容比例：' + percent + '%。';
            if (percent >= 90) {{
                msg += ' 🎉 已达到90%目标！';
                result.classList.add('success');
            }} else if (percent >= 85) {{
                msg += ' 👍 已达到85%目标！';
                result.classList.add('success');
            }} else {{
                var need85 = Math.ceil(total * 0.85) - new_quality;
                var need90 = Math.ceil(total * 0.90) - new_quality;
                msg += ' 距85%还需优化 ' + (need85 > 0 ? need85 : 0) + ' 条，距90%还需优化 ' + (need90 > 0 ? need90 : 0) + ' 条。';
                result.classList.add('warning');
            }}
        }}
        result.innerText = msg;
    }}
    </script>
    """
    return html

def generate_low_quality_directories_page(directory_stats, merged_data, report_dir):
    """生成单独的低质量目录页面"""
    # 1. 收集每个低质量目录下所有"较差/极差"URL
    low_quality_dir_urls = {}
    for url, data in merged_data["urls"].items():
        directory = data.get("directory", "未分类")
        quality_level = data.get("quality_level", "")
        if quality_level in ["差", "极差"]:
            if directory not in low_quality_dir_urls:
                low_quality_dir_urls[directory] = []
            low_quality_dir_urls[directory].append(url)

    html = []
    html.append("""
<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>质量分布低的目录 - SEO内容质量报告</title>
    <style>
body {
    font-family: 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
    background: linear-gradient(135deg, #f8fafc 0%, #e8f0fe 100%);
    color: #222;
    margin: 0;
    padding: 0;
}
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 16px;
}
.header {
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(52,152,219,0.08);
    padding: 36px 36px 24px 36px;
    margin-bottom: 36px;
    border-left: 8px solid #e74c3c;
}
.header h1 {
    color: #e74c3c;
    margin: 0 0 12px 0;
    font-size: 2.2em;
    letter-spacing: 1px;
}
.header p {
    color: #888;
    margin: 0;
    font-size: 1.1em;
}
.back-link {
    display: inline-block;
    margin: 24px 0 0 0;
    padding: 12px 22px;
    background: linear-gradient(90deg, #3498db 60%, #6dd5fa 100%);
    color: #fff;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
    font-size: 1.1em;
    box-shadow: 0 2px 8px rgba(52,152,219,0.08);
    transition: background 0.2s, box-shadow 0.2s;
}
.back-link:hover {
    background: linear-gradient(90deg, #217dbb 60%, #3498db 100%);
    box-shadow: 0 4px 16px rgba(52,152,219,0.16);
}
.low-quality-summary {
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 2px 16px rgba(52,152,219,0.06);
    padding: 32px 24px;
}
.low-quality-summary h2 {
    color: #e67e22;
    margin-top: 0;
    font-size: 1.5em;
}
.summary-text {
    color: #555;
    margin-bottom: 18px;
}
.low-quality-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-bottom: 32px;
    font-size: 1.08em;
    background: #f9fbfd;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 8px rgba(52,152,219,0.04);
}
.low-quality-table th, .low-quality-table td {
    padding: 16px 10px;
    text-align: left;
}
.low-quality-table th {
    background: #eaf6ff;
    color: #217dbb;
    font-weight: 700;
    position: sticky;
    top: 0;
    z-index: 2;
}
.low-quality-table tr:nth-child(even) {
    background: #f4f8fb;
}
.low-quality-table tr:hover {
    background: #e3f2fd;
    transition: background 0.2s;
}
.quality-distribution {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}
.quality-label {
    font-size: 0.98em;
    color: #888;
}
.quality-bar-container {
    flex: 1;
    height: 16px;
    background: #e0eafc;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
}
.quality-bar {
    height: 100%;
    transition: width 0.6s cubic-bezier(.4,2,.6,1);
}
.poor-quality-bar {
    background: linear-gradient(90deg, #e74c3c 60%, #f9ca24 100%);
    border-radius: 8px 0 0 8px;
}
.good-quality-bar {
    background: linear-gradient(90deg, #27ae60 60%, #2ecc71 100%);
    border-radius: 0 8px 8px 0;
}
.optimization-target-cell {
    background: #fef9e7;
    border-radius: 8px;
    font-size: 0.98em;
}
.need-optimize {
    color: #e67e22;
    font-weight: bold;
}
.optimization-number {
    color: #e74c3c;
    font-size: 1.2em;
    font-weight: bold;
}
.improvement-tips {
    margin-top: 32px;
    background: #f8f6f0;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 6px rgba(230, 126, 34, 0.06);
}
.improvement-tips h3 {
    color: #e67e22;
    margin-top: 0;
}
.improvement-tips ul {
    margin: 0;
    padding-left: 20px;
}
.improvement-tips li {
    margin-bottom: 8px;
    font-size: 1.05em;
}
@media (max-width: 900px) {
    .container { padding: 16px 2vw; }
    .header, .low-quality-summary { padding: 18px 6px; }
    .low-quality-table th, .low-quality-table td { padding: 10px 4px; }
}

/* 404检查按钮样式 */
.check-404-btn {
    display: inline-block;
    margin: 24px 0 0 24px;
    padding: 12px 22px;
    background: linear-gradient(90deg, #e74c3c 60%, #f39c12 100%);
    color: #fff;
    border: none;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 600;
    font-size: 1.1em;
    box-shadow: 0 2px 8px rgba(231, 76, 60, 0.08);
    transition: background 0.2s, box-shadow 0.2s, transform 0.1s;
    cursor: pointer;
}
.check-404-btn:hover {
    background: linear-gradient(90deg, #c0392b 60%, #d35400 100%);
    box-shadow: 0 4px 16px rgba(231, 76, 60, 0.16);
    transform: translateY(-2px);
}
.check-404-btn:disabled {
    background: #bdc3c7;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
}
.check-404-btn .spinner {
    display: none;
    width: 16px;
    height: 16px;
    margin-right: 8px;
    border: 2px solid #fff;
    border-top: 2px solid transparent;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    vertical-align: middle;
}
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
.check-404-btn.loading .spinner {
    display: inline-block;
}
.check-404-btn.loading span {
    display: none;
}

/* 404状态样式 */
.status-404 {
    color: #e74c3c;
    font-weight: bold;
    background: #fde8e8;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
}
.status-ok {
    color: #27ae60;
    font-weight: bold;
    background: #e8f8e8;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
}
.status-checking {
    color: #f39c12;
    font-weight: bold;
    background: #fef5e7;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>质量分布低的目录</h1>
            <p>本页展示所有内容质量分布低于85%的目录，包含主要问题、改进建议及优化目标。</p>
            <div style="display: flex; align-items: center;">
                <a href="index.html" class="back-link">返回首页</a>
                <button id="check404Btn" class="check-404-btn">
                    <span>一键检查下线</span>
                </button>
            </div>
        </div>""")
    html.append(generate_low_quality_directories_section(directory_stats, merged_data))
    # 注入低质量目录URL数据
    html.append(f"""
    <script>
    window.lowQualityDirUrls = {json.dumps(low_quality_dir_urls, ensure_ascii=False)};
    </script>
    """)
    html.append("""
    </div>
<script>
// ... existing code ...

// 下载功能
function downloadCheckResults(data, filename) {
    try {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log('检查结果已下载:', filename);
    } catch (error) {
        console.error('下载失败:', error);
        // 如果下载失败，显示结果在新窗口
        const newWindow = window.open('', '_blank');
        newWindow.document.write('<pre>' + JSON.stringify(data, null, 2) + '</pre>');
    }
}

// 生成CSV格式的检查结果
function generateCSVReport(directoryStats, detailedResults) {
    try {
        const csvRows = [];
        
        // CSV头部
        csvRows.push('目录,总URL数,可访问,已下线(404),超时,连接错误,其他错误');
        
        // 目录统计
        for (const [directory, stats] of Object.entries(directoryStats)) {
            csvRows.push([
                directory,
                stats.total || 0,
                stats.accessible || 0,
                stats.not_found || 0,
                stats.timeout || 0,
                stats.connection_error || 0,
                stats.error + stats.unknown_error || 0
            ].join(','));
        }
        
        csvRows.push(''); // 空行
        csvRows.push('详细URL检查结果');
        csvRows.push('URL,状态,状态码,消息');
        
        // 详细结果
        if (detailedResults && Array.isArray(detailedResults)) {
            for (const result of detailedResults) {
                csvRows.push([
                    result.url || '',
                    result.status || '',
                    result.status_code || '',
                    (result.message || '').replace(/,/g, ';') // 替换逗号避免CSV格式问题
                ].join(','));
            }
        }
        
        return csvRows.join('\\n');
    } catch (error) {
        console.error('生成CSV失败:', error);
        return null;
    }
}

// 404检查功能 - 使用服务器端API（增强版）
document.getElementById('check404Btn').addEventListener('click', async function() {
    const btn = this;
    const originalText = btn.innerHTML;
    
    // 防止重复点击
    if (btn.disabled) return;
    
    btn.disabled = true;
    btn.classList.add('loading');
    btn.innerHTML = '<div class="spinner"></div>检查中...';

    const dirUrls = window.lowQualityDirUrls || {};
    let checkResults = null;
    
    try {
        // 验证数据
        if (!dirUrls || Object.keys(dirUrls).length === 0) {
            throw new Error('没有找到需要检查的URL数据');
        }
        
        console.log('开始404检查，目录数:', Object.keys(dirUrls).length);
        
        // 调用服务器端404检查API
        const response = await fetch('http://localhost:8080/api/check_404', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                urls: dirUrls
            })
        });

        if (!response.ok) {
            throw new Error(`服务器响应错误: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();
        checkResults = result; // 保存结果用于下载
        
        if (result.success) {
            console.log('404检查成功完成');
            
            // 先清除所有目录优化目标区域的旧统计
            try {
                document.querySelectorAll('.optimization-target-cell .downline-stat').forEach(e => e.remove());
            } catch (e) {
                console.warn('清除旧统计时出错:', e);
            }
            
            const directoryStats = result.directory_stats || {};
            let updatedCount = 0;
            
            // 更新页面优化目标区域
            try {
                const rows = document.querySelectorAll('.low-quality-table tr');
                for (const row of rows) {
                    const dirCell = row.cells && row.cells[0];
                    if (dirCell) {
                        const dirName = dirCell.textContent.trim();
                        const stats = directoryStats[dirName];
                        
                        if (stats) {
                            const optCell = row.cells[row.cells.length - 1];
                            let statDiv = optCell.querySelector('.downline-stat');
                            if (!statDiv) {
                                statDiv = document.createElement('div');
                                statDiv.className = 'downline-stat';
                                statDiv.style.margin = '8px 0 0 0';
                                statDiv.style.fontSize = '0.98em';
                            }
                            
                            const downCount = stats.not_found || 0;
                            const accessibleCount = stats.accessible || 0;
                            const totalChecked = stats.total || 0;
                            
                            // 安全地计算剩余需优化数量
                            let needNum = 0;
                            try {
                                const need85Match = optCell.innerHTML.match(/达到85%需优化:<\\/strong>\\s*<span[^>]*>(\\d+)<\\/span>/);
                                needNum = need85Match ? parseInt(need85Match[1]) : 0;
                            } catch (e) {
                                console.warn('解析优化目标数量时出错:', e);
                            }
                            
                            let remain = Math.max(needNum - downCount, 0);
                            
                            statDiv.innerHTML = `
                                <div style="margin-top: 8px; padding: 8px; background: #f8f9fa; border-radius: 4px; border-left: 3px solid #17a2b8;">
                                    <div style="margin-bottom: 4px;"><span style='color:#e74c3c; font-weight: bold;'>已下线: ${downCount}条</span></div>
                                    <div style="margin-bottom: 4px;"><span style='color:#27ae60; font-weight: bold;'>可访问: ${accessibleCount}条</span></div>
                                    <div><span style='color:#e67e22; font-weight: bold;'>剩余需优化: ${remain}条</span></div>
                                </div>
                            `;
                            optCell.appendChild(statDiv);
                            updatedCount++;
                        }
                    }
                }
            } catch (e) {
                console.error('更新页面统计时出错:', e);
            }
            
            // 显示总体统计和下载按钮
            const totalStats = result.summary || {};
            const total404 = totalStats.total_404 || 0;
            const totalUrls = totalStats.total_urls || 0;
            
            btn.innerHTML = `
                <span>检查完成</span>
                <div style="font-size: 0.9em; margin-top: 4px;">
                    ${total404}个404 / ${totalUrls}个URL
                </div>
            `;
            
            // 自动下载检查结果
            try {
                const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
                const jsonFilename = `404检查结果_${timestamp}.json`;
                downloadCheckResults(result, jsonFilename);
                
                // 同时生成CSV格式
                const csvContent = generateCSVReport(directoryStats, result.detailed_results);
                if (csvContent) {
                    const csvBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const csvUrl = URL.createObjectURL(csvBlob);
                    const csvLink = document.createElement('a');
                    csvLink.href = csvUrl;
                    csvLink.download = `404检查结果_${timestamp}.csv`;
                    document.body.appendChild(csvLink);
                    csvLink.click();
                    document.body.removeChild(csvLink);
                    URL.revokeObjectURL(csvUrl);
                }
                
                // 显示下载成功提示
                const downloadMsg = document.createElement('div');
                downloadMsg.style.cssText = `
                    position: fixed; top: 20px; right: 20px; z-index: 10000;
                    background: #28a745; color: white; padding: 12px 20px;
                    border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    font-size: 14px; font-weight: bold;
                `;
                downloadMsg.textContent = '✅ 检查结果已自动下载 (JSON + CSV)';
                document.body.appendChild(downloadMsg);
                
                setTimeout(() => {
                    if (downloadMsg.parentNode) {
                        downloadMsg.parentNode.removeChild(downloadMsg);
                    }
                }, 5000);
                
            } catch (downloadError) {
                console.error('下载结果时出错:', downloadError);
            }
            
            // 5秒后恢复按钮
            setTimeout(() => {
                btn.innerHTML = '<span>重新检查下线</span>';
            }, 5000);
            
            console.log(`页面更新完成，共更新了 ${updatedCount} 个目录的统计信息`);
            
        } else {
            throw new Error(result.error || '404检查失败');
        }
        
    } catch (error) {
        console.error('404检查出错:', error);
        btn.innerHTML = '<span>检查失败，点击重试</span>';
        
        // 显示友好的错误提示
        const errorMsg = document.createElement('div');
        errorMsg.style.cssText = `
            position: fixed; top: 20px; right: 20px; z-index: 10000;
            background: #dc3545; color: white; padding: 12px 20px;
            border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            font-size: 14px; max-width: 300px;
        `;
        
        let errorText = '404检查失败：' + error.message;
        if (error.message.includes('fetch')) {
            errorText += '\\n\\n请确保Flask应用正在运行 (http://localhost:8080)';
        }
        
        errorMsg.textContent = errorText;
        document.body.appendChild(errorMsg);
        
        setTimeout(() => {
            if (errorMsg.parentNode) {
                errorMsg.parentNode.removeChild(errorMsg);
            }
        }, 8000);
        
        // 5秒后恢复按钮
        setTimeout(() => {
            btn.innerHTML = originalText;
        }, 5000);
    } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
    }
});
// ... existing code ...
</script>

</body>
</html>
""")
    html_path = os.path.join(report_dir, "low_quality_directories.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(''.join(html))
    return html_path

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='SEO内容质量综合报告生成工具')
    parser.add_argument('-s', '--seo', help='SEO内容重复分析JSON文件路径（可选，默认自动查找最新的）')
    parser.add_argument('-q', '--quality', help='文章质量检测CSV文件路径（可选，默认自动查找）')
    parser.add_argument('-o', '--output', default=REPORT_DIR, help='输出目录路径')
    
    args = parser.parse_args()
    
    # 如果没有指定SEO文件，自动查找
    seo_json_path = args.seo
    if not seo_json_path:
        logger.info("未指定SEO分析文件，自动查找最新文件...")
        seo_json_path = find_seo_json()
        if not seo_json_path:
            logger.error("无法找到SEO分析文件，请手动指定 -s/--seo 参数")
            return 1
    
    # 如果没有指定质量检测文件，自动查找
    quality_csv_path = args.quality
    if not quality_csv_path:
        logger.info("未指定文章质量检测文件，自动查找...")
        quality_csv_path = find_quality_csv()
        if not quality_csv_path:
            logger.error("无法找到文章质量检测文件，请手动指定 -q/--quality 参数")
            return 1
    
    # 加载数据
    logger.info(f"正在加载SEO数据: {seo_json_path}")
    seo_data = load_seo_data(seo_json_path)
    
    logger.info(f"正在加载质量检测数据: {quality_csv_path}")
    quality_data = load_quality_data(quality_csv_path)
    
    # 合并数据
    logger.info("正在合并数据...")
    merged_data = merge_data(seo_data, quality_data)
    
    if merged_data:
        # 生成报告
        logger.info("正在生成综合报告...")
        report_dir = generate_html_report(merged_data, args.output)
        
        if report_dir:
            logger.info(f"处理完成！综合报告已保存到: {report_dir}")
            
            # 打印报告URL以便直接访问
            index_path = os.path.join(report_dir, "index.html")
            file_url = f"file://{index_path}"
            logger.info(f"报告URL: {file_url}")
            
            # 尝试自动打开报告
            try:
                import webbrowser
                webbrowser.open(file_url)
                logger.info("已自动打开报告")
            except:
                logger.info("无法自动打开报告，请手动访问上述URL")
            
            return 0
    
    logger.error("生成报告失败！")
    return 1

if __name__ == "__main__":
    sys.exit(main()) 