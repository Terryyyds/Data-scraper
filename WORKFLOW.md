# 工作流程文档

本文档描述完整的爬虫工作流程，从初始化到数据导出。

## 1. 环境准备

### 1.1 系统要求

- Python 3.8+
- 2GB+ RAM
- 1GB+ 磁盘空间
- 网络连接

### 1.2 安装步骤

```bash
# 克隆或下载代码
cd PG533

# 运行安装脚本
./setup.sh

# 或手动安装
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 1.3 配置

1. 复制配置模板：
```bash
cp env.example .env
```

2. 编辑 `.env` 文件，调整参数：
```bash
QPS_LIMIT=0.5          # 降低以更保守
BURST=2                # 并发数
HEADLESS=true          # 后台运行
ALERT_SINK=...         # Slack webhook (可选)
```

## 2. 首次完整抓取

### 2.1 执行完整抓取

```bash
# 激活环境
source venv/bin/activate

# 运行完整抓取
python main.py --mode full --headless

# 或使用自定义参数
python main.py \
  --mode full \
  --headless \
  --qps 0.3 \
  --burst 1 \
  --data-dir ./data
```

### 2.2 工作流程

```
启动浏览器
    ↓
访问列表页 (m.ydl.com/ask)
    ↓
提取 preloadedState
    ↓
解析帖子列表
    ↓
├─→ 遍历每个帖子
│      ↓
│   访问详情页
│      ↓
│   提取完整数据（帖子+评论）
│      ↓
│   应用限速 (QPS)
│      ↓
│   保存到 data/posts/
│      ↓
│   更新检查点
│      └─→ 返回
│
↓
生成统计报告
    ↓
导出数据集 (dataset.jsonl)
    ↓
关闭浏览器
```

### 2.3 监控输出

实时日志输出：

```
2025-11-03T15:30:00 [info] scrape_started mode=full target=https://m.ydl.com/ask
2025-11-03T15:30:01 [info] browser_started
2025-11-03T15:30:02 [info] post_parsed post_id=970141 comments=1
2025-11-03T15:30:04 [info] post_saved post_id=970141 filepath=data/posts/970141_a3b2c1d5.json
...
2025-11-03T15:35:00 [info] scrape_completed posts_count=50
2025-11-03T15:35:01 [info] posts_saved count=48
2025-11-03T15:35:02 [info] dataset_exported path=data/dataset.jsonl
```

### 2.4 预期结果

```
data/
├── posts/
│   ├── 970141_a3b2c1d5.json
│   ├── 970140_b4c3d2e6.json
│   └── ...
├── raw/
│   ├── 970141_raw.json
│   └── ...
├── checkpoint.json
├── seen_ids.txt
└── dataset.jsonl

logs/
└── metrics.jsonl
```

## 3. 增量更新

### 3.1 执行增量抓取

```bash
# 基于上次检查点，只抓取新内容
python main.py --mode incremental --headless
```

### 3.2 工作流程

```
加载检查点
    ↓
读取 last_post_id
    ↓
访问列表页
    ↓
提取新帖子 (id > last_post_id)
    ↓
跳过已抓取帖子 (基于 seen_ids.txt)
    ↓
仅抓取新帖子详情
    ↓
更新检查点
    ↓
追加到数据集
```

### 3.3 调度策略

**方式 1: Cron 定时任务**

```bash
# 每30分钟运行一次增量更新
# crontab -e
*/30 * * * * cd /path/to/PG533 && ./venv/bin/python main.py --mode incremental --headless >> logs/cron.log 2>&1
```

**方式 2: Systemd Timer**

创建 `/etc/systemd/system/ydl-scraper.service`:

```ini
[Unit]
Description=YDL Incremental Scraper

[Service]
Type=oneshot
WorkingDirectory=/path/to/PG533
ExecStart=/path/to/PG533/venv/bin/python main.py --mode incremental --headless
User=your_user
```

创建 `/etc/systemd/system/ydl-scraper.timer`:

```ini
[Unit]
Description=Run YDL scraper every 30 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min

[Install]
WantedBy=timers.target
```

启用：

```bash
sudo systemctl enable ydl-scraper.timer
sudo systemctl start ydl-scraper.timer
```

**方式 3: Python 脚本循环**

```python
import asyncio
from datetime import datetime

