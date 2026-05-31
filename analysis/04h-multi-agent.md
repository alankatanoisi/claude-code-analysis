# Chapter 10: Multi-Agent Mechanism and Implementation Details

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter directly answers one question:

**Claude Code's source code not only has multi-agent, but actually contains three coexisting multi-agent operating models.**

It's not just "you can start a background subtask" — three models exist simultaneously:

1. Normal `subagent`
2. `coordinator -> workers` coordinator pattern
3. `swarm teammates` team collaboration pattern

This chapter focuses on explaining:

1. The different types of multi-agent in the source code
2. How `AgentTool` decides whether something is a normal subagent or a teammate
3. What enhancements the coordinator mode actually provides
4. How swarm mode implements the collaboration chain of team, mailbox, permission, and task list
5. What this implementation adds compared to "single agent + background task"

This chapter is based on these implementations:

- [`src/tools/AgentTool/AgentTool.tsx`](../src/tools/AgentTool/AgentTool.tsx)
- [`src/tools/AgentTool/runAgent.ts`](../src/tools/AgentTool/runAgent.ts)
- [`src/tools/AgentTool/forkSubagent.ts`](../src/tools/AgentTool/forkSubagent.ts)
- [`src/coordinator/coordinatorMode.ts`](../src/coordinator/coordinatorMode.ts)
- [`src/tools/shared/spawnMultiAgent.ts`](../src/tools/shared/spawnMultiAgent.ts)
- [`src/utils/swarm/spawnInProcess.ts`](../src/utils/swarm/spawnInProcess.ts)
- [`src/utils/swarm/inProcessRunner.ts`](../src/utils/swarm/inProcessRunner.ts)
- [`src/tasks/InProcessTeammateTask/InProcessTeammateTask.tsx`](../src/tasks/InProcessTeammateTask/InProcessTeammateTask.tsx)
- [`src/utils/teammateMailbox.ts`](../src/utils/teammateMailbox.ts)
- [`src/hooks/useInboxPoller.ts`](../src/hooks/useInboxPoller.ts)
- [`src/tools/SendMessageTool/SendMessageTool.ts`](../src/tools/SendMessageTool/SendMessageTool.ts)
- [`src/tools/TeamCreateTool/TeamCreateTool.ts`](../src/tools/TeamCreateTool/TeamCreateTool.ts)
- [`src/tools/TaskCreateTool/TaskCreateTool.ts`](../src/tools/TaskCreateTool/TaskCreateTool.ts)
- [`src/tools/TaskStopTool/TaskStopTool.ts`](../src/tools/TaskStopTool/TaskStopTool.ts)
- [`src/utils/swarm/leaderPermissionBridge.ts`](../src/utils/swarm/leaderPermissionBridge.ts)

TL;DR:

Claude Code's multi-agent is not a single implementation but a layered system:

```text
1. Normal AgentTool Sub-agent
   - Single main agent dispatches a subagent
   - Supports sync, background, and fork

2. Coordinator Mode
   - Main thread becomes coordinator
   - Continuously dispatches multiple workers via AgentTool
   - Worker results flow back via task-notification

3. Swarm / Teammates
   - Create team
   - Produce lead + teammates
   - Supports in-process / tmux / iTerm2 backends
   - Supports mailbox, permission bridging, task list collaboration
```

Therefore, Claude Code's multi-agent is not simply "added an AgentTool."

More precisely, it implements a small agent runtime:

- Agent identity model
- Agent creation and scheduling
- Inter-agent communication
- Leader/worker permission bridging
- Shared task plane
- UI layer task / teammate visualization

## 2. Overall Structure: The Three Multi-Agent Models Are Not the Same

Related implementations:

- [`src/tools/AgentTool/AgentTool.tsx`](../src/tools/AgentTool/AgentTool.tsx)
- [`src/coordinator/coordinatorMode.ts`](../src/coordinator/coordinatorMode.ts)
- [`src/tools/shared/spawnMultiAgent.ts`](../src/tools/shared/spawnMultiAgent.ts)

Many people see `AgentTool` and jump to an oversimplified conclusion:

"Claude Code just supports starting subagents."

