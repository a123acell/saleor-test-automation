# -*- coding: utf-8 -*-
"""工程自检脚本（机械化校验，替代人工检查）。

运行：python scripts/selfcheck.py
退出码：0 全部通过；1 存在失败项。

校验项：
1.  用例编号唯一（测试函数名 + 数据文件 id 互不重复）
2.  数据文件引用的 GraphQL 语句常量真实存在
3.  数据文件声明的操作名在 schema 中存在（Query / Mutation）
4.  config.py 读取的环境变量在 .env.example 中有说明
5.  requirements.txt 依赖全部锁定版本
6.  代码中不存在硬编码 JWT / 明文密钥
7.  用例使用的 pytest marker 已在 pytest.ini 注册
8.  用例文件命名规范、testcases 包结构完整
9.  schema 文件存在且规模合理
10. 数据文件 JSON 格式合法
11. 文档口径一致（接口清单 / schema_stats / 内省 JSON 三处操作数一致）
12. 文档引用的脚本与文件路径真实存在
13. 第三方 import 均已在 requirements.txt 声明
14. UI 用例编号唯一、格式规范且与测试函数一一对应
15. UI 用例清单文档与实际用例编号完全一致
16. UI 层不存在过长的固定 sleep（盲等会制造假通过）
17. JMeter 压测计划自洽（请求体 JSON 合法 / GraphQL 语句可解析且根字段存在 / 变量均已声明）
18. Jenkinsfile 编排的阶段与 ci/pipeline.py 的 STAGES 完全一致
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from common import queries  # noqa: E402

TEST_DIR = os.path.join(ROOT, "testcases")
UITEST_DIR = os.path.join(ROOT, "uitests")
DATA_DIR = os.path.join(ROOT, "data")
SCHEMA_SDL = os.path.join(ROOT, "schema", "saleor_schema.graphql")
STATS_JSON = os.path.join(ROOT, "schema", "schema_stats.json")
DOCS_DIR = os.path.join(ROOT, "docs")
INVENTORY_MD = os.path.join(DOCS_DIR, "接口清单.md")
UI_DOC = os.path.join(DOCS_DIR, "UI用例清单.md")
JENKINSFILE = os.path.join(ROOT, "Jenkinsfile")
PIPELINE_PY = os.path.join(ROOT, "ci", "pipeline.py")

_results = []


def check(name):
    def decorator(func):
        try:
            detail = func() or ""
            _results.append((name, True, detail))
        except AssertionError as exc:
            _results.append((name, False, str(exc)))
        except Exception as exc:  # noqa: BLE001
            _results.append((name, False, "执行异常：%s: %s" % (type(exc).__name__, exc)))
        return func

    return decorator


def _read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def _iter_test_files():
    for name in sorted(os.listdir(TEST_DIR)):
        if name.startswith("test_") and name.endswith(".py"):
            yield os.path.join(TEST_DIR, name)


def _iter_ui_test_files():
    for name in sorted(os.listdir(UITEST_DIR)):
        if name.startswith("test_") and name.endswith(".py"):
            yield os.path.join(UITEST_DIR, name)


def _iter_all_test_files():
    yield from _iter_test_files()
    yield from _iter_ui_test_files()


def _load_data_cases():
    cases = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name.endswith(".json"):
            path = os.path.join(DATA_DIR, name)
            with io.open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for case in data:
                case["_file"] = name
                cases.append(case)
    return cases


def _load_schema():
    """从 SDL 构建 GraphQL Schema，作为权威口径。

    只依赖随仓库提交的 saleor_schema.graphql（约 1MB）。
    内省 JSON（约 5MB）已被 .gitignore 排除，自检若依赖它会在离线 CI 上误报。
    """
    from graphql import build_schema

    return build_schema(_read(SCHEMA_SDL))


def _schema_field_counts(schema):
    """返回 (Query 字段数, Mutation 字段数)。"""
    return (
        len(schema.query_type.fields or {}),
        len(schema.mutation_type.fields or {}),
    )


def _schema_operations(schema):
    """返回 Query + Mutation 的全部操作名。"""
    names = set(schema.query_type.fields or {})
    names |= set(schema.mutation_type.fields or {})
    return names


# ---------------- 校验项 ----------------


@check("1. 用例编号唯一")
def check_case_ids_unique():
    ids = {}
    for path in _iter_all_test_files():
        text = _read(path)
        for match in re.finditer(r"def (test_[A-Za-z0-9_]+)", text):
            name = match.group(1)
            ids.setdefault(name, []).append(os.path.basename(path))
    dup = {k: v for k, v in ids.items() if len(v) > 1}
    assert not dup, "重复的测试函数名：%s" % dup

    data_ids = {}
    for case in _load_data_cases():
        cid = case.get("id")
        assert cid, "数据文件 %s 中存在缺少 id 的用例" % case["_file"]
        data_ids.setdefault(cid, []).append(case["_file"])
    dup2 = {k: v for k, v in data_ids.items() if len(v) > 1}
    assert not dup2, "重复的数据用例 id：%s" % dup2

    return "测试函数 %d 个，数据用例 %d 条，均唯一" % (len(ids), len(data_ids))


@check("2. 数据文件引用的语句常量存在")
def check_query_constants():
    missing = []
    for case in _load_data_cases():
        if not hasattr(queries, case["query"]):
            missing.append("%s(%s)" % (case["query"], case["id"]))
    assert not missing, "common/queries.py 中不存在的常量：%s" % missing
    return "全部 %d 条数据用例引用的语句常量均存在" % len(_load_data_cases())


@check("3. 操作名在 schema 中存在")
def check_operations_in_schema():
    schema = _load_schema()
    fields = _schema_operations(schema)
    assert len(fields) > 300, "schema 解析异常，仅解析到 %d 个操作" % len(fields)

    missing = []
    for case in _load_data_cases():
        op = case.get("operation")
        if op and op not in fields:
            missing.append("%s(%s)" % (op, case["id"]))
    assert not missing, "schema 中不存在的操作名：%s" % missing

    qn, mn = _schema_field_counts(schema)
    return "schema 共 %d 个操作（%d Query + %d Mutation），数据用例引用全部命中" % (qn + mn, qn, mn)


@check("4. 环境变量模板与 config.py 同步")
def check_env_example():
    config_text = _read(os.path.join(ROOT, "config.py"))
    used = set(re.findall(r'os\.getenv\(\s*"([A-Z0-9_]+)"', config_text))
    used |= set(re.findall(r'_get_int\(\s*"([A-Z0-9_]+)"', config_text))
    example = _read(os.path.join(ROOT, ".env.example"))
    missing = sorted(v for v in used if v not in example)
    assert not missing, ".env.example 缺少环境变量说明：%s" % missing
    return "config.py 使用 %d 个环境变量，模板全部覆盖" % len(used)


@check("5. 依赖版本已锁定")
def check_requirements_pinned():
    lines = [
        line.strip()
        for line in _read(os.path.join(ROOT, "requirements.txt")).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    unpinned = [line for line in lines if "==" not in line]
    assert not unpinned, "未锁定版本的依赖：%s" % unpinned
    return "%d 个依赖全部锁定版本" % len(lines)


@check("6. 无硬编码密钥")
def check_no_hardcoded_secrets():
    self_path = os.path.abspath(__file__)
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", "venv", "allure-results", "logs"}]
        for name in filenames:
            if not name.endswith((".py", ".json", ".ini")):
                continue
            path = os.path.join(dirpath, name)
            if os.path.abspath(path) == self_path:
                continue  # 跳过本脚本自身（其校验特征串会被误判）
            text = _read(path)
            if "eyJhbGciOi" in text:
                offenders.append(os.path.relpath(path, ROOT))
    assert not offenders, "发现疑似硬编码 JWT：%s" % offenders
    return "未发现硬编码 JWT / 明文 Token"


# pytest 内置 marker，无需在 pytest.ini 中声明
_BUILTIN_MARKERS = {
    "parametrize",
    "skip",
    "skipif",
    "xfail",
    "filterwarnings",
    "usefixtures",
    "timeout",
}


@check("7. pytest marker 已注册")
def check_markers_declared():
    ini = _read(os.path.join(ROOT, "pytest.ini"))
    declared = set(re.findall(r"^\s{4}([a-z][a-z0-9_]*):", ini, re.MULTILINE))
    used = set()
    for path in _iter_all_test_files():
        used |= set(re.findall(r"@pytest\.mark\.([a-z][a-z0-9_]*)", _read(path)))
    used -= _BUILTIN_MARKERS
    missing = sorted(used - declared)
    assert not missing, "pytest.ini 未注册的 marker：%s" % missing
    return "使用 %d 个自定义 marker，全部已注册" % len(used)


@check("8. 用例文件命名与包结构")
def check_test_layout():
    pattern = r"^(test_[a-z0-9_]+|conftest|__init__)\.py$"
    for directory, label in ((TEST_DIR, "testcases"), (UITEST_DIR, "uitests")):
        bad = [
            name
            for name in os.listdir(directory)
            if name.endswith(".py") and not re.match(pattern, name)
        ]
        assert not bad, "%s 下命名不规范的用例文件：%s" % (label, bad)
        assert os.path.exists(os.path.join(directory, "__init__.py")), "%s 缺少 __init__.py" % label
    assert os.path.exists(os.path.join(UITEST_DIR, "pages", "__init__.py")), "uitests/pages 缺少 __init__.py"
    assert os.path.exists(os.path.join(ROOT, "conftest.py")), "根目录缺少 conftest.py"
    return "testcases / uitests 用例文件命名规范，包结构完整"


@check("9. schema 文件规模合理")
def check_schema_size():
    size = os.path.getsize(SCHEMA_SDL)
    assert size > 500_000, "schema SDL 体积异常：%d 字节" % size
    assert os.path.exists(STATS_JSON), "缺少 schema/schema_stats.json"
    return "SDL %.1f MB" % (size / 1024 / 1024)


@check("10. 数据文件 JSON 合法且字段完整")
def check_data_schema():
    required = {"id", "name", "query"}
    cases = _load_data_cases()
    for case in cases:
        missing = required - set(case)
        assert not missing, "%s 中用例 %s 缺少字段：%s" % (case["_file"], case.get("id"), missing)
    return "%d 条数据用例结构完整" % len(cases)


@check("11. 文档口径一致性")
def check_doc_consistency():
    qn, mn = _schema_field_counts(_load_schema())

    with io.open(STATS_JSON, "r", encoding="utf-8") as f:
        stats = json.load(f)
    assert (stats["query_field_count"], stats["mutation_field_count"]) == (qn, mn), (
        "schema_stats.json（%d/%d）与 SDL（%d/%d）不一致"
        % (stats["query_field_count"], stats["mutation_field_count"], qn, mn)
    )

    md = _read(INVENTORY_MD)
    expected = "%d 个 Query + %d 个 Mutation = %d 个操作" % (qn, mn, qn + mn)
    assert expected in md, "docs/接口清单.md 未出现权威口径「%s」" % expected

    return "接口清单 / schema_stats / SDL 三处一致：%d 个操作" % (qn + mn)


_DOC_PATH_RE = re.compile(
    r"`([A-Za-z0-9_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff\-]*"
    r"(?:/[A-Za-z0-9_\u4e00-\u9fff\-]+)+\.(?:py|md|json|graphql|ini|txt))`"
)


@check("12. 文档引用的文件路径存在")
def check_doc_references():
    docs = [n for n in sorted(os.listdir(DOCS_DIR)) if n.endswith(".md")]
    missing = []
    for name in docs:
        text = _read(os.path.join(DOCS_DIR, name))
        for ref in sorted(set(_DOC_PATH_RE.findall(text))):
            if not os.path.exists(os.path.join(ROOT, ref.replace("/", os.sep))):
                missing.append("%s → %s" % (name, ref))
    assert not missing, "文档引用了不存在的文件：%s" % missing
    return "docs 下 %d 个文档，文件引用全部有效" % len(docs)


# import 名 → PyPI 包名（不一致时需登记）
_IMPORT_TO_PACKAGE = {
    "pytest": "pytest",
    "requests": "requests",
    "allure": "allure-pytest",
    "dotenv": "python-dotenv",
    "graphql": "graphql-core",
    "playwright": "playwright",
}

_LOCAL_MODULES = {"common", "config", "conftest", "testcases", "uitests", "ui", "scripts", "data", "docs"}


def _third_party_imports():
    found = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {".git", "__pycache__", ".venv", "venv", "allure-results", "logs"}
        ]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            text = _read(os.path.join(dirpath, name))
            for mod in re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE):
                if mod not in sys.stdlib_module_names and mod not in _LOCAL_MODULES:
                    found.add(mod)
    return found


@check("13. 第三方依赖声明完整")
def check_deps_declared():
    declared = set()
    for line in _read(os.path.join(ROOT, "requirements.txt")).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            declared.add(line.split("==")[0].strip().lower())

    imports = _third_party_imports()
    missing = []
    for mod in sorted(imports):
        pkg = _IMPORT_TO_PACKAGE.get(mod)
        if pkg is None:
            missing.append("%s（未登记 import→包名 映射）" % mod)
        elif pkg.lower() not in declared:
            missing.append("%s → %s" % (mod, pkg))
    assert not missing, "requirements.txt 未声明的第三方依赖：%s" % missing
    return "第三方 import %d 个，全部已在 requirements.txt 声明" % len(imports)


_UI_FUNC_RE = re.compile(r'def (test_[a-z0-9_]+)\([^)]*\):\s*\n\s*"""(UI-[A-Z]+-\d{3})')
_UI_CASE_RE = re.compile(r"UI-[A-Z]+-\d{3}")


