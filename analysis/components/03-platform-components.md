# Component System Deep Dive (3): Platform Capability Components & Control Plane Implementation

[Back to Table of Contents](../../README.md)

[Previous Chapter: Core Interaction Components](./02-core-interaction-components.md)

[Next Chapter: Component Index](./04-component-index.md)

## 1. Chapter Guide

If the previous chapter analyzed the "session backbone," this chapter analyzes the capability control plane that this agent platform exposes to the user.

The core conclusion is: most of the complex components in this project are not in the message display layer, but in the "permissions, agents, tasks, MCP, teams, Settings, memory, skills, hooks, sandbox" panels. Together, they wrap the execution kernel into a controllable platform.

Here is the overall platform control plane diagram:

```text
PromptInput / slash command / footer
 ├─> permissions
 ├─> tasks
 ├─> agents
 ├─> mcp
 ├─> teams
 ├─> Settings
 └─> memory / skills / hooks / sandbox

The above control planes uniformly depend downward on:
 -> AppState / Context / hooks
 -> services / tools / swarm / mcp / permissions / fs
```

## 2. permissions: The Permission Component Family Is the Heaviest Control Plane

Permission components live under [`src/components/permissions`](../../src/components/permissions), with the largest file count in the entire component directory.

### 2.1 Main Entry Point

The main entry point is [`src/components/permissions/PermissionRequest.tsx`](../../src/components/permissions/PermissionRequest.tsx).

This component's implementation is straightforward: it dispatches approval rendering to corresponding sub-components based on the tool type.

The sub-components it can dispatch to include:

- `FileEditPermissionRequest`
- `FileWritePermissionRequest`
- `BashPermissionRequest`
- `PowerShellPermissionRequest`
- `WebFetchPermissionRequest`
- `NotebookEditPermissionRequest`
- `SkillPermissionRequest`
- `AskUserQuestionPermissionRequest`
- `FilesystemPermissionRequest`
- Permission requests corresponding to plan mode enter/exit

### 2.2 Design Features

The highlight of this layer is:

- Permission logic is not hardcoded in tools, but handled by the permission component family for final interaction
- The same `ToolUseConfirm` protocol can be consumed by multiple sub-components
- Sticky footer, reject/allow, user interaction detection, classifier auto-approve, etc. are all incorporated into a unified interface

This makes permission mode truly a system-level mechanism, not just "showing a confirmation dialog."

### 2.3 Sub-component Structure

This directory also contains several important types of sub-components:

- File-related UI: `FilePermissionDialog/*`
- Rule-related UI: `permissions/rules/*`
- Plan approval: `EnterPlanModePermissionRequest`, `ExitPlanModePermissionRequest`
- Specialized tool approval: such as bash, web fetch, skill, notebook edit

This set of components embodies a principle: permission approval is scenario-specific UI, not a uniform template applied rigidly to all tools.

## 3. tasks: Background Task Workspace

Core files are in [`src/components/tasks`](../../src/components/tasks).

### 3.1 Main Entry Point

[`src/components/tasks/BackgroundTasksDialog.tsx`](../../src/components/tasks/BackgroundTasksDialog.tsx) is the main entry point for the task panel.

It reads background tasks from `AppState.tasks` and further distinguishes:

- local bash
- remote agent
- local agent
- in-process teammate
- local workflow
- monitor MCP
- dream

This shows that "tasks" in this project are not a single type, but a multi-backend state collection above a unified abstraction.

### 3.2 Detail Sub-components

Task details are respectively delegated to:

- `AsyncAgentDetailDialog`
- `ShellDetailDialog`
- `RemoteSessionDetailDialog`
- `InProcessTeammateDetailDialog`
- `DreamDetailDialog`
- Feature-gated detail dialogs for workflow/monitor

In other words, `BackgroundTasksDialog` is the state machine and list view controller, while specific task descriptions are handled by their respective detail components.

### 3.3 Design Implications of Task Components

These components formally incorporate "background execution bodies" into the UI: users are not limited to waiting for model responses, but can view the asynchronous status of agents, shells, workflows, and MCP monitors.

## 4. agents: Agent Lifecycle Management Interface

The core directory is [`src/components/agents`](../../src/components/agents).

### 4.1 Main Entry Point

[`src/components/agents/AgentsMenu.tsx`](../../src/components/agents/AgentsMenu.tsx) is the agent management master controller.

