# Chapter 4: How Agent Memory Works

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter no longer just talks about "types of memory," but breaks down the implementation chain:

1. Where is memory actually stored
2. When is it written
3. When is it recalled
4. What are the boundaries between Agent Memory and Auto / Session / Team Memory
5. When the agent actually runs, how is memory connected to the prompt, tools, snapshot, and UI

This chapter is based on these implementations:

- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)
- [`src/memdir/paths.ts`](../src/memdir/paths.ts)
- [`src/memdir/findRelevantMemories.ts`](../src/memdir/findRelevantMemories.ts)
- [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts)
- [`src/services/SessionMemory/sessionMemoryUtils.ts`](../src/services/SessionMemory/sessionMemoryUtils.ts)
- [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts)
- [`src/tools/AgentTool/loadAgentsDir.ts`](../src/tools/AgentTool/loadAgentsDir.ts)
- [`src/tools/AgentTool/agentMemorySnapshot.ts`](../src/tools/AgentTool/agentMemorySnapshot.ts)
- [`src/components/memory/MemoryFileSelector.tsx`](../src/components/memory/MemoryFileSelector.tsx)

TL;DR:

This project does not use a single database for memory, nor does it use a hidden internal KV store. Instead, it implements a "multi-layered file-based memory system." Agent Memory is just one layer, but it is coupled with agent definitions, agent prompts, agent tool permissions, snapshot initialization, and UI file selectors. So it is not an auxiliary feature, but a component of the agent runtime.

Overall diagram:

```text
Session transcript / current query
 ├─> Auto Memory extraction
 │ ├─> MEMORY.md index
 │ ├─> topic memories/*.md
 │ └─> relevant recall selects a few files to inject back into the current context
 │
 ├─> Session Memory
 │ └─> Current session summary markdown
 │
 ├─> Agent Memory
 │ ├─> user scope
 │ ├─> project scope
 │ └─> local scope
 │ └─> Injected directly into the agent system prompt
 │
 └─> Team Memory
 └─> Team-synchronized shared memory

Additionally:
 └─> Agent Memory Snapshot
 ├─> Initialize local agent memory
 └─> Notify that a new version of local memory snapshot is available for sync
```

## 2. Overall Design: Why It's Not a Single Database

Related implementations:

- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)
- [`src/memdir/paths.ts`](../src/memdir/paths.ts)

The core of this memory design is not "remembering content," but "separately storing content with different lifecycles, scopes, and visibility."

From an implementation perspective, it is divided into at least four layers:

1. `Auto Memory`
 Long-term memory for the entire user and project collaboration process, stored in a unified memory directory.
2. `Session Memory`
 Summary file for the current session, designed to assist with compact and long-running sessions.
3. `Agent Memory`
 Persistent memory for a specific agent type, directly bound to the agent definition.
4. `Team Memory`
 Repo-level knowledge synchronization shared across the team.

They are not forced into a single schema. Each has its own independent directory, independent prompt, and independent update strategy.

This brings three direct benefits:

- Transparent: Users can open the directory directly and view markdown files
- Governable: Different memories can be individually toggled, synchronized, and constrained
- Composable: Auto / Session / Agent / Team Memory can coexist, but with different responsibilities

## 3. Underlying Storage Model: Directory + `MEMORY.md` Index

Related implementations:

- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)

### 3.1 Basic Conventions

The lowest level of memory is a directory, not a database.

In [`src/memdir/memdir.ts`](../src/memdir/memdir.ts), you can see several key constants:

- `ENTRYPOINT_NAME = 'MEMORY.md'`
- `MAX_ENTRYPOINT_LINES = 200`
- `MAX_ENTRYPOINT_BYTES = 25_000`

This indicates that the system treats `MEMORY.md` as an entry-point index file, not a body storage file.

The design intent is clear:

- Each memory should be written as a separate markdown file
- `MEMORY.md` only maintains index links and a one-line description
- The agent / model is only guaranteed to see `MEMORY.md` by default in the prompt
- When more detail is needed, it reads the specific memory file

This is more stable than "piling all memories into one big file," because a large file easily leads to:

- Prompt explosion
- Update conflicts
- Unmanageable historical garbage
- A single erroneous memory polluting the entire context

