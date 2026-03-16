# Future Plan

## 定位

这份文档描述 `standalone_food_risk_kb` 后续可继续推进的方向。

核心判断：

- 这件事很难做
- 数据确实难找
- 但依然是可以做的
- 路线不需要过度抽象，思路可以非常直接：
  - 抓足够多维度的数据
  - 做分层知识治理
  - 用案例做测试
  - 看系统能否给出大致正确的候选风险和概率分布

本项目后续不是只做一个“文本 RAG”，而是逐步扩展成：

- 乳制品风险知识库
- 企业风险画像
- 多模态包装标签一致性审查
- 未知异常事件入口

## 当前系统能做到什么程度

现阶段最现实、最有价值的能力，不是“预测一切未知风险”，而是下面三类：

### 1. 已知风险模式识别

例如：

- 三聚氰胺 -> 肾结石 / 泌尿系统损伤
- 阪崎肠杆菌 -> 婴幼儿感染 / 脑膜炎
- 李斯特菌 -> 冷链场景下的感染风险
- 黄曲霉毒素 M1 -> 乳制品污染
- 重金属 -> 神经 / 肾损伤

系统目标：

- 从症状、检验项、产品类型中拉出候选风险因子
- 给出相应的 GB 依据、方法依据、生产环节候选

## 新版 risk_taxonomy 数据源 Todo

这部分属于 README 中的：

- `已知风险模式层`

它不是当前 `GB Agent` 主线的一部分，但应作为紧随其后的下一阶段数据建设任务。

### 源优先级判断

新版 `risk_taxonomy` 不建议先以 Hugging Face 语料集作为主知识源。

更合适的主来源顺序是：

1. `PubTator Central`
2. `Europe PMC / PubMed`
3. `OpenFoodTox`
4. `JECFA`
5. `openFDA Food Enforcement`
6. `FDA CORE outbreak / outbreak reports`
7. `CDC NORS`
8. `FDA Warning Letters`
9. `RASFF`

Hugging Face 数据集更适合放在第二圈：

- 作为 `NER / relation extraction / weak supervision` 的辅助材料
- 不直接作为新版 taxonomy 的一手事实库

### 字段落点

后续采集时，优先映射到最小可用字段：

- `hazard_id`
- `hazard_name`
- `hazard_class`
- `product_domain`
- `symptoms`
- `vulnerable_group`
- `typical_products`
- `indicative_tests`
- `process_stage`
- `authority`
- `evidence_type`
- `source_url_or_id`
- `confidence`

### 建议执行顺序

第一步：

- 先做事件证据与毒理证据层
- 来源优先：
  - `openFDA`
  - `FDA outbreak`
  - `CDC NORS`
  - `FDA Warning Letters`
  - `OpenFoodTox`
  - `JECFA`

目标：

- 先落一版
  - `hazard_name + product + event + authority + evidence_type`

第二步：

- 用 `PubTator Central + Europe PMC / PubMed` 补文献关系

目标：

- 扩充：
  - `symptoms`
  - `vulnerable_group`
  - `indicative_tests`
  - `organ_damage`
  - `literature_support`

第三步：

- 再考虑引入 Hugging Face 数据集

用途限定为：

- `relation extraction`
- `weak supervision`
- `evaluation / warm start`

### 子域边界

新版 `risk_taxonomy` 必须先限定在乳制品子域，不做开放域全食品大一统。

起步产品词表建议仅覆盖：

- `milk`
- `powdered infant formula`
- `cheese`
- `yogurt`
- `butter`
- `cream`
- `whey`

### 后续具体待办

- 新增 `source_registry.yaml`
- 为每个外部源定义：
  - `source_name`
  - `source_type`
  - `access_mode`
  - `priority`
  - `target_fields`
  - `dairy_filter_strategy`
  - `notes`
- 为新版 `risk_taxonomy` 建立采集脚本清单
- 先做一个乳制品子域的 `source registry + query templates` 最小版本

### 2. 企业 / 产品风险先验画像

不是对企业“定罪”，而是形成：

- 哪些企业更值得重点关注
- 哪些产品更高风险
- 哪些渠道更值得审查

### 3. 未知异常 watchlist

对于今天突然出现的新问题，系统不一定知道最终答案，但可以做到：

- 把它识别为异常簇
- 先归入某类候选风险方向
- 给出待补充证据
- 进入持续观察列表

## 企业风险画像

### 原则

不能把企业风险画像做成一个简单黑箱总分。

更合理的是做成：

**企业风险先验画像 + 证据型标签**

### 可建维度

- `企业规模画像`
  - 上市 / 非上市
  - 大型 / 中小 / 小作坊倾向
- `供应链复杂度`
  - 自有奶源 / 代工 / 多供应商 / 跨区域
- `产品风险结构`
  - 婴配粉 / 巴氏乳 / 发酵乳 / 调制乳 / 饮料
- `历史合规记录`
  - 抽检 / 处罚 / 召回 / 投诉
- `标签宣传风险`
  - 宣称激进 / 类别模糊 / 配料复杂
- `渠道画像`
  - 商超 / 生鲜平台 / 电商 / 社区团购 / 线下散售
- `信息透明度`
  - 是否公开质量说明、检测报告、供应链说明

### 关于财务报表

财务报表只能覆盖上市企业，因此不能作为主数据源。

对大量中小乳企，更重要的是：

- 抽检通报
- 行政处罚
- 召回公告
- 生产许可信息
- 产品包装和标签信息
- 电商与生鲜渠道商品页

