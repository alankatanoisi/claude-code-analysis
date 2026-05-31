# Chapter 1: Software Architecture and Program Entry

[Back to Table of Contents](../README.md)

---

## 1. Chapter Guide and Conclusion

This chapter answers two questions:

1. Where does this project start from, and how does the main pipeline flow.
2. How is its overall architecture layered, and what responsibilities does each layer take on.

**TL;DR**: This project is not a simple command-line chat program, but a local agent platform. It adopts a six-layer structure: "CLI bootstrap layer → TUI/REPL interaction layer → Query/Agent execution kernel → Tool/Permission layer → Memory/Persistence layer → MCP/Remote/Swarm extension layer".

---

## 2. Overall Structure Diagram

### 2.1 Layered Architecture Diagram

```text
+------------------------------+
| CLI Bootstrap Layer          |
| entrypoints/cli.tsx          |
| main.tsx                     |
+------------------------------+
               |
               v
+------------------------------+
| Initialization Layer         |
| entrypoints/init.ts          |
| setup.ts                     |
+------------------------------+
      |                  |
      v                  v
+------------------+   +------------------------------+
| Control / Cmd    |   | TUI / REPL Layer             |
| Plane            |   | replLauncher.tsx / REPL.tsx  |
| commands.ts      |-->+------------------------------+
| slash/menu       |                  |
+------------------+                  |
                                      v
                         +------------------------------+
                         | Execution Kernel             |
                         | query.ts / QueryEngine.ts    |
                         +------------------------------+
                           |            |            |
                           v            v            v
                 +---------------+ +-----------------+ +------------------+
                 | Tool/Perm     | | Memory/Persist  | | Extension Layer  |
                 | Layer         | | Layer           | | MCP/Plugin/      |
                 | Tool.ts       | | sessionStorage  | | Remote/Swarm     |
                 | orchestration | | memdir/SM       | +------------------+
                 +---------------+ +-----------------+
```

### 2.2 Default Main Interaction Pipeline

```text
entrypoints/cli.tsx
  -> main.tsx
  -> init.ts + setup.ts
  -> launchRepl()
  -> App + REPL
  -> PromptInput / slash command / footer menu
  -> query()
     -> services/api/claude.ts
     -> runTools() / StreamingToolExecutor
     -> sessionStorage / SessionMemory / compact / hooks
     -> Return to query main loop
```

---

## 3. Program Entry

### 3.1 Lightweight Entry: `cli.tsx` Early Routing

**File**: [`src/entrypoints/cli.tsx`](../src/entrypoints/cli.tsx)

This layer is the "entry router", not a complete application. Its responsibility is to identify fast paths and exit early, avoiding full application startup.

**Pseudo-code (based on source file structure)**:

```typescript
// src/entrypoints/cli.tsx structure pseudo-code
async function main() {
  const argv = parseArgs(process.argv)

  // Fast path routing — if matched, execute and exit, don't enter main.tsx
  if (argv['--version']) {
    console.log(version); process.exit(0)
  }
  if (argv['--dump-system-prompt']) {
    await dumpSystemPrompt(); process.exit(0)
  }
  if (argv['remote-control']) {
    return runRemoteControl(argv)
  }
  if (argv['daemon'] || argv['bg'] || argv['runner']) {
    return runDaemonOrBackground(argv)
  }

  // Default: enter full main launcher
  await import('./main.tsx').then(m => m.main(argv))
}
```

Benefit of this design: common fast commands don't need to load the entire application (React, Ink, MCP, etc.), resulting in fast startup and fewer side effects.

---

### 3.2 Main Launcher: `main.tsx` is the System Orchestration Center

**File**: [`src/main.tsx`](../src/main.tsx)

`main.tsx` is actually the **master control entry**, responsible for all main path initialization. Its responsibilities can be directly inferred from its import list (simplified excerpt from source imports):

```typescript
// src/main.tsx —— key imports reflecting scope of responsibility
import { init, initializeTelemetryAfterTrust } from './entrypoints/init.js'
import { launchRepl } from './replLauncher.js'
import { fetchBootstrapData } from './services/api/bootstrap.js'
import { getMcpToolsCommandsAndResources } from './services/mcp/client.js'
import { getTools } from './tools.js'
import { getAgentDefinitionsWithOverrides } from './tools/AgentTool/loadAgentsDir.js'
import { initBundledSkills } from './skills/bundled/index.js'
import { showSetupScreens, exitWithError } from './interactiveHelpers.js'
import { settingsChangeDetector } from './utils/settings/changeDetector.js'
// ... and about 80 more imports
```

**Main flow pseudo-code**:

```typescript
// src/main.tsx main flow (pseudo-code)
export async function main(argv: ParsedArgs) {
  // 1. Early initialization (doesn't depend on trust)
  await init(argv)

  // 2. Parse CLI args -> determine permission mode, model, tools, etc.
  const permissionMode = initialPermissionModeFromCLI(argv)
  const model = resolveModel(argv)

  // 3. Conditional branches: select execution path
  if (argv['--print'] || argv['--sdk']) {
    return runHeadless(argv, model, permissionMode)
  }
  if (argv['bridge']) {
    return runBridge(argv)
  }
  if (argv['remote']) {
    return runRemote(argv)
  }

  // 4. Default path: initialize full runtime then enter REPL
  const bootstrap = await fetchBootstrapData()          // Fetch remote config
  const mcpTools  = await getMcpToolsCommandsAndResources() // Connect MCP
  const tools     = getTools(permissionContext)          // Assemble tool pool
  const skills    = initBundledSkills()                  // Load built-in skills
  const agents    = getAgentDefinitionsWithOverrides()   // Load agent definitions

  await initializeTelemetryAfterTrust()                 // Start telemetry only after trust

  settingsChangeDetector.start()                        // Listen for config hot-reload

  // 5. Enter REPL
  await launchRepl(root, appProps, replProps, renderAndRun)
}
```

---

### 3.3 Initialization Layer: `init.ts` and `setup.ts` Separation of Concerns

The project splits initialization into two logically independent parts:

**`init.ts`**: [`src/entrypoints/init.ts`](../src/entrypoints/init.ts) — **Logic initialization**

```typescript
// src/entrypoints/init.ts structure pseudo-code
export async function init(argv) {
  applySafeEnvironmentVariables()    // Only apply safe env vars (pre-trust)
  initializeCertificates()           // Certificates and HTTPS proxy
  initializeHttpAgent()              // HTTP agent configuration
  initTelemetrySkeleton()            // Register telemetry sink, but don't emit events
  // Note: initializeTelemetryAfterTrust() is called by main.tsx after trust is established
}

export async function initializeTelemetryAfterTrust() {
  applyFullEnvironmentVariables()    // Apply all env vars only after trust passes
  attachAnalyticsSink()              // Start processing telemetry event queue
}
```

**`setup.ts`**: [`src/setup.ts`](../src/setup.ts) — **Runtime environment initialization**

```typescript
// src/setup.ts structure pseudo-code
export async function setup(argv, permissionContext) {
  setCwd(resolvedWorkingDir)         // Set working directory
  startHooksWatcher()                // Listen for hooks config changes
  initWorktreeSnapshot()             // tmux/worktree snapshot
  initSessionMemory()                // Initialize session memory system
  startTeamMemoryWatcher()           // Start team memory file watcher
}
```

**Design intent**: Only apply safe environment variables before trust is established, preventing the risk of "config files/includes themselves being attack surfaces" (see `06-extra-findings.md` Section 2 for details).

---

## 4. Runtime Modes

The system supports multiple runtime modes, all sharing the same execution kernel.

### 4.1 Default REPL/TUI Mode

Key function:

```typescript
// src/replLauncher.tsx
export async function launchRepl(
  root: Root,
  appProps: AppWrapperProps,
  replProps: REPLProps,
  renderAndRun: (root: Root, element: React.ReactNode) => Promise<void>
): Promise<void>
```

This function dynamically loads `App + REPL` components then starts the Ink rendering loop.  
`REPL.tsx` maintains the complete `AppState` (messages, input box, permission dialogs, tasks, remote status), and user input ultimately enters the execution kernel through `query()`.

### 4.2 Headless / SDK Mode

Key files:
- [`src/QueryEngine.ts`](../src/QueryEngine.ts) — Manages multi-turn session state
- [`src/query.ts`](../src/query.ts) — Manages single query loop

`QueryEngine` is a UI-less execution engine that can be directly instantiated by the SDK without depending on Ink/React rendering:

```typescript
// src/QueryEngine.ts structure pseudo-code
export class QueryEngine {
  async query(userInput: string): AsyncGenerator<StreamEvent> {
    // 1. Assemble messages + system prompt
    // 2. Call claude.ts API
    // 3. Handle tool_use / tool_result
    // 4. yield events to caller
  }
}
```

### 4.3 MCP Server Mode

**File**: [`src/entrypoints/mcp.ts`](../src/entrypoints/mcp.ts)

```typescript
// src/entrypoints/mcp.ts structure pseudo-code
async function startMcpServer() {
  const server = new McpServer({ name: 'claude-code', version })
  // Wrap internal Tools (FileEdit, FileRead, Bash...) as MCP tool schemas
  for (const tool of getInternalTools()) {
    server.registerTool(tool.name, tool.inputSchema, wrapToolAsMcpHandler(tool))
  }
  await server.connect(new StdioServerTransport())
}
```

This path allows Claude Code to **both consume external capabilities as an MCP client and expose capabilities as an MCP server**.

### 4.4 Remote / Bridge Mode

