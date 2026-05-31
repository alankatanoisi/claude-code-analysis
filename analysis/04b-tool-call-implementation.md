# Chapter 4 Supplement: Tool Call Mechanism Implementation Details

[Back to Table of Contents](../README.md)

---

## Chapter Guide

If Part 3 only covers memory, it wouldn't be complete enough. Another core capability of this project is turning "model-initiated tool_use" into an engineering-controllable, concurrent, auditable execution chain that can flow back into the next round of conversation.

This chapter focuses on explaining:

1. How tools are defined in code
2. How the tool pool is assembled
3. How tool_use actually executes
4. How permissions, Hooks, concurrent scheduling, and tool_result are connected
5. How the query main loop feeds tool results back into the next model call

**Main related source code**:
- [`src/Tool.ts`](../src/Tool.ts)
- [`src/tools.ts`](../src/tools.ts)
- [`src/services/tools/toolOrchestration.ts`](../src/services/tools/toolOrchestration.ts)
- [`src/services/tools/StreamingToolExecutor.ts`](../src/services/tools/StreamingToolExecutor.ts)
- [`src/services/tools/toolExecution.ts`](../src/services/tools/toolExecution.ts)
- [`src/query.ts`](../src/query.ts)

> **For beginners**: This chapter will dive into the execution engine of Claude Code as an Agent platform. We will disassemble the black box of "large model tool calling" into a clear pipeline and show you how it is implemented as a rigorous system design using concrete source code.

---

## Section 1: Full Chain: From `tool_use` to `tool_result`

**Related source code**:
- [`src/query.ts`](../src/query.ts)
- [`src/services/tools/toolExecution.ts`](../src/services/tools/toolExecution.ts)

First, the complete chain:

```text
Model outputs assistant message
  │
  ▼ Contains one or more tool_use blocks
  │
query.ts collects these tool_use blocks
  │
  ▼ Selects streaming executor or regular runTools()
  │
toolOrchestration.ts batches by concurrency safety
  │
  ▼
toolExecution.ts executes each tool_use one by one
     ├─ 1. Schema validation
     ├─ 2. validateInput
     ├─ 3. pre-tool hooks
     ├─ 4. permission / ask / deny
     ├─ 5. tool.call()
     └─ 6. Generate tool_result / attachment / progress
  │
  ▼ Normalizes results into user-side tool_result messages
  │
On the next API call, these results are carried back (flow back into transcript)
```

**The most critical point is**: tool call is not "the model directly calls a function," but is broken down into a multi-layer Runtime Pipeline.

---

## Section 2: `Tool` Abstraction: The Unified Tool Protocol

**Related source code**:
- [`src/Tool.ts`](../src/Tool.ts)

### 2.1 What the `Tool` Interface Contains

**Actual source code** ([`src/Tool.ts:362`](../src/Tool.ts)):

```typescript
export type Tool<
  Input extends AnyObject = AnyObject,
  Output = unknown,
  P extends ToolProgressData = ToolProgressData,
> = {
  aliases?: string[]
  searchHint?: string
  call(
    args: z.infer<Input>,
    context: ToolUseContext,
    canUseTool: CanUseToolFn,
    parentMessage: AssistantMessage,
    onProgress?: ToolCallProgress<P>,
  ): Promise<ToolResult<Output>>
  // ... other properties and methods ...
}
```

In `src/Tool.ts`, the `Tool` interface goes far beyond just the `call()` function. It covers at least these aspects of the runtime protocol:

- **Capability description**: `name`, `description()`, `prompt()`, `searchHint`
- **Input/Output**: `inputSchema`, `outputSchema`, `mapToolResultToToolResultBlockParam()`
- **Security attributes**: `isConcurrencySafe()`, `isReadOnly()`, `isDestructive()`, `checkPermissions()`, `preparePermissionMatcher()`
- **Semantic validation**: `validateInput()`
- **UI presentation**: `renderToolUseMessage()`, `renderToolResultMessage()`, `renderToolUseRejectedMessage()`, `renderToolUseErrorMessage()`
- **Execution control**: `interruptBehavior()`, `requiresUserInteraction()`, `backfillObservableInput()`

