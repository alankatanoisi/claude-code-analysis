# Chapter 12: Program Architecture and Highlights

[Back to Table of Contents](../README.md)

---

## 1. Chapter Guide

This chapter only discusses the architectural highlights of Claude Code itself, without making comparisons to similar products (see [`analysis/08-competitive-comparison.md`](./08-competitive-comparison.md) for comparisons).

TL;DR: What sets this project apart from a "model API wrapper tool" comes down to three points that hold simultaneously:
1. **A unified execution kernel**, where multiple runtime modes reuse the same query/tool/permission loop
2. **A file-based, layered memory system** that is auditable, distributable, and governable
3. **Local-first but seamlessly extensible**, scaling smoothly from standalone local operation to remote/bridge/swarm

---

## 2. Highlight 1: Unified Execution Kernel

**Files**: [`src/query.ts`](../src/query.ts), [`src/QueryEngine.ts`](../src/QueryEngine.ts)

The most prominent engineering decision: using the same `query()` main loop to support all runtime modes:

```text
REPL (with UI) ──┐
headless/SDK ──┤
subagent (sub-task) ──┤──> query.ts / QueryEngine.ts ──> tool/memory/permission
background agent ──┤
bridge/remote ──┘
```

This means "how Claude calls tools in the local REPL" and "how Claude calls tools in a background automation task" go through **exactly the same code path** — there is no behavioral divergence risk from two separate implementations.

`query.ts` outputs an `AsyncGenerator<StreamEvent>`, and the caller (UI layer or SDK layer) simply consumes this stream:

```typescript
// src/query.ts (pseudocode skeleton)
export async function* query(
 userMessages: Message[],
 systemPrompt: SystemPrompt,
 toolUseContext: ToolUseContext,
 deps: QueryDeps,
): AsyncGenerator<StreamEvent> {
 let messages = userMessages

 while (true) {
 // 1. Call model API, stream output
 for await (const event of deps.claudeApi.stream(messages, systemPrompt)) {
 yield event
 }

 // 2. Check if there are tool_use blocks to execute
 const toolUseBlocks = extractToolUseBlocks(messages)
 if (toolUseBlocks.length === 0) break

 // 3. Execute tools, batched by concurrency safety
 for await (const update of runTools(toolUseBlocks,...)) {
 yield update
 }

 // 4. Append tool results to messages -> next loop iteration
 messages = appendToolResults(messages, toolResults)

 // 5. Session management: compact check, hook execution, memory update
 await executePostSamplingHooks(messages, toolUseContext)
 if (shouldAutoCompact(messages)) await compactConversation(messages,...)
 }
}
```

---

## 3. Highlight 2: Memory Is Not a Black Box

**Files**: [`src/memdir/memdir.ts`](../src/memdir/memdir.ts), [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts), [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts)

The unique aspect of the memory system: all memory is stored as **readable and writable Markdown files on the filesystem**, not in a black-box database.

`isAutoMemoryEnabled()` actual source code ([`src/memdir/paths.ts:30`](../src/memdir/paths.ts)) shows its control priority:

```typescript
// src/memdir/paths.ts
/**
 * Priority from highest to lowest:
 * 1. CLAUDE_CODE_DISABLE_AUTO_MEMORY environment variable
 * 2. CLAUDE_CODE_SIMPLE (--bare mode) -> disabled
 * 3. Remote mode without persistent storage -> disabled
 * 4. autoMemoryEnabled field in settings.json
 * 5. Default: enabled
 */
export function isAutoMemoryEnabled(): boolean {
 const envVal = process.env.CLAUDE_CODE_DISABLE_AUTO_MEMORY
 if (isEnvTruthy(envVal)) return false // explicitly disabled
 if (isEnvDefinedFalsy(envVal)) return true // explicitly enabled
 if (isEnvTruthy(process.env.CLAUDE_CODE_SIMPLE)) return false // --bare mode
 if (isEnvTruthy(process.env.CLAUDE_CODE_REMOTE) &&
 !process.env.CLAUDE_CODE_REMOTE_MEMORY_DIR) return false // remote without persistent storage
 const settings = getInitialSettings()
 if (settings.autoMemoryEnabled !== undefined) return settings.autoMemoryEnabled
 return true // default enabled
}
```

