# 统一SEO分析平台

一个集成了文章质量检测、内容重复分析和SEO综合评分的工业级Web分析平台。

## 📋 功能特性

### 1. 文章质量分析
- 基于百度千飞AI的暗示性语言检测
- 段落级内容分析
- 智能评分系统（0-10分）
- 三级质量评估（轻微/中等/强烈）

### 2. 内容重复检测
- 基于TF-IDF和余弦相似度的重复检测
- 中文分词支持（jieba）
- 批量URL相似度分析
- 可配置重复度阈值

### 3. SEO综合分析
- 整合质量和重复度的综合评分
- 四级质量等级（优/良/差/极差）
- 智能优化建议生成
- 批量分析统计

## 🚀 快速开始

### 环境要求
- Python 3.8+
- pip

### 安装步骤

1. **克隆项目**
```bash
cd seo_unified_platform
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**（可选）
```bash
export QIANFAN_ACCESS_KEY="your_access_key"
export QIANFAN_SECRET_KEY="your_secret_key"
```

4. **运行应用**
```bash
python app.py
```

5. **访问平台**
```
http://localhost:5000
```

## 📁 项目结构

```
seo_unified_platform/
├── app.py                      # Flask主应用
├── config/
│   ├── __init__.py
│   └── settings.py             # 配置文件
├── core/
│   ├── __init__.py
│   ├── base_analyzer.py        # 基础分析器
│   ├── quality_analyzer.py     # 质量分析器
│   ├── duplicate_analyzer.py   # 重复检测分析器
│   └── seo_analyzer.py         # SEO综合分析器
├── templates/
│   └── dashboard.html          # 前端界面
├── uploads/                    # 上传文件目录
├── reports/                    # 报告输出目录
├── logs/                       # 日志目录
├── requirements.txt            # 依赖列表
└── README.md                   # 项目说明
```

## 🔌 API接口

### 1. 健康检查
```
GET /api/health
```

### 2. 文章质量分析
```
POST /api/analyze/quality
Content-Type: application/json

{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ]
}
```

### 3. 内容重复检测
```
POST /api/analyze/duplicate
Content-Type: application/json

{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ]
}
```

### 4. SEO综合分析
```
POST /api/analyze/seo
Content-Type: application/json

{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ]
}
```

### 5. 综合分析（支持多种分析类型）
```
POST /api/analyze/comprehensive
Content-Type: application/json

{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ],
  "types": ["quality", "duplicate", "seo"]
}
```

## ⚙️ 配置说明

### 基础配置（config/settings.py）

- **DUPLICATE_THRESHOLD**: 重复率阈值（默认：15.0%）
- **SIMILARITY_THRESHOLD**: 相似度阈值（默认：0.85）
- **IMPLICIT_LANGUAGE_WEIGHT**: 暗示性语言权重（默认：0.3）
- **DUPLICATE_CONTENT_WEIGHT**: 内容重复权重（默认：0.7）
- **MAX_WORKERS**: 并发处理线程数（默认：4）
- **REQUEST_TIMEOUT**: 请求超时时间（默认：15秒）

## 📊 评分规则

### SEO综合评分计算

```
综合评分 = 重复内容权重 × (100 - 重复率) + 暗示语言权重 × (100 - 暗示分数 × 10)
```

### 质量等级划分

- **优**: 评分 >= 85
- **良**: 评分 >= 70
- **差**: 评分 >= 50
- **极差**: 评分 < 50

## 🔧 开发说明

### 添加新的分析器

1. 继承`BaseAnalyzer`类
2. 实现`analyze()`和`batch_analyze()`方法
3. 在`app.py`中注册新路由

### 扩展前端功能

编辑`templates/dashboard.html`，添加新的UI组件和JavaScript函数。

## 📝 注意事项

1. **千帆API**: 质量分析需要配置百度千帆API密钥，否则将使用规则引擎作为备选方案
2. **并发限制**: 建议根据服务器性能调整`MAX_WORKERS`参数
3. **超时设置**: 网络较慢时，可增加`REQUEST_TIMEOUT`值
4. **日志管理**: 定期清理`logs/`目录下的日志文件

## 🚧 生产部署

### 使用Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用Docker

```bash
docker build -t seo-platform .
docker run -p 5000:5000 -e QIANFAN_ACCESS_KEY=xxx -e QIANFAN_SECRET_KEY=xxx seo-platform
```

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📄 许可证

MIT License

## 👥 贡献者

- 基于三个参考SEO项目整合开发
- 使用Claude Code AI辅助生成

## 📞 支持

如有问题或建议，请提交Issue。
