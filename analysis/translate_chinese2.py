#!/usr/bin/env python3
"""Second pass: fix remaining Chinese patterns in 10-src-file-tree.md"""

import re

PATH = '/Users/alanman/Developer/claude-code-analysis/analysis/10-src-file-tree.md'

with open(PATH, 'r') as f:
    content = f.read()

def has_chinese(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s))

before = sum(1 for l in content.split('\n') if has_chinese(l))

# Fix known remaining patterns (specific to this file)
replacements = [
    # 工作台 -> workspace
    ('工作台 UI', 'workspace UI'),
    
    # 压缩与Cleanup -> compression and cleanup
    ('压缩与Cleanup逻辑', 'compression and cleanup logic'),
    ('压缩与Cleanup', 'compression and cleanup'),
    
    # command系统 -> command system  
    ('command系统 — ', 'command system — '),
    ('command系统 state', 'command system state'),
    ('command系统', 'command system'),
    
    # agent description fixes  
    ('agent list、详情、Edit与Creation组件', 'agent list, details, edit, and creation components'),
    ('agent Manages component', 'agent management component'),
    ('agent Manages 组件', 'agent management component'),
    
    # 单个步骤 -> single step
    (' — 单个步骤.', ' — single step.'),
    (' — 单个步骤', ' — single step'),
    
    # Select器组件 -> selector component
    (' — Select器组件', ' — selector component'),
    
    # 组件 -> component (remaining)
    ('` 组件.', ' component.'),
    ('` 组件', ' component'),
    
    # 对话框 -> dialog (remaining)  
    ('` 对话框.', ' dialog.'),
    ('` 对话框', ' dialog'),
    
    # 菜单或面板 -> menu or panel
    ('` 菜单或面板.', ' menu or panel.'),
    ('` 菜单或面板', ' menu or panel'),
    
    # 视图 -> view
    ('` 视图.', ' view.'),
    ('` 视图', ' view'),
    
    # 列表 -> list
    ('` 列表.', ' list.'),
    ('` 列表', ' list'),
    
    # 模块 -> module (remaining)
    ('模块，— module', 'module, — module'),
    
    # 子系统 -> subsystem
    ('子系统', 'subsystem'),
    
    # 路由 -> routing
    ('路由', 'routing'),
    
    # Fix Renders/Implements patterns that got partially mangled
    ('Renders workspace UI — ', 'Renders the '),
    ('Implements workspace UI — ', 'Implements the '),
    
    # Fix "Renders the X component in the workspace UI component" -> "Renders the X component in the workspace UI"
    ('in the workspace UI component', 'in the workspace UI'),
    ('in the workspace UI dialog', 'in the workspace UI'),
    ('in the workspace UI menu or panel', 'in the workspace UI'),
    
    # Fix remaining patterns like "Design system component — X" component
    ('design system component', 'design system component'),
]

for old, new in replacements:
    content = content.replace(old, new)

# Pattern: "X — Y` component" where X is a module
content = re.sub(
    r'(Renders|Implements) ([a-zA-Z0-9_/]+)(?: component)? — ([a-zA-Z]+)` component',
    r'\1 the \3 component in the \2',
    content
)

# Pattern: "Renders [module] component — [Name]` component" 
content = re.sub(
    r'Renders ([a-zA-Z0-9_/]+) component — ([a-zA-Z]+)` component',
    r'Renders the \2 component in the \1',
    content
)

# Fix duplicate "in the X" patterns
content = re.sub(r'in the the ', 'the ', content)
content = re.sub(r'  +', ' ', content)

# Fix trailing artifacts
content = content.replace('` component.', ' component.')
content = content.replace('` component', ' component')
content = content.replace('` dialog.', ' dialog.')
content = content.replace('` dialog', ' dialog')
content = content.replace('` view.', ' view.')
content = content.replace('` view', ' view')
content = content.replace('` list.', ' list.')
content = content.replace('` list', ' list')

# Fix "Renders the X command — Y` component" patterns
content = re.sub(
    r'Renders the (`[a-zA-Z_-]+` command)(?: component)? — ([a-zA-Z]+)` component',
    r'Renders \1 — \2 component',
    content
)

# More cleanup
content = content.replace('Renders the the', 'Renders the')
content = content.replace('Implements the the', 'Implements the')

# Fix: "Implements the X dialog in the workspace UI" (correct pattern but with "in the" duplication)
content = re.sub(r'in the (workspace UI|design system|command system) component', r'in the \1', content)

# Fix remaining explicit "in the X component" where it should just be "in the X"
content = re.sub(r'in the ([a-zA-Z/]+) component$', r'in the \1', content, flags=re.MULTILINE)
content = re.sub(r'in the ([a-zA-Z/]+) component\.$', r'in the \1.', content, flags=re.MULTILINE)

after = sum(1 for l in content.split('\n') if has_chinese(l))
print(f"Lines with Chinese before: {before}")
print(f"Lines with Chinese after: {after}")

with open(PATH, 'w') as f:
    f.write(content)

print("Done!")