That's wrong.

The source code contains at least three distinct levels of multi-agent:

### 2.1 Normal Subagent

This is the most basic layer:

- Main agent calls `AgentTool`
- Creates a new agent session
- Subagent inherits part of the context and tool pool
- When done, passes results back to the main thread

This is more like a "background worker."

### 2.2 Coordinator Mode

This layer is not simply "spawning multiple subagents" — it redefines the main thread's role as a coordinator.

In [`src/coordinator/coordinatorMode.ts`](../src/coordinator/coordinatorMode.ts), `getCoordinatorSystemPrompt()` directly defines the main thread as:

```typescript
You are Claude Code, an AI assistant that orchestrates software engineering tasks across multiple workers.
```

In other words:

- The main thread is no longer primarily responsible for writing code itself
- The main thread is responsible for dispatching multiple workers
- Workers are responsible for research / implementation / verification
- The main thread is responsible for synthesizing results, continuing to assign work, and reporting to the user

This is a true orchestrator pattern.

### 2.3 Swarm Teammates

Swarm goes a step further.

It's not "temporary workers" — it explicitly creates a team:

- Has `team_name`
- Has a lead agent
- Has a teammate roster
- Has inbox / mailbox
- Has a shared task list
- Has a permission bridging mechanism for teammates

This layer approaches a lightweight "agent organization system."

## 3. `AgentTool` Is the Unified Entry Point for Multi-Agent

Related implementations:

- [`src/tools/AgentTool/AgentTool.tsx`](../src/tools/AgentTool/AgentTool.tsx)

### 3.1 The Input Schema Directly Exposes Multi-Agent Capabilities

`AgentTool`'s schema contains a critical set of fields:

```typescript
const baseInputSchema = z.object({
  description: z.string(),
  prompt: z.string(),
  subagent_type: z.string().optional(),
  model: z.enum(['sonnet', 'opus', 'haiku']).optional(),
  run_in_background: z.boolean().optional(),
})

const multiAgentInputSchema = z.object({
  name: z.string().optional(),
  team_name: z.string().optional(),
  mode: permissionModeSchema().optional(),
})
```

These fields already show it's not just "run a task":

- `subagent_type` determines agent type
- `run_in_background` determines sync vs async
- `name` makes the agent addressable later
- `team_name` directs the agent into the swarm / teammate path
- `mode` lets the spawned teammate inherit permission modes like plan

### 3.2 How `AgentTool` Determines If Something Is a Teammate

The core branching in `call()` is critical:

```typescript
if (teamName && name) {
  const result = await spawnTeammate({
    name,
    prompt,
    description,
    team_name: teamName,
    use_splitpane: true,
    plan_mode_required: spawnMode === 'plan',
    model: model ?? agentDef?.model,
    agent_type: subagent_type,
    invokingRequestId: assistantMessage?.requestId
  }, toolUseContext);
}
```

This logic shows:

- When only `subagent_type` / `prompt` is provided, it takes the normal subagent path
- When both `teamName + name` are provided, it takes the `spawnTeammate()` path

In other words, **the same AgentTool serves as the entry point for both normal subagents and teammate spawning.**

### 3.3 Restrictions on Teammates Are Also Written Here

The same function has several very practical constraints:

```typescript
if (isTeammate() && teamName && name) {
  throw new Error('Teammates cannot spawn other teammates ...')
}

if (isInProcessTeammate() && teamName && run_in_background === true) {
  throw new Error('In-process teammates cannot spawn background agents ...')
}
```

This shows the authors didn't just pile on features — they constrained the multi-agent topology:

- Teammates cannot infinitely nest other teammates
- In-process teammates cannot start their own background agents

Otherwise the agent graph could easily spiral out of control.

## 4. Normal Subagent: Essentially a "Side Chain of the Main Session"

Related implementations:

- [`src/tools/AgentTool/runAgent.ts`](../src/tools/AgentTool/runAgent.ts)
- [`src/tools/AgentTool/forkSubagent.ts`](../src/tools/AgentTool/forkSubagent.ts)

### 4.1 `runAgent()` Is the Real Agent Executor

