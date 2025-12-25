# 统一SEO分析平台 - 架构设计文档

生成时间: 2024-12-25
版本: 1.0.0

## 1. 系统架构概述

### 1.1 架构原则
- **模块化设计**: 每个分析器独立实现，易于扩展
- **单一职责**: 每个模块只负责一个功能
- **依赖倒置**: 高层模块不依赖低层模块，都依赖抽象
- **开闭原则**: 对扩展开放，对修改关闭

### 1.2 技术栈选择

| 层次 | 技术选型 | 理由 |
|------|---------|------|
| Web框架 | Flask | 轻量级、灵活、参考项目已使用 |
| 前端 | Bootstrap + Chart.js | 响应式设计、组件丰富 |
| 数据处理 | NumPy, Pandas | 高效的数值计算 |
| NLP | jieba, scikit-learn | 中文分词、TF-IDF |
| AI模型 | 百度千帆API | 参考项目已集成 |
| 数据库 | SQLite/PostgreSQL | 轻量级/生产级 |
| 缓存 | Redis | 提高性能 |
| 任务队列 | Celery | 异步处理 |

### 1.3 系统分层架构

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (Flask Routes + HTML Templates)        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│  (QualityAnalyzer, DuplicateAnalyzer,   │
│   SEOAnalyzer)                          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Data Access Layer               │
│  (BaseAnalyzer, Utils, Database)        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         External Services Layer         │
│  (Qianfan API, HTTP Requests)           │
└─────────────────────────────────────────┘
```

## 2. 核心模块设计

### 2.1 分析器基类 (BaseAnalyzer)

**职责**:
- 定义分析器接口
- 提供通用方法（内容获取、日期提取等）
- 统一错误处理

**关键方法**:
```python
class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(url: str) -> Dict: pass

    @abstractmethod
    def batch_analyze(urls: List[str]) -> Dict: pass

    def fetch_content(url: str) -> Tuple: pass
    def extract_publish_date(soup, url: str) -> str: pass
```

**设计模式**: 模板方法模式

### 2.2 质量分析器 (QualityAnalyzer)

**职责**:
- URL内容提取
- 段落分析
- AI驱动的暗示性语言检测

**核心算法**:
```
输入: URL列表
  ↓
提取HTML内容 (BeautifulSoup)
  ↓
段落提取和清理
  ↓
AI分析 (千帆API)
  ↓
评分计算 (0-10分)
  ↓
输出: 质量分析结果
```

**评分规则**:
- 强烈暗示: 7分
- 中等暗示: 5分
- 轻微暗示: 3分
- 无暗示: 0分

**备选方案**: 规则引擎（关键词匹配）

### 2.3 重复检测分析器 (DuplicateAnalyzer)

**职责**:
- 批量URL内容提取
- 相似度计算
- 重复度统计

**核心算法**:
```
输入: URL列表 (n个)
  ↓
提取所有段落 (m个)
  ↓
中文分词 (jieba)
  ↓
TF-IDF向量化
  ↓
计算余弦相似度矩阵 (m×m)
  ↓
检测重复段落 (相似度 > 0.85)
  ↓
计算每个URL的重复率
  ↓
输出: 重复度分析结果
```

**相似度计算**:
```python
# TF-IDF向量化
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(tokenized_texts)

# 余弦相似度
similarity_matrix = cosine_similarity(tfidf_matrix)
```

**重复率计算**:
```
重复率 = (重复段落数 / 总段落数) × 100%
```

### 2.4 SEO综合分析器 (SEOAnalyzer)

**职责**:
- 整合质量和重复度数据
- 综合评分计算
- 优化建议生成

**评分算法**:
```python
# 1. 重复内容评分 (0-100)
duplicate_score = max(0, 100 - duplicate_rate)

# 2. 暗示性语言评分 (0-100)
implicit_score = max(0, 100 - implicit_raw_score * 10)

# 3. 加权平均
seo_score = (
    0.7 × duplicate_score +
    0.3 × implicit_score
)
```

**质量等级**:
- 优: score >= 85
- 良: score >= 70
- 差: score >= 50
- 极差: score < 50

## 3. 数据流设计

### 3.1 单URL分析流程

```
用户请求
  ↓
[API Gateway]
  ↓
┌─────────────┐  ┌──────────────┐  ┌─────────────┐
│ Quality     │  │ Duplicate    │  │ SEO         │
│ Analyzer    │  │ Analyzer     │  │ Analyzer    │
└─────────────┘  └──────────────┘  └─────────────┘
       ↓                 ↓                  ↓
    [Quality Data]  [Duplicate Data]  [Merged Data]
                            ↓
                     [Score Calculator]
                            ↓
                    [Recommendations]
                            ↓
                      [Response]
```

### 3.2 批量分析流程

```
批量URL列表
  ↓
[线程池并行处理]
  ↓
┌─────────────────────────────────┐
│  ThreadPoolExecutor (4 workers) │
└─────────────────────────────────┘
  ↓          ↓          ↓
Worker1    Worker2    Worker3
  ↓          ↓          ↓
[结果聚合]
  ↓
[统计计算]
  ↓
