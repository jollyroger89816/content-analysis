# 内容质量分析平台

统一的SEO内容分析工具，整合文章质量检测、重复内容检测和综合报告生成。

## 功能

- ✅ 文章质量检测（千帆AI + 规则引擎）
- ✅ 重复内容检测（TF-IDF + 余弦相似度）
- ✅ 综合HTML报告生成
- ✅ 并行处理，效率提升48%

## 快速开始

### 安装

```bash
cd generated_output/seo_unified_platform
pip install -r requirements.txt
```

### 运行

```bash
# 准备URL文件
cat > urls.txt << EOF
https://example.com/page1.html
https://example.com/page2.html
EOF

# 运行分析
cd generated_output
python full_seo_analysis.py urls.txt
```

报告自动生成到 `reports/` 目录并在浏览器中打开。

## 配置（可选）

如需使用AI质量检测，配置千帆API密钥：

```bash
export QIANFAN_ACCESS_KEY="你的密钥"
export QIANFAN_SECRET_KEY="你的密钥"
```

## 项目结构

```
content_analysis/
├── generated_output/          # 核心代码
│   ├── seo_unified_platform/  # 新平台
│   └── full_seo_analysis.py   # 主脚本
├── docs/                      # 文档
└── reports/                   # 报告输出
```

## 配置说明

核心配置：`generated_output/seo_unified_platform/config/settings.py`

```python
DUPLICATE_THRESHOLD = 15.0      # 重复率阈值(%)
SIMILARITY_THRESHOLD = 0.65     # 相似度阈值
MAX_WORKERS = 4                 # 并发数
```

## 质量等级

- **优**: 无暗示性语言，重复率<15%
- **良**: 轻微暗示或低重复率
- **差**: 中等暗示或中等重复率
- **极差**: 强烈暗示或高重复率

## 许可证

MIT License
