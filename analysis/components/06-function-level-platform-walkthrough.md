# Component System Deep Dive (6): Platform Control Plane Function-Level Implementation Breakdown

[Back to Table of Contents](../../README.md)

[Previous Chapter: Core Component Function-Level Implementation Breakdown](./05-function-level-core-walkthrough.md)

## 1. Chapter Guide

This chapter maintains the function-level granularity, but switches the subject to the platform control plane:

- permissions
- tasks
- agents
- mcp
- teams
- memory
- skills
- hooks
- design-system

The focus is not "which directory they belong to," but "which specific function is responsible for mapping, switching, aggregating, dispatching, and syncing."

## 2. permissions: From Tool Type Mapping to Approval UI

Location:

- [`src/components/permissions/PermissionRequest.tsx`](../../src/components/permissions/PermissionRequest.tsx)

### 2.1 `permissionComponentForTool(tool)`

Implementation responsibilities:

- Maps a specific `Tool` type to a specific approval component
- For example:
  - `FileEditTool -> FileEditPermissionRequest`
  - `BashTool -> BashPermissionRequest`
  - `WebFetchTool -> WebFetchPermissionRequest`
  - `GlobTool/GrepTool/FileReadTool -> FilesystemPermissionRequest`
- Feature-gated tools with missing implementation fall back to `FallbackPermissionRequest`

This shows that the permission UI dispatch is based not on strings, but on the tool class object itself.

### 2.2 `getNotificationMessage(toolUseConfirm)`

Implementation responsibilities:

- Gets the user-facing tool name via `tool.userFacingName(input)`
- Returns specialized text for special tools like enter/exit plan mode, review artifact
- Falls back to a generic message if tool name is unavailable

It is responsible for the notification semantics of the permission dialog, not the approval itself.

### 2.3 `PermissionRequest(...)`

Implementation responsibilities:

- Constructs the rejection chain:
  - `onDone()`
  - `onReject()`
  - `toolUseConfirm.onReject()`
- Binds `app:interrupt`
- Calls `useNotifyAfterTimeout(notificationMessage, 'permission_prompt')`
- Selects the actual approval component based on `toolUseConfirm.tool`
- Passes down `toolUseConfirm / toolUseContext / verbose / workerBadge / setStickyFooter`

It is essentially "the unified approval entry point + tool approval component router."

## 3. tasks: Background Task Workspace Function-Level Implementation

Location:

- [`src/components/tasks/BackgroundTasksDialog.tsx`](../../src/components/tasks/BackgroundTasksDialog.tsx)

### 3.1 `getSelectableBackgroundTasks(tasks, foregroundedTaskId)`

Implementation responsibilities:

- First filters for `isBackgroundTask`
- Then excludes the current foreground `local_agent`

The purpose of this is to prevent an agent already being viewed in the main interface from appearing again in the task dialog.

### 3.2 `BackgroundTasksDialog(...)`

Implementation responsibilities:

- Gets `tasks`, `foregroundedTaskId`, `expandedView` from `AppState`
- Determines initial viewState based on `initialDetailTaskId` or "only one task remaining"
- Prevents upper-level Chat shortcut leaks via `useRegisterOverlay('background-tasks-dialog')`
- Uses `useMemo` to convert all background tasks into list items and sort/group them:
  - bash
  - remote agent
  - local agent
  - teammates
  - workflows
  - MCP monitors
  - dream
- Binds `confirm:previous/next/yes` to list navigation via `useKeybindings`

Its core is not display, but "normalizing multiple backend execution bodies into a unified navigation list."

### 3.3 `toListItem(task)`

Implementation responsibilities:

- Uniformly maps by task.type into `ListItem`
- Extracts the most appropriate label for each task type:
  - shell uses `command` or `description`
  - remote agent uses `title`
  - local agent uses `description`
  - teammate uses `@agentName`
  - workflow uses `summary ?? description`