It is responsible for:

- Aggregating agent definitions from various sources
- Displaying grouped by source
- Merging MCP tools and local tools
- Switching between list, detail, edit, and creation wizard
- Refreshing `AppState.agentDefinitions` after deleting an agent

### 4.2 Sub-component Division

Regular management sub-components:

- [`AgentDetail.tsx`](../../src/components/agents/AgentDetail.tsx)
- [`AgentEditor.tsx`](../../src/components/agents/AgentEditor.tsx)
- [`AgentsList.tsx`](../../src/components/agents/AgentsList.tsx)
- [`AgentNavigationFooter.tsx`](../../src/components/agents/AgentNavigationFooter.tsx)

Edit helper sub-components:

- `ColorPicker`
- `ModelSelector`
- `ToolSelector`
- `validateAgent`
- `agentFileUtils`

Creation wizard:

- [`new-agent-creation/CreateAgentWizard.tsx`](../../src/components/agents/new-agent-creation/CreateAgentWizard.tsx)
- And `wizard-steps/*`

### 4.3 Sub-component Highlights

[`AgentDetail.tsx`](../../src/components/agents/AgentDetail.tsx) is very representative. It does not just display the agent name and description, but directly shows:

- Parsed tools results
- Model
- Permission mode
- Memory scope
- Hooks
- Skills
- Color
- System prompt

In other words, an agent is treated in the UI as a complete runtime configuration unit, not just a piece of prompt text.

## 5. mcp: MCP Management Component Family

The core directory is [`src/components/mcp`](../../src/components/mcp).

### 5.1 Main Entry Point

[`src/components/mcp/MCPSettings.tsx`](../../src/components/mcp/MCPSettings.tsx) is the main entry point for the MCP panel.

It extracts from `AppState.mcp` and `agentDefinitions`:

- Normal MCP clients
- Agent-bound MCP servers
- Server transport types
- Authentication status
- Tools available under a given server

### 5.2 View State Machine

`MCPSettings` is not a single-page view internally, but a menu system with a state machine. Views include:

- list
- server-menu
- agent-server-menu
- server-tools
- tool-detail

Corresponding sub-components include:

- `MCPListPanel`
- `MCPStdioServerMenu`
- `MCPRemoteServerMenu`
- `MCPAgentServerMenu`
- `MCPToolListView`
- `MCPToolDetailView`

It is more intuitive as a state machine diagram:

```text
MCPSettings View State Machine

list
 -> server-menu
 -> server-tools
 -> tool-detail
 -> back to server-tools
 -> back to list

list
 -> agent-server-menu
 -> server-tools
 -> tool-detail
 -> back to server-tools
 -> back to list
```

### 5.3 Design Assessment

Here, MCP is not just "a settings item," but is treated as a first-class platform capability. The UI already covers:

- Transport differentiation
- Auth status
- Tool filtering
- Server-level and tool-level two-layer browsing

This is far more complete than many CLI tools that only "list MCP server names."

## 6. Settings: Three-Part Structure of Status, Config & Usage

The structure of [`src/components/Settings/Settings.tsx`](../../src/components/Settings/Settings.tsx) is very clear:

- `Status`
- `Config`
- `Usage`
- Ant-only `Gates`

Its implementation highlights are:

- Unified page navigation via `Tabs`
- Adapting to both modal and terminal sizes via `contentHeight`
- Allowing `Config` / `Gates` to temporarily take over Esc, avoiding conflicts between search state and global cancel key

This shows that the settings page is not a purely static form, but a tool panel with internal interaction state.

## 7. teams: Multi-Agent Collaboration View

[`src/components/teams/TeamsDialog.tsx`](../../src/components/teams/TeamsDialog.tsx) is the main UI entry for the swarm/teammate view.

### 7.1 Two-Layer View

It has only two main levels:

- teammateList
- teammateDetail

But behavior-wise it is very heavy, supporting:

- Viewing teammate status
- Switching permission mode
- Killing a teammate
- Graceful shutdown
- Hide/show teammate pane
- One-click prune idle teammates
- Navigating to the corresponding output pane

### 7.2 Many Backend Dependencies

This component simultaneously connects to:

- Teammate mailbox
- Swarm backends registry
- Team helpers
- Tasks utilities
- Tmux/IT2 pane backend

So it is actually the terminal console for the "multi-agent collaboration backend," not just a list.

