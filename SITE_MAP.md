# 壹点灵 (YDL) 站点地图与API端点

## 站点结构

### 主要入口

- **首页**: https://m.ydl.com/ask
- **详情页**: https://m.ydl.com/ask/detail/{post_id}

### URL 模式

```
https://m.ydl.com/ask
├── / (列表页)
│   ├── 默认显示最新帖子
│   └── SSR 渲染，包含 preloadedState
│
└── /detail/{post_id} (详情页)
    ├── 完整帖子内容
    ├── 所有评论（包括嵌套回复）
    └── SSR 渲染，包含 preloadedState
```

## 数据获取方式

### 方式 1: Server-Side Rendering (SSR) 数据提取 ⭐ 推荐

网站使用 React SSR，HTML 中包含初始状态：

```javascript
window.$G = {
  "env": "9",
  "preloadedState": {
    "data": {
      "code": "200",
      "data": {
        "data": [/* 帖子数组 */],
        "extData": [/* 扩展数据 */]
      }
    }
  }
}
```

**优点**:
- ✅ 无需执行 JavaScript
- ✅ 数据结构稳定
- ✅ 包含完整数据
- ✅ 更快速，资源消耗少

**提取方法**:
```python
import re
import json

pattern = r'window\.\$G\s*=\s*(\{.*?"preloadedState".*?\});'
match = re.search(pattern, html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    posts = data["preloadedState"]["data"]["data"]["data"]
```

### 方式 2: 动态加载（滚动翻页）

**注意**: 初步调查显示列表页可能不支持无限滚动。大部分帖子通过 SSR 初始加载提供。

如果需要更多帖子：
- 可能需要访问分页 URL（如存在）
- 或访问特定话题/分类页面

### 方式 3: 直接 API 调用 (未验证)

可能存在的 API 端点（需进一步测试）：

```
GET /api/ask/list?page={page}&limit={limit}
GET /api/ask/detail/{post_id}
GET /api/ask/comments/{post_id}?page={page}
```

**当前状态**: 未发现公开文档化的 API，建议使用 SSR 数据提取。

## 数据结构

### 帖子对象 (Post)

```json
{
  "id": 970141,
  "timeStr": "今天 14:51",
  "time_str": "今天 14:51",
  "timeDate": "Nov 3, 2025 2:51:46 PM",
  "hits": 3,
  "title": "",
  "multitextType": 1,
  "topicId": 0,
  "replyCounter": 1,
  "extContent": "",
  "content": "真正厉害的人，从不分享过去的痛苦。",
  "uid": 15427050,
  "name": "赤橙黄绿青蓝紫！",
  "gender": 2,
  "askTag": "",
  "zanCount": 1,
  "avatar": "http://...",
  "header": "http://...",
  "commentsCount": 1,
  "topicTitle": "",
  "isZan": 2,
  "visitCount": 3,
  "from": "来自Unknown客户端",
  "smallAttach": [],
  "bigAttach": [],
  "utype": 2,
  "isAd": 0,
  "comments": [/* 评论数组 */],
  "ext": null,
  "ip": ""
}
```

### 评论对象 (Comment)

```json
{
  "name": "暖暖",
  "content": "你这句话像一片轻轻飘落的羽毛...",
  "toName": "",
  "to_name": "",
  "userHead": "https://pic.ydlcdn.com/35f2M8Xi64.png",
  "answerCreateTime": "今天 14:51",
  "time_str": "今天 14:51",
  "toContent": "",
  "to_content": "",
  "isZan": 2,
  "id": 4831707,
  "uid": 32104968,
  "askId": 970141,
  "zan": 0,
  "gender": 1,
  "userType": 1,
  "user_type": 1,
  "doctorId": 0,
  "doctor_id": 0,
  "ip": "",
  "ipProvince": ""
}
```

## 字段映射

### 关键字段对照

| API 字段 | 含义 | 类型 | 备注 |
|---------|------|------|------|
| `id` | 帖子ID | int | 主键 |
| `uid` | 用户ID | int | 0=匿名 |
| `name` | 用户名 | str | "匿名"表示匿名 |
| `content` | 内容 | str | 帖子正文 |
| `timeStr` / `time_str` | 时间 | str | 相对时间 |
| `timeDate` | 时间戳 | str | ISO 格式 |
| `hits` | 浏览数 | int | 阅读量 |
| `zanCount` | 温暖数 | int | 点赞数 |
| `visitCount` | 看见数 | int | 互动指标 |
| `replyCounter` | 回复数 | int | 评论总数 |
| `topicTitle` | 心球名称 | str | 话题/分类 |
| `topicId` | 话题ID | int | 话题标识 |
| `askTag` | 标签 | str | 如"个人成长" |
| `gender` | 性别 | int | 1=女, 2=男 |
| `avatar` / `header` | 头像 | str | URL |
| `from` | 来源 | str | 客户端信息 |
| `smallAttach` | 小图 | array | 图片URL数组 |
| `bigAttach` | 大图 | array | 图片URL数组 |
| `comments` | 评论 | array | 评论对象数组 |