### 3.2 `buildMemoryLines()` — The Real Constraint for the Model

**Actual source code** ([`src/memdir/memdir.ts:199`](../src/memdir/memdir.ts)):

```typescript
export function buildMemoryLines(
 displayName: string,
 memoryDir: string,
 extraGuidelines?: string[],
 skipIndex = false,
): string[] {
 const lines: string[] = [
 `# ${displayName}`,
 '',
 // DIR_EXISTS_GUIDANCE = "This directory already exists - write to it directly..."
 // Prevents the model from wasting a round of conversation on ls/mkdir to confirm the directory
 `You have a persistent, file-based memory system at ${"`"}${memoryDir}${"`"}. ${DIR_EXISTS_GUIDANCE}`,
 '',
...TYPES_SECTION_INDIVIDUAL, // Memory type classification
...WHAT_NOT_TO_SAVE_SECTION, // Content not to save (derivable from code, duplicates)
 '',
...howToSave, // Two-step method: first write topic file, then add index line in MEMORY.md
 '',
...(extraGuidelines ?? []), // Agent-specific additional rules (scope description, etc.)
 ]
 lines.push(...buildSearchingPastContextSection(memoryDir))
 return lines
}
```

The model is asked to operate the memory directory like maintaining a small knowledge base: store each memory as a separate file, maintain the index, update outdated memories, and avoid duplicates.

### 3.3 How `buildMemoryPrompt()` Assembles Context

**Actual source code** ([`src/memdir/memdir.ts:272`](../src/memdir/memdir.ts)):

```typescript
export function buildMemoryPrompt(params: {
 displayName: string
 memoryDir: string
 extraGuidelines?: string[]
}): string {
 const entrypoint = params.memoryDir + ENTRYPOINT_NAME // <dir>/MEMORY.md

 // Synchronous read (some calls come from the React render path and cannot use await)
 let entrypointContent = ''
 try {
 entrypointContent = fs.readFileSync(entrypoint, { encoding: 'utf-8' })
 } catch { /* Silently ignore when file does not exist */ }

 const lines = buildMemoryLines(params.displayName, params.memoryDir, params.extraGuidelines)

 if (entrypointContent.trim()) {
 const t = truncateEntrypointContent(entrypointContent) // Hard truncation protection
 logMemoryDirCounts(params.memoryDir, {
 content_length: t.byteCount, line_count: t.lineCount,
 was_truncated: t.wasLineTruncated,
 // Type annotation prevents PII from being mistakenly reported
 memory_type: memoryType as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
 })
 lines.push(`## ${ENTRYPOINT_NAME}`, '', t.content)
 } else {
 lines.push(
 `## ${ENTRYPOINT_NAME}`, '',
 `Your ${ENTRYPOINT_NAME} is currently empty. When you save new memories, they will appear here.`,
)
 }
 return lines.join('\n')
}
```

**Two key implementation details**:
1. **Synchronous read**: `getSystemPrompt()` exists in a synchronous call path and cannot use `await`
2. **Hard truncation protection**: `truncateEntrypointContent()` limits MEMORY.md to 200 lines / 25KB to prevent prompt explosion

## 4. Auto Memory: The General Persistent Memory Layer

Related implementations:

- [`src/memdir/paths.ts`](../src/memdir/paths.ts)
- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)
- [`src/services/extractMemories/extractMemories.ts`](../src/services/extractMemories/extractMemories.ts)

### 4.1 Storage Location

The Auto Memory directory is not hardcoded; it is computed via [`src/memdir/paths.ts`](../src/memdir/paths.ts).

The general rules are as follows:

```text
Priority from high to low:

1. CLAUDE_COWORK_MEMORY_PATH_OVERRIDE
2. autoMemoryDirectory from a trusted source in settings.json
3. <memoryBase>/projects/<sanitized-git-root>/memory/

Where memoryBase =
 - CLAUDE_CODE_REMOTE_MEMORY_DIR
 - Otherwise ~/.claude
