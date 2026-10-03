# Saleor 电商平台测试工程

> GraphQL 接口自动化 + Dashboard UI 自动化 + JMeter 性能压测 + Jenkins CI
> 技术栈：Python · pytest · requests · Playwright · JMeter · Allure

针对开源电商平台 [Saleor](https://saleor.io/)（本地 3.23.34 实例）搭建的一套完整测试工程：
从接口功能、UI 回归到性能压测，全部用例可一键执行，并配有 18 项机械化工程自检与 Jenkins 流水线。

---

## 一、测试覆盖概览

| 层次 | 规模 | 技术 | 说明 |
| --- | --- | --- | --- |
| 接口自动化 | **73 条**（含 14 条数据驱动） | pytest + requests | GraphQL 接口：鉴权 / 商品 / 购物车 / 结算 / 订单 / 账户 / 安全 |
| UI 自动化 | **22 条**（冒烟 7 条） | Playwright + POM | Saleor Dashboard：登录鉴权 / 导航 / 商品 / 订单 / 设置 / 增删 |
| 性能压测 | 梯度 5→10→20→50 并发 | JMeter 5.6.3 | 只读查询 + 结算写链路，双层清理保证零残留 |
| 工程自检 | **18 项** | 自研脚本 | 编号唯一、口径一致、依赖声明、JMeter 计划自洽、CI 编排同步 |
| CI 流水线 | **6 个阶段** | Jenkins + 自研执行器 | 环境检查 → 自检 → 收集 → 接口 → UI → 性能冒烟 |

**被测接口规模**：内省得到 **429 个操作**（90 Query + 339 Mutation）、1475 个类型，权威清单见 [`docs/接口清单.md`](docs/接口清单.md)。

---

## 二、目录结构

```
.
├── Jenkinsfile              # Jenkins 流水线（只做编排，命令统一走 ci/pipeline.py）
├── ci/
│   └── pipeline.py          # CI 阶段执行器：Jenkins 与本地演练共用同一入口
├── common/                  # 统一请求层、响应封装、断言、日志、GraphQL 语句
├── config.py                # 全局配置（全部从环境变量读取，无硬编码凭据）
├── conftest.py              # 全局 fixture：登录客户端 / 购物车自动清理 / 订单复用
├── data/                    # 数据驱动用例数据（JSON）
├── testcases/               # 接口自动化用例（按业务模块分文件）
├── uitests/                 # Dashboard UI 用例（Playwright + 页面对象）
│   └── pages/               # 页面对象（POM）
├── perftests/               # JMeter 计划、参数文件、JTL 汇总脚本、README
├── schema/                  # GraphQL schema（SDL）+ 规模统计
├── apifox/                  # 可导入 Apifox 的接口集合 + 导入说明
├── scripts/                 # schema 拉取 / 清单生成 / 集合校验 / 工程自检
├── docs/                    # 接口清单 / 核心链路 / UI 用例清单 / 性能报告 / CI 说明
├── pytest.ini
├── requirements.txt
└── .env.example
```

---

## 三、快速开始

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

### 2. 配置

复制 `.env.example` 为 `.env`（Windows 用 `copy`，macOS/Linux 用 `cp`），按需修改。
模板内已列出全部环境变量与默认值，敏感信息不写入代码。

### 3. 启动被测服务

本地需运行 Saleor：接口 `http://localhost:8000/graphql/`，Dashboard `http://localhost:9000`。

### 4. 执行测试

```bash
pytest testcases                 # 接口自动化
pytest uitests -m ui_smoke       # UI 冒烟
pytest -m smoke                  # 主链路冒烟
python ci/pipeline.py all        # 整条 CI 流水线（自检 + 收集 + 接口 + UI + 性能冒烟）
```

`python ci/pipeline.py --list` 可查看全部阶段；单个阶段（如 `python ci/pipeline.py api`）可单独执行。

---

## 四、工程亮点

**1. 统一请求层，避免散落的 `requests.get`**
`common/client.py` 统一 base url / 超时 / 鉴权头，复用 `requests.Session`；每次请求记录耗时供阈值断言；
保留最近 50 条请求历史便于失败回溯；Token 失效自动重登重试；识别 Saleor 登录限流并等待解封，
避免用例因环境安全机制而假失败。

**2. 分层 fixture + 用例自清理，压测与功能测试均零数据残留**
session 级只取一次登录与商品变体，function 级购物车用例结束自动删除；
压测采用「轮内回收 + tearDown 兜底扫描」双层清理，实测残留 0 个。

**3. 断言口径面向 `code` 而非文案**
业务错误与传输错误分层断言，优先匹配错误 `code` / `field`，避免开发改文案导致用例假失败。
金额比较统一归一化到两位小数（浮点误差）。

**4. 数据驱动 + schema 权威口径**
14 条数据驱动用例覆盖正常与异常场景；接口清单、schema 统计、SDL 三处操作数由自检机械对齐。

**5. 18 项机械化工程自检，替代人工 review**
`scripts/selfcheck.py` 覆盖编号唯一性、文档口径一致、依赖声明完整、硬编码密钥扫描、
JMeter 计划自洽（GraphQL 语法与根字段存在性）、CI 编排与执行器同步等——人工检查易漏，脚本不会。

**6. CI 编排与命令分离，本地可完整复现**
Jenkinsfile 只负责编排，具体命令统一走 `ci/pipeline.py`；本地 `python ci/pipeline.py all`
即可复现整条流水线，杜绝「改了脚本忘了改编排」的静默漂移。

---

## 五、文档索引

| 文档 | 内容 |
| --- | --- |
| [`docs/接口清单.md`](docs/接口清单.md) | 429 个操作的模块归属与签名（内省生成，可重复执行） |
| [`docs/核心业务链路.md`](docs/核心业务链路.md) | 11 个接口的完整下单链路 + 14 条踩坑记录（错误码口径） |
| [`docs/UI用例清单.md`](docs/UI用例清单.md) | 22 条 Dashboard 用例清单 |
| [`docs/性能测试报告.md`](docs/性能测试报告.md) | 梯度压测结果、瓶颈分析与容量结论 |
| [`docs/CI持续集成.md`](docs/CI持续集成.md) | Jenkins 流水线设计、本地演练、插件与变量配置 |
| [`perftests/README.md`](perftests/README.md) | JMeter 计划参数、场景设计与复现命令 |
| [`apifox/导入说明.md`](apifox/导入说明.md) | 19 个请求的 Apifox 集合导入与联调步骤 |

---

## 六、说明与边界

- 用例设计为「环境可移植」：不硬编码 ID，运行时按 `role_key` / 用户名等动态获取。
- 性能报告的绝对值仅代表**单机本地部署**水位（容器共享约 3.8 GiB 内存，压测机与服务同机竞争 CPU），
  不等价于生产容量，生产评估需在独立集群重测。
- 核心链路与异常场景探针脚本仅本地保留，不随仓库发布。