# 性能压测（JMeter）

对 Saleor GraphQL 接口做梯度加压，验证只读查询与结算写链路在并发下的表现，并保证压测数据零残留。

## 目录

```
perftests/
├── saleor-perf.jmx       # 压测计划（setUp 备数据 + 场景A/B + tearDown 兜底清理）
├── perf.properties       # 参数文件（可用 -J 覆盖，见下表）
├── analyze_results.py    # JTL 汇总脚本，输出 Markdown 统计表（仅标准库）
└── results/              # 运行产物（JTL / HTML 看板），已被 .gitignore 忽略
```

## 前置条件

1. 本地 Saleor 已启动（`http://localhost:8000/graphql/`）。
2. JMeter 5.6.3 可用（`jmeter -v`）。
3. 管理员账号可登录（默认 `admin@example.com` / `admin`，与 `.env.example` 一致）。

## 运行

单档：

```bash
jmeter -n -t perftests/saleor-perf.jmx -q perftests/perf.properties \
       -Jthreads=5 -Jduration=20 -l perftests/results/grad-5.jtl
```

峰值档同时产出 JMeter HTML 看板（`-o` 目录必须为空或不存在）：

```bash
jmeter -n -t perftests/saleor-perf.jmx -q perftests/perf.properties \
       -Jthreads=50 -Jduration=20 -l perftests/results/grad-50.jtl \
       -e -o perftests/results/grad-50-report
```

汇总统计（把 `grad-<并发>.jtl` 放在同一目录即可自动识别档位）：

```bash
python perftests/analyze_results.py --dir perftests/results --out perftests/results/summary.md
```

## 参数

`-J` 传参优先级高于 `perf.properties`，便于做梯度。

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `host` / `port` / `protocol` | localhost / 8000 / http | 被测服务地址 |
| `channel` | default-channel | 商品查询与结算所用渠道 slug |
| `page_size` | 20 | 商品列表查询条数 |
| `threads` | 5 | 并发线程数 |
| `rampup` | 5 | 爬坡时间（秒） |
| `duration` | 60 | 单档持续时间（秒） |
| `admin_email` / `admin_password` | admin@example.com / admin | 场景B 回收 checkout 所需的 MANAGE_CHECKOUTS 权限账号 |

## 场景设计

- **setUp**：解析一个「有定价的变体 id」，并用 `tokenCreate` 登录一次拿管理员 Token。
  两者通过 `props.put()` 提升为全局属性——`vars` 是线程私有的，跨线程组读不到，这是踩过的坑。
- **场景A 商品列表查询**：匿名并发查询 `products`，代表游客浏览商品列表。
- **场景B 结算写链路**：`checkoutCreate → 收货地址 → 账单地址 → 取配送方式 → 选配送 → 取应付金额 → 创建支付 → checkoutDelete 回收`，每轮自清理。
- **tearDown**：兜底扫描 `email` 以 `perf-` 开头的 checkout 并删除。持续时间到点时，最后一轮可能停在创建之后、删除之前，故必须有这层兜底。

## 已知约束

- `checkoutDelete` 需要 `MANAGE_CHECKOUTS` 权限，匿名调用返回**顶层** errors（`PermissionDenied`，`data` 为 null）。因此场景B 带管理员 Token，且断言必须同时检查顶层与 payload 两层 errors。
- Saleor 没有 `orderDelete`，所以压测不调用 `checkoutComplete`，避免产生无法回收的订单。
- `checkouts` 的 `filter.search` 不匹配 `email`，tearDown 只能取回后按前缀过滤。

## 相关文档

- 压测结果与结论：`docs/性能测试报告.md`
- 工程自检（含 JMeter 计划自洽校验，第 17 项）：`scripts/selfcheck.py`