```

This shows that Auto Memory is designed to be compatible with three deployment modes from the start:

- Local default installation
- Custom directory via configuration file
- Remote / cowork environments with mounted disks

### 4.2 Toggle Control

The priority of `isAutoMemoryEnabled()` is also very engineering-oriented:

1. `CLAUDE_CODE_DISABLE_AUTO_MEMORY`
2. `CLAUDE_CODE_SIMPLE`
3. Disabled in remote mode without a persistent directory
4. `settings.autoMemoryEnabled`
5. Enabled by default

So although Agent Memory is a separate directory, whether it is enabled actually reuses Auto Memory's master toggle logic.

### 4.3 Write Method

Updates to Auto Memory are not manually done by the current main thread agent each time; they can be completed by a background extraction process.

Its goal is to (crystallize) long-term valid information into durable memories, such as:

- User long-term preferences
- Project external context
- Non-code-intrinsic knowledge
- Collaboration constraints that need to persist across sessions

This layer is the "global persistent memory base," while Agent Memory is more like "the dedicated long-term memory of a specific agent."

## 5. Relevant Memory Recall: Not Stuffing Everything into the Prompt, but Making Selections

Related implementations:

- [`src/memdir/findRelevantMemories.ts`](../src/memdir/findRelevantMemories.ts)

Many systems, once they have memory, stuff all historical memories into the prompt. This project does not do that.

`findRelevantMemories()` works as follows:

```text
memoryDir
 -> scanMemoryFiles() scans file headers
 -> filters out alreadySurfaced files
 -> formatMemoryManifest() generates a "filename + description" manifest
 -> sideQuery(...) calls a lightweight model to make selections
 -> selects at most 5 memory files
 -> returns absolute paths and mtimeMs
```

Several details in the implementation are worth noting:

- What is selected is the filename, not the full body text
- The selector only looks at the header / manifest, without first stuffing all the body text in
- `MEMORY.md` itself is not selected here because it is already separately injected into the system prompt
- `recentTools` affects the selection, preventing duplicate recall of tool documents currently in active use
- `alreadySurfaced` filters memories that have been presented before, preventing the same batch of files from being selected every round

So this layer is essentially a "lightweight retriever," not a "full-text vector library."

## 6. Session Memory: Current Session Summary Layer

Related implementations:

- [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts)
- [`src/services/SessionMemory/sessionMemoryUtils.ts`](../src/services/SessionMemory/sessionMemoryUtils.ts)

Session Memory is not Agent Memory, but it is very important because it shows that the author separated "current session summary" from "long-term agent memory."

### 6.1 Trigger Thresholds

The default thresholds are clearly specified in [`src/services/SessionMemory/sessionMemoryUtils.ts`](../src/services/SessionMemory/sessionMemoryUtils.ts):

- `minimumMessageTokensToInit = 10000`
- `minimumTokensBetweenUpdate = 5000`
- `toolCallsBetweenUpdates = 3`

The meaning is:

- Session Memory is not enabled until the conversation is long enough
- Even when enabled, it is not updated every round
- Both tool call count and token growth participate in the judgment

### 6.2 When Is It Considered "Worth Extracting"

**Actual source code** ([`src/services/SessionMemory/sessionMemory.ts:134`](../src/services/SessionMemory/sessionMemory.ts)):

```typescript
export function shouldExtractMemory(messages: Message[]): boolean {
 const currentTokenCount = tokenCountWithEstimation(messages)

 if (!isSessionMemoryInitialized()) {
 if (!hasMetInitializationThreshold(currentTokenCount)) return false
 markSessionMemoryInitialized()
 }

 const hasMetTokenThreshold = hasMetUpdateThreshold(currentTokenCount)
 const hasMetToolCallThreshold =
 countToolCallsSince(messages, lastMemoryMessageUuid) >= getToolCallsBetweenUpdates()
 const hasToolCallsInLastTurn = hasToolCallsInLastAssistantTurn(messages)

 // Token threshold is always required; trigger at natural breakpoints (no tool_use) or when both thresholds are met
 const shouldExtract =
 (hasMetTokenThreshold && hasMetToolCallThreshold) ||
 (hasMetTokenThreshold && !hasToolCallsInLastTurn)

 if (shouldExtract) {
 lastMemoryMessageUuid = messages[messages.length - 1]?.uuid
 return true
 }
 return false
}
```

`!hasToolCallsInLastTurn` looks for natural breakpoints, preventing truncation in the middle of a tool_use chain that would generate an orphaned summary.

### 6.3 Storage and Permissions

Session Memory files are created with strict permissions ([`src/services/SessionMemory/sessionMemory.ts:183`](../src/services/SessionMemory/sessionMemory.ts)):

```typescript
async function setupSessionMemoryFile(ctx) {
 const sessionMemoryDir = getSessionMemoryDir()
 await fs.mkdir(sessionMemoryDir, { mode: 0o700 }) // Directory: owner only can read/write/execute

 const memoryPath = getSessionMemoryPath()
 await writeFile(memoryPath, '', {
 mode: 0o600, // File: owner only can read/write
 flag: 'wx', // O_CREAT|O_EXCL: create only if file does not exist, prevent overwriting existing memory
 })
}
```

`0o700` + `0o600` indicates that Session Memory is treated as sensitive local state, not an ordinary cache file.

### 6.4 Update Method: Background Forked Subagent

Dispatch chain:

```text
Main session shouldExtractMemory() == true
 -> registerPostSamplingHook triggers
 -> setupSessionMemoryFile() // Create 0o600 file, 0o700 directory
 -> buildSessionMemoryUpdatePrompt() // Construct summary instructions
 -> runForkedAgent({ canUseTool: createMemoryFileCanUseTool(memoryPath) })