def _ui_case_ids():
    """返回 {UI 编号: [测试函数名]}。"""
    cases = {}
    for path in _iter_ui_test_files():
        for func, cid in _UI_FUNC_RE.findall(_read(path)):
            cases.setdefault(cid, []).append(func)
    return cases


@check("14. UI 用例编号唯一且规范")
def check_ui_case_ids():
    cases = _ui_case_ids()
    dup = {k: v for k, v in cases.items() if len(v) > 1}
    assert not dup, "重复的 UI 用例编号：%s" % dup

    total_funcs = 0
    for path in _iter_ui_test_files():
        total_funcs += len(re.findall(r"def (test_[a-z0-9_]+)\(", _read(path)))
    assert len(cases) == total_funcs, (
        "有 %d 个 UI 测试函数的 docstring 缺少 UI-XXX-NNN 编号（已编号 %d 个）"
        % (total_funcs - len(cases), len(cases))
    )
    return "%d 条 UI 用例编号唯一且格式规范" % len(cases)


@check("15. UI 用例清单与代码一致")
def check_ui_doc_consistency():
    code_ids = set(_ui_case_ids())
    doc_ids = set(_UI_CASE_RE.findall(_read(UI_DOC)))
    missing_in_doc = sorted(code_ids - doc_ids)
    extra_in_doc = sorted(doc_ids - code_ids)
    assert not missing_in_doc, "docs/UI用例清单.md 缺少用例：%s" % missing_in_doc
    assert not extra_in_doc, "docs/UI用例清单.md 存在代码中不存在的用例：%s" % extra_in_doc
    return "UI 用例清单与代码一致：%d 条" % len(code_ids)


