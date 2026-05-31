# Component System Deep Dive (1): Component Overview, Layering & Dependency Backbone

[Back to Table of Contents](../../README.md)

[Next Chapter: Core Interaction Components](./02-core-interaction-components.md)

## 1. Chapter Guide

This set of chapters no longer starts from the "execution kernel," but instead approaches from `src/components/`, answering three questions:

1. How is the component tree layered, and which components are the true hubs.
2. What are the dependency directions between component families, and how do child components get orchestrated by their parents.
3. What common design patterns exist across component implementations.

TL;DR: This project's component system is not a "page + buttons" frontend structure, but a TUI component platform organized around a terminal agent workspace. Its typical path is:

`App -> REPL/FullscreenLayout -> Messages + PromptInput -> Capability Layers/Capability Panels -> services/state/hooks/tools/tasks`

The true dual hubs are:

- [`src/components/Messages.tsx`](../../src/components/Messages.tsx)
- [`src/components/PromptInput/PromptInput.tsx`](../../src/components/PromptInput/PromptInput.tsx)

The former is responsible for "displaying what has happened," and the latter for "organizing what to do next."

Here is the component backbone diagram:

```text
App
 -> REPL / FullscreenLayout
 -> Messages
 | -> VirtualMessageList
 | -> MessageRow / Message / messages/*
 |
 -> PromptInput
 -> Footer / Suggestions / Notifications
 -> QuickOpen / Search / Tasks / Teams / Bridge / ModelPicker

Messages and PromptInput both depend downward on:
 -> AppState
 -> hooks
 -> services
```

## 2. Component Layering

### 2.1 Provider & Root Wrapper Layer

The root wrapper component is [`src/components/App.tsx`](../../src/components/App.tsx).

It does not implement complex UI itself, but is responsible for setting up the context needed for an interactive session:

- [`src/state/AppState.tsx`](../../src/state/AppState.tsx) provides the global state store
- [`src/context/stats.tsx`](../../src/context/stats.tsx) provides statistics context
- [`src/context/fpsMetrics.tsx`](../../src/context/fpsMetrics.tsx) provides rendering performance metrics

This shows that the project's component tree is not a "stateless display tree" from the start, but a "workspace tree with runtime state, statistics, and performance sampling."

### 2.2 Session Workspace Layer

The session workspace layer is responsible for combining the message area, input area, scroll area, status bar, and overlays. Core files include:

- [`src/components/FullscreenLayout.tsx`](../../src/components/FullscreenLayout.tsx)
- [`src/components/Messages.tsx`](../../src/components/Messages.tsx)
- [`src/components/PromptInput/PromptInput.tsx`](../../src/components/PromptInput/PromptInput.tsx)
- [`src/components/ScrollKeybindingHandler.tsx`](../../src/components/ScrollKeybindingHandler.tsx)
- [`src/hooks/useGlobalKeybindings.tsx`](../../src/hooks/useGlobalKeybindings.tsx)

This layer is the true "terminal workspace shell." It is responsible for:

- Assembling the transcript and input box into the same interactive plane
- Managing global shortcuts, scrolling, searching, transcript mode, brief mode
- Providing mount points for various dialogs and panels

### 2.3 Session Rendering Layer

The session rendering layer consists of the following component chain:

- [`src/components/Messages.tsx`](../../src/components/Messages.tsx)
- [`src/components/VirtualMessageList.tsx`](../../src/components/VirtualMessageList.tsx)
- [`src/components/MessageRow.tsx`](../../src/components/MessageRow.tsx)
- [`src/components/Message.tsx`](../../src/components/Message.tsx)
- [`src/components/messages`](../../src/components/messages)

The responsibility of this layer is not "simply mapping an array of messages," but:

- Normalizing messages
- Folding and grouping tool calls, read/search, hooks, and background bash notifications
- Taking different rendering paths depending on fullscreen/transcript/brief mode
- Reducing re-render cost through virtual list and offscreen freeze for long sessions

### 2.4 Input Orchestration Layer

The input orchestration layer uses [`src/components/PromptInput/PromptInput.tsx`](../../src/components/PromptInput/PromptInput.tsx) as its main entry point, decomposing into:

- `PromptInputFooter`
- `PromptInputFooterLeftSide`
- `PromptInputFooterSuggestions`
- `PromptInputModeIndicator`
- `PromptInputQueuedCommands`
- `PromptInputStashNotice`
- `Notifications`
- Several `use*` helper hooks

This layer is responsible for unifying actual user input, completion suggestions, history retrieval, image pasting, mode switching, background task entry points, team/bridge/quick open/global search, etc.

### 2.5 Capability Panels & Capability Overlay Layer

This is the "control plane UI," with the most widely distributed components, mainly including:

- agents[`src/components/agents`](../../src/components/agents)
- permissions[`src/components/permissions`](../../src/components/permissions)
- tasks[`src/components/tasks`](../../src/components/tasks)
- mcp[`src/components/mcp`](../../src/components/mcp)
- Settings[`src/components/Settings`](../../src/components/Settings)
- teams[`src/components/teams`](../../src/components/teams)
- hooks[`src/components/hooks`](../../src/components/hooks)
- memory[`src/components/memory`](../../src/components/memory)
- skills[`src/components/skills`](../../src/components/skills)
- sandbox[`src/components/sandbox`](../../src/components/sandbox)

These components do not directly drive the main query loop, but they determine how the workspace exposes agent platform capabilities.

### 2.6 Design System & Common Components Layer

This layer mainly lives in:

- [`src/components/design-system`](../../src/components/design-system)
- [`src/components/ui`](../../src/components/ui)
- [`src/components/wizard`](../../src/components/wizard)
- [`src/components/CustomSelect`](../../src/components/CustomSelect)

They provide reusable building blocks for the terminal UI, such as:

- `Dialog`
- `Pane`
- `Tabs`
- `ListItem`
- `ThemedText`
- `TreeSelect`
- `WizardProvider`
- `Select`

The project does not depend on an external mature terminal design system, but has grown its own component foundation on top of Ink.

## 3. Component Family Distribution

By directory statistics, the main component families of `src/components/` are as follows:

| Component Family | File Count | Description |
| --- | ---: | --- |
| `permissions` | 51 | Permission requests, file comparison, rules & approval UI |
| `messages` | 41 | Message type rendering & tool result sub-components |
| `agents` | 26 | Agent list, details, editing, creation wizard |
| `PromptInput` | 21 | Input box, suggestions, notifications, footer, mode |
| `design-system` | 16 | Terminal UI base components |
| `mcp` | 13 | MCP service & tool views |
| `tasks` | 12 | Background task list, details, progress view |
| `Spinner` | 12 | Various state spinner variants |
| `FeedbackSurvey` | 9 | Survey/feedback UI |
| `CustomSelect` | 10 | Dropdown, selector, cursor movement logic |

This set of statistics is very telling: in this project, "permissions, messages, agents, input, MCP, tasks" are the true center of gravity of component design.

## 4. Dependency Backbone

### 4.1 Backbone Dependency Relationships

From high to low, the component dependency relationships can be summarized as:

1. `App` first establishes Providers.
2. The workspace layer mounts `Messages` and `PromptInput` side by side.
3. `Messages` further splits messages into `VirtualMessageList -> MessageRow -> Message -> messages/*`.
4. `PromptInput` further splits input and panels into footer, suggestions, dialogs, task/team/bridge/search, and other sub-components.
5. Panel-type components then depend downward on `state/context/hooks/services/tools/tasks`.

This dependency direction has two characteristics:

- The interaction backbone is very clear, and the main path is not polluted by edge capabilities like "settings pages."
- Capability panels do not depend directly on each other, but collectively depend on `AppState`, hooks, and services, so horizontal coupling is controllable.

It can also be understood in the form of "orchestration layer -> rendering layer -> state/service layer":

```text
Orchestration Layer
 - App
 - REPL
 - Messages
 - PromptInput
 |
 +--> Rendering Layer
 | - message leaves
 | - dialog leaves
 | - select leaves
 |
 +--> Capability Panel Layer
 - permissions
 - agents
 - mcp
 - tasks
 - teams

Rendering Layer / Capability Panel Layer
 -> State & Context
 - AppState
 - overlay
 - notifications
 -> hooks / services / tools / tasks
```