```

**`createMemoryFileCanUseTool()` actual source code** ([`src/services/SessionMemory/sessionMemory.ts:460`](../src/services/SessionMemory/sessionMemory.ts)):

```typescript
export function createMemoryFileCanUseTool(memoryPath: string): CanUseToolFn {
 return async (tool: Tool, input: unknown) => {
 if (
 tool.name === FILE_EDIT_TOOL_NAME &&
 typeof input === 'object' && input !== null &&
 'file_path' in input &&
 typeof input.file_path === 'string' &&
 input.file_path === memoryPath // Exact path matching, no path traversal allowed
) {
 return { behavior: 'allow' as const, updatedInput: input }
 }
 return {
 behavior: 'deny' as const,
 message: `only ${FILE_EDIT_TOOL_NAME} on ${memoryPath} is allowed`,
 decisionReason: { type: 'other', reason: `only ${FILE_EDIT_TOOL_NAME} on ${memoryPath} is allowed` },
 }
 }
}
```

The Session Memory extraction subagent is a tightly sandboxed summary agent: only `FileEditTool` is allowed, and only on the exact path — even `FileReadTool` and `FileWriteTool` are denied.

## 7. Agent Memory: Persistent Memory Truly Bound to an Agent

Related implementations:

- [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts)
- [`src/tools/AgentTool/loadAgentsDir.ts`](../src/tools/AgentTool/loadAgentsDir.ts)
- [`src/tools/AgentTool/agentMemorySnapshot.ts`](../src/tools/AgentTool/agentMemorySnapshot.ts)
- [`src/components/memory/MemoryFileSelector.tsx`](../src/components/memory/MemoryFileSelector.tsx)

This section is the focus of this chapter.

### 7.1 Positioning of Agent Memory

The difference between Agent Memory and Auto Memory is:

- Auto Memory is "user / project dimension" long-term memory
- Agent Memory is "a specific agent type" long-term memory

In other words, it's not "what the current session remembers," but "what this agent should know long-term in the future."

This means the agent is no longer just a static prompt template, but:

```text
agent =
 static role prompt
 + memory scope
 + memory directory
 + writable memory tools
 + snapshot initialization capability
```

### 7.2 Three Scopes

In [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts), `AgentMemoryScope` has exactly three types:

- `user`
- `project`
- `local`

Their meanings:

- `user`
 Cross-project reusable agent long-term memory
- `project`
 Agent memory shared within the current project
- `local`
 Local agent memory for the current project, current machine, or current mount environment

### 7.3 Actual Directory Layout

The directory resolution rules for `getAgentMemoryDir(agentType, scope)` are very clear:

```text
user:
 <memoryBase>/agent-memory/<agentType>/

project:
 <cwd>/.claude/agent-memory/<agentType>/

