# AGENT.md — IoT 传感器数据 ETL 与可视化项目规则

## 一、项目背景与目标

**一句话目标**：做一个端到端的物联网传感器数据 ETL + 可视化项目，作为求职（数据开发 / 大模型应用方向）的 GitHub 展示仓库，证明「采集 → 清洗 → 入库 → 指标集市 → 前端看板」的完整链路能力。

**范围边界**：
- 做：传感器时序数据的模拟采集、ETL 清洗、SQLite 入库、指标聚合、静态 HTML 看板可视化、README 与可复现脚本。
- 不做：真实硬件接入、云端部署、用户登录、实时流式处理（本版只做离线批处理）。

**成功标准（验收判据，三条可数）**：
1. 一条命令 `make run`（或等效入口）能在全新环境跑通全链路，产出 SQLite 数据库 + 一个可打开的 HTML 看板。
2. README 含架构图、分层说明、快速开始、以及「SQL 重写 + 索引优化」的可量化亮点（呼应实习中 BI 提速 50%）。
3. 测试覆盖核心 ETL 逻辑，`make test` 全绿。

## 二、目录与文档规范

```
iot-etl-dashboard/
├── AGENT.md               # 本文件（项目规则）
├── README.md              # 对外展示文档（最终交付）
├── docs/                  # 流水线过程文档
│   ├── 00-总控计划.md
│   ├── 01-总体方案.md
│   ├── 02-PRD.md
│   ├── 03-开发设计.md
│   └── 04-测试报告.md
├── src/                   # 源代码
├── tests/                 # 测试
├── data/                  # 原始与处理后的数据（gitignore 可忽略中间产物）
└── output/                # 最终看板与数据库产物
```

## 三、技术操作规范

- 语言：Python 3（标准库 + 最小第三方依赖，优先 sqlite3 标准库）
- 数据库：SQLite（标准库 sqlite3，无需外部服务）
- 看板：纯静态 HTML + 内嵌 SVG + 原生 JS（无 CDN、无外链，断网可打开）
- 依赖安装、构建、运行、测试命令（实测通过，供小测/小发直接使用）：

```bash
# 安装测试依赖（运行时零第三方依赖，仅 pytest 用于测试）
python -m pip install -r requirements.txt

# 一键跑通全链路（默认规模 ≈65 万行，产出 output/iot_etl.db + dashboard.html + dashboard_data.json 等）
python -m src.cli run --scale default        # 等价 make run

# 压测规模全链路（≈432 万行，耗时约 2~3 分钟）
python -m src.cli run --scale stress         # 等价 make run-stress

# 仅 SQL 优化对比（压测规模，产出 output/sql_optimization_report.json，EXPLAIN 呈现 SCAN→SEARCH）
python -m src.cli benchmark --scale stress   # 等价 make benchmark

# 单元测试（覆盖去重 / 异常值处理 / 聚合三类核心逻辑）
python -m pytest -q                          # 等价 make test

# 清理中间产物
python -m src.cli clean                      # 对已有 ODS 数据执行清洗并输出质量报告
```

CLI 参数：`run` / `benchmark` 支持 `--scale {default,stress}`，并可显式覆盖 `--sites`、`--devices-per-site`、`--interval`、`--days`、`--seed`、`--rounds`；`run`（默认）与 `benchmark` 支持 `--output-dir`。退出码：`0` 成功、`1` 运行期异常、`2` 参数错误。

## 四、编码与提交规范

- 代码遵循 PEP 8，函数单一职责，核心 ETL 逻辑可单测。
- 提交信息用中文动词开头（如「新增：ETL 采集模块」）。
- 敏感信息（真实数据、密钥、账号）一律不入库。

## 五、协作流程与交接协议

- 按「做应用小队」流水线：小顾（方案/PRD）→ 小开（开发设计/编码）→ 小测（测试）→ 小发（发布说明/运维手册）。
- 每阶段产出落盘到 docs/，队长评审通过后推进下一阶段。
- 交接协议：产出落盘 → 回传「交付摘要 + 文件绝对路径 + 自检结果」。

## 六、评审与验收标准

- 总体方案：目标明确、范围清晰、技术路线可行、风险识别充分。
- PRD：需求完整带优先级、每条需求有可测验收标准。
- 开发设计：与 PRD 一致、模块接口清晰、含环境与命令。
- 测试报告：用例覆盖需求、缺陷关闭。
- 最终交付：README + 可跑通全链路 + 看板可打开。