## 多模态方向

### 不是“为了做多模态而做多模态”

多模态的价值，不在于泛泛识别图片，而在于解决纯文本做不到的问题：

**包装正面宣称、品类、配料表、标准号、卖点图标之间是否一致。**

### 可解决的典型问题

- 正面大字写“牛奶”，实际是复合蛋白饮品
- 正面强调“椰子水 / 100%果汁 / NFC”，但配料首位是水
- “调制乳”被弱化显示
- “0添加 / 纯天然 / 原榨 / 原产地” 与法定信息不一致

### 任务定义

多模态方向建议定义为：

**包装标签一致性与误导性表达识别**

### 核心子任务

1. 正面主宣称提取
   - 产品主名称
   - 卖点词
   - 功能词
   - 含量词
   - 图标词

2. 背标法定信息提取
   - 配料表
   - 产品类别
   - 执行标准
   - 果汁含量
   - 营养成分
   - 贮存条件

3. 一致性判断
   - 主宣称 vs 配料表
   - 主宣称 vs 产品类别
   - 图标卖点 vs 标准属性
   - 正面视觉印象 vs 法定标签事实

4. 风险输出
   - 标签误导风险
   - 品类表达风险
   - 宣称与配料不一致风险
   - 需人工复核

## 面对未知问题能做到什么

### 已知模式

系统可以做得比较稳：

- 症状 -> 风险因子
- 风险因子 -> 产品场景
- 风险因子 -> GB / 方法 / 环节依据

### 未知模式

系统不可能一开始就直接知道“这就是某个全新风险”。

更现实的目标是：

- 从新症状 / 新投诉 / 新通报中识别异常
- 聚类成某类风险方向
- 输出候选风险因子
- 输出待核查证据
- 放入 `watchlist`

也就是说，系统可以做“候选归因与观察”，但不应假装能一开始给出终极答案。

## 建议收集的数据

### 第一优先级

- GB 标准正文
- 方法标准
- 抽检通报
- 行政处罚
- 召回公告
- 产品包装正反面图片
- 配料表 / 类别 / 执行标准 / 营养成分

### 第二优先级

- 企业工商和许可信息
- 产品备案信息
- 电商商品页
- 生鲜平台上架页
- 渠道价格

### 第三优先级

- 投诉文本
- 舆情异常
- 医学症状描述
- 退货 / 异味 / 胀包 / 沉淀等异常描述
- 企业公开质量说明

### 最后再考虑

- 上市公司财报
- 复杂供应链金融数据
- 全图谱多跳推理

原因：

- 覆盖面太窄
- 不能作为主底座

## 推荐实验路线

后面如果要验证系统有效性，建议按这条顺序做：

### A. 统一向量检索

作为基线。

### B. 统一向量检索 + metadata 过滤

加入：

- `product_domain`
- `knowledge_type`
- `authority`

### C. 分层检索

按：

- `product_domain × knowledge_type`

做检索路由。

### D. C + hybrid retrieval + rerank

适用于：

- GB / 方法 / 管理 / 推断等多类证据

### E. D + 图谱 / 本体扩展

用于：

- 症状 -> 风险因子 -> 原因 -> 生产环节 -> 依据

### F. E + 受控生成与引用校验

要求模型明确区分：

- `GB主依据`
- `辅助证据`
- `经验推断`
- `不确定点`

## 建议评估指标

不要只看普通 QA 分数，更要看你这个任务真正痛的指标：

- `cross-domain contamination rate`
- `primary-evidence precision`
- `knowledge-type confusion rate`
- `unsupported inference rate`
- `causal-chain completeness`
- `risk_prior_calibration`

## ClaudeCode Agent 规划

可以直接把 ClaudeCode 作为主 Agent 来配置。

### 适合交给 ClaudeCode 的任务

- 逐批清洗语料
- 逐条判断 `product_domain`
- 逐条判断 `knowledge_type`
- 逐条判断 `kb_role`
- 生成结构化输出文件
- 做小批量人工式改写
- 对异常案例做分析和解释

### 不适合让 ClaudeCode 独立完成的部分

- 全自动海量数据爬取闭环
- 纯靠 Prompt 替代数据治理
- 没有 schema 约束的大规模批处理

### 推荐使用方式

把 ClaudeCode 当作：

- 高语义判断引擎
- 逐批文件改写 Agent
- 小步增量知识治理 Agent

而不是：

- 无约束大规模自动清洗脚本替代品

## 下一步建议

### 第一阶段

- 继续清洗方法层
- 补 `product_domain`
- 补 `knowledge_type`
- 建立最小可用的已知风险模式库

### 第二阶段

- 建立企业风险画像标签体系
- 收集企业 / 产品 / 渠道 / 处罚 / 抽检数据

### 第三阶段

- 建立多模态包装标签一致性审查样本集
- 做规则版 MVP
- 再决定是否引入视觉模型

### 第四阶段

- 建立未知异常 watchlist
- 用真实案例做测试
- 看系统能否给出大致合理的候选概率分布

## 总结

这件事不是“先把所有东西做完”，而是：

- 先把高价值、可验证的部分做出来
- 再用案例做测试
- 再逐步扩充数据维度

现实上很难，但方向是成立的。

可以接受的目标不是“全知全能”，而是：

**一个面向乳制品与相关食品的分层风险知识库 + 企业风险画像 + 多模态标签一致性审查 + 未知异常观察入口。**