local:
 Default:
 <cwd>/.claude/agent-memory-local/<agentType>/
 If CLAUDE_CODE_REMOTE_MEMORY_DIR is set:
 <remoteMemoryDir>/projects/<sanitized-git-root>/agent-memory-local/<agentType>/
```

Two implementation details:

1. `agentType` is path-sanitized first
 `:` is replaced with `-`, because plugin namespaces might look like `my-plugin:my-agent`, but this is unsafe as a filename on some platforms.
2. `local` scope in remote environments is not truly "local disk only"
 It is relocated to the project namespace of the remote memory mount.

### 7.4 Why `isAgentMemoryPath()` Exists

`isAgentMemoryPath()` normalizes the candidate path and then determines whether it belongs to one of the three agent memory directories.

This is not an ordinary utility; its significance is:

- Prevents path traversal like `..` from bypassing memory boundary checks
- Lets the permission system know "this is an agent memory file"
- Enables the UI or tool layer to handle it specially

In other words, Agent Memory in the system is not an "ordinary folder" — it is recognized as a special storage boundary.

### 7.5 Agent Memory Entrypoint File

`getAgentMemoryEntrypoint()` directly returns:

```text
<agent-memory-dir>/MEMORY.md
```

This means Agent Memory does not have a new protocol independent of the memdir system — it directly reuses the entire memory file system design.

In other words, Agent Memory is not reinventing the wheel, but:

- Directory structure follows memdir
- Prompt construction follows `buildMemoryPrompt()`
- Memory governance rules also follow typed memory instructions

### 7.6 How Memory Is Declared in Agent Definitions

The agent definition loading logic is in [`src/tools/AgentTool/loadAgentsDir.ts`](../src/tools/AgentTool/loadAgentsDir.ts).

Whether it is a JSON agent or a Markdown agent, if the definition includes a `memory` field, the system does two things:

1. Automatically appends the memory prompt to the end of the agent system prompt
2. Automatically injects the `Write / Edit / Read` three file tools into the agent's tool list

Both steps are indispensable.

If only the prompt is injected without the file tools, the agent can see the rules but cannot persist to disk.
If only the file tools are injected without the prompt, the agent has write permissions but does not know the memory directory or governance rules.

### 7.7 How `getSystemPrompt()` Wires in Agent Memory

In both `parseAgentFromJson()` and `parseAgentFromMarkdown()`, there is logic like this:

```text
if (isAutoMemoryEnabled() && parsed.memory) {
 return systemPrompt + '\n\n' + loadAgentMemoryPrompt(agentType, parsed.memory)
}
```

So the injection timing for Agent Memory is very early:

- Not dynamically attached during agent runtime
- Not added after tool calls
- But directly fixed in when constructing the agent system prompt

This means from the very first round, the agent knows:

- Where its memory directory is
- How to write memory
- What indices are currently in `MEMORY.md`

### 7.8 What `loadAgentMemoryPrompt()` Does

`loadAgentMemoryPrompt(agentType, scope)` does several very critical things:

```text
loadAgentMemoryPrompt()
 -> Generates scopeNote based on scope
 -> Computes memoryDir
 -> fire-and-forget ensureMemoryDirExists(memoryDir)
 -> buildMemoryPrompt({
 displayName: 'Persistent Agent Memory',
 memoryDir,
 extraGuidelines: [scopeNote,...possible additional environment rules]
 })
```

These points correspond to different intentions:

- `scopeNote`
 Tells the agent: user scope should write more generally, project scope should be project-oriented, local scope should be for the current machine/workspace.
- `ensureMemoryDirExists(memoryDir)`
 Creates the directory in advance during prompt construction, but does not block the main path.
- `buildMemoryPrompt(...)`
 Lets Agent Memory reuse the entire set of memdir rules instead of writing a separate prompt.
- `CLAUDE_COWORK_MEMORY_EXTRA_GUIDELINES`
 Allows attaching additional memory rules in cowork scenarios.

### 7.9 Why Directory Creation Is Fire-and-Forget

The comments clearly explain the reason:

- This logic runs in a synchronous `getSystemPrompt()` callback
- Some call scenarios come from the React render path
- Therefore, it cannot be asynchronously blocked here

So the author took a very pragmatic approach:

- Create the directory asynchronously first
- Even if the directory hasn't been created yet, the `FileWriteTool` will create it later on its own

This is a typical engineering trade-off: not disrupting the synchronicity of the prompt construction path for the sake of "theoretical perfection."

### 7.10 How Agent Memory Write Capability Is Granted to the Agent

`loadAgentsDir.ts` contains a very critical auto-injection logic:

```text
If memory is enabled, and auto memory is enabled:
 Forcefully add the following tools to the agent tools:
 - FileWriteTool
 - FileEditTool
 - FileReadTool