_UI_SLEEP_RE = re.compile(r"wait_for_timeout\(\s*(\d+)")

# UI 层允许的固定等待上限（毫秒）。超过该值的盲等属于脆弱写法：
# 请求尚未返回时「未进入 Dashboard / 无侧边导航」这类断言恒成立（假通过），
# 或响应更快时白白拖慢用例。真实信号（wait_for_selector / expect_response /
# wait_for_function）才是正确做法。
_UI_SLEEP_MAX_MS = 3000


def _ui_source_files():
    files = list(_iter_ui_test_files())
    pages_dir = os.path.join(UITEST_DIR, "pages")
    files += [os.path.join(pages_dir, n) for n in sorted(os.listdir(pages_dir)) if n.endswith(".py")]
    return files


@check("16. UI 用例无长固定 sleep")
def check_ui_no_long_sleep():
    offenders = []
    longest = 0
    for path in _ui_source_files():
        for match in _UI_SLEEP_RE.finditer(_read(path)):
            ms = int(match.group(1))
            longest = max(longest, ms)
            if ms >= _UI_SLEEP_MAX_MS:
                offenders.append("%s: wait_for_timeout(%d)" % (os.path.relpath(path, ROOT), ms))
    assert not offenders, "UI 层存在过长固定等待，应改为等待真实信号：%s" % offenders
    return "UI 层最长固定等待 %d ms（上限 %d ms）" % (longest, _UI_SLEEP_MAX_MS)


