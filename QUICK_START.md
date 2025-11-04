# 快速开始指南

## 🎉 数据已成功采集！

已成功采集 **5,000条帖子** 和 **20,992条评论**，日期范围从 **2025-01-01** 至今。

## 📁 数据文件位置

```
data/
├── dataset.jsonl          # 完整数据集 (5,000条记录)
└── posts/                 # 单独帖子文件 (5,000个文件)
```

## 🔍 查看数据

### 1. 查看统计报告
```bash
python view_stats.py
```

### 2. 查看数据集
```bash
# 查看前10条
head -10 data/dataset.jsonl

# 美化显示第一条
head -1 data/dataset.jsonl | python -m json.tool

# 统计总数
wc -l data/dataset.jsonl
```

### 3. Python分析
```python
import json

# 读取所有数据
with open('data/dataset.jsonl', 'r') as f:
    posts = [json.loads(line) for line in f]

# 示例分析
print(f"总帖子数: {len(posts)}")
print(f"总评论数: {sum(p['reply_counter'] for p in posts)}")

# 查看一条帖子
print(json.dumps(posts[0], indent=2, ensure_ascii=False))
```

## 📊 数据统计摘要

- **总帖子数**: 5,000
- **总评论数**: 20,992
- **平均评论数**: 4.20 条/帖
- **总浏览量**: 564,535
- **平均浏览量**: 112.9 次/帖
- **日期范围**: 2025-03-14 至 2025-11-04 (235天)
- **性别分布**:
  - 男: 41.1%
  - 女: 24.2%
  - 未知: 34.6%
- **匿名帖子**: 26.0%

## 🔄 持续更新数据

### 增量更新（只抓取新帖子）
```bash
source venv/bin/activate
python main.py --mode incremental --start-date 2025-01-01
```

### 完整重新抓取
```bash
source venv/bin/activate
python main.py --mode full --start-date 2025-01-01 --max-pages 500 --headless
```

## 🛠️ 命令参数说明

```bash
python main.py [选项]

选项:
  --mode {full,incremental}   抓取模式
  --start-date YYYY-MM-DD     起始日期过滤
  --max-pages N               最大抓取页数
  --qps FLOAT                 每秒请求数限制
  --headless                  无头浏览器模式
  --no-export                 不导出数据集
```

## 📈 数据字段说明

每条帖子包含以下字段：

```json
{
  "post_id": 970155,              // 帖子ID
  "username": "匿名",              // 用户名
  "publish_time": "今天 12:34",    // 发布时间
  "content": "帖子内容...",        // 帖子内容
  "view_count": 15,               // 浏览数
  "warm_count": 1,                // 温暖数
  "visit_count": 15,              // 看见数
  "reply_counter": 1,             // 评论总数
  "gender": 1,                    // 性别 (1=女, 2=男)
  "is_anonymous": true,           // 是否匿名
  "topic_title": "我的情绪日记",   // 主题
  "comments": [                   // 评论列表
    {
      "comment_id": 4831706,
      "username": "暖暖",
      "comment_content": "评论内容...",
      "like_count": 0,
      "comment_time": "今天 12:34"
    }
  ]
}
```

## 💡 数据分析示例

### 1. 评论最多的帖子
```python
top_posts = sorted(posts, key=lambda p: p['reply_counter'], reverse=True)[:10]
for post in top_posts:
    print(f"ID: {post['post_id']}, 评论: {post['reply_counter']}")
```

### 2. 按月统计
```python
from collections import Counter
from src.date_utils import parse_chinese_date

month_counter = Counter()
for post in posts:
    date = parse_chinese_date(post['publish_time'])
    if date:
        month_counter[date.strftime('%Y-%m')] += 1

for month, count in sorted(month_counter.items()):
    print(f"{month}: {count} 条")
```

### 3. 主题分析
```python
topics = Counter(p.get('topic_title', '无') for p in posts if p.get('topic_title'))
for topic, count in topics.most_common(10):
    print(f"{topic}: {count} 条")
```

## 📚 其他文档

- `SCRAPING_SUMMARY.md` - 详细采集报告
- `README.md` - 项目完整文档
- `full_scrape.log` - 完整采集日志

## ⚠️ 注意事项

1. **数据使用**: 请遵守数据使用条款和隐私政策
2. **限速保护**: 默认QPS=0.5，请勿过度频繁请求
3. **数据备份**: 建议定期备份data目录
4. **增量更新**: 建议每天运行一次增量更新

## 🎯 下一步建议

1. **数据分析**: 
   - 情感分析
   - 关键词提取
   - 用户行为分析

2. **数据导出**:
   - 导出为CSV: `pandas.DataFrame(posts).to_csv('data.csv')`
   - 导入数据库: MySQL/PostgreSQL
   - 可视化: Tableau/PowerBI

3. **自动化运行**:
   ```bash
   # 添加到crontab每天运行
   0 2 * * * cd /path/to/Data-scraper && source venv/bin/activate && python main.py --mode incremental --start-date 2025-01-01
   ```

## 🆘 需要帮助？

查看项目文档或检查日志文件：
- `full_scrape.log` - 完整日志
- `logs/metrics.jsonl` - 性能指标

---

**数据采集完成时间**: 2025-11-04 16:05  
**状态**: ✅ 成功完成

