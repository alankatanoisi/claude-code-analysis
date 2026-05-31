#!/usr/bin/env python3
"""Third and final pass: fix ALL remaining Chinese in 10-src-file-tree.md"""

import re

PATH = '/Users/alanman/Developer/claude-code-analysis/analysis/10-src-file-tree.md'

with open(PATH, 'r') as f:
    content = f.read()

# Count before
before = len(re.findall(r'[\u4e00-\u9fff]', content))

# ===== SPECIFIC DIRECTORY DESCRIPTION FIXES =====
dir_fixes = {
    'Claude Code Prompt与Prompt菜单组件': 'Claude Code prompt and prompt menu component',
    '自Defines Select器 base 组件': 'custom defines selector base component',
    '终端设计系统 base 组件': 'terminal design system base component',
    '桌面端导 stream / upgrade Prompt组件': 'desktop-side redirect / upgrade prompt component',
    'diff 明细和 file 列表组件': 'diff details and file list component',
    '反馈问卷与分享调查组件': 'feedback survey and share survey component',
    '合规/隐私/政策Related notice 组件': 'compliance/privacy/policy related notice component',
    '帮助页与帮助内容Displays组件': 'help page and help content display component',
    '代码 highlight Renders 组件': 'code highlight rendering component',
    'hooks ConfigurationView与Select组件': 'hooks configuration view and select component',
    '欢迎头图、品牌 info 与 notice 组件': 'welcome header, brand info, and notice component',
    'LSP 推荐与Prompt组件': 'LSP recommendation and prompt component',
    '托管Settings安全 confirm 组件': 'managed settings security confirmation component',
    'MCP service、Tool与ConnectionManages 组件': 'MCP service, tool, and connection management component',
    'memory file Select和 memory Notification组件': 'memory file select and memory notification component',
    'MessageRenders 叶子组件': 'message rendering leaf component',
    'input area主链路与输入 auxiliary 组件': 'input area main chain and input auxiliary component',
    'sandbox Settings与 diagnose 组件': 'sandbox settings and diagnostic component',
    'Settings页与State/用量组件': 'Settings page and state/usage component',
    'shell 输出Renders auxiliary 组件': 'shell output rendering auxiliary component',
    'skills browse 与说明组件': 'skills browse and description component',
    'wait 态与Streaming反馈组件': 'wait state and streaming feedback component',
    '结构化 diff Renders 组件': 'structured diff rendering component',
    '后台任务面板组件': 'background task panel component',
    'team/teammate/swarm Control面组件': 'team/teammate/swarm control panel component',
    '信任与安全 confirm 组件': 'trust and security confirmation component',
    'general UI 拼装组件': 'general UI assembly component',
    '权益或通行证Displays组件': 'entitlement or pass display component',
    'permission 审批与 permission 解释组件': 'permission approval and permission explanation component',
    'SDK schema 与 class 型 entry': 'SDK schema and type entry',
    'agent 摘要Generation服务': 'agent summary generation service',
    'API 调用与RetryWraps': 'API calls and retry wrappers',
    'compact compression and cleanup服务': 'compact compression and cleanup service',
    'memory Extraction服务': 'memory extraction service',
    'MCP Connection、Configuration与客户端服务': 'MCP connection, configuration, and client service',
    'OAuth login 与 token Related服务': 'OAuth login and token related service',
    'plugin服务层': 'plugin service layer',
    'Prompt 建议与PromptGeneration服务': 'Prompt suggestion and prompt generation service',
    '远程托管SettingsSyncs服务': 'remote managed settings sync service',
    'SettingsSyncs服务': 'settings sync service',
    'team memory Syncs服务': 'team memory sync service',
    'Prompt词/UsagePrompt服务': 'prompt word/usage prompt service',
    'ToolExecutesOrchestrates服务': 'tool execution orchestration service',
    'Tool调用摘要服务': 'tool call summary service',
    'Generation代码与Generation的 protocol class 型': 'generated code and generated protocol types',
    '后台 stream 程与远程后台 auxiliary': 'background process and remote background helper',
    'Bash Parsing、命令规格与补全逻辑': 'Bash parsing, command specification, and completion logic',
    'Claude in Chrome integrate 逻辑': 'Claude in Chrome integration logic',
    'computer use 原生 bridge 与运行Control': 'computer use native bridge and runtime control',
    'deep linkParsing、 register 与终端拉起': 'deep link parsing, registration, and terminal launch',
    'Git 读写、Parsing与 file 系统Adaptation': 'Git read/write, parsing, and filesystem adaptation',
    'hook Executes、 register 与 hook ConfigurationManages': 'hook execution, registration, and hook configuration management',
    'MCP auxiliary Parsing、 verify 和输出 persistence': 'MCP auxiliary parsing, validation, and output persistence',
    'memory version 与 class 型 auxiliary': 'memory version and type helper',
    'MessageMapping与系统 initialize Message': 'message mapping and system initialization message',
    '模型Configuration、 capability 、别名和Validation': 'model configuration, capabilities, aliases, and validation',
    '原生依赖 download install 与锁Manages': 'native dependency download, installation, and lock management',
    'permission rule 、Classification器和 permission stream 转': 'permission rules, classifiers, and permission flow',
    'pluginLoads、Validation、市场、 install 与Update': 'plugin loading, validation, marketplace, installation, and update',
    'PowerShell Parsing与静态前缀 rule': 'PowerShell parsing and static prefix rules',
    'user 输入分 stream 与命令/文本Handles': 'user input分流 and command/text handling',
    'sandbox Adaptation与 sandbox UI auxiliary': 'sandbox adaptation and sandbox UI helper',
    '安全 storage 和 macOS Keychain Adaptation': 'secure storage and macOS Keychain adaptation',
    'SettingsLoads、Validation、Cache与托管 strategy': 'settings loading, validation, cache, and management strategy',
    'shell provider、Detection和只读 verify': 'shell provider, detection, and read-only validation',
    'skills Detection与技能变更 auxiliary': 'skills detection and skill change helper',
    'command、 directory 、 history 等建议补全': 'command, directory, history, and other suggestion completions',
    '多 agent/swarm backend与 permission Syncs': 'multi-agent/swarm backend and permission sync',
    '任务输出、 format 化与 SDK progress auxiliary': 'task output, formatting, and SDK progress helper',
    '遥测、Tracing 与Exports链路': 'telemetry, tracing, and export pipeline',
    'teleport 环境Select与打包Transport': 'teleport environment selection and package transport',
    'todo 结构Defines': 'todo structure definitions',
    'ultraplan / CCR auxiliary 逻辑': 'ultraplan / CCR helper logic',
    'service层': 'service layer',
    'Tool系统': 'tool system',
    '辅助': 'helper',
    '组件': 'component',
}

