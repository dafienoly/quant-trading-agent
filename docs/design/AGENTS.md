# AGENTS.md

## 1. 项目目标

本项目目标是构建一个面向 A股、港股以及可扩展多市场的量化交易 Agent 系统，逐步实现：

1. 量化因子挖掘
2. 历史数据接入
3. 新闻与公告数据接入
4. 回测与组合评估
5. 实盘行情监听
6. 自动盯盘
7. 自动生成买卖信号
8. 人工确认下单
9. 小资金实盘验证
10. 风控约束下的半自动或自动交易

项目必须遵循：

> 先研究，后回测；先模拟，后实盘；先人工确认，后自动执行；先风控，后收益。

---

## 2. Agent 总原则

所有 Agent 必须遵守以下原则：

### 2.1 不允许直接跳过验证

任何策略、因子、交易逻辑在进入实盘前，必须经过：

1. 单元测试
2. 历史数据完整性检查
3. 回测
4. 样本外测试
5. 模拟盘或纸面交易
6. 风险评估
7. 人工确认

禁止未经验证直接进入实盘交易。

---

### 2.2 不允许默认自动下单

系统默认只生成信号，不直接下单。

交易模式分为四级：

- **LEVEL 0**: 研究模式，只能读取数据和生成报告
- **LEVEL 1**: 信号模式，只能生成买卖建议
- **LEVEL 2**: 人工确认交易模式，Agent 生成订单，用户确认后执行
- **LEVEL 3**: 自动交易模式，仅允许在明确配置、严格风控和小资金验证后启用

默认模式必须为：

```
TRADING_MODE = LEVEL_1_SIGNAL_ONLY
```

---

### 2.3 风控优先于收益

任何时候，风控模块拥有最高优先级。

如果出现以下情况，系统必须阻止交易：

1. 单日亏损超过限制
2. 单票亏损超过限制
3. 板块集中度超过限制
4. 数据源异常
5. 行情延迟异常
6. 账户资金异常
7. 策略信号冲突
8. 交易接口异常
9. 回测结果不达标
10. 人工设置了禁止交易

---

### 2.4 所有决策必须可解释

每一个买入、卖出、持有信号都必须输出解释，包括：

1. 触发时间
2. 股票代码
3. 股票名称
4. 所属板块
5. 策略名称
6. 触发因子
7. 总评分
8. 买入理由
9. 卖出理由
10. 止损位
11. 止盈位
12. 仓位建议
13. 风险提示

禁止输出不可解释的黑盒交易信号。

---

## 3. Agent 角色划分

### 3.1 Architect Agent

**职责：**

1. 维护系统架构
2. 审查模块边界
3. 审查接口设计
4. 保证代码可扩展
5. 防止策略、数据、交易逻辑耦合

**禁止：**

1. 直接修改交易策略逻辑
2. 直接修改实盘交易代码
3. 绕过测试合并代码

---

### 3.2 Data Agent

**职责：**

1. 接入行情数据
2. 接入财务数据
3. 接入新闻、公告、研报数据
4. 清洗数据
5. 对齐交易日历
6. 检查数据缺失、复权、停牌、涨跌停

**必须输出：**

- `data_quality_report`
- `data_missing_report`
- `data_delay_report`

**禁止：**

1. 静默使用缺失数据
2. 静默前向填充关键行情字段
3. 将未来数据泄漏到历史回测中

---

### 3.3 Factor Research Agent

**职责：**

1. 生成量化因子
2. 计算因子 IC
3. 计算 Rank IC
4. 分层回测
5. 因子去极值
6. 标准化
7. 行业中性化
8. 市值中性化
9. 分析因子衰减

**必须输出：**

- `factor_name`
- `factor_formula`
- `factor_logic`
- `ic_mean`
- `ic_std`
- `ic_ir`
- `rank_ic_mean`
- `turnover`
- `coverage`
- `decay_analysis`
- `long_short_return`

**禁止：**

1. 只根据单次回测结果推荐因子
2. 使用未来函数
3. 忽略交易成本
4. 忽略停牌、涨跌停和流动性约束