**File**: [`src/bridge/bridgeMain.ts`](../src/bridge/bridgeMain.ts)

```typescript
// src/bridge/bridgeMain.ts structure pseudo-code
async function runBridge(config: BridgeConfig) {
  const ws = connectToRemoteOrchestrator(config.orchestratorUrl)
  ws.on('session-start', (session) => spawnLocalAgent(session))
  ws.on('heartbeat',     ()        => sendHeartbeat())
  ws.on('disconnect',    ()        => scheduleReconnect())
}
```

This extends Claude Code from a "local terminal tool" to a "hybrid local and remote agent platform".

---

## 5. Architecture Layer Details

### 5.1 Command and Mode Dispatch Layer

**File**: [`src/commands.ts`](../src/commands.ts)

```typescript
// src/commands.ts structure pseudo-code
// Internal-only commands (stripped from external builds)
const INTERNAL_ONLY_COMMANDS = [
  'backfillSessions', 'bughunter', 'commit', 'teleport', 'antTrace', // ...
]

export function getCommands(options: CommandOptions): Command[] {
  const baseCommands = [
    compactCommand, configCommand, doctorCommand, helpCommand, // ...built-in commands
    ...(feature('VOICE_MODE')   ? [voiceCommand]   : []),     // Compile-time switch
    ...(feature('BUDDY')        ? [buddyCommand]   : []),
    ...(process.env.USER_TYPE === 'ant' ? INTERNAL_ONLY_COMMANDS.map(loadCmd) : []),
  ]
  // Filter based on permissionContext / feature gates / environment
  return baseCommands.filter(cmd => cmd.isEnabled(options))
}
```

### 5.2 TUI and State Layer

**Files**: [`src/screens/REPL.tsx`](../src/screens/REPL.tsx), [`src/state/AppStateStore.ts`](../src/state/AppStateStore.ts)

`AppState` is the system's shared state bus, not just simple UI state:

```typescript
// src/state/AppState.ts type structure (simplified)
type AppState = {
  messages:              Message[]
  toolPermissionContext: ToolPermissionContext
  mainLoopModel:         string
  mcpClients:            McpClient[]
  plugins:               Plugin[]
  agentRegistry:         AgentDefinition[]
  notifications:         NotificationQueue
  remoteBridgeState:     BridgeState | null
  // ...and about 20 more fields
}
```

### 5.3 Query / Agent Execution Kernel

**Files**: [`src/query.ts`](../src/query.ts), [`src/QueryEngine.ts`](../src/QueryEngine.ts)

`query.ts` is the system's core main loop, containing the complete tool call loop:

```typescript
// src/query.ts —— main loop skeleton (pseudo-code)
export async function* query(
  userMessages: Message[],
  systemPrompt: SystemPrompt,
  toolUseContext: ToolUseContext,
  deps: QueryDeps,
): AsyncGenerator<StreamEvent> {
  let messages = userMessages

  while (true) {
    // 1. Assemble context (memory injection happens here)
    const apiMessages = normalizeMessagesForAPI(messages)

    // 2. Call Claude API, stream response
    for await (const event of deps.claudeApi.stream(apiMessages, systemPrompt)) {
      yield event
    }

    // 3. Extract tool_use list from model output
    const toolUseBlocks = extractToolUseBlocks(messages)
    if (toolUseBlocks.length === 0) break  // No tool calls -> end

    // 4. Execute tools (concurrent / serial determined by partitionToolCalls)
    const toolResults = []
    for await (const update of runTools(toolUseBlocks, ...)) {
      yield update  // Yield to UI in real-time
      toolResults.push(update.message)
    }

    // 5. Append tool results to messages -> next round
    messages = [...messages, ...toolResults]

    // 6. compact check, hook execution
    await executePostSamplingHooks(messages, toolUseContext)
    if (shouldCompact(messages)) await compact(messages, toolUseContext)
  }
}
```

### 5.4 Tool and Permission Layer

**Files**: [`src/Tool.ts`](../src/Tool.ts), [`src/services/tools/toolOrchestration.ts`](../src/services/tools/toolOrchestration.ts)

`runTools()` is the tool scheduling core, and its `partitionToolCalls()` determines concurrent vs. serial grouping:

```typescript
// src/services/tools/toolOrchestration.ts (actual source code excerpt)
export async function* runTools(
  toolUseMessages: ToolUseBlock[],
  assistantMessages: AssistantMessage[],
  canUseTool: CanUseToolFn,
  toolUseContext: ToolUseContext,
): AsyncGenerator<MessageUpdate, void> {
  let currentContext = toolUseContext
  for (const { isConcurrencySafe, blocks } of partitionToolCalls(
    toolUseMessages,
    currentContext,
  )) {
    if (isConcurrencySafe) {
      // Concurrent batch: collect contextModifiers first, apply sequentially after batch
      for await (const update of runToolsConcurrently(blocks, ...)) { yield update }
    } else {
      // Serial batch: each tool must wait for previous to complete
      for await (const update of runToolsSerially(blocks, ...)) { yield update }
    }
  }
}

function partitionToolCalls(toolUseMessages: ToolUseBlock[], ctx: ToolUseContext): Batch[] {
  return toolUseMessages.reduce((acc: Batch[], toolUse) => {
    const tool = findToolByName(ctx.options.tools, toolUse.name)
    const isConcurrencySafe = Boolean(tool?.isConcurrencySafe(parsedInput.data))
    // Merge into same batch if previous batch is also concurrency-safe
    if (isConcurrencySafe && acc[acc.length - 1]?.isConcurrencySafe) {
      acc[acc.length - 1]!.blocks.push(toolUse)
    } else {
      acc.push({ isConcurrencySafe, blocks: [toolUse] })
    }
    return acc
  }, [])
}
```

### 5.5 Persistence / Memory Layer

**Files**: [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts), [`src/memdir/memdir.ts`](../src/memdir/memdir.ts), [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts)

Core Memory system construction functions (see Chapter 4 for detailed analysis):

```typescript
// src/memdir/memdir.ts (actual source code excerpt)
export const ENTRYPOINT_NAME    = 'MEMORY.md'
export const MAX_ENTRYPOINT_LINES = 200
export const MAX_ENTRYPOINT_BYTES = 25_000

export function buildMemoryPrompt(params: {
  displayName: string
  memoryDir:   string
  extraGuidelines?: string[]
}): string {
  const entrypoint = params.memoryDir + ENTRYPOINT_NAME
  const raw = fs.readFileSync(entrypoint, { encoding: 'utf-8' })  // Sync read
  const t   = truncateEntrypointContent(raw)                       // Hard truncation protection

  const lines = buildMemoryLines(params.displayName, params.memoryDir, ...)
  lines.push(`## ${ENTRYPOINT_NAME}`, '', t.content)
  return lines.join('\n')
}
```

### 5.6 MCP / Plugin / Remote / Swarm Extension Layer

**Files**: [`src/services/mcp/client.ts`](../src/services/mcp/client.ts), [`src/utils/swarm/backends/registry.ts`](../src/utils/swarm/backends/registry.ts)

MCP tool naming convention:

```typescript
// src/services/mcp/mcpStringUtils.ts
export function buildMcpToolName(serverName: string, toolName: string): string {
  return `mcp__${serverName}__${toolName}`
  // Example: mcp__filesystem__read_file
  //          mcp__puppeteer__screenshot
}
```

Swarm (multi-agent) backend registry is extensible:

```typescript
// src/utils/swarm/backends/registry.ts structure pseudo-code
const BACKEND_REGISTRY: Record<string, TeammateBackend> = {
  'in-process': InProcessBackend,
  'tmux':       TmuxBackend,
  'iterm2':     ITerm2PaneBackend,
}

export function spawnTeammate(config: TeammateConfig): TeammateHandle {
  const Backend = BACKEND_REGISTRY[config.backendType]
  return new Backend(config).spawn()
}
```

---

## 6. Typical Complete Pipeline

Putting all the pieces together:

```text
1. Process Startup
   entrypoints/cli.tsx -> fast path routing OR main.tsx

2. Initialization
   init.ts -> pre-trust initialization
   setup.ts -> environment, CWD, hooks, memory startup

3. Capability Assembly
   getCommands()          -> command system
   getTools()             -> built-in tool pool
   getMcpToolsAndResources() -> MCP tools
   getAgentDefinitions()  -> custom agents
   initBundledSkills()    -> skill system

4. REPL Startup
   launchRepl() -> App + REPL.tsx -> PromptInput

5. User Input
   query.ts -> normalizeMessagesForAPI() -> claude.ts API

6. Tool Execution
   runTools() -> partitionToolCalls() -> runToolsConcurrently / runToolsSerially
   -> toolExecution.ts -> schema validation -> permission -> tool.call()

7. Result Flowback
   tool_result -> messages -> next query round -> (loop)

8. Session Management
   sessionStorage -> transcript persistence
   shouldExtractMemory() -> runForkedAgent() -> Session Memory update
   compact() -> context compression
```

---

## 7. Chapter Summary

From an architectural perspective, this project has three distinct characteristics:

1. **Multi-entry system**: cli.tsx handles early routing, main.tsx is the true orchestration center, with clear separation of responsibilities.
2. **Layered decoupling**: UI, execution kernel, tool layer, memory layer, and extension layer are each independent, with query.ts serving as the main coordinator connecting them.
3. **Platform-oriented design**: Not just a "wrapped chat tool", but a local agent platform with an independent execution kernel, permission system, memory architecture, and multi-agent runtime.