### 4.2 State Injection Method

The component layer does not use the traditional Redux `connect` style, but heavily uses:

- `useAppState` from [`src/state/AppState.tsx`](../../src/state/AppState.tsx)
- `useSetAppState`
- `useAppStateStore`
- Overlay, notifications, mailbox, modal and other providers from context

The slice subscription design of `useAppState` is critical. It requires the selector to directly return stable slices, not temporary objects, so components do not re-render wholesale due to minor changes in global state.

### 4.3 Hook-Driven Rather Than Class Controller-Driven

The component system heavily relies on hooks as the behavior injection layer, typically including:

- [`src/hooks/useGlobalKeybindings.tsx`](../../src/hooks/useGlobalKeybindings.tsx)
- [`src/hooks/useVirtualScroll.ts`](../../src/hooks/useVirtualScroll.ts)
- [`src/hooks/useArrowKeyHistory.tsx`](../../src/hooks/useArrowKeyHistory.tsx)
- [`src/hooks/useTypeahead.tsx`](../../src/hooks/useTypeahead.tsx)
- [`src/hooks/useCommandQueue.ts`](../../src/hooks/useCommandQueue.ts)
- [`src/hooks/usePromptSuggestion.ts`](../../src/hooks/usePromptSuggestion.ts)

This means the "display structure" and "interaction behavior" of components are clearly separated. When adding new capabilities in the future, the priority is to add new hooks or services, rather than continuing to bloat individual components.

## 5. Common Design Patterns at the Implementation Level

### 5.1 Clear Orchestrator / Leaf Layering

Almost every component family can distinguish two types of components:

- orchestrator: manages state, switches views, calls hooks or services
- leaf: only responsible for rendering a specific sub-block

For example, in the message chain:

- orchestrators are `Messages`, `MessageRow`, `Message`
- leaves are `AssistantTextMessage`, `UserTextMessage`, `RateLimitMessage`, etc.

For example, in the agent component family:

- orchestrator is `AgentsMenu`
- leaves are `AgentDetail`, `AgentEditor`, `ColorPicker`, `ToolSelector`

This decomposition allows the upper layer to be responsible for orchestration, while the lower layer handles replaceable rendering.

### 5.2 Specialized Optimization for Terminal Performance

From the source code, you can see many optimization points not typically found in ordinary Web React projects:

- `VirtualMessageList` handles message virtualization and search indexing
- `OffscreenFreeze` avoids repeated re-rendering of offscreen areas
- `MessageRow` pre-computes `hasContentAfterIndex`, avoiding passing the entire history array to children
- `Messages` memoizes the logo header, preventing leading nodes from polluting full-screen blits

This shows the author is well aware: the bottleneck of this UI is not the DOM, but terminal screen redraws and extremely long transcripts.

### 5.3 Compile-Time Trimming via `feature()` and Lazy `require()`

Many components contain:

- `feature('...')`
- Conditional `require(...)`

For example, permissions, workflow, monitor, theme watcher, brief/proactive, etc. all adopt this pattern. The effect is:

- ant-only or internally gated features do not leak to external builds
- Can be dead-code eliminated during bundling
- Components do not unnecessarily introduce dependencies for unavailable features

### 5.4 Systematic Abstraction of Terminal Interaction Details

The component layer doesn't just "display things," but systematically abstracts terminal interaction objects:

- Dialog and Confirmation keybinding
- Overlay registration and conflict masking
- Sticky footer / modal / fullscreen scroll
- Theme preview / auto theme watcher
- Dual-track support for text input and vim input

This set of abstractions shows that the project is essentially building a terminal IDE-style workspace, not a single-page chat window.

## 6. Chapter Summary

The overall assessment of the component system is:

- `Messages` and `PromptInput` form the dual hubs of the session workspace.
- Most other component families are capability control planes centered around permissions, agents, MCP, tasks, and team collaboration.
- Component design emphasizes "upper-layer orchestration, lower-layer specialized rendering," and is heavily optimized for performance and interaction details in long terminal sessions.

The following two chapters dive into the two main lines:

- One is the core interaction line of "messages and input."
- One is the platform capability line of "permissions, agents, MCP, tasks, teams," etc.
