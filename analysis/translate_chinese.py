#!/usr/bin/env python3
"""Translate remaining Chinese text in 10-src-file-tree.md to English."""

import re

PATH = '/Users/alanman/Developer/claude-code-analysis/analysis/10-src-file-tree.md'

with open(PATH, 'r') as f:
    lines = f.readlines()

def has_chinese(s):
    return bool(re.search(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', s))

# Count lines with Chinese before
before = sum(1 for l in lines if has_chinese(l))
print(f"Lines with Chinese before: {before}")

# ---- Fix specific line patterns ----

fixed_lines = []
for line in lines:
    original = line
    s = line

    # Pattern: "X 辅助module" (various module contexts)
    s = re.sub(r'assistant 辅助module', 'assistant auxiliary module', s)
    s = re.sub(r'(\w+) 辅助module', r'\1 auxiliary module', s)

    # Pattern: "子系统" -> "subsystem"
    s = s.replace('子系统', 'subsystem')

    # Pattern: "bridge subsystem — X` module，— module responsible for implementing this topic ."
    s = re.sub(
        r'([a-zA-Z]+) subsystem — ([a-zA-Z]+)` module，— module responsible for implementing this topic \.',
        r'\2 module in the \1 subsystem, responsible for implementing this topic.',
        s
    )

    # Same pattern with comma variants
    s = re.sub(
        r'([a-zA-Z]+)  subsystem — ([a-zA-Z]+)` module，— module responsible for implementing this topic \.',
        r'\2 module in the \1 subsystem, responsible for implementing this topic.',
        s
    )

    # Pattern: "X 子系统中的 Y` module" (older pattern)
    s = re.sub(
        r'([a-zA-Z]+) 子系统中的 ([a-zA-Z]+)` 模块，负责该主题下的具体实现',
        r'\2 module in the \1 subsystem, responsible for implementing this topic.',
        s
    )

    # Pattern: "X模块 — Y` module，— module responsible for implementing this topic ."
    s = re.sub(
        r'([a-zA-Z]+)模块 — ([a-zA-Z]+)` module，— module responsible for implementing this topic .',
        r'\2 module in the \1 module, responsible for implementing this topic.',
        s
    )
    s = re.sub(
        r'([a-zA-Z]+) 模块 — ([a-zA-Z]+)` module，— module responsible for implementing this topic .',
        r'\2 module in the \1 module, responsible for implementing this topic.',
        s
    )

    # Pattern: "X — Y` module，— module responsible for implementing this topic ."
    s = re.sub(
        r'([a-zA-Z/]+) — ([a-zA-Z]+)` module，— module responsible for implementing this topic \.',
        r'\2 module in the \1, responsible for implementing this topic.',
        s
    )

    # Pattern: "X — Y` 组件" -> "X — Y component"
    s = re.sub(
        r'` ([a-zA-Z]+)` 组件',
        r'` \1 component',
        s
    )

    # Pattern: "Renders X — Y` 组件" or "Implements X — Y` 组件"
    s = re.sub(
        r'(Renders|Implements) ([a-zA-Z0-9/]+) 组件 — ([a-zA-Z]+)` 组件',
        r'\1 the \3 component in the \2 component',
        s
    )

    # Pattern: "Renders X — Y` 对话框"
    s = re.sub(
        r'Implements ([a-zA-Z0-9/]+) 组件 — ([a-zA-Z]+)` 对话框',
        r'Implements the \2 dialog in the \1 component',
        s
    )

    # Pattern: "Implements X — Y` 菜单或面板"
    s = re.sub(
        r'Implements ([a-zA-Z0-9/]+) 组件 — ([a-zA-Z]+)` 菜单或面板',
        r'Implements the \2 menu or panel in the \1 component',
        s
    )

    # Pattern: "Implements X — Select器组件"
    s = re.sub(
        r'Implements ([a-zA-Z0-9/]+) 组件 — Select器组件',
        r'Implements a selector component in the \1 component',
        s
    )

    # Pattern: "Renders X — Y` 列表"
    s = re.sub(
        r'Renders ([a-zA-Z0-9/]+) 组件 — ([a-zA-Z]+)` 列表',
        r'Renders the \2 list in the \1 component',
        s
    )

    # Pattern: "Renders X — Y` 视图"
    s = re.sub(
        r'Renders ([a-zA-Z0-9/]+) 组件 — ([a-zA-Z]+)` 视图',
        r'Renders the \2 view in the \1 component',
        s
    )

    # Pattern: "X 组件 — Y` module，— module responsible ..."
    s = re.sub(
        r'([a-zA-Z0-9/]+) 组件 — ([a-zA-Z]+)` module，— module responsible for implementing this topic .',
        r'\2 module in the \1 component, responsible for implementing this topic.',
        s
    )

    # Pattern: "X 模块 — Y` module，— module responsible ..."
    s = re.sub(
        r'([a-zA-Z/]+) 模块 — ([a-zA-Z]+)` module，— module responsible for implementing this topic\.',
        r'\2 module in the \1 module, responsible for implementing this topic.',
        s
    )

    # Pattern: "X — Y` 模块，— module responsible ..."
    s = re.sub(
        r'([a-zA-Z/]+) — ([a-zA-Z]+)` 模块，— module responsible for implementing this topic\.',
        r'\2 module in the \1, responsible for implementing this topic.',
        s
    )

    # Pattern: "X module — Y` module，— module responsible ..."
    s = re.sub(
        r'([a-zA-Z/]+) module — ([a-zA-Z]+)` module，— module responsible for implementing this topic\.',
        r'\2 module in the \1 module, responsible for implementing this topic.',
        s
    )

    # Remaining standalone Chinese words / phrases
    replacements = {
        '的Transport层': ' Transport layer',
        '的Transport': ' Transport',
        '的客户端Wraps': ' client wrapper',
        '对外部系统': ' for external systems',
        '客户端的类型、接口或结构': " client's types, interfaces, or structures",
        '的类型、接口或结构': ' types, interfaces, or structures used by the',
        '的类型、接口或结构。': ' types, interfaces, or structures.',
        'Usage的类型、接口或结构': ' types, interfaces, or structures used by',
        '的类型、接口或结构.': ' types, interfaces, or structures.',
        ' 服务 — ': ' service — ',
        ' 服务.': ' service.',
        ' 服务层的': ' service layer ',
        ' 服务层 ': ' service layer ',
        ' 服务\n': ' service\n',
        ' 服务': ' service',
        '的终端界面': ' terminal interface',
        '的终端界面。': ' terminal interface.',
        '集中Defines': ' centrally defines',
        'Related常量': '-related constants',
        ' 常量。': ' constants.',
        ' 任务 — ': ' task — ',
        ' 任务的': ' task ',
        '任务逻辑。': ' task logic.',
        '任务逻辑': ' task logic',
        'Implements a request handling interface or object in 权限审批组件': 'Implements a request handling interface or object in the permission approval component',
        ' 权限审批组件': ' permission approval component',
        ' 输入区组件': ' input area component',
        ' 输入区': ' input area',
        ' 共享上下文': ' shared context',
        ' 通用UI组件': ' general UI component',
        ' 通用UI 组件': ' general UI component',
        ' 通用辅助module': ' general utility module',
        ' 全局State': ' global state',
        ' 全局状态': ' global state',
        ' 跨组件 Hook': ' cross-component hook',
        ' 跨组件Hook': ' cross-component hook',
        ' Hook子目录': ' hook subdirectory',
        ' Hook': ' hook',
        ' 命令行系统': ' command system',
        ' 命令系统': ' command system',
        ' 组件。': ' component.',
        ' 对话框。': ' dialog.',
        ' 模块。': ' module.',
        ' 列表。': ' list.',
        '上下文': ' context',
        ' 组件——': ' component — ',
        ' 单一步骤。': ' single step.',
        ' 单一步骤': ' single step',
        ' 步骤。': ' step.',
        ' 步骤': ' step',
        ' 任务系统': ' task system',
        ' 任务面板组件': ' task panel component',
        ' 任务面板': ' task panel',
        ' 输出风格module': ' output style module',
        ' 插件module': ' plugin module',
        ' 插件': ' plugin',
        ' 类型Defines module': ' type defines module',
        ' 类型Define': ' type definition',
        ' 设计系统组件': ' design system component',
        ' 程序入口': ' program entry point',
        ' 本地服务module': ' local service module',
        ' 远程会话module': ' remote session module',
        ' 服务端或本地服务Wraps': ' server or local service wrapper',
        ' 权限规则、分类器和权限流转': ' permission rules, classifiers, and permission flow',
        ' 权限 ': ' permission ',
        ' 编译/压缩辅助': ' build/compress helper',
        ' 打包/压缩辅助': ' packaging/compress helper',
        ' 生成代码与生成的协议类型': ' generated code and protocol types',
        ' 生成代码与生成的协议类型。': ' generated code and protocol types.',
        ' 生成代码与生成的协议类型.': ' generated code and protocol types.',
        ' 分析埋点和事件元数据服务': ' analytics and event metadata service',
        ' 分析埋点': ' analytics',
        ' 自动 dream/后台探索服务': ' auto dream/background exploration service',
        ' 自动': ' auto ',
        ' 钩子执行、注册与钩子配置管理': ' hook execution, registration, and hook configuration management',
        ' 权益或通行证显示组件': ' pass or entitlement display component',
        ' 会话 记忆': ' session memory',
        ' 会话 memory': ' session memory',
        ' 记忆提取服务': ' memory extraction service',
        ' 记忆文件选择和记忆通知组件': ' memory file selector and memory notification component',
        ' 记忆': ' memory',
        ' 策略限额与能力边界服务': ' policy limits and capability boundary service',
        ' 远程托管设置同步服务': ' remote managed settings sync service',
        ' 设置加载、验证、缓存与托管策略': ' settings loading, validation, caching, and management policy',
        ' 设置同步服务': ' settings sync service',
        ' 设置': ' setting',
        ' 团队 记忆 同步服务': ' team memory sync service',
        ' 团队记忆同步服务': ' team memory sync service',
        ' 团队/teammate/swarm 控制面板组件': ' team/teammate/swarm control panel component',
        ' 团队协作组件': ' team collaboration component',
        ' 团队': ' team',
        ' 提示词/使用提示服务': ' prompt/usage tip service',
        ' 提示词': ' prompt',
        ' 提示建议与提示生成服务': ' prompt suggestion and prompt generation service',
        ' 合规/隐私/政策相关通知组件': ' compliance/privacy/policy related notice component',
        ' 对话 压缩与清理逻辑': ' conversation compression and cleanup logic',
        ' 压缩与清理服务': ' compression and cleanup service',
        ' 压缩与清理逻辑': ' compression and cleanup logic',
        ' 压缩与清理': ' compression and cleanup',
        ' 帮助页与帮助内容展示组件': ' help page and help content display component',
        ' 代码高亮渲染组件': ' code highlighting rendering component',
        ' 消息渲染叶组件': ' message rendering leaf component',
        ' 消息渲染': ' message rendering',
        ' 等待态与流式反馈组件': ' waiting state and streaming feedback component',
        ' LSP 查询与代码理解服务': ' LSP query and code understanding service',
        ' LSP 推荐与提示组件': ' LSP recommendation and prompt component',
        ' 文档理解与文档辅助服务': ' document understanding and document assistance service',
        ' 工作流/CCR 辅助逻辑': ' workflow/CCR helper logic',
        ' 工作流': ' workflow',
        ' 深链分析、注册与终端拉起': ' deep link parsing, registration, and terminal launch',
        ' 深链': ' deep link',
        ' 原生桥接与运行控制': ' native bridge and runtime control',
        ' 原生依赖下载安装与锁管理': ' native dependency download, installation, and lock management',
        ' 睡眠': ' sleep',
        ' 进度': ' progress',
        ' UI 面板': ' UI panel',
        ' 界面': ' interface',
        ' 抽象': ' abstract',
        ' 状态持久化和读取逻辑': ' state persistence and reading logic',
        ' 配置项和默认值': ' configuration items and defaults',
        ' 配置项': ' configuration item',
        ' 加载、发现或延迟初始化': ' loading, discovery, or lazy initialization',
        ' 加载、发现、或延迟初始化': ' loading, discovery, or lazy initialization',
        ' 加载、发现': ' loading, discovery',
        ' 加载、': ' loading, ',
        ' 加载与配置': ' loading and configuration',
        ' 加载或': ' loading or ',
        ' 加载、管理或验证逻辑': ' loading, management, or validation logic',
        ' 钩子': ' hook',
        ' 钩子': ' hook',
        ' 推送 ': ' push ',
        ' 应用 ': ' apply ',
        ' 角色 ': ' role ',
        ' 支持 ': ' support ',
        ' 状态 ': ' state ',
        ' 状态相关': ' state-related',
        ' 状态 ': ' state ',
        ' 注册流': ' registration flow',
        ' 注册或': ' registration or ',
        ' 类型、接口或结构。': ' types, interfaces, or structures.',
        ' 类型、接口或结构': ' types, interfaces, or structures',
        ' 运行时状态': ' runtime state',
        ' 后端': ' backend',
        ' 前端': ' frontend',
        ' 构建 ': ' build ',
        ' 停止 ': ' stop ',
        ' 启动 ': ' start ',
        ' 启动状态准备和自举组装': ' startup state preparation and bootstrap assembly',
        ' 自举': ' bootstrap',
        ' 主链路与输入辅助': ' main chain and input helper',
        ' 集成 ': ' integration ',
        ' HTTP ': ' HTTP ',
        ' 入口 ': ' entry ',
        ' 查询 ': ' query ',
        ' 查询执行循环助手配置和依赖': ' query execution loop helper configuration and dependencies',
        ' 模型配置、能力、别名和验证': ' model configuration, capabilities, aliases, and validation',
        ' 事件 ': ' event ',
        ' 服务端 ': ' server ',
        ' 时间 ': ' time ',
        ' 选项 ': ' option ',
        ' 监听 ': ' listen ',
        ' 监听器 ': ' listener ',
        ' 运行时 ': ' runtime ',
        ' 语言 ': ' language ',
        ' 提供商 ': ' provider ',
        ' 快照 ': ' snapshot ',
        ' 格式 ': ' format ',
        ' 路径 ': ' path ',
        ' 文件 ': ' file ',
        ' 文件系统 ': ' filesystem ',
        ' 文件级持久化与输出扫描': ' file-level persistence and output scanning',
        ' 测试 ': ' test ',
        ' 测试 ': ' test ',
        ' 注释 ': ' comment ',
        ' 文档 ': ' document ',
        ' 文档 ': ' document ',
        ' 参数 ': ' parameter ',
        ' 配置 ': ' configuration ',
        ' 配置 ': ' configuration ',
        ' 数据 ': ' data ',
        ' 数据源 ': ' data source ',
        ' 数据库 ': ' database ',
        ' 请求 ': ' request ',
        ' 响应 ': ' response ',
        ' 索引 ': ' index ',
        ' 缓存 ': ' cache ',
        ' 日志 ': ' log ',
        ' 签名 ': ' sign ',
        ' 签名 ': ' sign ',
        ' 密钥 ': ' key ',
        ' 秘钥 ': ' secret key ',
        ' 令牌 ': ' token ',
        ' 重试 ': ' retry ',
        ' 重连 ': ' reconnect ',
        ' 恢复 ': ' recover ',
        ' 回滚 ': ' rollback ',
        ' 超时 ': ' timeout ',
        ' 过期 ': ' expire ',
        ' 活跃 ': ' active ',
        ' 重载 ': ' reload ',
        ' 刷新 ': ' refresh ',
        ' 更新 ': ' update ',
        ' 清理 ': ' cleanup ',
        ' 移除 ': ' remove ',
        ' 添加 ': ' add ',
        ' 创建 ': ' create ',
        ' 删除 ': ' delete ',
        ' 读取 ': ' read ',
        ' 写入 ': ' write ',
        ' 修改 ': ' modify ',
        ' 同步 ': ' sync ',
        ' 异步 ': ' async ',
        ' 适配 ': ' adapt ',
        ' 桥接 ': ' bridge ',
        ' 过滤器 ': ' filter ',
        ' 策略 ': ' policy ',
        ' 规则 ': ' rule ',
        ' 启发 ': ' heuristic ',
        ' 算法 ': ' algorithm ',
        ' 验证 ': ' validation ',
        ' 验证 ': ' validation ',
        ' 解析 ': ' parse ',
        ' 解析 ': ' parse ',
        ' 分析 ': ' analysis ',
        ' 统计 ': ' statistics ',
        ' 估算 ': ' estimate ',
        ' 预算 ': ' budget ',
        ' 限制 ': ' limit ',
        ' 速率 ': ' rate ',
        ' 配额 ': ' quota ',
        ' 峰值 ': ' peak ',
        ' 下限 ': ' lower bound ',
        ' 上限 ': ' upper bound ',
        ' 默认 ': ' default ',
        ' 自定义 ': ' custom ',
        ' 高级 ': ' advanced ',
        ' 基础 ': ' basic ',
        ' 通用 ': ' general ',
        ' 公共 ': ' public ',
        ' 私有 ': ' private ',
        ' 受保护 ': ' protected ',
        ' 内部 ': ' internal ',
        ' 外部 ': ' external ',
        ' 本地 ': ' local ',
        ' 远程 ': ' remote ',
        ' 全局 ': ' global ',
        ' 会话 ': ' session ',
        ' 用户 ': ' user ',
        ' 管理员 ': ' admin ',
        ' 访客 ': ' guest ',
        ' 身份验证 ': ' authentication ',
        ' 授权 ': ' authorization ',
        ' 认证 ': ' authentication ',
        ' 凭据 ': ' credential ',
        ' 环境 ': ' environment ',
        ' 部署 ': ' deploy ',
        ' 发布 ': ' release ',
        ' 调试 ': ' debug ',
        ' 监控 ': ' monitor ',
        ' 仪表盘 ': ' dashboard ',
        ' 概览 ': ' overview ',
        ' 详细 ': ' detail ',
        ' 总结 ': ' summary ',
        ' 摘要 ': ' summary ',
        ' 报告 ': ' report ',
        ' 导出 ': ' export ',
        ' 导入 ': ' import ',
        ' 备份 ': ' backup ',
        ' 恢复 ': ' restore ',
        ' 迁移 ': ' migration ',
        ' 升级 ': ' upgrade ',
        ' 降级 ': ' downgrade ',
        ' 兼容 ': ' compatible ',
        ' 集成 ': ' integration ',
        ' 扩展 ': ' extension ',
        ' 插件 ': ' plugin ',
        ' 主题 ': ' theme ',
        ' 多语言 ': ' multilingual ',
        ' 国际化 ': ' internationalization ',
        ' 本地化 ': ' localization ',
        ' 安全 ': ' security ',
        ' 加密 ': ' encryption ',
        ' 解密 ': ' decryption ',
        ' 散列 ': ' hash ',
        ' 证书 ': ' certificate ',
        ' HTTPS ': ' HTTPS ',
        ' SSL ': ' SSL ',
        ' TLS ': ' TLS ',
        ' 压缩 ': ' compress ',
        ' 解压 ': ' decompress ',
        ' 归档 ': ' archive ',
        ' 序列化 ': ' serialize ',
        ' 反序列化 ': ' deserialize ',
        ' 编组 ': ' marshal ',
        ' 解组 ': ' unmarshal ',
        ' 编码 ': ' encode ',
        ' 解码 ': ' decode ',
        ' 转换 ': ' convert ',
        ' 映射 ': ' mapping ',
        ' 排序 ': ' sort ',
        ' 过滤 ': ' filter ',
        ' 聚合 ': ' aggregate ',
        ' 分页 ': ' pagination ',
        ' 分片 ': ' shard ',
        ' 复制 ': ' replicate ',
        ' 负载 ': ' load ',
        ' 均衡 ': ' balance ',
        ' 故障 ': ' fault ',
        ' 容错 ': ' tolerance ',
        ' 重试 ': ' retry ',
        ' 超时 ': ' timeout ',
        ' 断路器 ': ' circuit breaker ',
        ' 速率限制 ': ' rate limiting ',
        ' 节流 ': ' throttle ',
        ' 回退 ': ' fallback ',
        ' 降级 ': ' degrade ',
        ' 熔断 ': ' fuse ',
        ' 隔离 ': ' isolate ',
        ' 健康 ': ' health ',
        ' 存活 ': ' liveness ',
        ' 就绪 ': ' readiness ',
        ' 探针 ': ' probe ',
        ' 检查 ': ' check ',
        ' 诊断 ': ' diagnostic ',
        ' 追踪 ': ' trace ',
        ' 跨度 ': ' span ',
        ' 度量 ': ' metric ',
        ' 计数器 ': ' counter ',
        ' 直方图 ': ' histogram ',
        ' 仪表 ': ' gauge ',
        ' 警报 ': ' alert ',
        ' 通知 ': ' notification ',
        ' 审计 ': ' audit ',
        ' 合规 ': ' compliance ',
        ' 治理 ': ' governance ',
        ' 风险 ': ' risk ',
        ' 安全 ': ' safety ',
        ' 隐私 ': ' privacy ',
        ' 泄露 ': ' leak ',
        ' 漏洞 ': ' vulnerability ',
        ' 补丁 ': ' patch ',
        ' CVE ': ' CVE ',
        ' 供应链 ': ' supply chain ',
        ' 依赖 ': ' dependency ',
        ' 软件物料清单 ': ' SBOM ',
        ' 签名 ': ' signing ',
        ' 验证 ': ' verification ',
        ' 可信 ': ' trusted ',
        ' 不可信 ': ' untrusted ',
        ' 沙箱 ': ' sandbox ',
        ' 隔离 ': ' isolation ',
        ' 容器 ': ' container ',
        ' 镜像 ': ' image ',
        ' 仓库 ': ' repository ',
        ' 注册表 ': ' registry ',
        ' 编排 ': ' orchestration ',
        ' 调度 ': ' schedule ',
        ' 队列 ': ' queue ',
        ' 主题 ': ' topic ',
        ' 分区 ': ' partition ',
        ' 偏移 ': ' offset ',
        ' 消费 ': ' consume ',
        ' 生产 ': ' produce ',
        ' 发布 ': ' publish ',
        ' 订阅 ': ' subscribe ',
        ' 事件 ': ' event ',
        ' 消息 ': ' message ',
        ' 代理 ': ' broker ',
        ' 流 ': ' stream ',
        ' 管道 ': ' pipeline ',
        ' 批处理 ': ' batch ',
        ' 实时 ': ' real-time ',
        ' 近实时 ': ' near-real-time ',
        ' 离线 ': ' offline ',
        ' 在线 ': ' online ',
        ' 同步 ': ' synchronous ',
        ' 异步 ': ' asynchronous ',
        ' 阻塞 ': ' block ',
        ' 非阻塞 ': ' non-blocking ',
        ' 回调 ': ' callback ',
        ' Promise ': ' Promise ',
        ' 异步 ': ' async ',
        ' 等待 ': ' await ',
        ' 生成器 ': ' generator ',
        ' 迭代器 ': ' iterator ',
        ' 可观察 ': ' observable ',
        ' 响应式 ': ' reactive ',
        ' 函数式 ': ' functional ',
        ' 面向对象 ': ' object-oriented ',
        ' 声明式 ': ' declarative ',
        ' 命令式 ': ' imperative ',
        ' AOP ': ' AOP ',
        ' DI ': ' DI ',
        ' IoC ': ' IoC ',
        ' MVC ': ' MVC ',
        ' MVP ': ' MVP ',
        ' MVVM ': ' MVVM ',
        ' 架构 ': ' architecture ',
        ' 模式 ': ' pattern ',
        ' 设计 ': ' design ',
        ' 原则 ': ' principle ',
        ' 单一职责 ': ' single responsibility ',
        ' 开闭 ': ' open-closed ',
        ' 里氏替换 ': ' Liskov substitution ',
        ' 接口隔离 ': ' interface segregation ',
        ' 依赖反转 ': ' dependency inversion ',
        ' 重构 ': ' refactor ',
        ' 优化 ': ' optimize ',
        ' 性能 ': ' performance ',
        ' 延迟 ': ' latency ',
        ' 吞吐量 ': ' throughput ',
        ' 并发 ': ' concurrency ',
        ' 并行 ': ' parallel ',
        ' 分布式 ': ' distributed ',
        ' 一致性 ': ' consistency ',
        ' 可用性 ': ' availability ',
        ' 分区容忍 ': ' partition tolerance ',
        ' CAP ': ' CAP ',
        ' BASE ': ' BASE ',
        ' 事务 ': ' transaction ',
        ' 锁 ': ' lock ',
        ' 死锁 ': ' deadlock ',
        ' 活锁 ': ' livelock ',
        ' 饥饿 ': ' starvation ',
        ' 原子 ': ' atomic ',
        ' 一致 ': ' consistent ',
        ' 持久 ': ' durable ',
        ' 隔离 ': ' isolated ',
        ' ACID ': ' ACID ',
        ' 最终一致性 ': ' eventual consistency ',
        ' 强一致性 ': ' strong consistency ',
        ' 弱一致性 ': ' weak consistency ',
        ' 时间戳 ': ' timestamp ',
        ' 版本 ': ' version ',
        ' 版本控制 ': ' version control ',
        ' 变更 ': ' change ',
        ' 差异 ': ' diff ',
        ' 合并 ': ' merge ',
        ' 分支 ': ' branch ',
        ' 标签 ': ' tag ',
        ' 提交 ': ' commit ',
        ' 推送 ': ' push ',
        ' 拉取 ': ' pull ',
        ' 克隆 ': ' clone ',
        ' 分支 ': ' branch ',
        ' 检出 ': ' checkout ',
        ' 贮藏 ': ' stash ',
        ' 变基 ': ' rebase ',
        ' 快进 ': ' fast-forward ',
        ' 解决 ': ' resolve ',
        ' 冲突 ': ' conflict ',
        ' 补丁 ': ' patch ',
        ' 差异 ': ' diff ',
        ' 审查 ': ' review ',
        ' 批准 ': ' approve ',
        ' 拒绝 ': ' reject ',
        ' 请求 ': ' request ',
        ' 流水线 ': ' pipeline ',
        ' 构建 ': ' build ',
        ' 测试 ': ' test ',
        ' 部署 ': ' deploy ',
        ' 发布 ': ' release ',
        ' 回滚 ': ' rollback ',
        ' 灰度 ': ' canary ',
        ' 蓝绿 ': ' blue-green ',
        ' A/B ': ' A/B ',
        ' 金丝雀 ': ' canary ',
        ' 功能开关 ': ' feature flag ',
        ' 实验 ': ' experiment ',
        ' 指标 ': ' metric ',
        ' 仪表板 ': ' dashboard ',
        ' 告警 ': ' alert ',
        ' 通知 ': ' notification ',
        ' 日志 ': ' log ',
        ' 追踪 ': ' trace ',
        ' 遥测 ': ' telemetry ',
        ' 分析 ': ' analytics ',
        ' 报告 ': ' report ',
        ' 图表 ': ' chart ',
        ' 可视化 ': ' visualization ',
        ' 大盘 ': ' dashboard ',
        ' 面板 ': ' panel ',
        ' 小部件 ': ' widget ',
        ' 组件 ': ' component ',
        ' 模块 ': ' module ',
        ' 包 ': ' package ',
        ' 库 ': ' library ',
        ' 框架 ': ' framework ',
        ' 平台 ': ' platform ',
        ' 系统 ': ' system ',
        ' 应用 ': ' application ',
        ' 服务 ': ' service ',
        ' 接口 ': ' interface ',
        ' 实现 ': ' implementation ',
        ' 抽象 ': ' abstraction ',
        ' 基类 ': ' base class ',
        ' 抽象类 ': ' abstract class ',
        ' 接口 ': ' interface ',
        ' 枚举 ': ' enum ',
        ' 结构 ': ' struct ',
        ' 联合 ': ' union ',
        ' 泛型 ': ' generic ',
        ' 重载 ': ' overload ',
        ' 重写 ': ' override ',
        ' 隐藏 ': ' hide ',
        ' 多态 ': ' polymorphism ',
        ' 继承 ': ' inheritance ',
        ' 封装 ': ' encapsulation ',
        ' 组合 ': ' composition ',
        ' 聚合 ': ' aggregation ',
        ' 关联 ': ' association ',
        ' 依赖 ': ' dependency ',
        ' 内聚 ': ' cohesion ',
        ' 耦合 ': ' coupling ',
        ' 委派 ': ' delegation ',
        ' 工厂 ': ' factory ',
        ' 单例 ': ' singleton ',
        ' 原型 ': ' prototype ',
        ' 构建器 ': ' builder ',
        ' 适配器 ': ' adapter ',
        ' 桥接 ': ' bridge ',
        ' 组合 ': ' composite ',
        ' 装饰 ': ' decorator ',
        ' 外观 ': ' facade ',
        ' 享元 ': ' flyweight ',
        ' 代理 ': ' proxy ',
        ' 职责链 ': ' chain of responsibility ',
        ' 命令 ': ' command ',
        ' 解释器 ': ' interpreter ',
        ' 迭代器 ': ' iterator ',
        ' 中介 ': ' mediator ',
        ' 备忘录 ': ' memento ',
        ' 观察者 ': ' observer ',
        ' 状态 ': ' state ',
        ' 策略 ': ' strategy ',
        ' 模板方法 ': ' template method ',
        ' 访问者 ': ' visitor ',
    }

    for cn, en in replacements.items():
        s = s.replace(cn, en)

    # Clean up remaining Chinese characters
    # General: component, dialog, list, view, etc.
    s = s.replace(' 组件。', ' component.')
    s = s.replace(' 对话框中。', ' dialog.')
    s = s.replace(' 对话框。', ' dialog.')
    s = s.replace(' 视图。', ' view.')
    s = s.replace(' 视图', ' view')
    s = s.replace(' 列表。', ' list.')
    s = s.replace(' 列表', ' list')
    s = s.replace(' 菜单或面板。', ' menu or panel.')
    s = s.replace(' 菜单或面板', ' menu or panel')
    s = s.replace(' 对话框', ' dialog')
    
    # Fix remaining common patterns
    s = s.replace('的处理', ' processing')
    s = s.replace('的实现', ' implementation')
    s = s.replace('的应用', ' application')
    s = s.replace('部分', ' part')
    s = s.replace('中的', ' of ')
    s = s.replace('用于', ' used for ')
    s = s.replace('提供', ' provides ')
    s = s.replace('支持', ' supports ')
    s = s.replace('包含', ' contains ')
    s = s.replace('通过', ' through ')
    s = s.replace('基于', ' based on ')
    s = s.replace('根据', ' according to ')
    s = s.replace('作为', ' as ')
    s = s.replace('当', ' when ')
    s = s.replace('使用', ' using ')
    s = s.replace('利用', ' leveraging ')
    s = s.replace('进行', ' perform ')
    s = s.replace('完成', ' complete ')
    s = s.replace('实现', ' implement ')
    s = s.replace('定义', ' define ')
    s = s.replace('描述', ' describe ')
    s = s.replace('管理', ' manage ')
    s = s.replace('控制', ' control ')
    s = s.replace('处理', ' handle ')
    s = s.replace('显示', ' display ')
    s = s.replace('展示', ' display ')
    s = s.replace('生成', ' generate ')
    s = s.replace('构建', ' build ')
    s = s.replace('组织', ' organize ')
    s = s.replace('协调', ' coordinate ')
    s = s.replace('集成', ' integrate ')
    s = s.replace('配置', ' configure ')
    s = s.replace('转换', ' convert ')
    s = s.replace('对应', ' corresponding ')
    s = s.replace('相关', ' related ')
    s = s.replace('主要', ' main ')
    s = s.replace('核心', ' core ')
    s = s.replace('辅助', ' auxiliary ')
    s = s.replace('通用', ' general ')
    s = s.replace('公共', ' public ')
    s = s.replace('基础', ' base ')
    s = s.replace('基本', ' basic ')
    s = s.replace('底层', ' low-level ')
    s = s.replace('中间', ' intermediate ')
    s = s.replace('上层', ' upper ')
    s = s.replace('下层', ' lower ')
    s = s.replace('前端', ' frontend ')
    s = s.replace('后端', ' backend ')
    s = s.replace('外层', ' outer ')
    s = s.replace('内层', ' inner ')
    s = s.replace('包装', ' wrapper ')
    s = s.replace('适配', ' adapt ')
    s = s.replace('桥接', ' bridge ')
    s = s.replace('抽象', ' abstract ')
    s = s.replace('扩展', ' extend ')
    s = s.replace('继承', ' inherit ')
    s = s.replace('实现', ' implement ')
    s = s.replace('实例', ' instance ')
    s = s.replace('对象', ' object ')
    s = s.replace('类', ' class ')
    s = s.replace('方法', ' method ')
    s = s.replace('函数', ' function ')
    s = s.replace('属性', ' property ')
    s = s.replace('字段', ' field ')
    s = s.replace('参数', ' parameter ')
    s = s.replace('返回值', ' return value ')
    s = s.replace('异常', ' exception ')
    s = s.replace('错误', ' error ')
    s = s.replace('警告', ' warning ')
    s = s.replace('信息', ' info ')
    s = s.replace('调试', ' debug ')
    s = s.replace('追踪', ' trace ')
    s = s.replace('进程', ' process ')
    s = s.replace('线程', ' thread ')
    s = s.replace('协程', ' coroutine ')
    s = s.replace('同步', ' sync ')
    s = s.replace('异步', ' async ')
    s = s.replace('回调', ' callback ')
    s = s.replace('事件', ' event ')
    s = s.replace('消息', ' message ')
    s = s.replace('信号', ' signal ')
    s = s.replace('状态', ' state ')
    s = s.replace('模式', ' mode ')
    s = s.replace('策略', ' strategy ')
    s = s.replace('算法', ' algorithm ')
    s = s.replace('格式', ' format ')
    s = s.replace('模板', ' template ')
    s = s.replace('模式', ' pattern ')
    s = s.replace('版本', ' version ')
    s = s.replace('配置', ' config ')
    s = s.replace('设置', ' setting ')
    s = s.replace('选项', ' option ')
    s = s.replace('开关', ' toggle ')
    s = s.replace('特性', ' feature ')
    s = s.replace('功能', ' function ')
    s = s.replace('能力', ' capability ')
    s = s.replace('权限', ' permission ')
    s = s.replace('角色', ' role ')
    s = s.replace('策略', ' policy ')
    s = s.replace('规则', ' rule ')
    s = s.replace('限制', ' limit ')
    s = s.replace('边界', ' boundary ')
    s = s.replace('范围', ' scope ')
    s = s.replace('级别', ' level ')
    s = s.replace('层级', ' level ')
    s = s.replace('顺序', ' order ')
    s = s.replace('随机', ' random ')
    s = s.replace('预设', ' preset ')
    s = s.replace('默认', ' default ')
    s = s.replace('自定义', ' custom ')
    s = s.replace('允许', ' allow ')
    s = s.replace('禁止', ' deny ')
    s = s.replace('拒绝', ' reject ')
    s = s.replace('批准', ' approve ')
    s = s.replace('同意', ' consent ')
    s = s.replace('自动', ' auto ')
    s = s.replace('手动', ' manual ')
    s = s.replace('交互', ' interactive ')
    s = s.replace('用户', ' user ')
    s = s.replace('会话', ' session ')
    s = s.replace('连接', ' connection ')
    s = s.replace('断开', ' disconnect ')
    s = s.replace('重连', ' reconnect ')
    s = s.replace('传输', ' transport ')
    s = s.replace('协议', ' protocol ')
    s = s.replace('管道', ' pipeline ')
    s = s.replace('通道', ' channel ')
    s = s.replace('流', ' stream ')
    s = s.replace('缓冲区', ' buffer ')
    s = s.replace('缓存', ' cache ')
    s = s.replace('存储', ' storage ')
    s = s.replace('持久化', ' persistence ')
    s = s.replace('序列化', ' serialization ')
    s = s.replace('渲染', ' render ')
    s = s.replace('绘制', ' draw ')
    s = s.replace('布局', ' layout ')
    s = s.replace('主题', ' theme ')
    s = s.replace('样式', ' style ')
    s = s.replace('颜色', ' color ')
    s = s.replace('字体', ' font ')
    s = s.replace('动画', ' animation ')
    s = s.replace('过渡', ' transition ')
    s = s.replace('效果', ' effect ')
    s = s.replace('光标', ' cursor ')
    s = s.replace('焦点', ' focus ')
    s = s.replace('键盘', ' keyboard ')
    s = s.replace('鼠标', ' mouse ')
    s = s.replace('触摸', ' touch ')
    s = s.replace('手势', ' gesture ')
    s = s.replace('滚动', ' scroll ')
    s = s.replace('缩放', ' zoom ')
    s = s.replace('选择', ' select ')
    s = s.replace('高亮', ' highlight ')
    s = s.replace('提示', ' tooltip ')
    s = s.replace('通知', ' notification ')
    s = s.replace('确认', ' confirm ')
    s = s.replace('取消', ' cancel ')
    s = s.replace('关闭', ' close ')
    s = s.replace('打开', ' open ')
    s = s.replace('搜索', ' search ')
    s = s.replace('查找', ' find ')
    s = s.replace('替换', ' replace ')
    s = s.replace('过滤', ' filter ')
    s = s.replace('排序', ' sort ')
    s = s.replace('分组', ' group ')
    s = s.replace('分类', ' classify ')
    s = s.replace('聚类', ' cluster ')
    s = s.replace('合并', ' merge ')
    s = s.replace('分割', ' split ')
    s = s.replace('复制', ' copy ')
    s = s.replace('粘贴', ' paste ')
    s = s.replace('剪切', ' cut ')
    s = s.replace('删除', ' delete ')
    s = s.replace('移动', ' move ')
    s = s.replace('重命名', ' rename ')
    s = s.replace('编辑', ' edit ')
    s = s.replace('查看', ' view ')
    s = s.replace('浏览', ' browse ')
    s = s.replace('导航', ' navigate ')
    s = s.replace('跳转', ' jump ')
    s = s.replace('返回', ' return ')
    s = s.replace('历史', ' history ')
    s = s.replace('收藏', ' favorite ')
    s = s.replace('书签', ' bookmark ')
    s = s.replace('链接', ' link ')
    s = s.replace('路径', ' path ')
    s = s.replace('目录', ' directory ')
    s = s.replace('文件夹', ' folder ')
    s = s.replace('文件', ' file ')
    s = s.replace('名称', ' name ')
    s = s.replace('命名', ' naming ')
    s = s.replace('描述', ' description ')
    s = s.replace('注释', ' comment ')
    s = s.replace('文档', ' documentation ')
    s = s.replace('入口', ' entry ')
    s = s.replace('出口', ' exit ')
    s = s.replace('分隔', ' separate ')
    s = s.replace('连接', ' join ')
    s = s.replace('填充', ' fill ')
    s = s.replace('清空', ' clear ')
    s = s.replace('重置', ' reset ')
    s = s.replace('初始化', ' initialize ')
    s = s.replace('启动', ' start ')
    s = s.replace('停止', ' stop ')
    s = s.replace('暂停', ' pause ')
    s = s.replace('恢复', ' resume ')
    s = s.replace('等待', ' wait ')
    s = s.replace('休眠', ' sleep ')
    s = s.replace('激活', ' activate ')
    s = s.replace('禁用', ' disable ')
    s = s.replace('启用', ' enable ')
    s = s.replace('注册', ' register ')
    s = s.replace('注销', ' unregister ')
    s = s.replace('登录', ' login ')
    s = s.replace('退出', ' logout ')
    s = s.replace('订阅', ' subscribe ')
    s = s.replace('取消订阅', ' unsubscribe ')
    s = s.replace('发布', ' publish ')
    s = s.replace('推送', ' push ')
    s = s.replace('拉取', ' pull ')
    s = s.replace('上传', ' upload ')
    s = s.replace('下载', ' download ')
    s = s.replace('安装', ' install ')
    s = s.replace('卸载', ' uninstall ')
    s = s.replace('更新', ' update ')
    s = s.replace('升级', ' upgrade ')
    s = s.replace('降级', ' downgrade ')
    s = s.replace('补丁', ' patch ')
    s = s.replace('捕获', ' capture ')
    s = s.replace('录制', ' record ')
    s = s.replace('播放', ' play ')
    s = s.replace('重放', ' replay ')
    s = s.replace('回溯', ' thinkback ')
    s = s.replace('诊断', ' diagnose ')
    s = s.replace('检查', ' check ')
    s = s.replace('验证', ' verify ')
    s = s.replace('测试', ' test ')
    s = s.replace('断言', ' assert ')
    s = s.replace('度量', ' measure ')
    s = s.replace('评估', ' evaluate ')
    s = s.replace('监控', ' monitor ')
    s = s.replace('日志', ' log ')
    s = s.replace('追踪', ' trace ')
    s = s.replace('性能', ' performance ')
    s = s.replace('基准', ' benchmark ')
    s = s.replace('分析', ' analyze ')
    s = s.replace('报告', ' report ')
    s = s.replace('总结', ' summary ')
    s = s.replace('概览', ' overview ')

    # Remaining multi-character Chinese substrings
    # These are specific to the codebase context
    specific_fixes = [
        ('集中Defines', 'centrally defines'),
        ('的终端界面', ' terminal interface'),
        ('Related常量', '-related constants'),
        ('客户端的类型、接口或结构', 'client types, interfaces, or structures'),
        ('的类型、接口或结构', 'types, interfaces, or structures'),
        ('的类型、接口或结构。', 'types, interfaces, or structures.'),
        ('的类型、接口或结构.', 'types, interfaces, or structures.'),
        ('Usage的类型、接口或结构', 'types, interfaces, or structures used by'),
        ('的交互逻辑', ' interaction logic'),
        ('的注册流', ' registration flow'),
        ('的注册', ' registration'),
        ('的常量', ' constants'),
        ('的接口', ' interface'),
        ('的配置', ' configuration'),
        ('的实现', ' implementation'),
        ('的定义', ' definition'),
    ]

    for old, new in specific_fixes:
        s = s.replace(old, new)

    # Fix remaining patterns like "handlers CLI module — util` 组件"
    s = re.sub(r'` ([a-zA-Z]+)` 组件', r'` \1 component`', s)

    # Clean up double spaces
    s = re.sub(r'  +', ' ', s)

    if s != original and has_chinese(original):
        print(f"  FIXED: {original.strip()[:80]}")
        print(f"     TO: {s.strip()[:80]}")

    fixed_lines.append(s)

after = sum(1 for l in fixed_lines if has_chinese(l))
print(f"\nLines with Chinese after: {after}")
print(f"Lines fixed: {before - after}")

with open(PATH, 'w') as f:
    f.writelines(fixed_lines)

print("Done!")