```

This means an agent that declares memory naturally gets a minimal closed loop:

```text
Read index -> FileReadTool
Create memory -> FileWriteTool
Update memory -> FileEditTool
```

From this, you can also see the author's design stance:

- Agent Memory is not secretly maintained by the "system backend"
- But explicitly read and written by the agent itself as markdown files

### 7.11 Typical Usage Flow for Agent Memory

Putting the above mechanisms together, the actual runtime chain is roughly:

```text
Load agent definition
 -> agent.memory = user / project / local
 -> Automatically add FileRead / FileWrite / FileEdit
 -> getSystemPrompt() appends Agent Memory prompt

Spawn agent
 -> Prompt already contains:
 1. Memory usage rules
 2. Memory directory location
 3. Current MEMORY.md index content

Agent discovers information worth remembering during work
 -> First read MEMORY.md or existing memory files
 -> Add or update a memory entry
 -> Then maintain the MEMORY.md index

Subsequent invocation of the same agent
 -> Re-read the same directory's MEMORY.md
 -> Get the long-term memory (accumulated) from last time
```

This shows that the "application" of Agent Memory is not a retrieval plugin, but directly changes the starting point of the agent's system prompt for the next invocation.

### 7.12 Agent Memory Snapshot: Treating Memory as a Distributable Asset

This is one of the most interesting implementations in this chapter.

In [`src/tools/AgentTool/agentMemorySnapshot.ts`](../src/tools/AgentTool/agentMemorySnapshot.ts), the snapshot directory is fixed at:

```text
<cwd>/.claude/agent-memory-snapshots/<agentType>/
```

There are two key files:

- `snapshot.json`
 Records the snapshot's `updatedAt`
- `.snapshot-synced.json`
 Records the local snapshot timestamp from which the current state was synced

### 7.13 Three States of Snapshot

`checkAgentMemorySnapshot()` only returns three actions:

- `none`
- `initialize`
- `prompt-update`

The judgment logic can be summarized as:

```text
If there is no snapshot.json in the project:
 -> none

If there are no.md files in the local agent memory directory:
 -> initialize

If local memory exists, but:
 -.snapshot-synced.json does not exist
 - or snapshot.updatedAt > syncedFrom
 -> prompt-update

Otherwise:
 -> none
```

This shows that snapshot is not blindly overwritten every time, but distinguishes between:

- First-time initialization
- A new version is available and can be prompted for update
- Already synced, no action needed

### 7.14 How Snapshot Initializes Local Memory

The logic of `initializeFromSnapshot()` is straightforward:

```text
Snapshot directory
 -> Copy all files except snapshot.json
 -> Write to local agent memory directory
 -> Save.snapshot-synced.json
```

And `replaceFromSnapshot()` is more aggressive:

```text
Local agent memory directory
 -> First delete existing.md files
 -> Then copy snapshot
 -> Then write synced metadata
