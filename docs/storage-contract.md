# Dashboard 存储契约

本文档定义了 Dashboard 记录的完整数据契约。所有读写 Dashboard 数据的代码都应通过 `DashboardStore` 网关（`dashboard/server/resources/dash_store.py`），遵守本文档中的规则。

---

## 1. Redis 数据结构

所有 Dashboard 数据存储在 Redis DB 1（`r_db`），使用以下四个 key：

| Redis Key | 类型 | 用途 |
|-----------|------|------|
| `dash_id` | Sorted Set | 排序索引。member=dash_id，score=time_modified 时间戳 |
| `dash_meta` | Hash | 元数据。field=dash_id，value=JSON meta dict |
| `dash_content` | Hash | 内容数据。field=dash_id，value=JSON content dict |
| `dash_seq` | String | ID 序列号计数器。通过 `INCR` 原子递增生成新 ID |

---

## 2. 记录 Schema

### 2.1 Meta（元数据）

存储在 `dash_meta` hash 中，JSON 格式。

```json
{
  "id": 5,
  "name": "Dashboard: Chinese Population",
  "author": "Alice",
  "time_modified": 1450000000.123
}
```

| 字段 | 类型 | 必选 | 约束 |
|------|------|------|------|
| `id` | int | 是 | 全局唯一，单调递增，由 `dash_seq` INCR 生成 |
| `name` | string | 是 | 1 ~ 200 字符，不能为空或纯空白 |
| `author` | string | 否 | 可为空字符串，最长 200 字符 |
| `time_modified` | float | 是 | Unix 时间戳，每次更新自动刷新 |

### 2.2 Content（内容）

存储在 `dash_content` hash 中，JSON 格式。

```json
{
  "id": 5,
  "name": "Dashboard: Chinese Population",
  "grid": {
    "0": {
      "id": "0",
      "graph_name": "Chinese Pop 2014",
      "x": 0, "y": 4, "width": 6, "height": 8,
      "key": "chinese_population",
      "type": "bar",
      "option": {"x": ["地区"], "y": ["2014年", "2005年"]}
    }
  }
}
```

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 与 meta.id 一致 |
| `name` | string | 是 | 与 meta.name 一致 |
| `grid` | dict | 是 | key 为 grid_id（str），value 为 widget dict |

### 2.3 Grid Widget

grid 中的每个 widget 必须包含以下字段：

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `id` | string | 是 | widget 标识 |
| `graph_name` | string | 否 | 图表显示名称 |
| `x` | int | 是 | 网格 x 坐标 |
| `y` | int | 是 | 网格 y 坐标 |
| `width` | int | 是 | 网格宽度 |
| `height` | int | 是 | 网格高度 |
| `key` | string | 是 | 数据源 key（引用 r_kv 中的数据），`"none"` 表示无数据 |
| `type` | string | 是 | 图表类型：`table`/`bar`/`line`/`pie`/`area`/`none` |
| `option` | dict | 是 | 轴配置 `{"x": [...], "y": [...]}` |

---

## 3. ID 生成策略

- 使用 Redis `INCR` 命令对 `dash_seq` key 原子递增
- **单调递增**：即使删除记录，新 ID 也不会复用已删除的 ID
- **并发安全**：`INCR` 是 Redis 原子操作
- **历史兼容**：首次使用时自动从 `dash_id` sorted set 中的最大 ID seed 初始值

```python
# DashboardStore.next_id() 的逻辑
if not r_db.exists("dash_seq"):
    existing = r_db.zrevrange("dash_id", 0, 0, withscores=True)
    if existing:
        max_id = int(existing[0][0])
        r_db.set("dash_seq", max_id)
return r_db.incr("dash_seq")
```

---

## 4. 读写规则

### 写入（严格校验）

- `DashboardStore.create()` / `update()` 在写入前调用 `DashboardRecord.validate_meta()` 和 `validate_content()`
- name 不能为空或纯空白，长度不超过 200
- grid widget 必须包含所有必选字段
- 写入使用 Redis `pipeline()` 保障多 key 操作的原子性

### 读取（宽容规范化）

- `DashboardStore.get_content()` / `list_meta()` 在读取后调用 `normalize_meta()` 和 `normalize_content()`
- 缺失字段补默认值（如 `author` → `""`，`time_modified` → `0`）
- grid widget 缺失字段补安全默认值（如 `key` → `"none"`，`type` → `"none"`）
- 列表接口自动跳过 meta 缺失的孤儿 ID，不会因一条缺失导致整页崩溃

---

## 5. 错误响应格式

所有 API 错误使用统一的结构化响应：

```json
{
  "status": "error",
  "code": 404,
  "message": "Dashboard not found",
  "data": null
}
```

| HTTP 状态码 | 场景 |
|-------------|------|
| 200 | 操作成功 |
| 400 | 输入校验失败（空 name、格式错误等） |
| 404 | 记录不存在或数据损坏 |
| 301/302 | 创建成功后重定向到首页 |

---

## 6. 向后兼容承诺

1. **API 路径不变**：`POST /`、`GET /data/dashes/`、`GET /data/dash/<id>`、`PUT /data/dash/<id>`、`DELETE /data/dash/<id>` 均保持原有路径
2. **历史数据无需重建**：`normalize_*` 方法自动为缺少字段的旧记录补默认值
3. **ID 序列号自动 seed**：`dash_seq` 不存在时自动从现有数据初始化，不影响已有记录
4. **孤儿数据自动跳过**：列表接口遇到 sorted set 中有 ID 但 meta 缺失时静默跳过

---

## 7. 后续扩展指引

`DashboardStore` 作为单一网关，后续功能可以直接在此类上扩展：

| 功能 | 扩展方式 |
|------|---------|
| **复制 Dashboard** | 新增 `DashboardStore.copy(dash_id)` — 读取现有 content → `next_id()` → 写入新记录 |
| **归档** | 利用已定义的 `DASH_DELETED_KEY`，`delete()` 改为移入归档 hash 而非直接删除 |
| **分享** | 在 `share.py` 中新增 `DashboardStore.get_shared(share_token)` — 基于 content 生成只读快照 |
| **版本历史** | 在 `update()` 中将旧 content 推入版本历史 sorted set |

所有新功能只需在 `DashboardStore` 上添加方法，复用现有的校验、规范化和原子写入机制。