---

### 3.4 Strategy Agent

**职责：**

1. 将因子组合成策略
2. 生成买入规则
3. 生成卖出规则
4. 生成仓位规则
5. 生成择时规则
6. 输出每日候选股

**必须输出：**

- `candidate_list`
- `buy_signal`
- `sell_signal`
- `hold_signal`
- `position_suggestion`
- `risk_exposure`

**禁止：**

1. 只买强势股但不设止损
2. 只看技术面忽略风控
3. 只按 LLM 主观判断买卖

---

### 3.5 Backtest Agent

**职责：**

1. 运行历史回测
2. 计算收益、回撤、胜率、盈亏比
3. 计算换手率和交易成本
4. 检查过拟合
5. 做样本外测试
6. 做不同市场环境测试

**必须输出：**

- `annual_return`
- `max_drawdown`
- `sharpe_ratio`
- `calmar_ratio`
- `win_rate`
- `profit_loss_ratio`
- `turnover`
- `cost_adjusted_return`
- `benchmark_return`
- `excess_return`
- `monthly_return`
- `yearly_return`

**禁止：**

1. 不计手续费
2. 不计滑点
3. 不计印花税
4. 不处理涨跌停无法成交
5. 不处理停牌
6. 不做样本外测试

---

### 3.6 Risk Agent

**职责：**

1. 检查单票仓位
2. 检查行业仓位
3. 检查主题仓位
4. 检查账户回撤
5. 检查当日亏损
6. 检查交易频率
7. 检查异常波动
8. 检查黑名单股票

Risk Agent 拥有一票否决权。

只要 Risk Agent 返回：

```
risk_pass = false
```

交易系统必须禁止下单。

---

### 3.7 Execution Agent

**职责：**

1. 接收经过风控确认的订单
2. 生成委托指令
3. 检查价格、数量、账户、交易时间
4. 执行模拟交易或真实交易
5. 记录成交结果

默认只能运行在人工确认模式。

**禁止：**

1. 未经 Risk Agent 许可下单
2. 未经用户确认真实下单
3. 非交易时间强制下单
4. 使用超出账户可用资金的订单
5. 交易不在白名单内的股票

---

### 3.8 Report Agent

**职责：**

1. 生成每日盘前计划
2. 生成盘中盯盘提醒
3. 生成盘后复盘报告
4. 生成策略表现报告
5. 生成持仓风险报告

**输出格式必须清晰，包括：**

- 今日市场状态
- 最强板块
- 最弱板块
- 候选股票
- 持仓建议
- 风险提示
- 明日计划

---

### 3.9 BugFix Agent

**职责：**

1. 自动分析 Bug 报告的根因
2. 生成修复方案（含代码 diff）
3. 经人工审批后执行修复
4. 验证修复结果（运行 pytest）
5. 修复失败时自动回滚

**必须输出：**

- `root_cause`: 根因分析
- `affected_files`: 受影响文件列表
- `fix_steps`: 修复步骤
- `risk_level`: 风险评估 (low/medium/high)
- `estimated_impact`: 预估影响范围

**禁止：**

1. 未经人工审批执行修复
2. 修改风控模块代码
3. 修改交易日志代码
4. 修改回测报告代码
5. 绕过 pytest 验证
6. 提交包含密钥的修复

---

## 4. 代码修改规则

### 4.1 所有代码修改必须满足

1. 有明确任务说明
2. 有对应测试
3. 不破坏已有接口
4. 不绕过风控模块
5. 不在策略代码中硬编码账户信息
6. 不提交真实 API Key、Token、Cookie
7. 不提交券商账号密码

---

### 4.2 禁止项

Agent 禁止执行以下操作：

1. 删除风控模块
2. 删除交易日志
3. 删除回测报告
4. 删除交易记录
5. 提交密钥
6. 绕过人工确认
7. 修改历史回测结果
8. 在没有测试的情况下修改核心交易代码
9. 将模拟交易伪装成实盘收益
10. 将单次收益归因成稳定策略