**For beginners**: This means that in this system, a Tool is not a simple "function mapping," but a standardized **runtime protocol object**. It forces every tool author to consider concurrency, security, presentation form, and interruption compensation at the code level.

### 2.2 Default Value Strategy of `buildTool()`

**Actual source code** ([`src/Tool.ts:757`](../src/Tool.ts)):

```typescript
const TOOL_DEFAULTS = {
  isEnabled: () => true,
  isConcurrencySafe: (_input?: unknown) => false,
  isReadOnly: (_input?: unknown) => false,
  isDestructive: (_input?: unknown) => false,
  checkPermissions: (
    input: { [key: string]: unknown },
    _ctx?: ToolUseContext,
  ): Promise<PermissionResult> =>
    Promise.resolve({ behavior: 'allow', updatedInput: input }),
  toAutoClassifierInput: (_input?: unknown) => '',
  userFacingName: (_input?: unknown) => '',
}

export function buildTool<D extends AnyToolDef>(def: D): BuiltTool<D> {
  return {
    ...TOOL_DEFAULTS,
    userFacingName: () => def.name,
    ...def,
  } as BuiltTool<D>
}
```

All tools must be constructed via `buildTool()`. This default value strategy embodies a **system-level Fail-Closed principle**:

- Concurrency is unsafe by default (`isConcurrencySafe: false`)
- Write operations are assumed risky by default (non-read-only `isReadOnly: false`)
- Security-related capabilities must be explicitly declared (security classifier short-circuits by default with `toAutoClassifierInput: ''`)

**Simple explanation**: The framework would rather err on the side of caution — all newly created tools are assumed to be "risky" and "non-concurrent" unless the developer explicitly declares otherwise. This eliminates security blind spots in subsequent development.

### 2.3 `ToolUseContext` Is the Execution-Time Context Bus

`ToolUseContext` carries rich runtime state:
- Current tool pool and permission context
- App state and MCP clients / resources
- File cache, abort controller, and current message sequence

This means tool execution deeply depends on the **entire system's session runtime**, not just isolated parameters.

---

## Section 3: How the Tool Pool Is Assembled

**Related source code**:
- [`src/tools.ts`](../src/tools.ts)

### 3.1 `getAllBaseTools()` Is the Built-in Tool Master List

**Actual source code** ([`src/tools.ts:193`](../src/tools.ts)):

```typescript
export function getAllBaseTools(): Tools {
  return [
    AgentTool,
    TaskOutputTool,
    BashTool,
    ...
    FileEditTool,
    WebFetchTool,
    ...(isEnvTruthy(process.env.ENABLE_LSP_TOOL) ? [LSPTool] : []),
    ...(isWorktreeModeEnabled() ? [EnterWorktreeTool, ExitWorktreeTool] : []),
    ...(isToolSearchEnabledOptimistic() ? [ToolSearchTool] : []),
  ]
}
```

Several types of sources can be seen in this list:
- Always-present base tools: e.g., `BashTool`, `FileEditTool`
- Tools enabled by Feature Flags or environment variables: e.g., `LSPTool`, `WorkflowTool`
- Tools exclusive to Ant internal users: e.g., `ConfigTool`

**Conclusion**: All tools in the system are dynamically loaded and configured on demand.

### 3.2 `assembleToolPool()`: The Fusion Point of Native Tools and MCP

**Actual source code** ([`src/tools.ts:345`](../src/tools.ts)):

```typescript
export function assembleToolPool(
  permissionContext: ToolPermissionContext,
  mcpTools: Tools,
): Tools {
  const builtInTools = getTools(permissionContext)
  // Filter out blocked MCP Server tools
  const allowedMcpTools = filterToolsByDenyRules(mcpTools, permissionContext)

  const byName = (a: Tool, b: Tool) => a.name.localeCompare(b.name)
  // Merge, sort, and prefer built-in tools on name conflict
  return uniqBy(
    [...builtInTools].sort(byName).concat(allowedMcpTools.sort(byName)),
    'name',
  )
}
```

**For beginners**: MCP tools are directly injected here as first-class citizens! The system uses `uniqBy` with the preceding array (built-in tools first) for fusion, ensuring that even if external MCP contains a malicious component with the same name as `BashTool`, it is reliably intercepted and discarded.

