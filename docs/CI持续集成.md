# 持续集成（Jenkins）

把「环境检查 → 工程自检 → 用例收集 → 接口自动化 → UI 自动化 → 性能冒烟」串成一条流水线，
每次提交或手动触发时自动执行，产物归档到构建页。

## 设计：编排与命令分离

Jenkinsfile **只负责编排**（agent / 参数 / when / post 归档），具体命令统一走 `ci/pipeline.py`。

原因：若 Jenkinsfile 直接内联 `pytest` / `jmeter` 命令，本地想验证流水线就得再手抄一遍，
两处必然漂移——改了脚本忘了改编排，CI 会静默地跑旧命令或漏跑阶段。
统一入口后，本地执行 `python ci/pipeline.py all` 即可完整复现 CI 行为。

编排（`Jenkinsfile`）与执行器（`ci/pipeline.py`）的阶段是否一致，
由 `scripts/selfcheck.py` **第 18 项**机械校验，防止二者分家。

## 阶段划分

| # | 阶段 id | 名称 | 需要被测服务 | 说明 |
| --- | --- | --- | --- | --- |
| 1 | `bootstrap` | 环境与依赖检查 | 否 | Python 版本、依赖包、Playwright 浏览器；JMeter/Allure 缺失仅告警 |
| 2 | `selfcheck` | 工程自检 | 否 | 18 项机械化校验（用例编号、口径一致、JMeter 计划、Jenkinsfile 同步等） |
| 3 | `collect` | 用例收集 | 否 | `pytest --collect-only` 离线确认用例可被正确发现 |
| 4 | `api` | 接口自动化 | 是 | 接口用例，产出 Allure 原始数据 + JUnit XML |
| 5 | `ui` | UI 自动化 | 是 | Dashboard 冒烟用例（`-m ui_smoke`），产出同上 |
| 6 | `perf` | 性能冒烟 | 是 | 单档短时压测，校验链路与清理机制，失败率非 0 即失败 |

前三个阶段**离线可跑**，后三个阶段标记 `needs_service=True`：服务离线时**明确失败**而非静默跳过，
避免在无效环境下执行用例产生假通过。

## 本地演练

无需安装 Jenkins，用统一执行器把整条流水线跑一遍：

```bash
# 全部阶段（任一阶段失败即中止后续，避免在坏环境上继续消耗时间）
python ci/pipeline.py all

# 单个阶段（调试用）
python ci/pipeline.py bootstrap
python ci/pipeline.py api

# 查看阶段清单
python ci/pipeline.py --list
```

性能冒烟的并发/时长可用环境变量覆盖（默认 5 并发 / 15 秒）：

```bash
PERF_THREADS=20 PERF_DURATION=30 python ci/pipeline.py perf
```

## Jenkins 配置

### 插件

- **Allure Jenkins Plugin** —— 渲染 `allure-results/` 生成趋势报告
- **JUnit Plugin** —— 构建页展示失败用例（通常随 Jenkins 自带）

### 工具与全局环境变量

代理机需具备 Python 3.9+、已装 `requirements.txt` 依赖、已执行 `playwright install chromium`。
`jmeter` / `allure` 若未加入 PATH，按以下优先级定位（`JMETER_HOME` 为 JMeter 安装时自带的标准变量）：

| 变量 | 用途 | 示例 |
| --- | --- | --- |
| `JMETER_HOME` | JMeter 安装根目录（自动拼 `bin/jmeter`） | `D:\测试工具\JMeter\apache-jmeter-5.6.3` |
| `JMETER_BIN` | 直接指定 JMeter 可执行文件（优先级最高） | `/opt/apache-jmeter/bin/jmeter` |
| `ALLURE_BIN` | 本地渲染 Allure 报告（Jenkins 用插件时可省） | `/opt/allure/bin/allure` |

被测服务地址、账号等走 `.env`（模板见 `.env.example`），不写入 Jenkinsfile。

### 构建参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `PERF_THREADS` | 5 | 性能冒烟并发数 |
| `PERF_DURATION` | 15 | 性能冒烟持续秒数 |

### 产物归档

`post` 段在每次构建后归档：

- `reports/*.xml` —— JUnit 结果，构建页直接可读
- `allure-results/` —— Allure 原始数据，插件渲染
- `perftests/results/ci/*.jtl` —— 性能冒烟原始采样

以上目录均已被 `.gitignore` 忽略，不入库。

## 相关文档

- 阶段执行器与阶段定义：`ci/pipeline.py`
- 工程自检（含 Jenkinsfile 同步校验，第 18 项）：`scripts/selfcheck.py`
- 性能压测的梯度加压与容量结论：`perftests/README.md`、`docs/性能测试报告.md`