`AgentTool` is more like the entry and routing layer — the actual agent execution happens in `runAgent()`.

From the implementation, several key points emerge:

- It initializes agent-specific MCP servers
- It constructs the sub-agent's `ToolUseContext`
- It executes `executeSubagentStartHooks()`
- It writes the transcript to a sidechain
- Finally it calls `query()`

The source code reference shows this chain:

```typescript
for await (const hookResult of executeSubagentStartHooks(...)) { ... }

const agentToolUseContext = createSubagentContext(toolUseContext, { ... })

void recordSidechainTranscript(initialMessages, agentId)
void writeAgentMetadata(agentId, { ... })

for await (const message of query({ ... })) { ... }
```

This shows that a normal subagent is not "running a function in the main thread" — it fully reuses the query runtime.

### 4.2 Fork Subagent Is a Special Variant

[`src/tools/AgentTool/forkSubagent.ts`](../src/tools/AgentTool/forkSubagent.ts) clearly defines the rules for fork mode:

- Omitting `subagent_type` triggers implicit fork
- Child inherits the parent's full conversation context
- Child inherits the parent's rendered system prompt
- All fork children run in the background by default

The key comment explains the design intent clearly:

```typescript
When enabled:
- Omitting `subagent_type` triggers an implicit fork
- the child inherits the parent's full conversation context and system prompt
- All agent spawns run in the background
```

### 4.3 Why Fork Preserves the Parent Prompt's Raw Bytes

This is a significant technical point.

The `FORK_AGENT` comment notes:

```typescript
The getSystemPrompt here is unused: the fork path passes
`override.systemPrompt` with the parent's already-rendered system prompt bytes ...
Reconstructing by re-calling getSystemPrompt() can diverge ... and bust the prompt cache
```

In other words, the fork child doesn't regenerate the system prompt — it directly uses the parent session's already-rendered prompt bytes.

The purpose isn't logical correctness but **prompt cache hit stability**.

This shows that the multi-agent implementation is deeply coupled with the prompt/caching infrastructure.

## 5. Coordinator Mode: Turning the Main Thread Into a Scheduler

Related implementations:

- [`src/coordinator/coordinatorMode.ts`](../src/coordinator/coordinatorMode.ts)

### 5.1 Coordinator Mode Is Not a Tool, It's a Mode Switch

`isCoordinatorMode()` checks an environment variable:

```typescript
export function isCoordinatorMode(): boolean {
  if (feature('COORDINATOR_MODE')) {
    return isEnvTruthy(process.env.CLAUDE_CODE_COORDINATOR_MODE)
  }
  return false
}
```

This means it's not a normal slash command — it's a runtime mode.

### 5.2 The Coordinator System Prompt Directly Rewrites the Main Thread's Identity

Its most critical part isn't function logic but the system prompt:

```typescript
You are Claude Code, an AI assistant that orchestrates software engineering tasks across multiple workers.
```

It then provides a clear set of operational rules:

- Use `Agent` to spawn workers
- Use `SendMessage` to continue an existing worker
- Use `TaskStop` to stop a worker
- Don't have one worker check on another worker
- Launch independent workers in parallel
- Serialize write operations by file set, research tasks can be parallel

This shows that the coordinator isn't "the main agent deciding to dispatch a few subagents on its own" — the prompt layer has already cut its role into that of a dispatcher.

### 5.3 Worker Results Are Not Assistant Messages, but Task Notifications

The same file defines the worker result format:

```xml
<task-notification>
<task-id>{agentId}</task-id>
<status>completed|failed|killed</status>
<summary>...</summary>
<result>...</result>
<usage>...</usage>
</task-notification>
```

This is a critical point:

- Worker results are packaged as user-role messages
- The coordinator must recognize `<task-notification>`
- The coordinator can't treat it as "a normal user speaking"

So the coordinator-worker pattern is fundamentally event-driven.

### 5.4 The Coordinator Workflow Is Explicitly Phased

The source code defines the workflow directly:

| Phase | Executor | Purpose |
|------|--------|------|
| Research | Workers | Find files, understand the problem |
| Synthesis | Coordinator | Aggregate research results, design implementation plan |
| Implementation | Workers | Execute modifications per spec |
| Verification | Workers | Run validation |