async def scheduled_scrape():
    while True:
        print(f"Starting scrape at {datetime.now()}")
        # Run main_scrape
        await main_scrape(mode="incremental")
        
        # Wait 30 minutes
        await asyncio.sleep(1800)

asyncio.run(scheduled_scrape())
```

## 4. 数据处理流程

### 4.1 去重机制

```python
# 1. 基于内容的 SHA1 指纹
unique_id = sha1(f"{post_id}_{content[:100]}_{publish_time}")

# 2. 检查 seen_ids.txt
if unique_id in seen_ids:
    skip()

# 3. 保存时记录
seen_ids.add(unique_id)
```

### 4.2 数据验证

每个帖子保存前自动验证：

- ✅ 必需字段存在
- ✅ 数据类型正确
- ✅ 关系完整（评论关联到帖子）
- ✅ URL 可访问
- ✅ 时间格式有效

### 4.3 错误处理

```
请求失败
    ↓
重试 (最多3次)
    ↓
指数退避 (1s → 2s → 4s)
    ↓
仍失败？
    ↓
记录错误
    ↓
发送告警 (如配置)
    ↓
继续下一个
```

## 5. 监控与告警

### 5.1 健康检查

自动检测异常并告警：

| 条件 | 严重程度 | 动作 |
|------|---------|------|
| 成功率 < 50% | Critical | 立即告警 + 停止 |
| 成功率 < 80% | Warning | 发送告警 |
| 遇到 403/429 | Critical | 立即告警 + 停止 |
| 空页 > 5 | Warning | 发送告警 |
| 错误率 > 10% | Warning | 发送告警 |

### 5.2 实时指标

```json
{
  "timestamp": "2025-11-03T15:30:00",
  "total_posts": 50,
  "total_comments": 125,
  "errors": 2,
  "success_rate": 96.0,
  "duration_seconds": 300,
  "http_status_codes": {
    "200": 48,
    "404": 2
  }
}
```

### 5.3 告警示例

**Slack 通知**:

```
🔔 INFO: Scraping completed: 48 posts
  • mode: incremental
  • posts: 48
  • success_rate: 96.0%
```

**Critical 告警**:

```
🔥 CRITICAL: Access restricted - possible rate limiting
  • http_codes: {"403": 5, "429": 2}
```

## 6. 数据导出与分析

### 6.1 导出格式

**JSONL (默认)**:

```bash
python main.py --export-only
# 输出: data/dataset.jsonl
```

每行一个 JSON 对象，适合流式处理：

```jsonl
{"post_id": 970141, "username": "...", "content": "...", "comments": [...]}
{"post_id": 970140, "username": "...", "content": "...", "comments": [...]}
```

**CSV (自定义)**:

```python
import json
import csv

posts = []
with open('data/dataset.jsonl') as f:
    for line in f:
        posts.append(json.loads(line))