This step converts the backend task state model into a frontend displayable model.

### 3.4 `Item(...)`

Implementation responsibilities:

- Calculates `maxActivityWidth` based on terminal width
- Uses `isCoordinatorMode()` to decide whether the selection pointer uses gray
- If `item.type === 'leader'`, directly shows `@TEAM_LEAD_NAME`
- Otherwise delegates to `BackgroundTaskComponent`

It is the unified renderer for task list items.

### 3.5 `TeammateTaskGroups(...)`

Implementation responsibilities:

- Separates `leader` and `in_process_teammate`
- Then groups teammates by `teamName`
- Generates a team-grouped list

This shows that the task dialog does not flatten teammates as ordinary tasks, but preserves team semantics.

## 4. agents: Function-Level Implementation of Agent Creation and Browsing

Location:

- [`src/components/agents/AgentsMenu.tsx`](../../src/components/agents/AgentsMenu.tsx)
- [`src/components/agents/AgentDetail.tsx`](../../src/components/agents/AgentDetail.tsx)
- [`src/components/agents/new-agent-creation/CreateAgentWizard.tsx`](../../src/components/agents/new-agent-creation/CreateAgentWizard.tsx)

### 4.1 `AgentsMenu(...)`

Implementation responsibilities:

- Reads `agentDefinitions`, `mcpTools`, `toolPermissionContext` from `AppState`
- Calls `useMergedTools(tools, mcpTools, toolPermissionContext)` to form the complete tool set
- Splits `allAgents` by source:
  - built-in
  - userSettings
  - projectSettings
  - policySettings
  - localSettings
  - flagSettings
  - plugin
- Uses `resolveAgentOverrides(...)` to get the final effective resolved agents
- Handles mode switching for creation, deletion, details, editing, wizard, etc.

This function is the master state machine of the agent control plane.

### 4.2 `AgentDetail(...)`

Implementation responsibilities:

- Calls `resolveAgentTools(agent, tools, false)` to compute valid/invalid tools
- Uses `getActualRelativeAgentFilePath(agent)` to determine the file source
- Uses `getAgentColor(agent.agentType)` to decide color display
- Shows the model via `getAgentModelDisplay(agent.model)`
- Shows memory scope via `getMemoryScopeDisplay(agent.memory)`
- For non-built-in agents, also renders `agent.getSystemPrompt()`

The focus of this function is "expanding the agent definition object into a user-reviewable configuration unit."

### 4.3 `CreateAgentWizard(...)`

Implementation responsibilities:

- Dynamically builds the wizard steps array
- Wraps `TypeStep` and `ToolsStep` into closure steps with props
- Only inserts `MemoryStep` when `isAutoMemoryEnabled()`
- Uses `ConfirmStepWrapper` for the last page
- Passes these steps to `WizardProvider`

The key design is: the agent creation flow is not hardcoded pages, but "array-driven steps."

## 5. mcp: MCP Panel Function-Level Implementation

Location:

- [`src/components/mcp/MCPSettings.tsx`](../../src/components/mcp/MCPSettings.tsx)

### 5.1 `MCPSettings(...)`

Implementation responsibilities:

- Reads `mcp` and `agentDefinitions` from `AppState`
- Calls `extractAgentMcpServers(agentDefinitions.allAgents)` to get agent-bound MCP servers
- Filters `mcp.clients`, keeping displayable clients
- In an effect, executes `prepareServers()`:
  - Iterates each client
  - Determines transport type (`sse/http/stdio/claudeai-proxy`)
  - For `sse/http`, uses `ClaudeAuthProvider(...).tokens()` to probe authentication status
  - Combines session ingress token and "connected and has tools" to infer `isAuthenticated`
  - Finally writes to `servers`
- If both `servers` and `agentMcpServers` are empty, calls `onComplete(...)` with an empty config message
- Then switches between list / server-menu / server-tools views via `viewState.type`