---

## Section 4: Scheduling Layer: Concurrency Is Not Enabled by Default

**Related source code**:
- [`src/services/tools/toolOrchestration.ts`](../src/services/tools/toolOrchestration.ts)

### 4.1 How `partitionToolCalls()` Groups

`runTools()` does not execute multiple `tool_use` blocks all at once; instead, it batches them according to safety declarations:

```typescript
// Pseudo code: Parse the tool_uses list returned by the model, batch by concurrency safety
function partitionToolCalls(toolUses: ToolUseBlock[], context: ToolUseContext): ToolUseBatch[] {
  const batches: ToolUseBatch[] = [];
  let currentConcurrentBatch: ToolUseBlock[] = [];

  for (const toolUse of toolUses) {
    const tool = findToolByName(context.tools, toolUse.name);
    // Look ahead: is it concurrency-safe?
    const isSafe = tool?.isConcurrencySafe(toolUse.input);

    if (isSafe) {
      currentConcurrentBatch.push(toolUse);
    } else {
      // Close off the preceding safe tools
      if (currentConcurrentBatch.length > 0) {
        batches.push({ type: 'concurrent', tools: currentConcurrentBatch });
        currentConcurrentBatch = [];
      }
      // Unsafe tools form their own sequential phase
      batches.push({ type: 'sequential', tools: [toolUse] });
    }
  }
  if (currentConcurrentBatch.length > 0) {
    batches.push({ type: 'concurrent', tools: currentConcurrentBatch });
  }
  return batches;
}
```

**For example**: If the LLM returns `[A(Read), B(Read), C(Write), D(Read)]`.
Since Write produces state mutations, the batched result will strictly become:
1. `[A, B]` processed concurrently
2. `[C]` processed sequentially
3. `[D]` processed with remaining capacity exclusively

### 4.2 Deferred Application of `contextModifier`

For concurrent batches, context modifications (`contextModifier`) returned by tools are collected lazily and applied sequentially after the entire batch is completed. This prevents parallel Read processes from causing read-write overwrite issues (race condition pollution) due to mutual local storage variables.

---

## Section 5: Streaming Tool Executor: Execute as You Receive

**Related source code**:
- [`src/services/tools/StreamingToolExecutor.ts`](../src/services/tools/StreamingToolExecutor.ts)

In specific high-speed streaming scenarios, the system does not wait for the lengthy Assistant Content to be fully received before starting tool dispatch. Instead, the system uses a state machine to track each tool's status:

Maintained state transitions: `queued` -> `executing` -> `completed` -> `yielded`.
1. Concurrency-safe tools are launched immediately once the Zod schema is parsed.
2. Unsafe sibling tools enter a queue waiting for exclusive access.
3. If a parallel tool throws an error midway, it can cancel unfinished sibling tools and return early to the model with an exception report.

---

## Section 6: `runToolUse()`: The True Execution Backbone

**Related source code**:
- [`src/services/tools/toolExecution.ts`](../src/services/tools/toolExecution.ts)
- [`src/services/tools/toolHooks.ts`](../src/services/tools/toolHooks.ts)

### 6.1 Analysis of Each Processing Link

The specific execution process of a tool is very rigorous.

- **Step 1: Zod schema validation** (`tool.inputSchema.safeParse`)
  Hard constraint on parameters. If it fails, the system does not crash, but passes the exception stack to the LLM for correction and retry.
- **Step 2: Independent semantic validation** (`validateInput()`)
  Even if the schema is satisfied, semantic correctness must be ensured. For example, whether the old and new strings are equal, whether a blacklisted directory is encountered, etc.
- **Step 3: Backfill implicit derived dependencies**
  Deeply injects hooks like `expandPath()` into the input structure for subsequent security auditing.

### 6.2 PreToolUse Hooks and Permission System

**Actual source code** ([`src/services/tools/toolHooks.ts:435`](../src/services/tools/toolHooks.ts)):
```typescript
export async function* runPreToolUseHooks(
  tool: Tool,
  toolUseID: string,
  input: { [key: string]: unknown },
  // ...
): AsyncGenerator<HookProgress | MessageUpdateLazy | StopHookInfo, void> {
   // Trigger pre-interception validation logic in order, may directly modify the incoming input structure...
}
```