_PERF_DIR = os.path.join(ROOT, "perftests")
_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")


def _jmx_files():
    if not os.path.isdir(_PERF_DIR):
        return []
    return [
        os.path.join(_PERF_DIR, name)
        for name in sorted(os.listdir(_PERF_DIR))
        if name.endswith(".jmx")
    ]


@check("17. JMeter 压测计划自洽")
def check_jmeter_plan():
    """校验 JMeter 计划里的请求体。

    历史教训：手写的 GraphQL 语句少了一个 `}`，JMeter 照发不误，
    服务端返回 400 语法错误，而人工 review 很难发现——必须机械化校验。
    """
    import xml.etree.ElementTree as ET

    from graphql import OperationType
    from graphql import parse as gql_parse

    schema = _load_schema()
    query_fields = set(schema.query_type.fields or {})
    mutation_fields = set(schema.mutation_type.fields or {})

    files = _jmx_files()
    assert files, "perftests 目录下未找到 .jmx 文件"

    bodies = 0
    operations = 0
    placeholders = set()
    declared = set()

    for path in files:
        rel = os.path.relpath(path, ROOT)
        root = ET.parse(path).getroot()

        # TestPlan 中声明的用户变量
        for arg in root.iter("elementProp"):
            if arg.get("elementType") != "Argument":
                continue
            name_el = arg.find("stringProp[@name='Argument.name']")
            if name_el is not None and name_el.text:
                declared.add(name_el.text.strip())
        # 提取器（JSONPostProcessor）产出的变量
        for post in root.iter("JSONPostProcessor"):
            ref = post.find("stringProp[@name='JSONPostProcessor.referenceNames']")
            if ref is not None and ref.text:
                declared.add(ref.text.strip())

        for sampler in root.iter("HTTPSamplerProxy"):
            label = sampler.get("testname", "?")
            for arg in sampler.iter("elementProp"):
                if arg.get("elementType") != "HTTPArgument":
                    continue
                value_el = arg.find("stringProp[@name='Argument.value']")
                if value_el is None or not value_el.text:
                    continue
                body = value_el.text
                if not body.lstrip().startswith("{"):
                    continue

                for ph in _PLACEHOLDER_RE.findall(body):
                    if not ph.startswith("__"):
                        placeholders.add(ph)

                # 先把 JMeter 占位符替换成字面量：`"first":${PAGE_SIZE}` 这类
                # 未加引号的写法在替换前并非合法 JSON，替换后才是运行时的真实报文。
                sanitized = _PLACEHOLDER_RE.sub("0", body)
                try:
                    payload = json.loads(sanitized)
                except ValueError as exc:
                    raise AssertionError("%s / %s 请求体不是合法 JSON：%s" % (rel, label, exc))
                query = payload.get("query")
                assert query, "%s / %s 缺少 query 字段" % (rel, label)
                bodies += 1

                try:
                    doc = gql_parse(query)
                except Exception as exc:  # noqa: BLE001
                    raise AssertionError(
                        "%s / %s 的 GraphQL 语句语法错误：%s" % (rel, label, exc)
                    )

                for defn in doc.definitions:
                    if not hasattr(defn, "operation"):
                        continue
                    pool = query_fields if defn.operation == OperationType.QUERY else mutation_fields
                    roots = [sel.name.value for sel in defn.selection_set.selections]
                    bad = [r for r in roots if r not in pool]
                    assert not bad, (
                        "%s / %s 的根字段在 schema 中不存在：%s（%s）"
                        % (rel, label, bad, defn.operation.value)
                    )
                    operations += 1

    undeclared = sorted(placeholders - declared)
    assert not undeclared, "JMeter 计划引用了未声明的变量：%s" % undeclared

    return "%d 个请求体 JSON 合法、%d 条语句通过语法与根字段校验、%d 个变量已声明" % (
        bodies,
        operations,
        len(placeholders),
    )