This function is essentially the MCP console's state machine builder and server metadata aggregator.

## 6. teams: Multi-Agent Collaboration Control Plane Function-Level Implementation

Location:

- [`src/components/teams/TeamsDialog.tsx`](../../src/components/teams/TeamsDialog.tsx)

### 6.1 `TeamsDialog(...)`

Implementation responsibilities:

- Registers `useRegisterOverlay('teams-dialog')`
- Uses `dialogLevel` to distinguish `teammateList` from `teammateDetail`
- Uses `getTeammateStatuses(dialogLevel.teamName)` and polling `refreshKey` to refresh state
- Uses `handleCycleMode` to implement:
  - Detail page cycles only a single teammate
  - List page batch cycles all teammates
- Uses `useInput(...)` to directly handle:
  - Left/right, up/down navigation
  - Enter to drill down or jump to pane
  - `k` kill
  - `s` graceful shutdown
  - `h/H` hide/show
  - `p` prune idle teammates

It is the main state machine of the swarm console.

### 6.2 `sendModeChangeToTeammate(teammateName, teamName, targetMode)`

Implementation responsibilities:

- First calls `setMemberMode(...)` to directly change config, ensuring UI is immediately visible
- Then constructs `createModeSetRequestMessage(...)`
- Sends via `writeToMailbox(...)` to the teammate

This is a "dual-write" strategy: first update local config, then send a mailbox notification to the remote agent to update runtime state.

### 6.3 `cycleTeammateMode(teammate, teamName, isBypassAvailable)`

Implementation responsibilities:

- Constructs a minimal `ToolPermissionContext` from the teammate's current mode
- Calls `getNextPermissionMode(context)` to calculate the next mode level
- Then calls `sendModeChangeToTeammate(...)`

### 6.4 `cycleAllTeammateModes(teammates, teamName, isBypassAvailable)`

Implementation responsibilities:

- First collects all teammates' current modes
- If modes are inconsistent, resets them all to `default`
- If consistent, switches them all to the next mode uniformly
- Uses `setMultipleMemberModes(teamName, modeUpdates)` for batched config writes
- Then sends mailbox messages to each teammate individually

This solves one of the most typical consistency problems in multi-agent collaboration: team permission mode either resets together or advances to the next level together.

## 7. memory / skills / hooks: Knowledge & Configuration Panel Function-Level Implementation

### 7.1 `MemoryFileSelector(...)`

Location:

- [`src/components/memory/MemoryFileSelector.tsx`](../../src/components/memory/MemoryFileSelector.tsx)

Implementation responsibilities:

- Reads the memory file tree using `use(getMemoryFiles())`
- Manually fills in user/project root `CLAUDE.md`, even if the file does not yet exist
- Constructs depth based on `parent`, generating nested labels
- Decides whether project memory description is "Checked in at ./CLAUDE.md" or "Saved in ./CLAUDE.md" based on git repo status
- If auto-memory is enabled, adds:
  - auto-memory folder
  - team-memory folder
  - Each agent memory folder
- Retains last selection via `lastSelectedPath`
- Also maintains `autoMemoryOn`, `autoDreamOn`, `lastDreamAt`

This function actually unifies the memory entry points scattered across the file system into a single "memory resource selector."

### 7.2 `getSourceTitle(source)` / `getSourceSubtitle(source, skills)`

Location:

- [`src/components/skills/SkillsMenu.tsx`](../../src/components/skills/SkillsMenu.tsx)

Implementation responsibilities:

- `getSourceTitle` converts `plugin`, `mcp`, and various setting sources into user-facing text
- `getSourceSubtitle`:
  - For `mcp` skills, extracts server name
  - For file-based skills, shows the corresponding path
  - If old `commands_DEPRECATED` form exists, also shows commands path

### 7.3 `SkillsMenu(...)`

Implementation responsibilities:

- Filters skill commands from `commands`
- Groups by `policy/user/project/local/flag/plugin/mcp`
- Sorts within each group
- Shows empty state dialog when no skills exist
- Renders group by group when skills exist, showing total skill count

This shows that the skills UI does not just list commands; it treats skills as an asset catalog aggregated by source.

### 7.4 `HooksConfigMenu(...)`

Location:

- [`src/components/hooks/HooksConfigMenu.tsx`](../../src/components/hooks/HooksConfigMenu.tsx)

Implementation responsibilities:

- Maintains `modeState`:
  - `select-event`
  - `select-matcher`
  - `select-hook`
  - `view-hook`
- Uses `useSettingsChange(...)` to detect whether policySettings has:
  - `disableAllHooks`
  - `allowManagedHooksOnly`
- Merges `toolNames + mcp.tools.map(name)` into `combinedToolNames`
- Calls `groupHooksByEventAndMatcher(appStateStore.getState(), combinedToolNames)`
- Then uses `getSortedMatchersForEvent(...)`, `getHooksForMatcher(...)` to derive current level data
- Binds `confirm:no` return logic for each level

This makes the hooks config browser an obvious layered state machine, not a simple collapsible list.

## 8. design-system: Generic Interaction Foundation Function-Level Implementation

### 8.1 `Dialog(...)`

Location:

- [`src/components/design-system/Dialog.tsx`](../../src/components/design-system/Dialog.tsx)

Implementation responsibilities:

- Handles default color and `isCancelActive`
- Calls `useExitOnCtrlCDWithKeybindings(...)` to construct `exitState`
- Uses `useKeybinding('confirm:no', onCancel, { context: 'Confirmation', isActive: isCancelActive })`
- If the user has already pressed an exit key once, shows "Press {keyName} again to exit"
- Otherwise shows standard action hints:
  - Enter confirm
  - Esc cancel
- When `hideBorder` is true, only returns content; otherwise wraps in a `Pane`

This function unifies "cancel, exit, border, input guide" for all terminal dialogs.

### 8.2 `ThemeProvider(...)`

Location:

- [`src/components/design-system/ThemeProvider.tsx`](../../src/components/design-system/ThemeProvider.tsx)

Implementation responsibilities:

- Maintains:
  - `themeSetting`
  - `previewTheme`
  - `systemTheme`
- Determines the currently active setting by `activeSetting = previewTheme ?? themeSetting`
- If `feature('AUTO_THEME')` and `activeSetting === 'auto'`, dynamically loads `watchSystemTheme(...)`
- Outputs a set of theme control functions via `useMemo`:
  - `setThemeSetting(newSetting)`
  - `setPreviewTheme(newSetting)`
  - `savePreview()`
  - `cancelPreview()`
- `useTheme()` returns `[currentTheme, setThemeSetting]`
- `useThemeSetting()` returns the raw setting
- `usePreviewTheme()` returns the preview controller

This set of functions cleanly splits the theme system into three layers: "persistent setting, temporary preview, system resolution."

## 9. Chapter Summary

After drilling down to the function level in the platform control plane, it can be seen:

- `PermissionRequest` routes tool approvals to specialized UI through function mapping.
- `BackgroundTasksDialog` normalizes multi-backend tasks into a task panel through `getSelectableBackgroundTasks`, `toListItem`, and grouping logic.
- `AgentsMenu`, `CreateAgentWizard`, and `AgentDetail` cover agent management, creation flow, and config expansion respectively.
- `MCPSettings` aggregates MCP transport and authentication state through `prepareServers()` logic.
- `TeamsDialog` implements teammate mode synchronization through mailbox and config dual-write functions.
- `MemoryFileSelector`, `SkillsMenu`, and `HooksConfigMenu` turn memory, skills, and hooks into truly browsable control plane resources.

In other words, the real complexity of these "platform capability components" is not in the UI shell, but in the function-level mapping, aggregation, synchronization, and state machine implementation.