This shows it's not completely free-form division of labor — it explicitly encourages "research parallel, synthesis centralized, implementation dispatched, verification independent."

## 6. Swarm Mode: True Team-Based Multi-Agent

Related implementations:

- [`src/tools/TeamCreateTool/TeamCreateTool.ts`](../src/tools/TeamCreateTool/TeamCreateTool.ts)
- [`src/tools/shared/spawnMultiAgent.ts`](../src/tools/shared/spawnMultiAgent.ts)

### 6.1 Team Is an Explicit Entity

`TeamCreateTool` creates an actual team file:

```typescript
const teamFile: TeamFile = {
  name: finalTeamName,
  description: _description,
  createdAt: Date.now(),
  leadAgentId,
  leadSessionId: getSessionId(),
  members: [
    {
      agentId: leadAgentId,
      name: TEAM_LEAD_NAME,
      agentType: leadAgentType,
      model: leadModel,
      ...
    },
  ],
}

await writeTeamFileAsync(finalTeamName, teamFile)
```

It also:

- Resets and creates the task list directory
- Sets the leader team name
- Updates `teamContext` in AppState

So swarm is not a transient in-memory state.

It has at least three pieces of persisted state:

1. `team file`
2. `task list`
3. `AppState.teamContext`

### 6.2 `spawnTeammate()` Is the Main Teammate Creation Entry Point

[`src/tools/shared/spawnMultiAgent.ts`](../src/tools/shared/spawnMultiAgent.ts) exposes:

```typescript
export async function spawnTeammate(
  config: SpawnTeammateConfig,
  context: ToolUseContext,
): Promise<{ data: SpawnOutput }> {
  return handleSpawn(config, context)
}
```

This shows that teammate spawning has been extracted into a shared module, callable both by dedicated team tools and reused by `AgentTool`.

From an engineering perspective, this elevates "spawn multi-agent" into a platform capability, not local logic.

## 7. In-Process Teammate: Same-Process Multi-Agent

Related implementations:

- [`src/utils/swarm/spawnInProcess.ts`](../src/utils/swarm/spawnInProcess.ts)
- [`src/tasks/InProcessTeammateTask/InProcessTeammateTask.tsx`](../src/tasks/InProcessTeammateTask/InProcessTeammateTask.tsx)
- [`src/utils/swarm/inProcessRunner.ts`](../src/utils/swarm/inProcessRunner.ts)

### 7.1 It Doesn't Start a New Process — It Uses `AsyncLocalStorage` for Context Isolation

The header of `spawnInProcess.ts` makes it clear:

```typescript
Creates and registers an in-process teammate task.
Unlike process-based teammates (tmux/iTerm2), in-process teammates
run in the same Node.js process using AsyncLocalStorage for context isolation.
```

This is a very distinctive aspect of Claude Code's multi-agent implementation.

Not every teammate needs a tmux pane, and not everything needs a subprocess.

The system supports:

- Multiple teammates running concurrently in the same process
- Each teammate has its own identity / context / abortController
- The UI layer displays them as independent tasks

### 7.2 Spawning Registers an Independent Task State

The core logic of `spawnInProcessTeammate()` can be summarized as:

```text
Generate agentId / taskId
  -> create abortController
  -> create teammate identity
  -> create teammateContext
  -> construct InProcessTeammateTaskState
  -> registerTask(taskState)
```

Source code snippet:

```typescript
const agentId = formatAgentId(name, teamName)
const taskId = generateTaskId('in_process_teammate')

const teammateContext = createTeammateContext({ ... })

const taskState: InProcessTeammateTaskState = {
  type: 'in_process_teammate',
  status: 'running',
  identity,
  prompt,
  model,
  abortController,
  pendingUserMessages: [],
  messages: [],
}

registerTask(taskState, setAppState)
```

This shows it has the same status in the scheduling system as shell tasks and local agent tasks.

### 7.3 Teammates Have Their Own Lifecycle and Message Queue

`InProcessTeammateTask.tsx` provides several key operations:

- `requestTeammateShutdown()`
- `appendTeammateMessage()`
- `injectUserMessageToTeammate()`
- `findTeammateTaskByAgentId()`

This shows that a teammate is not a one-shot executor but a continuously interactable object:

- Can receive more messages
- Can switch to transcript view
- Can be shut down
- Can be reverse-looked up by `agentId`

## 8. Communication Mechanism: Dual-Track Mailbox + Direct Resume

Related implementations:

- [`src/utils/teammateMailbox.ts`](../src/utils/teammateMailbox.ts)
- [`src/tools/SendMessageTool/SendMessageTool.ts`](../src/tools/SendMessageTool/SendMessageTool.ts)
- [`src/hooks/useInboxPoller.ts`](../src/hooks/useInboxPoller.ts)

Inter-agent communication in Claude Code isn't single-path — there are at least two:

1. Mailbox file communication
2. Local task / transcript resume

### 8.1 Mailbox: Swarm's File-Based Inbox

The header of `teammateMailbox.ts` states directly:

```typescript
Teammate Mailbox - File-based messaging system for agent swarms
Each teammate has an inbox file at .claude/teams/{team_name}/inboxes/{agent_name}.json
```

It provides these core capabilities:

- `readMailbox()`
- `readUnreadMessages()`
- `writeToMailbox()`
- `markMessageAsReadByIndex()`

`writeToMailbox()` also includes a lock file:

```typescript
release = await lockfile.lock(inboxPath, {
  lockfilePath: lockFilePath,
  ...LOCK_OPTIONS,
})
```

This shows the mailbox is not a toy implementation — it accounts for concurrent multi-agent writes.

### 8.2 `SendMessageTool` Can Send to Both Teammates and Existing Subagents

`SendMessageTool` has two important routing paths.

First, continue an existing subagent:

```typescript
const registered = appState.agentNameRegistry.get(input.to)
const agentId = registered ?? toAgentId(input.to)
...
if (task.status === 'running') {
  queuePendingMessage(agentId, input.message, ...)
}
...
const result = await resumeAgentBackground({
  agentId,
  prompt: input.message,
  ...
})
```

Second, send to swarm mailbox:

```typescript
await writeToMailbox(
  recipientName,
  {
    from: senderName,
    text: content,
    summary,
    timestamp: new Date().toISOString(),
    color: senderColor,
  },
  teamName,
)
```

This shows that `SendMessage` is not a "unified message API" but a **message router**:

- If the target is a local agentId, use local queue or resume
- If the target is a teammate, use mailbox
- If the target is `*`, it also supports broadcast

### 8.3 `useInboxPoller()` Feeds Unread Mailbox Messages Back Into the Execution Flow

`useInboxPoller()` periodically:

```typescript
const unread = await readUnreadMessages(agentName, teamName)
```

Then splits by message type:

- permission request
- permission response
- shutdown request / approval
- plan approval request / response
- regular teammate messages

This shows that the mailbox doesn't carry plain text — it carries agent collaboration protocol messages.

## 9. Permission Mechanism: Leader Backstops Teammates

Related implementations:

- [`src/utils/swarm/leaderPermissionBridge.ts`](../src/utils/swarm/leaderPermissionBridge.ts)
- [`src/utils/swarm/inProcessRunner.ts`](../src/utils/swarm/inProcessRunner.ts)
- [`src/hooks/useInboxPoller.ts`](../src/hooks/useInboxPoller.ts)

### 9.1 In-Process Teammates Don't Pop Their Own Permission Dialogs

This is a critical point.

`leaderPermissionBridge.ts` provides a module-level bridge:

```typescript
let registeredSetter: SetToolUseConfirmQueueFn | null = null
let registeredPermissionContextSetter: SetToolPermissionContextFn | null = null
```

It allows the REPL to expose the leader's permission UI setter for teammate use.

### 9.2 Teammate Permission Requests Borrow the Leader's Standard Permission Dialog

The logic in `createInProcessCanUseTool()` in `inProcessRunner.ts` is clear:

```typescript
const setToolUseConfirmQueue = getLeaderToolUseConfirmQueue()

if (setToolUseConfirmQueue) {
  return new Promise<PermissionDecision>(resolve => {
    setToolUseConfirmQueue(queue => [
      ...queue,
      {
        ...,
        workerBadge: identity.color
          ? { name: identity.agentName, color: identity.color }
          : undefined,
      },
    ])
  })
}
```

In other words:

- Teammates don't have their own independent permission UI
- Teammate ask permissions flow back to the leader's ToolUseConfirmQueue
- The UI displays a `workerBadge`

This is a very pragmatic implementation:

- Avoids multiple permission UI instances
- Keeps unified user control over the entire swarm
- Still allows knowing who is requesting permission

### 9.3 When Leader Bridge Is Unavailable, Fall Back to Mailbox Permission Sync

The same function comment also notes that if the bridge is unavailable, it falls back to the mailbox path:

- Send permission request to leader inbox
- Wait for leader response
- Apply back to teammate context

This shows the permission mechanism also has dual-track disaster recovery.

## 10. Task Collaboration Plane: Not Chat Collaboration, but Task List Collaboration

Related implementations:

- [`src/tools/TaskCreateTool/TaskCreateTool.ts`](../src/tools/TaskCreateTool/TaskCreateTool.ts)
- [`src/utils/swarm/inProcessRunner.ts`](../src/utils/swarm/inProcessRunner.ts)
- [`src/tools/TaskStopTool/TaskStopTool.ts`](../src/tools/TaskStopTool/TaskStopTool.ts)

### 10.1 Team Creation Automatically Binds a Task List

A key segment in `TeamCreateTool`:

```typescript
const taskListId = sanitizeName(finalTeamName)
await resetTaskList(taskListId)
await ensureTasksDir(taskListId)
setLeaderTeamName(sanitizeName(finalTeamName))
```

This means as soon as a team is created, a shared task list is automatically bound.

### 10.2 Teammates Actively Claim Tasks

There is a key function `tryClaimNextTask()` in `inProcessRunner.ts`:

```typescript
const tasks = await listTasks(taskListId)
const availableTask = findAvailableTask(tasks)
...
const result = await claimTask(taskListId, availableTask.id, agentName)
...
await updateTask(taskListId, availableTask.id, { status: 'in_progress' })
```

This means teammate collaboration isn't just "sending messages to each other" — it's:

- A shared task pool
- Agents can claim unassigned tasks
- Task status is immediately updated after claiming

This is a genuine work queue design.

### 10.3 Teammate Tool Pools Are Force-Injected with Task Collaboration Tools

`inProcessRunner.ts` also forcibly injects essential collaboration tools into the teammate tool pool:

```typescript
tools: agentDefinition?.tools
  ? [
      ...new Set([
        ...agentDefinition.tools,
        SEND_MESSAGE_TOOL_NAME,
        TEAM_CREATE_TOOL_NAME,
        TEAM_DELETE_TOOL_NAME,
        TASK_CREATE_TOOL_NAME,
        TASK_GET_TOOL_NAME,
        TASK_LIST_TOOL_NAME,
        TASK_UPDATE_TOOL_NAME,
      ]),
    ]
  : ['*']
```

This shows that even custom agents are injected with a set of swarm-essential tools.

In other words, swarm collaboration capability is a runtime contract, not entirely determined by agent frontmatter.

### 10.4 Task Stopping Is Also a Unified Plane

`TaskStopTool` provides a unified stop entry:

- Input `task_id`
- Validate that the task exists and is still running
- Call `stopTask()`

This ensures that once multiple agents are running concurrently, the system still has a unified kill switch.

## 11. Multi-Agent Main Chain Flowchart

Below is a main flowchart that more closely reflects the source code implementation.

```text
User / Main Thread
   |
   | AgentTool(description, prompt, subagent_type, name?, team_name?)
   v
AgentTool.call()
   |
   +-- if team_name && name ------------------------------+
   |                                                     |
   |                                                     v
   |                                           spawnTeammate()
   |                                                     |
   |                          +--------------------------+-----------------------+
   |                          |                                                  |
   |                          v                                                  v
   |                 in-process teammate                                 tmux / iTerm2 teammate
   |                          |                                                  |
   |                          v                                                  v
   |              spawnInProcessTeammate()                              pane/backend spawn
   |                          |                                                  |
   |                          v                                                  v
   |                InProcessTeammateTask                             inbox / backend / team file
   |                          |
   |                          v
   |                 inProcessRunner -> runAgent()
   |
   +-- else ----------------------------------------------------------+
                                                                       |
                                                                       v
                                                              runAgent()
                                                                       |
                                                                       v
                                                                     query()
                                                                       |
                                                                       v
                                                         task-notification / transcript
```

