# 本地配置指南

## API密钥配置（可选）

这个项目可以不配置API密钥运行（会使用规则引擎），但配置千帆API后质量检测会更准确。

### 方法1: 系统环境变量（推荐）

```bash
# 编辑 shell 配置文件
nano ~/.zshrc  # 或 ~/.bash_profile

# 添加以下内容
export QIANFAN_ACCESS_KEY="你的千帆Access Key"
export QIANFAN_SECRET_KEY="你的千帆Secret Key"

# 保存后重新加载
source ~/.zshrc
```

### 方法2: 临时环境变量

```bash
# 每次运行前设置
export QIANFAN_ACCESS_KEY="你的密钥"
export QIANFAN_SECRET_KEY="你的密钥"

# 或者一行命令
QIANFAN_ACCESS_KEY="你的密钥" \
QIANFAN_SECRET_KEY="你的密钥" \
python full_seo_analysis.py urls.txt
```

### 方法3: .env 文件（本地配置，不上传）

```bash
cd /Users/tang/Desktop/python/content_analysis

# 创建 .env 文件
cat > .env << EOF
QIANFAN_ACCESS_KEY=你的千帆Access Key
QIANFAN_SECRET_KEY=你的千帆Secret Key
EOF

# 加载环境变量
export $(cat .env | xargs)

# 然后运行
python generated_output/full_seo_analysis.py urls.txt
```

### 验证配置

```bash
# 检查环境变量是否设置成功
echo $QIANFAN_ACCESS_KEY
echo $QIANFAN_SECRET_KEY

# 如果有输出，说明配置成功
```

## 不配置API密钥也能运行

如果不配置千帆API密钥：
- ✅ 重复检测：正常工作（不需要API）
- ✅ 质量检测：使用规则引擎（基于关键词匹配）
- ⚠️ AI分析：不可用（会回退到规则引擎）

## 上传Git后

- ✅ **本地功能**：完全不受影响
- ✅ **API密钥**：安全，不会上传
- ✅ **其他人使用**：需要自己配置密钥
- ✅ **开源安全**：完全符合安全规范

## 获取千帆API密钥

1. 访问：https://cloud.baidu.com/product/wenxinworkshop
2. 注册/登录百度账号
3. 进入"千帆大模型平台"
4. 创建应用获取 API Key 和 Secret Key
