# Chapter 11: Session Storage / Transcript / Resume Persistence Mechanism

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter directly answers a core question:

**Claude Code's sessions are not "chat in memory and done" — they are implemented as an append-only transcript log system. `/resume` is not simply stuffing old message arrays back into the REPL — it goes through an entire recovery pipeline of "log loading -> metadata restoration -> chain repair -> UI re-assumption."**

This chapter focuses on explaining:

1. Where the transcript is actually stored
2. Why writing uses append-only JSONL
3. What content goes into the transcript and what doesn't
4. How metadata like title / tag / agent / mode / worktree / PR is persisted
5. The relationship between local transcript, remote ingress, and subagent sidechain
6. How `/resume` reconstructs a continuable conversation chain from logs

This chapter is based on these implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)
- [`src/utils/sessionStoragePortable.ts`](../src/utils/sessionStoragePortable.ts)
- [`src/utils/conversationRecovery.ts`](../src/utils/conversationRecovery.ts)
- [`src/screens/ResumeConversation.tsx`](../src/screens/ResumeConversation.tsx)
- [`src/services/api/sessionIngress.ts`](../src/services/api/sessionIngress.ts)

TL;DR:

Claude Code's session persistence is not a database snapshot model — it's the following layered structure:

```text
1. Main transcript
   - One .jsonl per session
   - user / assistant / attachment / system written append-only

2. Additional metadata entries
   - summary / custom-title / tag / agent-setting / mode / worktree-state / pr-link
   - Written into the same transcript, but restored separately by type

3. Subagent sidechain transcript
   - Independent .jsonl per agent
   - Used for fork / teammate / subagent recovery

4. Remote ingress replica
   - Remote append chain of the main transcript
   - Used for hydration and cross-process recovery

5. Resume recovery pipeline
   - Read JSONL
   - Fix chain issues caused by compact / snip / progress / parallel tool result
   - Restore metadata / fileHistory / contextCollapse / worktree / agent state
   - Finally hand back to REPL
```

In other words, this project splits "session state" into two layers:

- **Write layer as simple as possible**: append-only, no in-place modification
- **Restore layer handles complexity**: fill gaps, repair, and rebuild on read

## 2. Storage Model: Core Is Not a Message Array, But an Append-Only JSONL Event Stream

Related implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)

The most critical design in `sessionStorage.ts` is not "writing messages to a file" — it's **treating the transcript as an event stream log, not a mutable snapshot.**

### 2.1 What Counts as Transcript

The source code defines "what constitutes a transcript message" very clearly:

**Actual source code** ([`src/utils/sessionStorage.ts:139`](../src/utils/sessionStorage.ts#L139))

```typescript
export function isTranscriptMessage(entry: Entry): entry is TranscriptMessage {
  return (
    entry.type === 'user' ||
    entry.type === 'assistant' ||
    entry.type === 'attachment' ||
    entry.type === 'system'
  )
}
```

The corresponding comment also clarifies:

- `progress` is not a transcript message
- `progress` cannot enter the `parentUuid` main chain
- Older versions that mixed progress into the transcript would truncate the real conversation chain on recovery

This shows Claude Code's transcript design goal is clear:

- **Preserve messages that genuinely affect context reconstruction**
- **Exclude high-frequency UI state from the persistence layer**

### 2.2 The Transcript Path Is Not Fixed — It Changes with Session Switching

**Actual source code** ([`src/utils/sessionStorage.ts:202`](../src/utils/sessionStorage.ts#L202))

```typescript
export function getTranscriptPath(): string {
  const projectDir = getSessionProjectDir() ?? getProjectDir(getOriginalCwd())
  return join(projectDir, `${getSessionId()}.jsonl`)
}
```

**Actual source code** ([`src/utils/sessionStorage.ts:247`](../src/utils/sessionStorage.ts#L247))

```typescript
export function getAgentTranscriptPath(agentId: AgentId): string {
  const projectDir = getSessionProjectDir() ?? getProjectDir(getOriginalCwd())
  const sessionId = getSessionId()
  const subdir = agentTranscriptSubdirs.get(agentId)
  const base = subdir
    ? join(projectDir, sessionId, 'subagents', subdir)
    : join(projectDir, sessionId, 'subagents')
  return join(base, `agent-${agentId}.jsonl`)
}
```

There are at least three key points here:

1. **Main transcript is `sessionId.jsonl`**
2. **Subagent transcript is not mixed with the main chain — it's a separate sidechain file**
3. **Path resolution depends on `sessionProjectDir` and the current sessionId; the same session still lands in the correct directory after resume / branch / switch**

So it's not "writing a chat log file under the current directory" — it's a log storage layer with session routing capability.

## 3. Write Path: First Asynchronous Batch Append, Then Split by Type

Related implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)

### 3.1 The Underlying Writer Does Batch Flush

**Actual source code** ([`src/utils/sessionStorage.ts:634`](../src/utils/sessionStorage.ts#L634))

```typescript
private async appendToFile(filePath: string, data: string): Promise<void> {
  try {
    await fsAppendFile(filePath, data, { mode: 0o600 })
  } catch {
    await mkdir(dirname(filePath), { recursive: true, mode: 0o700 })
    await fsAppendFile(filePath, data, { mode: 0o600 })
  }
}
```

**Actual source code** ([`src/utils/sessionStorage.ts:645`](../src/utils/sessionStorage.ts#L645))

```typescript
private async drainWriteQueue(): Promise<void> {
  for (const [filePath, queue] of this.writeQueues) {
    const batch = queue.splice(0)
    let content = ''
    for (const { entry } of batch) {
      const line = jsonStringify(entry) + '\n'
      ...
      content += line
    }
    await this.appendToFile(filePath, content)
  }
}
```

This code shows:

- Session storage does not synchronously `writeFile` on each entry
- It first goes into an in-memory queue, then `drainWriteQueue()` flushes in batches
- File and directory permissions are explicitly set to `0600 / 0700`

This is a classic log system design:

- Simple appends
- Easy crash recovery
- No need to rewrite the entire transcript each time

### 3.2 `appendEntry()` Is the Real "Splitter"

`appendEntry()` is the main entry point of the entire persistence system. It decides where an entry should go:

- Write to main transcript
- Write to sidechain transcript
- Update metadata only
- Whether to also send to remote ingress synchronously

It can be rewritten as the following pseudocode:

```typescript
async function appendEntry(entry, sessionId) {
  if (current session file hasn't materialized yet) {
    pendingEntries.push(entry)
    return
  }

  if (entry is summary/title/tag/mode/worktree/pr-link metadata) {
    enqueueWrite(mainSessionFile, entry)
    return
  }

  if (entry.type === 'content-replacement') {
    target = entry.agentId ? agentSidechainFile : mainSessionFile
    enqueueWrite(target, entry)
    return
  }

  // Remaining entries are transcript messages
  target = entry.isSidechain ? agentSidechainFile : mainSessionFile

  if (target is a sidechain local file) {
    // Allow writing UUIDs that duplicate the main chain, ensuring fork context completeness
    enqueueWrite(target, entry)
    return
  }

  if (uuid hasn't been written before) {
    enqueueWrite(mainSessionFile, entry)
    messageSet.add(entry.uuid)
    persistToRemote(sessionId, entry)
  }
}
```

This design is critical because it solves two conflicting problems:

1. **The main transcript cannot write the same UUID twice**
   Otherwise resume would encounter duplicate chains and remote 409 conflicts
2. **Sidechain must allow inherited messages to appear again**
   Otherwise fork / subagent recovery would lose inherited parent context

The source code states this very plainly:

**Actual source code** ([`src/utils/sessionStorage.ts:1212`](../src/utils/sessionStorage.ts#L1212))

```typescript
const isAgentSidechain =
  entry.isSidechain && entry.agentId !== undefined
const targetFile = isAgentSidechain
  ? getAgentTranscriptPath(asAgentId(entry.agentId!))
  : sessionFile

const isNewUuid = !messageSet.has(entry.uuid)
if (isAgentSidechain || isNewUuid) {
  void this.enqueueWrite(targetFile, entry)

  if (!isAgentSidechain) {
    messageSet.add(entry.uuid)
    if (isTranscriptMessage(entry)) {
      await this.persistToRemote(sessionId, entry)
    }
  }
}
```

The conclusion is clear: **main chain deduplicates, sidechain preserves fidelity, remote only follows the main chain.**

## 4. Metadata Persistence: Not an Independent Database, But "Same Log Writing + Tail Re-Append"

Related implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)

Many projects put metadata like title, tag, mode, and PR association into a separate SQLite or JSON sidecar. Claude Code doesn't do this — it still writes back to the transcript, but adds a very important mechanism:

**Metadata is periodically re-appended to the tail of the transcript.**

### 4.1 Why Re-Append to the Tail

The source code comment explains why:

**Actual source code** ([`src/utils/sessionStorage.ts:686`](../src/utils/sessionStorage.ts#L686))

```typescript
/**
 * Re-append cached session metadata to the end of the transcript file.
 * This ensures metadata stays within the tail window that readLiteMetadata
 * reads during progressive loading.
 */
```

In other words, the system has two reading modes:

1. **Full recovery**
   Read the entire transcript content
2. **Lite list reading**
   Read only the head and tail windows to quickly display session list, title, tag, firstPrompt

If title / tag is written too early in the transcript, it will be "pushed out of the tail window" as the conversation grows longer, and the list page won't see it. So it must be repeatedly re-appended to EOF.

### 4.2 The Actual Logic of `reAppendSessionMetadata()`

It doesn't blindly rewrite the cache — it first absorbs updated values from the tail, then re-appends:

```typescript
function reAppendSessionMetadata(skipTitleRefresh = false) {
  tail = readFileTailSync(sessionFile)

  // First absorb new title/tag from tail modified by external SDK, to avoid local cache overwriting with old values
  refreshTitleAndTagFromTail(tail)

  append(last-prompt)
  append(custom-title)
  append(tag)
  append(agent-name)
  append(agent-color)
  append(agent-setting)
  append(mode)
  append(worktree-state)
  append(pr-link)
}
```

This mechanism has three layers of significance:

1. **Enables progressive session list loading to read key metadata quickly from the tail**
2. **Ensures sessions that haven't sent new messages after resume can still persist metadata on exit**
3. **Compatible with external SDK / other processes modifying title and tag**

### 4.3 Why Resume Needs a Dedicated `adoptResumedSessionFile()`

**Actual source code** ([`src/utils/sessionStorage.ts:1511`](../src/utils/sessionStorage.ts#L1511))

```typescript
export function adoptResumedSessionFile(): void {
  const project = getProject()
  project.sessionFile = getTranscriptPath()
  project.reAppendSessionMetadata(true)
}
```

This step specifically solves a very practical problem:

- User resumed an old session
- Changed the title or other metadata
- But exits without sending a new message

If `sessionFile` is still `null` at that point, the exit cleanup logic, though it has a cache, won't actually write to disk. `adoptResumedSessionFile()` immediately binds the "current persistence target" to the old transcript after resume, giving subsequent metadata re-appends a destination.

### 4.4 Metadata Restoration Is Not Re-parsing the UI, But Restoring Into Memory Cache

**Actual source code** ([`src/utils/sessionStorage.ts:2758`](../src/utils/sessionStorage.ts#L2758))

```typescript
export function restoreSessionMetadata(meta: {
  customTitle?: string
  tag?: string
  agentName?: string
  agentColor?: string
  agentSetting?: string
  mode?: 'coordinator' | 'normal'
  worktreeSession?: PersistedWorktreeSession | null
  prNumber?: number
  prUrl?: string
  prRepository?: string
}): void
```

It restores not "page state" but the current session cache in `Project`. The agent banner, mode, worktree, and metadata re-appending on exit all depend on this cache.

## 5. Transcript Is Not Just a Local File — There's Also a Remote Ingress Replica

Related implementations:

- [`src/services/api/sessionIngress.ts`](../src/services/api/sessionIngress.ts)
- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)

Claude Code's session persistence is not purely local. While the main transcript message is being appended locally, it can also be incrementally sent to a remote ingress.

### 5.1 Remote Is Not Uploading the Entire File, But an Append Chain

**Actual source code** ([`src/services/api/sessionIngress.ts:57`](../src/services/api/sessionIngress.ts#L57))

```typescript
async function appendSessionLogImpl(sessionId, entry, url, headers) {
  const lastUuid = lastUuidMap.get(sessionId)
  if (lastUuid) {
    requestHeaders['Last-Uuid'] = lastUuid
  }

  const response = await axios.put(url, entry, { ... })
}
```

This shows the remote protocol is not "upload the entire transcript file" — it's:

- PUT one entry at a time
- Uses `Last-Uuid` for optimistic concurrency control
- When the server returns 409, the client tries to absorb the server's latest UUID and retries

### 5.2 Remote Appends for the Same Session Must Be Serialized

**Actual source code** ([`src/services/api/sessionIngress.ts:24`](../src/services/api/sessionIngress.ts#L24))

```typescript
const sequentialAppendBySession = new Map(...)
```

The corresponding `getOrCreateSequentialAppend()` creates a sequential execution queue for each session to avoid concurrent writes to the same remote session causing chain head contention.

This is complementary to the local append-only design:

- Local allows high-frequency async batch appends
- Remote requires single-session sequential ordering

### 5.3 Resume/Hydrate Can Pull Remote Transcript Back to Local

**Actual source code** ([`src/utils/sessionStorage.ts:1587`](../src/utils/sessionStorage.ts#L1587))

```typescript
export async function hydrateRemoteSession(sessionId: string, ingressUrl: string) {
  const remoteLogs = (await sessionIngress.getSessionLogs(sessionId, ingressUrl)) || []
  const sessionFile = getTranscriptPathForSession(sessionId)
  const content = remoteLogs.map(e => jsonStringify(e) + '\n').join('')
  await writeFile(sessionFile, content, ...)
}
```

In other words, the remote ingress is not just a backup — it also serves as a hydrate source. Another variant, `hydrateFromCCRv2InternalEvents()`, even writes foreground transcript and subagent transcript separately back to local files.

Conclusion: **The local transcript is the primary runtime copy; the remote ingress is an incremental replica that can be re-imported.**

## 6. Fast Listing and Large File Loading: Read Layer Is Not Full Parse, But Layered Optimization

Related implementations:

- [`src/utils/sessionStoragePortable.ts`](../src/utils/sessionStoragePortable.ts)
- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)

### 6.1 Session List Doesn't Always Full-Parse the Transcript

`sessionStoragePortable.ts` explicitly provides a lite reader:

**Actual source code** ([`src/utils/sessionStoragePortable.ts:17`](../src/utils/sessionStoragePortable.ts#L17))

```typescript
export const LITE_READ_BUF_SIZE = 65536
```

It only reads the file's head and tail (64KB), extracting:

- first prompt
- custom title
- tag
- Other lightweight metadata for list display

`extractFirstPromptFromHead()` is also pragmatic:

- Skip `tool_result`
- Skip `isMeta`
- Skip compact summary
- Skip `<command-name>` wrapping and system auto-injected fragments

So the session list page doesn't work by "deserializing the entire conversation" — it works via **head/tail window + field extraction**.

### 6.2 Full Recovery of Large Transcripts Is Also Not Blind Full-File Read

**Actual source code** ([`src/utils/sessionStorage.ts:3511`](../src/utils/sessionStorage.ts#L3511))

```typescript
if (size > SKIP_PRECOMPACT_THRESHOLD) {
  const scan = await readTranscriptForLoad(filePath, size)
  buf = scan.postBoundaryBuf
  hasPreservedSegment = scan.hasPreservedSegment
  if (scan.boundaryStartOffset > 0) {
    metadataLines = await scanPreBoundaryMetadata(filePath, scan.boundaryStartOffset)
  }
}
```

The meaning here is:

- If the transcript is large, don't hand the entire file to the JSON parser
- First scan for compact boundary at the file level
- Cut out as much discarded history before the boundary as possible
- But separately retain metadata lines before the boundary to avoid losing title / mode / agent-setting

`readTranscriptForLoad()` itself is specifically designed for this:

**Actual source code** ([`src/utils/sessionStoragePortable.ts:717`](../src/utils/sessionStoragePortable.ts#L717))

```typescript
export async function readTranscriptForLoad(filePath, fileSize): Promise<{
  boundaryStartOffset: number
  postBoundaryBuf: Buffer
  hasPreservedSegment: boolean
}>
```

This shows the recovery layer is no longer as simple as "read file -> parseJSONL" — it's:

```typescript
if (file is large) {
  buf = only read the portion still valid after the boundary
  metadata = re-scan session-scoped metadata from before the boundary
} else {
  buf = readFile(filePath)
}
```

## 7. Full Recovery: `loadTranscriptFile()` Is Not Reading a Log — It's Rebuilding a Conversation Graph

Related implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)

`loadTranscriptFile()` is the most core function in this chapter. It doesn't simply "parse JSONL into an array" — it does the following:

1. Split entries by type into different Maps
2. Bridge old-version progress chains
3. Apply compact / preserved segment / snip fixes
4. Collect file history, attribution, content replacement, context collapse
5. Recalculate leaf UUID

It can be summarized as the following pseudocode:

```typescript
async function loadTranscriptFile(filePath) {
  messages = new Map()
  summaries = new Map()
  titles = new Map()
  tags = new Map()
  agentSettings = new Map()
  contentReplacements = new Map()
  contextCollapseCommits = []

  buf = maybeReadPostCompactRegionOnly(filePath)
  metadataLines = maybeScanPreBoundaryMetadata(filePath)

  for (line of metadataLines) {
    restoreSessionScopedMaps(line)
  }

  progressBridge = new Map()
  for (entry of parseJSONL(buf)) {
    if (entry is legacy progress) {
      progressBridge[entry.uuid] = resolvedParent
      continue
    }

    if (entry is transcript message) {
      if (entry.parentUuid points to legacy progress) {
        entry.parentUuid = progressBridge[parent]
      }
      messages.set(entry.uuid, entry)
      continue
    }

    switch (entry.type) {
      case 'summary': ...
      case 'custom-title': ...
      case 'tag': ...
      case 'agent-setting': ...
      case 'content-replacement': ...
      case 'marble-origami-commit': ...
    }
  }

  applyPreservedSegmentRelinks(messages)
  applySnipRemovals(messages)
  leafUuids = recomputeLeaves(messages)

  return allMapsAndLeafs
}
```

This shows that Claude Code's transcript loader is actually rebuilding a "conversation graph," not restoring a simple chat record.

## 8. Resume Repair: Why Further Chain Remediation Is Needed After Reading

Related implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)
- [`src/utils/conversationRecovery.ts`](../src/utils/conversationRecovery.ts)

The advantage of append-only logs is simple writing, but the cost is that the read side must be more robust. Claude Code adds several layers of recovery repair logic for this.

### 8.1 `applySnipRemovals()` Deletes Messages and Reconnects parentUuid

**Actual source code** ([`src/utils/sessionStorage.ts:1982`](../src/utils/sessionStorage.ts#L1982))

It handles this problem:

- A segment of messages has been snipped out
- But surviving messages' `parentUuid` still points to a message in the deleted range

If you only delete without reconnecting, the recovery chain breaks. This function walks forward along the deleted message's own `parentUuid` until it finds an ancestor that still exists, then re-hangs the surviving message.

This is not something ordinary chat products do — it shows the transcript here is a repairable graph structure, not a static array.

### 8.2 `buildConversationChain()` Is Not Simple Backtracking — It Also Recovers Parallel Tool Results

**Actual source code** ([`src/utils/sessionStorage.ts:2069`](../src/utils/sessionStorage.ts#L2069))

```typescript
export function buildConversationChain(messages, leafMessage) {
  ...
  transcript.reverse()
  return recoverOrphanedParallelToolResults(messages, transcript, seen)
}
```

The subsequent `recoverOrphanedParallelToolResults()` specifically handles a very tricky situation:

- Assistant outputs multiple parallel tool_use at once
- During streaming, these blocks get split into multiple assistant messages
- tool_results are attached to different assistant blocks
- Simply backtracing along a single parent chain only preserves one branch

So recovery must do an additional "sibling node completion + orphaned tool_result recovery" post-processing.

This is also why the resume logic can't just rely on single-chain `parentUuid` traversal.

### 8.3 `checkResumeConsistency()` Also Performs Recovery Consistency Audit

**Actual source code** ([`src/utils/sessionStorage.ts:2224`](../src/utils/sessionStorage.ts#L2224))

It compares the `messageCount` recorded in the latest checkpoint with the length of the currently recovered chain, specifically to monitor whether the "conversation as written" and the "conversation as read after recovery" have drifted.

This shows the author treats resume drift as an online risk, not a purely theoretical problem.

## 9. `/resume` Main Chain: `conversationRecovery` Turns "Logs" Back Into a "Continuable Message Stream"

Related implementations:

- [`src/utils/conversationRecovery.ts`](../src/utils/conversationRecovery.ts)

`loadConversationForResume()` is the resume entry point, regardless of source:

- Most recent session
- Specified sessionId
- Specified `.jsonl` path
- Already loaded `LogOption`

All converge into the same set of recovery logic.

### 9.1 It Doesn't Do Single-Step Reading — It's a Full Recovery Orchestration

It can be rewritten as the following pseudocode:

```typescript
async function loadConversationForResume(source) {
  log = resolveSourceToLogOrJsonl(source)

  if (log is lite log) {
    log = loadFullLog(log)
  }

  sessionId = resolveSessionId(log)
  copyPlanForResume(log, sessionId)
  copyFileHistoryForResume(log)

  messages = log.messages
  checkResumeConsistency(messages)

  restoreSkillStateFromMessages(messages)

  deserialized = deserializeMessagesWithInterruptDetection(messages)
  messages = deserialized.messages

  hookMessages = processSessionStartHooks('resume', { sessionId })
  messages.push(...hookMessages)

  return {
    messages,
    turnInterruptionState,
    fileHistorySnapshots,
    attributionSnapshots,
    contentReplacements,
    contextCollapseCommits,
    session metadata...
  }
}
```

There are several easily overlooked but important points here:

1. **Restores invoked skills state before resume**
   Otherwise, the next compact might discard previous skill state
2. **Filters unresolved tool uses, orphaned thinking-only messages, pure whitespace assistant**
   This ensures the recovered transcript is still valid for the API
3. **Detects interrupted turns and injects `Continue from where you left off.` when needed**
   This turns an "interrupted old session" back into a "continuable current session"
4. **Re-runs session start hooks**
   This shows resume is not a purely static replay — it's a new runtime takeover

## 10. UI Resume: `ResumeConversation` Is What Actually Connects the Recovery Result Back to REPL

Related implementations:

- [`src/screens/ResumeConversation.tsx`](../src/screens/ResumeConversation.tsx)

`ResumeConversation.tsx` doesn't just call `loadConversationForResume()` and call it done — it's responsible for reconnecting the "recovered logical state" back to the current process.

The core flow can be summarized as:

```typescript
result = await loadConversationForResume(log)

if (result.sessionId && !forkSession) {
  switchSession(result.sessionId)
  renameRecordingForSession()
  resetSessionFilePointer()
  restoreCostStateForSession(result.sessionId)
}

restoreAgentFromSession(...)
restoreSessionMetadata(result)
restoreWorktreeForResume(result.worktreeSession)

if (result.sessionId) {
  adoptResumedSessionFile()
}

restoreContextCollapse(...)

render(<REPL initialMessages={result.messages} ... />)
```

This logic shows that resume truly restores not just messages:

- sessionId
- asciicast recording filename
- cost tracker
- agent identity
- session metadata cache
- worktree state
- context collapse persisted state
- Final REPL initial message set

So `/resume` is essentially a **runtime state takeover**, not "opening an old transcript to look at it."

## 11. Technical Conclusion: The Write Path Is Deliberately Simple; All Complexity Is Pushed to the Recovery Path

The technical orientation of this implementation is very clear:

### 11.1 Advantages

- Simple writing, append-only, easier to preserve evidence after crash
- Transcript, metadata, subagent, remote ingress can sync incrementally
- Large files have lite reader and pre-compact skip, not requiring full parse every time
- Resume has strong compatibility, can fix old progress, snip, parallel tool result, interrupted turn

### 11.2 Costs

- Read path is significantly more complex than write path
- Transcript is no longer a linear message array but a graph structure with repair rules
- Compact / preserved segment / sidechain / content replacement / context collapse all make the recovery chain harder to maintain

### 11.3 The Most Critical Judgment

Claude Code's Session Storage is not a "local chat history file" — it's:

**A session log system using JSONL as the underlying medium, supporting metadata tail re-appending, sidechains, remote ingress, recovery repair, and runtime takeover.**

This is also why `sessionStorage.ts` is very large. It doesn't serve a single IO function — it's the entire long-term state foundation of the agent runtime.