`MEMORY.md` index truncation protection (prevents unbounded growth):

```typescript
// src/memdir/memdir.ts
export const MAX_ENTRYPOINT_LINES = 200 // max 200 lines
export const MAX_ENTRYPOINT_BYTES = 25_000 // max 25KB

export function truncateEntrypointContent(raw: string): EntrypointTruncation {
 const lines = raw.trim().split('\n')
 let truncated = lines.length > MAX_ENTRYPOINT_LINES
 ? lines.slice(0, MAX_ENTRYPOINT_LINES).join('\n')
 : raw.trim()
 if (truncated.length > MAX_ENTRYPOINT_BYTES) {
 const cutAt = truncated.lastIndexOf('\n', MAX_ENTRYPOINT_BYTES)
 truncated = truncated.slice(0, cutAt > 0 ? cutAt : MAX_ENTRYPOINT_BYTES)
 }
 return { content: truncated + '\n\n> WARNING: MEMORY.md is truncated...',... }
}
```

This gives the Memory system three key properties:

| Property | Implementation |
|----------|---------------|
| Transparent | All memory is `.md` files on disk, users can `cat` to view directly |
| Governable | Four memory layers (Auto/Session/Agent/Team) each have independent toggles |
| Overflow protection | `truncateEntrypointContent()` hard-truncates to prevent prompt explosion |

---

## 4. Highlight 3: Permission System Is a Backbone, Not a Patch

**Files**: [`src/Tool.ts`](../src/Tool.ts), [`src/utils/permissions/permissionSetup.ts`](../src/utils/permissions/permissionSetup.ts)

The permission system is a first-class citizen from the `Tool` interface design stage, not a filter layer added afterward:

```typescript
// src/Tool.ts — Tool interface security-related fields (selected)
interface Tool {
 isConcurrencySafe(input: unknown): boolean // declares whether concurrency-safe
 isReadOnly(): boolean // declares whether read-only
 isDestructive(): boolean // declares whether destructive
 checkPermissions(input: unknown, context: ToolUseContext): PermissionResult
 preparePermissionMatcher(input: unknown): PermissionMatcher
 requiresUserInteraction(): boolean // whether UI interaction is needed (e.g., ask)
}
```

The default value strategy of `buildTool()` embodies the **fail-closed** principle:

```typescript
// src/Tool.ts
export function buildTool<T>(spec: ToolSpec<T>): Tool {
 return {
 isConcurrencySafe: spec.isConcurrencySafe ?? (() => false), // default: not concurrent
 isReadOnly: spec.isReadOnly ?? (() => false), // default: not read-only
 isDestructive: spec.isDestructive ?? (() => false), // default: not destructive
 checkPermissions: spec.checkPermissions ?? defaultAllow, // default: allow (controlled by outer permission system)
 //...
 }
}
```

When entering Auto mode, the system automatically strips dangerous permission rules:

```typescript
// src/utils/permissions/permissionSetup.ts
export function stripDangerousPermissionsForAutoMode(
 context: ToolPermissionContext,
): ToolPermissionContext {
 const dangerousPermissions = findDangerousClassifierPermissions(rules, [])
 // Remove dangerous rules from context but keep them in strippedDangerousRules
 return {
...removeDangerousPermissions(context, dangerousPermissions),
 strippedDangerousRules: stripped, // can be restored when exiting auto mode
 }
}

export function restoreDangerousPermissions(
 context: ToolPermissionContext,
): ToolPermissionContext {
 // When exiting auto mode, restore previously saved dangerous rules
 const stash = context.strippedDangerousRules
 for (const [source, ruleStrings] of Object.entries(stash)) {
 result = applyPermissionUpdate(result, { type: 'addRules', rules:..., destination: source })
 }
 return {...result, strippedDangerousRules: undefined }
}
```

---

## 5. Highlight 4: High Maturity of Multi-Agent Collaboration

**Files**: [`src/tools/AgentTool/runAgent.ts`](../src/tools/AgentTool/runAgent.ts), [`src/utils/swarm/backends/registry.ts`](../src/utils/swarm/backends/registry.ts)

The backend selection is auto-detected by `detectAndGetBackend()` ([`src/utils/swarm/backends/registry.ts:131`](../src/utils/swarm/backends/registry.ts)):