[返回完整结果]
```

## 4. API设计

### 4.1 RESTful API规范

| 端点 | 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|------|
| /api/health | GET | 健康检查 | - | 状态信息 |
| /api/analyze/quality | POST | 质量分析 | {urls: []} | 分析结果 |
| /api/analyze/duplicate | POST | 重复检测 | {urls: []} | 重复度结果 |
| /api/analyze/seo | POST | SEO分析 | {urls: []} | 综合评分 |
| /api/analyze/comprehensive | POST | 综合分析 | {urls: [], types: []} | 完整结果 |

### 4.2 响应格式

**成功响应**:
```json
{
  "success": true,
  "results": {...},
  "timestamp": "2024-12-25T10:00:00"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "错误信息"
}
```

## 5. 数据模型

### 5.1 质量分析结果
```python
{
    "url": str,
    "success": bool,
    "paragraphs_count": int,
    "content_preview": str,
    "analysis": {
        "has_implicit": bool,
        "score": int,
        "level": str,  # 轻微/中等/强烈
        "result": str
    }
}
```

### 5.2 重复度分析结果
```python
{
    "url_data": {
        url: {
            "url": str,
            "success": bool,
            "publish_date": str,
            "total_paragraphs": int,
            "paragraphs": []
        }
    },
    "similarities": {
        "duplicate_rates": {url: float},
        "duplicate_paragraphs": {url: []},
        "similarity_matrix": []
    },
    "stats": {
        "total_urls": int,
        "high_duplicate_count": int,
        "avg_duplicate_rate": float
    }
}
```

### 5.3 SEO综合分析结果
```python
{
    "url": str,
    "success": bool,
    "quality_level": str,  # 优/良/差/极差
    "seo_score": float,
    "quality_info": {...},
    "duplicate_info": {...},
    "recommendations": [],
    "analyzed_at": str
}
```

## 6. 性能优化

### 6.1 并发处理
- 使用ThreadPoolExecutor进行URL并发抓取
- 默认4个工作线程，可配置
- 避免GIL限制，使用多线程而非多进程

### 6.2 缓存策略
- URL内容缓存（Redis, 1小时）
- AI分析结果缓存（Redis, 24小时）
- TF-IDF模型缓存（内存）

### 6.3 数据库优化
- 创建索引（url, timestamp）
- 批量插入而非逐条插入
- 定期清理过期数据

## 7. 安全设计

### 7.1 输入验证
- URL格式验证
- 限制URL数量（最多100个）
- 防止恶意URL注入

### 7.2 访问控制
- API频率限制（每分钟最多10次）
- IP白名单（可选）
- 认证Token（未来）

### 7.3 数据安全
- SQL参数化查询
- XSS过滤
- HTTPS加密传输

## 8. 扩展性设计

### 8.1 添加新分析器
```python
# 继承BaseAnalyzer
class NewAnalyzer(BaseAnalyzer):
    def analyze(self, url):
        # 实现分析逻辑
        pass

    def batch_analyze(self, urls):
        # 实现批量分析
        pass
```

### 8.2 支持新AI模型
```python
# 在配置文件添加新模型
NEW_AI_MODEL = 'model-name'
NEW_AI_API_KEY = 'key'

# 在分析器中添加新方法
def _analyze_with_new_model(self, text):
    # 调用新模型
    pass
```

### 8.3 插件式架构
- 每个分析器作为独立插件
- 动态加载分析器
- 配置文件驱动

## 9. 部署架构

### 9.1 开发环境
```
Flask Development Server
- 单进程
- Debug模式
- SQLite数据库
```

### 9.2 生产环境
```
Nginx (反向代理)
  ↓
Gunicorn (WSGI服务器)
  ↓
Flask App (多worker)
  ↓
PostgreSQL + Redis + Celery
```

### 9.3 高可用架构
```
[Load Balancer]
  ↓
[Web Server 1] [Web Server 2]
  ↓              ↓
[Shared Database]
[Redis Cluster]
[Celery Cluster]
```

## 10. 监控和日志

### 10.1 日志级别
- DEBUG: 调试信息
- INFO: 一般信息
- WARNING: 警告信息
- ERROR: 错误信息
- CRITICAL: 严重错误

### 10.2 日志内容
- 请求信息（URL, IP, 时间）
- 分析进度
- 错误堆栈
- 性能指标

### 10.3 监控指标
- API响应时间
- 错误率
- 并发数
- CPU/内存使用率

## 11. 技术债务

### 11.1 已知问题
1. 缺少单元测试
2. 未实现异步任务队列
3. 缺少用户认证
4. 性能优化空间

### 11.2 改进计划
1. 添加完整的单元测试和集成测试
2. 使用Celery实现异步任务
3. 添加JWT认证
4. 优化数据库查询和缓存策略

## 12. 参考资料

### 12.1 参考项目
- 文章质量检测 (质量检测_最终版.py)
- 线上内容重复问题 (seo_jieba_optimized.py)
- SEO内容质量报告 (generate_comprehensive_report.py)

### 12.2 技术文档
- Flask官方文档: https://flask.palletsprojects.com/
- scikit-learn文档: https://scikit-learn.org/
- jieba分词: https://github.com/fxsjy/jieba
- 百度千帆SDK: https://cloud.baidu.com/product/wenxinworkshop

### 12.3 设计模式
- 模板方法模式: BaseAnalyzer
- 工厂模式: create_app()
- 策略模式: 多种分析算法