```

There is also `markSnapshotSynced()`:

- Does not modify content
- Only updates sync metadata

This is typically used for the scenario: "I know there is a new version, but I accept the current version state."

### 7.15 When Snapshot Is Checked

The snapshot check logic is in [`src/tools/AgentTool/loadAgentsDir.ts`](../src/tools/AgentTool/loadAgentsDir.ts).

Several conditions must be met to trigger it:

- `feature('AGENT_MEMORY_SNAPSHOT')`
- `isAutoMemoryEnabled()`
- The agent is a custom agent
- And in the current implementation, initialization check is only performed for agents with `memory === 'user'`

This last point is critical: the current snapshot mechanism is mainly for initializing and upgrading user-scope agent memory, not treating all scopes equally.

### 7.16 Why Snapshot Is Important

Because it elevates agent memory from a "runtime byproduct" to a "distributable role asset."

This means a project can not only define the agent's prompt, but also ship together:

- The agent's initial memory structure
- The agent's accumulated collaboration experience
- The agent's updated versions

This is more powerful than simply shipping a `prompt.md`, because it allows the project to gradually mature the agent.

### 7.17 Agent Memory Is Visible in the UI

[`src/components/memory/MemoryFileSelector.tsx`](../src/components/memory/MemoryFileSelector.tsx) exposes the agent memory directory to the UI.

This means Agent Memory is not an implicit storage for internal logic only, but a user-facing, browsable, openable filesystem object.

This is completely different from many products where "the model has memory, but the user cannot see it."

## 8. Team Memory: Shared Rather Than Personal Private Memory

Related implementations:

- [`src/services/teamMemorySync/index.ts`](../src/services/teamMemorySync/index.ts)
- [`src/services/teamMemorySync/watcher.ts`](../src/services/teamMemorySync/watcher.ts)
- [`src/memdir/teamMemPaths.ts`](../src/memdir/teamMemPaths.ts)

Team Memory is another dimension: it does not revolve around a single agent, but around team-shared knowledge.

From the implementation, it is not a simple shared directory, but includes:

- pull / push
- watcher
- checksum
- optimistic locking
- path validation
- secret scanning

So the goal of Team Memory is not to "help one agent remember things," but to "turn repo-level knowledge into a controlled synchronization team knowledge layer."

## 9. Division of Labor Between Agent Memory and Other Memories

Looking at the layers of memory together, the boundaries of responsibility become clearer:

```text
Auto Memory
 Solves: User / project long-term collaboration information (crystallization)

Relevant Recall
 Solves: Only recall relevant memories each round to avoid prompt pollution

Session Memory
 Solves: Long session summary and compact stability

Agent Memory
 Solves: Long-term dedicated memory for a specific agent type

Agent Memory Snapshot
 Solves: Initialization, distribution, and upgrade of agent memory

Team Memory
 Solves: Team shared knowledge synchronization
```

So if Chapter 4 only looks at "where the Agent Memory directory is," that's not enough. The real engineering design is: it is placed into a layered memory system, with each layer responsible for a different problem.

## 10. Coupling Points with the Agent Runtime

Related implementations:

- [`src/tools/AgentTool/loadAgentsDir.ts`](../src/tools/AgentTool/loadAgentsDir.ts)
- [`src/tools/AgentTool/runAgent.ts`](../src/tools/AgentTool/runAgent.ts)

Agent Memory is important because it is not outside the runtime, but inside the runtime.

There are four main coupling points:

1. `Agent definition phase`
 The `memory` field directly affects the agent parsing result.
2. `System prompt construction phase`
 The memory prompt is directly appended to the agent's system prompt.
3. `Tool capability phase`
 Memory agents automatically gain the ability to read, write, and edit memory files.
4. `Snapshot lifecycle phase`
 Snapshot initialization or update status is checked when the agent definition is loaded.

Therefore, what is called "the agent has memory" in this project is not an abstract concept, but:

```text
agent runtime
 = agent definition
 + system prompt
 + tool set
 + permission context
 + memory directory
 + snapshot state