```typescript
// src/utils/swarm/backends/registry.ts
export async function detectAndGetBackend(): Promise<BackendDetectionResult> {
 await ensureBackendsRegistered()
 if (cachedDetectionResult) return cachedDetectionResult // cache result

 const insideTmux = await isInsideTmux()
 const inITerm2 = isInITerm2()

 // Priority: tmux > iTerm2 native pane > in-process
 if (insideTmux) {
 return { backend: createTmuxBackend(), isNative: true, needsIt2Setup: false }
 }
 if (inITerm2) {
 if (!check_it2_installed()) {
 return { backend: null, isNative: false, needsIt2Setup: true } // needs it2 install
 }
 return { backend: createITermBackend(), isNative: true, needsIt2Setup: false }
 }
 // Fallback to in-process (no extra dependencies)
 return { backend: createInProcessBackend(), isNative: false, needsIt2Setup: false }
}
```

This architecture allows:

- **in-process**: lightweight, sub-agents share the same process as parent
- **tmux pane**: each teammate runs in an independent tmux pane, supports parallel visualization
- **iTerm2 pane**: leverages iTerm2 native API to create tabs

---

## 6. Highlight 5: Long Session Management as a Complete System

**Files**: [`src/services/compact/compact.ts`](../src/services/compact/compact.ts)

`compactConversation()` is not a simple "history truncation" — it's a complete session compression pipeline:

```typescript
// src/services/compact/compact.ts:387
export async function compactConversation(
 messages: Message[],
 context: ToolUseContext,
 cacheSafeParams: CacheSafeParams,
 suppressFollowUpQuestions: boolean,
 customInstructions?: string,
 isAutoCompact: boolean = false,
): Promise<CompactionResult> {
 // 1. Preprocessing: remove images and large attachments to prevent the summary request from exceeding token limits
 const strippedMessages = stripImagesFromMessages(
 stripReinjectedAttachments(messages)
)

 // 2. Execute PreCompact hooks (customizable compaction strategy)
 const hookResult = await executePreCompactHooks({
 trigger: isAutoCompact ? 'auto' : 'manual',
 customInstructions: customInstructions ?? null,
 }, context.abortController.signal)

 // 3. Try using Session Memory directly as the summary (avoiding an extra API call)
 const smResult = await trySessionMemoryCompaction(messages, context)
 if (smResult) return smResult

 // 4. Call model to generate summary
 //...calls claude.ts, generates summary message

 // 5. PTL (Prompt Too Long) retry protection
 // If the summary request itself exceeds the limit, truncateHeadForPTLRetry() cuts several rounds from the head
}
```

```typescript
// src/services/compact/compact.ts — Post-compaction capability re-injection
export function buildPostCompactMessages(result: CompactionResult): Message[] {
 // After compact, the model's tool schema and MCP tool descriptions are all cleared
 // This function is responsible for rebuilding: file attachments + Plans list + tool capability declarations
 return [
...createPostCompactFileAttachments(result), // restore file context
 getDeferredToolsDeltaAttachment(result), // re-declare all tool capabilities
 ]
}
```

The compact system includes four strategies:

| Strategy | Trigger Condition | Core File |
|----------|-----------------|-----------|
| Manual compact | User executes `/compact` | `compact.ts` |
| Auto compact | Token exceeds threshold | `autoCompact.ts` |
| Session Memory compact | When Session Memory file exists | `sessionMemoryCompact.ts` |
| Micro compact | Lightweight reduction (experimental) | `reactiveCompact.ts` |

---

## 7. Overall Architecture Assessment

| Feature | Implementation Evidence |
|---------|------------------------|
| Unified execution kernel | `query()` async generator, shared by all runtime modes |
| File-based memory | Markdown files + `MEMORY.md` index, `truncateEntrypointContent()` overflow protection |
| Permission system as backbone | `Tool.ts` interface has built-in `checkPermissions`, `buildTool()` fail-closed defaults |
| Multi-agent runtime | `detectAndGetBackend()` auto-selects tmux/iTerm2/in-process backend |
| Long session as a system | `compactConversation()` + Session Memory + `buildPostCompactMessages()` re-injection |

If summed up in one sentence: **Claude Code is not "wrapping a CLI skin around the Claude API" — it's a local agent platform with an independent query kernel, file-based memory, permission system as backbone, and multi-agent runtime.**