for old, new in dir_fixes.items():
    content = content.replace(old, new)

# Fix specific line patterns
# "`CustomSelect component" -> "`CustomSelect` component" (closed backtick)
content = content.replace('`CustomSelect component', '`CustomSelect` component')

# Fix general backtick issues on component names
content = re.sub(r'`([a-zA-Z]+) component', r'`\1` component', content)

# "Tool的." -> "Tool."
content = content.replace("Tool的.", "Tool.")
content = content.replace("Tool的", "Tool")

# "任务Usage" -> "task usage"
content = content.replace('任务Usage', 'task usage')

# "任务system的" -> "task system"
content = content.replace('任务 system的 task', 'task system task')
content = content.replace('任务 system的', 'task system')

# "全局State" clean up
content = content.replace('全局State selectors module', 'global state selectors module')

# "工作台" -> ""
content = content.replace('工作台 ', '')

# "的 task logic" -> "task logic"
content = content.replace(' workspace UI的 task logic', ' task logic in the workspace UI')

# Fix remaining "本地服务" -> "local service"
content = content.replace('本地服务', 'local service')

# Fix "语音voiceModeEnabled" -> "voiceModeEnabled"
content = content.replace('语音voiceModeEnabled', 'voiceModeEnabled')

# Fix remaining service lines 
for old in ['服务层', '服务']:
    pass  # handled above