```

## 11. Memory Compaction: Automatic Context Compression Mechanism

Related implementations:

- [`src/services/compact/compact.ts`](../src/services/compact/compact.ts)
- [`src/services/compact/sessionMemoryCompact.ts`](../src/services/compact/sessionMemoryCompact.ts)

No matter how many layers of memory are introduced, because agent conversations involve a large number of read/write results (especially file code output), the model's context tokens can easily reach the upper limit. The system has a bottom-level `compact` (context compression) logic, divided into manual `/compact` and automatic threshold triggering. To avoid losing agent functionality and key coherence during compression, it employs rigorous technical measures:

### 11.1 Preprocessing and Token Stop-Loss Protection

Before sending the summary request to the model, [`stripImagesFromMessages`](../src/services/compact/compact.ts) and [`stripReinjectedAttachments`](../src/services/compact/compact.ts) are called to strip all image inputs and lengthy static skill manifest attachments. This prevents the summary request from hitting the model's token wall due to excessive size (causing PTL errors). If PTL is triggered, [`truncateHeadForPTLRetry`](../src/services/compact/compact.ts) falls back to trimming the earliest API rounds to ensure the program itself can operate without obstruction.

### 11.2 Session Memory (SM) Direct Attachment and Tool Chain Breakpoint Protection

This is the most brilliant engineering design in the project's compaction mechanism. If the system is already in a long session with Session Memory enabled, it **does not call an additional API to waste tokens on summarizing** — instead, it directly calls [`trySessionMemoryCompaction`](../src/services/compact/sessionMemoryCompact.ts), reads the latest Session Memory file (accumulated) by the background memory extraction subagent, and uses it directly as a context breakpoint (SummaryMessage).
More importantly, when deciding which messages to discard, [`calculateMessagesToKeepIndex`](../src/services/compact/sessionMemoryCompact.ts) performs precise trimming:
- It must prioritize keeping a minimum configured lower-bound token count of original text from the tail backward (default retention configuration is approximately 10K-40K tokens), configured via [`getSessionMemoryCompactConfig`](../src/services/compact/sessionMemoryCompact.ts).
- It has built-in highly defensive code logic to solve the **noodle concurrency problem**: when truncating, if the cut position falls in the middle of a `tool_use / tool_result` execution chain, or encounters a Thinking stream sharing the same `message.id` as an Assistant message, [`adjustIndexToPreserveAPIInvariants`](../src/services/compact/sessionMemoryCompact.ts) forcibly shifts the index toward the head to bundle these records, absolutely avoiding cutting out illegal orphaned `tool_result` blocks, thus circumventing Anthropic's strict API validation errors.

### 11.3 State and Capability Reinjection

The discarded and compacted messages are transformed into short messages with [`SystemCompactBoundaryMessage`](../src/types/message.ts) pointing to the Summary, generated by [`createCompactBoundaryMessage`](../src/utils/messages.ts). However, this has a fatal side effect: the capability descriptions previously provided to the large model (such as Tool Schemas and MCP remote tool lists) are also trimmed and lost. Therefore, after compaction is complete, [`createPostCompactFileAttachments`](../src/services/compact/compact.ts) automatically rebuilds FileAttachments (keeping workspace reads) and the active Plans list, and re-declares all currently loaded external capabilities via [`getDeferredToolsDeltaAttachment`](../src/utils/attachments.ts), appending them back into the new queue. When the model wakes up for its first turn, although the past details are gone, its current skill blueprint remains fully loaded.

## 12. Advantages and Costs of This Implementation

### 12.1 Advantages

1. Transparent
 All memories are files; users can inspect, edit, and delete them.
2. Clear scope
 The three-layer scope of user / project / local is very practical.
3. Controllable retrieval cost
 Not all memories are loaded every round — relevant recall is used.
4. Agents can truly "grow"
 Because memory is bound to the agent type, not just a single session.
5. Distributable
 The snapshot mechanism allows agent memory to be published and upgraded along with the project.

### 12.2 Costs

1. Requires governance
 Incorrect, outdated, and duplicate memories will continuously pollute subsequent agent behavior.
2. Path and permission logic becomes complex
 User / project / local / remote mount all need to be handled separately.
3. Heavier prompt construction
 `MEMORY.md` participates in prompt generation every time, although there is truncation protection, there is still a cost.
4. Requires the model to follow writing conventions
 The system has already applied many rule constraints, but ultimately relies on the agent to correctly maintain the index and files.

## 13. Chapter Summary

If Agent Memory in this project could be summarized in one sentence:

It is not "adding a hidden cache to the agent," but turning the agent's long-term memory into a runtime infrastructure that is file-based, scoped, writable, initializable, upgradable, and viewable in the UI.

If the entire memory system were summarized further:

```text
Auto Memory manages long-term collaboration memory
Session Memory manages current session summary
Agent Memory manages the dedicated long-term memory of a specific agent type
Team Memory manages team-shared knowledge
Relevant Recall handles on-demand retrieval
Snapshot handles agent memory assetization
Compaction handles underlying token session stream compression
```