From a control plane perspective, the relationship between tasks, teams, and permissions is roughly as follows:

```text
User Actions
 -> BackgroundTasksDialog
 -> AppState.tasks
 -> agent / shell / workflow / remote runtime

 -> TeamsDialog
 -> teammate mailbox / swarm backends / pane state
 -> agent / shell / workflow / remote runtime

 -> PermissionRequest/*
 -> ToolUseConfirm / permission rules / classifier state
 -> agent / shell / workflow / remote runtime
```

## 8. memoryskillshookssandbox: Configuration & Knowledge Panels

### 8.1 memory

Memory components mainly live in [`src/components/memory`](../../src/components/memory).

Among them:

- [`MemoryFileSelector.tsx`](../../src/components/memory/MemoryFileSelector.tsx) is responsible for browsing and opening entry points for user, project, auto-memory, team-memory, and agent-memory
- `MemoryUpdateNotification` is responsible for notifying the user of the path after memory is written

This set of components is important because it unifies the memory file system, which was originally scattered across multiple directories, into a single user-visible entry point.

### 8.2 skills

[`src/components/skills/SkillsMenu.tsx`](../../src/components/skills/SkillsMenu.tsx) displays skills by source dimension:

- policy
- user
- project
- local
- plugin
- mcp

Its value lies in turning "skills" from scattered file system points into a browsable asset catalog.

### 8.3 hooks

[`src/components/hooks/HooksConfigMenu.tsx`](../../src/components/hooks/HooksConfigMenu.tsx) is the hooks configuration browser.

This menu is intentionally read-only, supporting:

- Browsing by event
- Browsing by matcher
- Then viewing the specific hook

This design is pragmatic: it avoids reinventing a settings.json editor in the terminal.

### 8.4 sandbox

The components under [`src/components/sandbox`](../../src/components/sandbox) split sandbox into:

- `SandboxSettings`
- `SandboxConfigTab`
- `SandboxDependenciesTab`
- `SandboxOverridesTab`
- `SandboxDoctorSection`

This shows that sandbox in this project is not a boolean toggle, but an entire set of diagnosable, configurable, overridable runtime environment subsystems.

## 9. Grove & Policy/Compliance Components

[`src/components/grove/Grove.tsx`](../../src/components/grove/Grove.tsx) is worth calling out separately.

It handles:

- Whether the user has seen new terms / policy notices
- Opt-in / opt-out / defer interactions
- Synchronization with API settings
- Analytics event recording

These kinds of components, together with `TrustDialog` and `ManagedSettingsSecurityDialog`, form a less common but important category: compliance and policy notice components.

## 10. design-system: Foundation of the Terminal Design System

The design system directory is at [`src/components/design-system`](../../src/components/design-system).

### 10.1 Key Building Blocks

The most core building blocks include:

- [`Dialog.tsx`](../../src/components/design-system/Dialog.tsx)
- [`Pane.tsx`](../../src/components/design-system/Pane.tsx)
- [`Tabs.tsx`](../../src/components/design-system/Tabs.tsx)
- [`ListItem.tsx`](../../src/components/design-system/ListItem.tsx)
- [`ThemeProvider.tsx`](../../src/components/design-system/ThemeProvider.tsx)
- `ThemedBox`
- `ThemedText`
- `KeyboardShortcutHint`
- `Byline`

### 10.2 Representative Design

`Dialog`'s design shows this system is very sensitive to terminal input conflicts:

- Built-in `confirm:no`
- Supports `isCancelActive`
- Supports custom input guide
- Supports Ctrl+C/D pending exit prompt

`ThemeProvider` shows that the theme system is not a simple string switch; it supports:

- Theme setting persistence
- Preview theme
- Auto theme
- Listening for terminal system theme changes

This design-system allows upper-level business components to build on a unified interaction semantic, without each dialog having to handle shortcuts and borders by itself.

## 11. Chapter Summary

The overall assessment of platform capability components is:

- `permissions` handles the approval control plane.
- `tasks` handles the async execution workspace.
- `agents` handles agent lifecycle management.
- `mcp` handles external capability access management.
- `teams` handles multi-agent collaboration control.
- `memory/skills/hooks/sandbox/settings` handle configuration, knowledge, and runtime environment visualization entry points.

In other words, this component system has already far exceeded a "chat UI," implementing an agent platform console in the terminal.
