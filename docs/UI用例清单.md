# Saleor Dashboard UI 自动化用例清单

> 被测对象：Saleor Dashboard（`http://localhost:9000`）
> 技术栈：Python + pytest + Playwright（Chromium）
> 用例规模：**22 条**（鉴权 5 · 板块冒烟 5 · 商品 4 · 订单 3 · 设置 3 · 写操作闭环 2）
> 用例目录：`uitests/`；页面对象：`uitests/pages/`
> 定位依据：全部来自本地探针脚本实测（探针位于仓库外的「自己留着看」目录，不随仓库提交）

## 一、运行方式

```bash
# 全量 UI 用例（Dashboard 需已启动）
python -m pytest uitests -v

# 仅冒烟
python -m pytest uitests -m ui_smoke -v

# 有头模式调试（可见浏览器窗口）
set SALEOR_UI_HEADED=1 && python -m pytest uitests -v
```

- Dashboard 不可达时整组自动跳过，不影响纯接口用例执行。
- 失败会自动截图并保存 Playwright trace 到 `ui-artifacts/`（该目录已 gitignore）。

## 二、定位策略

| 对象 | 定位方式 | 说明 |
| --- | --- | --- |
| 登录表单 | `input[name=email]` / `input[name=password]` / `[data-test-id=submit]` | 稳定 |
| 侧边导航 | `[data-test-id=menu-item-label-*]` | 稳定 |
| 页头标题 | `[data-test-id=page-header]` | 取首行文本 |
| 列表表头/行文本 | `table thead th` / `table tbody tr` | glide-data-grid 的无障碍表：文本可读但元素不可见 |
| 打开行详情 | canvas 几何坐标点击 | 网格由 canvas 绘制，无障碍单元格 `glide-cell-*` 不可点击 |
| 公告横幅 | `[data-test-id=ripple-video-announcement-dismiss]` | 浮层会拦截点击，导航后需先关闭 |

**三点已知约束（已在用例中规避）**

1. glide-data-grid 按视口宽度虚拟化列，宽视口下订单列表会多出 `Net` / `Total` 列，因此表头断言只校验前导核心列。
2. 新建商品的服务端搜索索引存在延迟，故写操作校验改用「列表按更新时间倒序置顶」而非搜索。
3. 商品列表搜索有防抖 + 服务端往返，等待条件必须是「网格内所有可见行都命中关键词」。用「首行命中关键词」会被搜索前的状态直接满足（初始首行商品名本身即含 `Reversed`），于是在过滤完成前就读到行数，表现为 20 → 20 的假阴性。

**等待策略（禁止盲等）**

- 一律等待真实信号：`wait_for_selector` / `wait_for_function` / `expect_response`。
- 断言「不存在」时尤其不能用固定 sleep 兜底：请求未返回时该类断言恒成立，会掩盖真实缺陷。
  例如 UI-AUTH-003 改为等 `tokenCreate` 响应返回并从响应体确认鉴权错误，而非 sleep 后断言「URL 未进入 Dashboard」。
- 自检第 16 项会机械拦截 UI 层 ≥ 3000ms 的固定等待。

## 三、用例清单

### 鉴权与访问控制（5）

| 编号 | 用例 | 关键断言 |
| --- | --- | --- |
| UI-AUTH-001 | 登录页关键元素完整 | 邮箱/密码/提交/忘记密码 4 个元素齐备，页面含 `Sign In` |
| UI-AUTH-002 | 正确账号登录成功 | URL 进入 `/dashboard/**`，且渲染侧边导航 |
| UI-AUTH-003 | 错误密码登录失败 | 等 `tokenCreate` 响应返回且含鉴权错误；未进入 Dashboard，无侧边导航 |
| UI-AUTH-004 | 未登录访问受保护页 | 等待登录表单渲染；不渲染业务导航 |
| UI-AUTH-005 | 登出后回到未登录态 | 等待登录表单出现，侧边导航消失 |

### 五大板块冒烟（5）

| 编号 | 用例 | 关键断言 |
| --- | --- | --- |
| UI-NAV-001 | 商品板块 | 侧边栏点击导航生效；页头 `Products`；6 列表头；行数 > 0 |
| UI-NAV-002 | 订单板块 | 页头 `Orders`；前 5 列表头；行数 > 0 |
| UI-NAV-003 | 客户板块 | 页头 `Customers`；3 列表头；行数 > 0 |
| UI-NAV-004 | 渠道板块 | 页头 `Channels`；渠道行 ≥ 1；状态列取值合法 |
| UI-NAV-005 | 配置中心 | 页头 `Configuration`；配置菜单项 ≥ 10 |

### 商品模块（4）

| 编号 | 用例 | 关键断言 |
| --- | --- | --- |
| UI-PROD-001 | 列表搜索 | 行数收敛、每行命中关键词，且过滤结果数 = 未过滤列表中命中数（交叉校验） |
| UI-PROD-002 | 表头列完整 | 前 6 列表头与顺序正确，行数 ≥ 1 |
| UI-PROD-003 | 打开商品详情 | 详情页标题非空，且为列表首行商品名的前缀 |
| UI-PROD-004 | 列表分页 | 下一页可用；翻页后行数 > 0 且首行变化 |

### 订单模块（3）

| 编号 | 用例 | 关键断言 |
| --- | --- | --- |
| UI-ORDER-001 | 订单列表 | 页头 `Orders`；前 5 列表头；行数 > 0 |
| UI-ORDER-002 | 打开订单详情 | 页头形如 `Order #N`，且 N 为数字 |
| UI-ORDER-003 | 筛选面板 | 面板可见，且含新增/重置/保存 3 个入口 |

### 渠道 / 员工 / 站点设置（3）

| 编号 | 用例 | 关键断言 |
| --- | --- | --- |
| UI-CHAN-001 | 渠道列表 | 页头 `Channels`；渠道行 ≥ 1；状态列取值合法 |
| UI-STAFF-001 | 员工列表 | 页头 `Staff Members`；4 列表头；行数 > 0 |
| UI-SET-001 | 站点设置 | 页头 `Store` |

### 写操作闭环（2）

| 编号 | 用例 | 关键断言 |
| --- | --- | --- |
| UI-WRITE-001 | 创建商品 | 创建后详情页标题 = 商品名；列表置顶命中；结束前删除本次数据 |
| UI-WRITE-002 | 删除商品 | 删除后列表不再出现该商品（等待真正落库，非仅等元素出现） |

## 四、数据清理

写操作用例使用带时间戳的唯一商品名（`UI-AUTO-<TAG>-<毫秒>`），并在用例内删除。

- 用例内清理：`ProductDetailPage.delete(expect_gone=<商品名>)` 会等到列表中该商品真正消失才返回，
  避免「只等元素出现」的假阳性导致删除请求被提前中断、留下残留数据。
- 本地另备两个校验/清理脚本（位于仓库外，不随仓库提交）：check_ui_residue.py 检测残留、cleanup_probe_products.py 批量清理。

## 五、与接口自动化的边界

- UI 层只验证「界面可达、渲染正确、交互闭环」，业务规则与错误码由接口用例（`testcases/`）覆盖，避免重复。
- 登录/鉴权在 UI 层只验证 1 条成功、1 条失败、1 条未登录拦截，不做参数化穷举。