# Fix "Renders MessageRenders组件 — X component" -> "Renders a message node in the MessageRenders component"
content = content.replace(
    'Renders MessageRenders组件 — GroupedToolUseContent component',
    'Renders a message node in the MessageRenders component'
)
content = content.replace(
    'Renders MessageRenders组件 — HighlightedThinkingText component',
    'Renders a message node in the MessageRenders component'
)

# Fix "in the hooks 组件" -> "in the hooks component"
content = content.replace('in the hooks 组件', 'in the hooks component')
content = content.replace('in the MCP 组件', 'in the MCP component')
content = content.replace('in the memory 组件', 'in the memory component')
content = content.replace('in the shell 组件', 'in the shell component')
content = content.replace('in the spinner 组件', 'in the spinner component')
content = content.replace('in the general UI 组件', 'in the general UI component')
content = content.replace('in the general UI component component', 'in the general UI component')
content = content.replace('in the MessageRenders 组件', 'in the MessageRenders component')
content = content.replace('for MessageRenders 组件', 'for the MessageRenders component')
content = content.replace('for spinner 组件', 'for the spinner component')
content = content.replace('for MCP 组件', 'for the MCP component')
content = content.replace('for Settings组件', 'for the Settings component')
content = content.replace('Renders Settings组件', 'Renders the Settings component')
content = content.replace('Computes, displays, or syncs Settings组件', 'Computes, displays, or syncs the Settings component')
content = content.replace('Defines configuration items and defaults for Settings组件', 'Defines configuration items and defaults for the Settings component')

# Fix "Implements workspace UI的 task logic" -> "Implements task logic in the workspace UI"
content = content.replace('Implements workspace UI的 task logic', 'Implements task logic in the workspace UI')

# Fix remaining "跨组件" -> "cross-component"
content = content.replace('跨组件', 'cross-component')

# Fix "Renders `X component — Y" -> "Renders the Y component in the X"
content = re.sub(
    r'Renders `([a-zA-Z]+)` component — ([a-zA-Z]+) component',
    r'Renders the \2 component in the \1',
    content
)

# Fix "Implements `X component — Y` menu" etc
content = re.sub(
    r'Implements `([a-zA-Z]+)` component — ([a-zA-Z]+)` (menu or panel|dialog)',
    r'Implements the \2 \3 in the \1',
    content
)

# Fix various backtick artifacts
content = content.replace('`component —', '` component —')

# Fix "Implements task panel component的 task logic"
content = content.replace('Implements task panel component的 task logic', 'Implements task logic in the task panel component')

# Fix "Implements the task logic for X Task的" -> "Implements the core tool logic for X Tool"
# Already handled by "Tool的" -> "Tool" above

# Fix "Renders X component — Y component" patterns in general UI
content = re.sub(
    r'Renders (general UI) component — ([a-zA-Z]+) list',
    r'Renders the \2 list in the \1',
    content
)

# Fix wizard description
content = content.replace('向导容器与步骤 navigate 组件', 'wizard container and step navigation component')

# Fix service layer line
content = content.replace('service层 — ', '')

# Remove remaining Chinese characters in specific remaining strings
# Fix "mcpServer.ts": Implements `claudeInChrome` auxiliary module的服务端或本地服务Wraps.
content = content.replace('auxiliary module的服务端或本地服务Wraps', 'auxiliary module server or local service wrapper')
content = content.replace('auxiliary module的服务端或本地服务Wraps.', 'auxiliary module server or local service wrapper.')

# Fix "SentryErrorBoundary.ts: workspace SentryErrorBoundary module in the UI"
content = content.replace('SentryErrorBoundary.ts: workspace SentryErrorBoundary module in the UI', 
                          'SentryErrorBoundary.ts: SentryErrorBoundary module in the workspace UI')

# Count after
after = len(re.findall(r'[\u4e00-\u9fff]', content))
print(f"Chinese chars before: {before}")
print(f"Chinese chars after: {after}")

with open(PATH, 'w') as f:
    f.write(content)

print("Done!")