Now look at the swarm internal collaboration flow:

```text
TeamCreate
  -> create team file
  -> create task list
  -> establish leader teamContext

teammate execution
  -> claimTask()
  -> execute task
  -> SendMessage / writeToMailbox
  -> leader inbox poller receives message
  -> leader decides / approves permissions / continues dispatching
```

## 12. Pseudocode: How to Understand the Core Scheduling Logic

### 12.1 `AgentTool` Routing Logic

```text
function agentToolCall(input):
    resolve permission mode
    resolve teamName

    if current process is teammate and input also wants to spawn teammate:
        reject

    if current process is in-process teammate and asks for background spawn:
        reject

    if input has teamName and name:
        return spawnTeammate(input)

    else:
        return runAgent(input)
```

### 12.2 In-Process Teammate Permission Bridging Logic

```text
function canUseToolAsTeammate(toolRequest):
    result = hasPermissionsToUseTool(toolRequest)

    if result is allow/deny:
        return result

    if leader permission UI bridge exists:
        enqueue request into leader ToolUseConfirmQueue
        wait for decision
        return decision

    else:
        send permission request via mailbox
        wait for mailbox response
        apply response
        return decision
```

### 12.3 Swarm Task Collaboration Logic

```text
function teammateLoop():
    while alive:
        msg = nextPendingUserMessage() or tryClaimNextTask()
        if no msg:
            go idle
            wait
        else:
            runAgent(msg)
            update progress
            if done:
                notify leader
```

## 13. Advantages and Costs of This Multi-Agent Implementation

### 13.1 Advantages

1. **Clear layering**
   The three tiers — normal subagent, coordinator, swarm teammate — are not muddled together; each has its own responsibilities.

2. **Reuses the main execution kernel**
   Most agents ultimately still go through `runAgent()` / `query()`, avoiding multiple inference engines.

3. **Practical communication mechanisms**
   Through mailbox, resume, task notification, and task list, collaboration is built into a workable engineering system.

4. **Unified permission entry point**
   Teammates cannot silently bypass the permission system — they flow back to the leader.

5. **Clear task perspective**
   A team is not a pure chat bot group — it's a work queue with a task list.

### 13.2 Costs

1. **Very high system complexity**
   Multi-agent already spans the tool layer, task layer, UI layer, permission layer, and context layer.

2. **Many state surfaces**
   Transcript, task state, team file, mailbox, AppState, and permission queue can all participate in the same chain.

3. **High debugging cost**
   Issues can arise in any layer: spawn, resume, mailbox, inbox poller, or permission bridge.

4. **Many patterns**
   All called "agent," but subagent, worker, teammate, fork child, and coordinator have different semantics.

## 14. Chapter Summary

Multi-agent in Claude Code's source code is not an edge feature — it's a complete system capability.

From the source code we can see:

- `AgentTool` is the unified entry point
- `runAgent()` is the unified executor
- `coordinatorMode` transforms the main thread into a scheduler
- `spawnTeammate()` and the swarm directory make team collaboration an explicit entity
- `teammateMailbox`, `useInboxPoller`, `leaderPermissionBridge`, and the task list complete the inter-agent communication, permission, and collaboration plane

Therefore, a more accurate conclusion is:

**Claude Code doesn't just "support multi-agent" — it has already implemented a layered multi-agent runtime.**

Its three most important engineering characteristics are:

1. Subagent and swarm teammate coexist
2. Coordinator explicitly turns itself into an orchestrator via the prompt
3. Team collaboration relies not only on messages but also on tasks, permissions, and persistent state

This is why its multi-agent implementation clearly exceeds the level of "starting a few background subtasks."