with open('posts.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['post_id', 'username', 'content', ...])
    writer.writeheader()
    for post in posts:
        writer.writerow({
            'post_id': post['post_id'],
            'username': post['username'],
            'content': post['content'],
            # ...
        })
```

### 6.2 数据分析示例

**统计分析**:

```python
import json
from collections import Counter

posts = []
with open('data/dataset.jsonl') as f:
    for line in f:
        posts.append(json.loads(line))

# 用户活跃度
user_counts = Counter(p['username'] for p in posts)
print("Top 10 active users:", user_counts.most_common(10))

# 话题分布
topic_counts = Counter(p['topic_title'] for p in posts if p['topic_title'])
print("Popular topics:", topic_counts.most_common(10))

# 评论统计
avg_comments = sum(len(p['comments']) for p in posts) / len(posts)
print(f"Average comments per post: {avg_comments:.2f}")
```

## 7. 故障恢复

### 7.1 中断恢复

爬虫支持断点续传：

1. 检查点每次抓取后自动保存
2. 中断后重新运行，自动从上次位置继续
3. 已抓取数据不会重复

```bash
# 即使中途 Ctrl+C，数据也已保存
python main.py --mode incremental
# ... 中断 ...

# 重新运行，自动继续
python main.py --mode incremental
```

### 7.2 数据恢复

如果 `checkpoint.json` 损坏：

```bash
# 手动重建检查点
python -c "
import json
from pathlib import Path

posts = sorted(Path('data/posts').glob('*.json'))
if posts:
    last_post = json.loads(posts[-1].read_text())
    checkpoint = {
        'last_post_id': last_post['post_id'],
        'last_post_time': last_post['publish_time'],
        'total_posts_scraped': len(posts)
    }
    Path('data/checkpoint.json').write_text(json.dumps(checkpoint, indent=2))
    print('Checkpoint rebuilt!')
"
```

### 7.3 日志分析

查看错误日志：

```bash
# 查看所有错误
grep "error" logs/metrics.jsonl

# 统计 HTTP 状态码
jq -r '.http_status_codes' logs/metrics.jsonl | jq -s 'add'

# 查看成功率趋势
jq -r '[.timestamp, .success_rate] | @csv' logs/metrics.jsonl
```

## 8. 最佳实践

### 8.1 生产环境配置

```bash
# .env for production
QPS_LIMIT=0.3          # 更保守
BURST=1                # 单线程
RETRY=5                # 更多重试
HEADLESS=true          # 后台运行
ALERT_SINK=...         # 必须配置告警
```

### 8.2 监控检查清单

- [ ] 配置 Slack/Discord 告警
- [ ] 设置 Cron 定时任务
- [ ] 监控磁盘空间 (`df -h`)
- [ ] 定期检查日志 (`tail -f logs/metrics.jsonl`)
- [ ] 验证数据质量（抽样检查）
- [ ] 备份数据到云存储

### 8.3 性能优化

**如果抓取太慢**:

1. 适当提高 QPS（风险：可能被限流）
2. 增加 BURST（风险：并发过多可能触发保护）
3. 使用多台机器分布式抓取
4. 仅抓取关键字段，跳过不重要数据

**如果被限流**:

1. 立即降低 QPS (`--qps 0.2`)
2. 增加退避时间
3. 更换 IP（使用代理池）
4. 暂停一段时间后恢复

### 8.4 数据质量保证

```bash
# 定期验证数据
python -c "
import json
from pathlib import Path

posts = Path('data/posts').glob('*.json')
issues = []

for post_file in posts:
    post = json.loads(post_file.read_text())
    
    # 检查必需字段
    if not post.get('post_id'):
        issues.append(f'{post_file}: missing post_id')
    if not post.get('content'):
        issues.append(f'{post_file}: missing content')
    
    # 检查评论完整性
    for comment in post.get('comments', []):
        if not comment.get('comment_content'):
            issues.append(f'{post_file}: comment missing content')

if issues:
    print('Issues found:')
    for issue in issues[:10]:
        print(f'  - {issue}')
else:
    print('✅ All data validated!')
"
```

## 9. 常见使用场景

### 场景 1: 每日数据同步

```bash
#!/bin/bash
# daily_sync.sh

cd /path/to/PG533
source venv/bin/activate

# 增量抓取
python main.py --mode incremental --headless

# 导出到云存储
aws s3 sync data/ s3://my-bucket/ydl-data/$(date +%Y-%m-%d)/

# 生成日报
python -c "
import json
posts = []
with open('data/dataset.jsonl') as f:
    for line in f:
        posts.append(json.loads(line))

print(f'Total posts: {len(posts)}')
print(f'Today: {sum(1 for p in posts if \"今天\" in p[\"publish_time\"])}')
"
```

### 场景 2: 关键词监控

```bash
# 监控特定关键词的帖子
python -c "
import json

keywords = ['焦虑', '抑郁', '压力']

with open('data/dataset.jsonl') as f:
    for line in f:
        post = json.loads(line)
        if any(kw in post['content'] for kw in keywords):
            print(f'{post[\"post_id\"]}: {post[\"content\"][:50]}...')
"
```

### 场景 3: 用户行为分析

```python
import json
from datetime import datetime

users = {}

with open('data/dataset.jsonl') as f:
    for line in f:
        post = json.loads(line)
        username = post['username']
        
        if username not in users:
            users[username] = {
                'posts': 0,
                'comments_received': 0,
                'topics': set()
            }
        
        users[username]['posts'] += 1
        users[username]['comments_received'] += len(post['comments'])
        if post.get('topic_title'):
            users[username]['topics'].add(post['topic_title'])

# 找出最活跃用户
top_users = sorted(users.items(), key=lambda x: x[1]['posts'], reverse=True)[:10]

for username, stats in top_users:
    print(f"{username}: {stats['posts']} posts, {stats['comments_received']} comments")
```

---

**持续改进**: 本工作流程会根据实际使用经验不断优化。欢迎提交改进建议！