# ci/pipeline.py 中的阶段定义：{"id": "...", "name": "..."}
_PIPELINE_STAGE_RE = re.compile(r'\{"id":\s*"([a-z0-9_]+)",\s*"name":\s*"([^"]+)"')
# Jenkinsfile 中每个 stage 的编排调用：runStage('id')
_JENKINS_STAGE_RE = re.compile(r"runStage\('([a-z0-9_]+)'\)")


@check("18. Jenkinsfile 阶段与流水线一致")
def check_jenkins_stages():
    """校验 Jenkinsfile 编排的阶段与 ci/pipeline.py 的 STAGES 完全一致。

    历史教训：编排与执行器分家后，改了执行器忘了改编排，CI 会静默地
    漏跑或跑错阶段——人工 review 很难发现，必须机械化比对。
    """
    assert os.path.exists(JENKINSFILE), "缺少 Jenkinsfile"
    assert os.path.exists(PIPELINE_PY), "缺少 ci/pipeline.py"

    declared = _PIPELINE_STAGE_RE.findall(_read(PIPELINE_PY))
    assert declared, "未能从 ci/pipeline.py 解析出 STAGES 定义"
    declared_ids = [sid for sid, _ in declared]

    used = _JENKINS_STAGE_RE.findall(_read(JENKINSFILE))

    missing = [sid for sid in declared_ids if sid not in used]
    extra = [sid for sid in used if sid not in declared_ids]
    assert not missing, "Jenkinsfile 缺少阶段：%s" % missing
    assert not extra, "Jenkinsfile 存在执行器未注册的阶段：%s" % extra

    dup = sorted({sid for sid in used if used.count(sid) > 1})
    assert not dup, "Jenkinsfile 重复编排的阶段：%s" % dup

    jf_text = _read(JENKINSFILE)
    renamed = [name for _, name in declared if name not in jf_text]
    assert not renamed, "Jenkinsfile 阶段名称与执行器不同步：%s" % renamed

    return "Jenkinsfile 编排 %d 个阶段，与 ci/pipeline.py 完全一致" % len(declared_ids)


def main():
    print("=" * 66)
    print("Saleor 自动化测试工程自检")
    print("=" * 66)
    failed = 0
    for name, ok, detail in _results:
        flag = "PASS" if ok else "FAIL"
        print("[%s] %-28s %s" % (flag, name, detail))
        if not ok:
            failed += 1
    print("-" * 66)
    total = len(_results)
    print("共 %d 项，通过 %d 项，失败 %d 项" % (total, total - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())