PreToolUse Hooks greatly extend the dynamic capabilities of the framework. The system's permission decisions (`allow` | `deny` | `ask`) are aggregated at this step.

If interception occurs, the program stops initiating the call to that tool and instead constructs and returns an error UI card message.

### 6.3 Final Invocation of `tool.call()`

**Reference concept / pseudo code representation**:

```typescript
// Executed after all pre-hooks have run and checkPermissions has passed:
try {
  const result = await tool.call(
    callInput,
    enrichedToolUseContext,
    canUseTool,
    assistantMessage,
    onProgress
  );
  // Execution successful, prepare to write the result into the return message
  processToolResultBlock(result);
} catch (error) {
  // Intercept exceptions thrown by the tool and standardize the wrapper, return tool_use_error to the model
  yield generateErrorResult(error, toolUse.id);
}
```

Only after going through all of the above constraints and completion logic does the action ultimately get handed off to `Tool.call()` itself for execution.

---

## Section 7: How the Query Main Loop Handles Tool Results

**Related source code**:
- [`src/query.ts`](../src/query.ts)

Tool result return has two aspects:

1. **For the UI**: The user immediately sees progress / result / reject / error.
2. **For the model**: The next model request receives standardized `tool_result`.

This process relies on a very core cleaner called `normalizeMessagesForAPI()`. It removes redundant components from the mixed queue containing rich text, locally mounted images, long strings of checkpoint metadata, etc., refining them into a standardized API-acceptable format before handing them back to the large model.

---

## Section 8: Concrete Case Analysis: `FileEditTool`

**Related source code**:
- [`src/tools/FileEditTool/FileEditTool.ts`](../src/tools/FileEditTool/FileEditTool.ts)

`FileEditTool` encompasses almost all capability requirements within the interface. Internally, it includes: UNC file lock validation, oversized entity blocking protection, team Secret Key matching mechanism to prevent leakage, and the ability to refine errors down to prompts like `did you mean ...?`.

**Analysis conclusion**: The "edit file" action was never a crude regex match and replace. Underneath, it is actually a highly autonomous environment governor with debounce capabilities.

---

## Section 9: Concrete Case Analysis: `AskUserQuestionTool`

**Related source code**:
- [`src/tools/AskUserQuestionTool/AskUserQuestionTool.tsx`](../src/tools/AskUserQuestionTool/AskUserQuestionTool.tsx)

This tool perfectly reveals: **A Tool is not necessarily a backend machine code operation!**
It configures: `shouldDefer = true`, `requiresUserInteraction = true`, `isReadOnly = true`.

**Simple explanation**: When the large model wants to ask the human for information, this is not some special "internal system interaction mechanism" — it is itself packaged as an equal Tool. The model calls the Tool's API to send a question form to the developer's screen, and the returned value is exactly what you type on the interface! This shows that the tool call chain is essentially a grand "bilateral interaction abstraction tunnel."

---

## Section 10: Mechanism Design Feature Summary

Through the source code comparison and logic diagrams above, we can see three core highlights of this mechanism:

1. **Pipeline Pattern**: Tool call behavior is wrapped in multiple layers of pipeline, gaining non-functional features such as pre-interception and semantic compensation.
2. **Transcript Is the Sole Ground Truth for Interaction**: All complex JS runtime state results are uniformly transformed into Transcript conversation flow text, recorded and passed back to the large model.
3. **Security Built into the Bottom-Level Interface**: From `buildTool`, read permissions and concurrency limits are constrained, blocking the risk of arbitrary calls from the start.

---

## Chapter Summary

If the local capability implementation structure of Claude Code could be summarized in two sentences:

- **Memory** handles long-period and cross-session role consistency (static knowledge base).
- **Tool Pipeline** builds an execution path with boundary security control and error retry disaster tolerance (dynamic limbs).

It is the combination of the two, along with the orchestration of `Query.ts` (the main loop scheduling mechanism), that transforms this CLI into a mature and fully functional AI Agent platform.