### 评论字段对照

| API 字段 | 含义 | 类型 | 备注 |
|---------|------|------|------|
| `id` | 评论ID | int | 主键 |
| `askId` | 帖子ID | int | 外键 |
| `uid` | 评论者ID | int | 0=匿名 |
| `name` | 评论者昵称 | str | |
| `content` | 评论内容 | str | |
| `answerCreateTime` / `time_str` | 时间 | str | |
| `zan` | 点赞数 | int | |
| `toName` / `to_name` | 回复目标 | str | 空=回复主帖 |
| `toContent` / `to_content` | 被回复内容 | str | 引用原文 |
| `userType` / `user_type` | 用户类型 | int | 1=咨询师 |
| `doctorId` / `doctor_id` | 医生ID | int | 咨询师标识 |
| `userHead` | 头像 | str | URL |
| `gender` | 性别 | int | 1=女, 2=男 |
| `ipProvince` | IP省份 | str | 地理位置 |

## 分页机制

### 列表页分页

**当前观察**: 列表页通过 SSR 返回固定数量的帖子（约10-20条）。

**可能的分页方式**:
1. **URL 参数**: `?page=2` 或 `?offset=20` (需验证)
2. **滚动加载**: JavaScript 动态请求 (未发现)
3. **游标**: `?cursor={last_post_id}` (未发现)

**建议策略**:
- 首次抓取列表页获取最新帖子
- 通过详情页补全历史数据
- 使用增量更新机制避免重复抓取

### 评论翻页

**当前观察**: 详情页的 `comments` 数组包含部分评论。

**如果评论很多**:
- 可能存在"加载更多评论"的 API
- 需要监控网络请求确定端点
- 或使用 Playwright 模拟点击"加载更多"

## Robots.txt 分析

```
User-agent: *
Disallow: /*?*        # 禁止带查询参数的URL
Disallow: /?*
Disallow: /reg/       # 注册页
Disallow: /login*     # 登录页
Disallow: /ot/
Disallow: /uc*
```

**结论**:
- ✅ `/ask` 允许访问
- ✅ `/ask/detail/{id}` 允许访问
- ❌ `/ask?page=2` 被禁止（如果使用查询参数分页）

**合规建议**:
- 使用路径式分页（如存在）：`/ask/page/2`
- 或仅抓取 SSR 提供的数据
- 不使用查询参数绕过限制

## 反爬措施观察

### 已发现的保护措施

1. **User-Agent 检测**: 需要设置移动端 UA
2. **Referer 检测**: 可能需要正确的 Referer 头
3. **频率限制**: 过快访问可能触发 429 Too Many Requests
4. **Cookie/Session**: 部分内容可能需要 Cookie

### 未发现的保护措施

- ❌ JavaScript 混淆/反调试
- ❌ 验证码（CAPTCHA）
- ❌ 动态 Token
- ❌ 指纹识别（目前未观察到）

### 建议策略

1. **尊重限速**: 保持 QPS ≤ 0.5
2. **模拟真实用户**: 
   - 使用移动端 UA
   - 设置合理的 Viewport
   - 添加 Accept-Language 等头部
3. **监控响应**: 及时发现并响应 403/429
4. **优雅降级**: 遇到限制时暂停并告警

## 数据更新频率

基于观察：

- **新帖子**: 每小时数十条（高峰期）
- **评论**: 实时更新
- **互动数据**: 异步更新（可能有延迟）

**增量抓取建议**:
- 每 30-60 分钟运行一次增量更新
- 使用 `last_post_id` 过滤新帖子
- 对热门帖子定期更新评论数据

## 技术栈识别

- **前端**: React + Server-Side Rendering
- **CSS**: Ant Design Mobile
- **字体图标**: Alibaba iconfont
- **CDN**: static.ydlcdn.com, pic.ydlcdn.com
- **统计**: 百度统计 (hm.baidu.com)
- **监控**: 阿里云 ARMS (arms-retcode.aliyuncs.com)

## 示例请求

### 列表页

```bash
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)" \
     -H "Accept-Language: zh-CN,zh;q=0.9" \
     https://m.ydl.com/ask
```

### 详情页

```bash
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)" \
     -H "Accept-Language: zh-CN,zh;q=0.9" \
     -H "Referer: https://m.ydl.com/ask" \
     https://m.ydl.com/ask/detail/970141
```

## 选择器清单

由于使用 SSR 数据提取，无需 CSS 选择器。以下仅作备用：

### 可能的 DOM 选择器

```css
/* 帖子列表（如需要） */
.post-item
.post-content
.post-author
.post-time

/* 详情页（如需要） */
.detail-container
.comment-list
.comment-item
```

**注意**: 实际选择器需通过浏览器开发者工具确认。

## 更新日志

- **2025-11-03**: 初始站点分析
- 确认 SSR 数据提取方式
- 记录 robots.txt 规则
- 识别数据结构与字段映射

---

**维护说明**: 网站结构可能随时变更。如发现本文档与实际不符，请及时更新。