---

## 5. 默认开发优先级

优先级从高到低：

1. 数据正确性
2. 风控正确性
3. 回测可信度
4. 信号可解释性
5. 系统稳定性
6. 交易执行能力
7. 收益优化
8. 自动化程度

任何 Agent 不得为了提高收益而牺牲前四项。

---

## 6. 当前默认策略方向

初期策略重点围绕：

**AI算力半导体轮动策略**

关注方向：

1. PCB / CCL / 高速材料
2. 先进封装 / 封测
3. 半导体设备 / 材料
4. 存储 / HBM
5. 光模块 / CPO / 硅光

当前限制：

1. 用户不能买创业板
2. 用户不能买科创板
3. 允许沪深主板
4. 允许中小板
5. 允许港股通标的
6. 不允许融资融券
7. 不允许期权、期货、杠杆产品

---

## 7. 开发协作流程硬约束

所有参与开发的 Agent，除遵守本文件前述交易安全规则外，还必须遵守：

- `docs/process/AGENT_DEVELOPMENT_PIPELINE.md`
- `docs/policy/SELF_TEST_CHECKLIST.md`

### 7.1 标准开发管线

任何新 Phase、完整新功能、核心模块变更，必须按以下顺序推进：

1. 用户提出目标和约束。
2. Product Manager Agent 输出需求文档。
3. Architect Agent 输出架构设计文档。
4. Developer Agent 按架构设计 TDD 开发并自测。
5. Test Engineer Agent 完整测试并输出测试报告。
6. Developer Agent 根据测试报告修复缺陷并补回归测试。
7. Architect Reviewer 进行代码 Review。
8. Product Manager Agent 对照需求文档做功能性全量验收。
9. 负责人更新开发日志、阶段报告和用户文档。

不得从用户需求直接跳到核心代码开发；不得在没有需求文档和架构设计的情况下开发新阶段或完整功能。

### 7.2 交付物要求

完整功能至少需要以下交付物：

| 阶段 | 必须交付 |
|---|---|
| 需求 | `docs/requirements/YYYY-MM-DD-<feature>-requirements.md` |
| 架构 | `docs/design/YYYY-MM-DD-<feature>-architecture.md` |
| 开发 | `docs/dev_reports/YYYY-MM-DD-<feature>-dev-report.md` |
| 测试 | `docs/test_reports/YYYY-MM-DD-<feature>-test-report.md` |
| Review | `docs/review/YYYY-MM-DD-<feature>-architecture-review.md` |
| 验收 | `docs/acceptance/YYYY-MM-DD-<feature>-acceptance.md` |
| 日志 | `docs/log/DEVELOPMENT_LOG.md` 和 `docs/log/PHASE_COMPLETION_REPORT.md` |

### 7.3 开发 Agent 禁止项

开发团队 Agent 不得：

1. 修改需求目标而不更新需求文档。
2. 修改架构边界而不更新架构设计文档。
3. 跳过 `SELF_TEST_CHECKLIST.md`。
4. 将测试工程师发现的阻断 Bug 标为非阻断。
5. 在 Review 未通过时进入产品验收。
6. 在产品验收未通过时声明功能完成。
7. 以“时间不够”或“测试太慢”为由跳过交易安全相关测试。
8. 用 Demo fallback、mock 或 paper trading 冒充真实能力。

### 7.4 失败回退规则

- 需求不清：退回 Product Manager Agent。
- 架构不合理：退回 Architect Agent。
- 自测失败：Developer Agent 继续修复。
- 测试失败：Developer Agent 修复后交回 Test Engineer Agent。
- Review 失败：Developer Agent 修复或 Architect Agent 重写设计。
- 产品验收失败：根据失败原因退回 PM、Architect 或 Developer。

任一门禁失败，不得进入下一阶段。

---

## 8. 交易安全声明

本系统只能作为辅助决策工具。

在未完成长期验证前，不得宣传为稳定盈利系统，不得默认自动交易，不得使用大额资金测试。

所有实盘交易必须由用户承担最终责任。
