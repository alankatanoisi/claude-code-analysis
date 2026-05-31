# Chapter 9: Prompt Management Mechanism and Implementation Details

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter directly answers one core question:

**Claude Code's prompt is not a fixed string, but a layered, cacheable, overridable, observable prompt management system.**

This chapter primarily analyzes four things:

1. Where the default system prompt actually comes from
2. How custom prompts, agent prompts, and append prompts override and stack
3. Which context items are not actually in `prompts.ts`, but are injected separately at runtime
4. How "specialized prompts" like compact, session memory, and memory extraction coexist with the main prompt system

This chapter is primarily based on these implementations:

- [`src/constants/prompts.ts`](../src/constants/prompts.ts)
- [`src/utils/systemPrompt.ts`](../src/utils/systemPrompt.ts)
- [`src/screens/REPL.tsx`](../src/screens/REPL.tsx)
- [`src/utils/queryContext.ts`](../src/utils/queryContext.ts)
- [`src/context.ts`](../src/context.ts)
- [`src/constants/systemPromptSections.ts`](../src/constants/systemPromptSections.ts)
- [`src/main.tsx`](../src/main.tsx)
- [`src/services/compact/prompt.ts`](../src/services/compact/prompt.ts)
- [`src/services/SessionMemory/prompts.ts`](../src/services/SessionMemory/prompts.ts)
- [`src/services/extractMemories/prompts.ts`](../src/services/extractMemories/prompts.ts)
- [`src/services/api/dumpPrompts.ts`](../src/services/api/dumpPrompts.ts)

TL;DR:

This project does not structure prompt management as "a system prompt file + some if else statements", but splits it into 6 layers:

```text
1. Default main system prompt
   src/constants/prompts.ts

2. Effective system prompt assembler
   src/utils/systemPrompt.ts
   - override
   - coordinator
   - agent
   - custom
   - append

3. Runtime context injection
   src/context.ts
   - CLAUDE.md
   - currentDate
   - git status
   - cache breaker

4. Startup additional instruction entry
   src/main.tsx
   - --system-prompt
   - --append-system-prompt
   - systemPromptFile / appendSystemPromptFile
   - proactive / chrome / teammate addendum

5. Prompt cache and invalidation management
   src/constants/systemPromptSections.ts
   - section cache
   - dynamic boundary
   - cache break

6. Specialized prompt family
   compact / session memory / extract memories / hooks / insights etc.
```

So what is actually managed here is not "prompt text", but:

- Which prompts belong to the main loop
- Which prompts belong to subtasks
- Which content should be cached long-term
- Which content must be recalculated each round
- Which content allows external override
- Which content can be exported and audited

## 2. Overall Design: This Is Not a Single Prompt, But a Prompt Runtime

Related implementations:

- [`src/constants/prompts.ts`](../src/constants/prompts.ts)
- [`src/utils/systemPrompt.ts`](../src/utils/systemPrompt.ts)
- [`src/context.ts`](../src/context.ts)

If you only look at the file name, it's easy to assume that `src/constants/prompts.ts` is the "complete prompt".

In reality, it is not.

The general flow before actually sending to the model is roughly as follows:

```text
Startup parameters / mode / agent / mcp / settings
                |
                v
getSystemPrompt() generates default system prompt array
                |
                v
buildEffectiveSystemPrompt() handles priority overrides
                |
                +---- userContext
                |       - CLAUDE.md
                |       - currentDate
                |
                +---- systemContext
                        - git status
                        - cacheBreaker
                |
                v
Query / REPL / Compact / Subagent call API
```

In other words, the "prompt" in this project is divided into at least three categories:

1. `system prompt`
   Defines the agent's identity, rules, tool usage, and session-level policies.
2. `userContext / systemContext`
   Additional context, not hardcoded into the main template of `prompts.ts`.
3. `task-specific prompts`
   Specifically used for background tasks such as compact, memory extraction, session memory updates, etc.

This split is very important because it shows that Claude Code does not cram all rules into one super-long system prompt, but separately governs **standing rules**, **session context**, and **specialized task instructions**.

## 3. The Source of the Default System Prompt: `getSystemPrompt()`

Related implementations:

- [`src/constants/prompts.ts`](../src/constants/prompts.ts)

### 3.1 It Returns Not a String, But an Array of Strings

The signature of `getSystemPrompt()` is:

```typescript
export async function getSystemPrompt(
  tools: Tools,
  model: string,
  additionalWorkingDirectories?: string[],
  mcpClients?: MCPServerConnection[],
): Promise<string[]>
```

This fact alone reveals the design intent:

- The system prompt is split into multiple sections
- Each section can be independently cached, plugged/unplugged, and token-counted
- Section-level cache boundaries and dynamic invalidation are possible later

### 3.2 Main Structure: Static Segments + Dynamic Segments

The most important return structure of `getSystemPrompt()` is as follows:

```typescript
return [
  getSimpleIntroSection(outputStyleConfig),
  getSimpleSystemSection(),
  outputStyleConfig === null ||
  outputStyleConfig.keepCodingInstructions === true
    ? getSimpleDoingTasksSection()
    : null,
  getActionsSection(),
  getUsingYourToolsSection(enabledTools),
  getSimpleToneAndStyleSection(),
  getOutputEfficiencySection(),
  ...(shouldUseGlobalCacheScope() ? [SYSTEM_PROMPT_DYNAMIC_BOUNDARY] : []),
  ...resolvedDynamicSections,
].filter(s => s !== null)
```

This code is very important because it reveals the basic engineering strategy of the main prompt:

- The first half is the **static backbone**
- A `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` is inserted in the middle
- The second half is **dynamic sections**

In other words, Claude Code does not write prompts only at the "content level", but designs prompts at the "cache level".

### 3.3 What the Static Backbone of the Default Prompt Looks Like

For example, the opening identity segment `getSimpleIntroSection()` returns:

```typescript
return `
You are an interactive agent that helps users ...

${CYBER_RISK_INSTRUCTION}
IMPORTANT: You must NEVER generate or guess URLs for the user unless ...
`
```

`getSimpleSystemSection()` then appends a set of basic rules, such as:

- How text output to the user is presented
- Tool calls rejected cannot be retried identically
- External tool results may contain prompt injection
- Hooks feedback should be treated as user input
- Context will be automatically compacted

`getSimpleDoingTasksSection()` contains more coding-agent-oriented working rules, such as:

- Don't over-engineer
- Don't add extra comments and types
- Read files before modifying code
- Diagnose failures before switching strategies
- Avoid introducing security vulnerabilities

In other words, the default system prompt is not a short identity declaration, but a very complete "execution policy package".

### 3.4 What Are the Dynamic Segments

`resolvedDynamicSections` comes from these sections:

```typescript
const dynamicSections = [
  systemPromptSection('session_guidance', ...),
  systemPromptSection('memory', ...),
  systemPromptSection('ant_model_override', ...),
  systemPromptSection('env_info_simple', ...),
  systemPromptSection('language', ...),
  systemPromptSection('output_style', ...),
  DANGEROUS_uncachedSystemPromptSection('mcp_instructions', ...),
  systemPromptSection('scratchpad', ...),
  systemPromptSection('frc', ...),
  systemPromptSection('summarize_tool_results', ...),
]
```

Unlike the static backbone, these sections are more dependent on runtime state:

- Currently enabled tools
- Language preference in current settings
- Current model
- Current MCP server instructions
- Current memory / scratchpad / output style

This shows that the prompt system does not "read a template and replace variables", but "assembles a set of sections at runtime".

## 4. The Effective System Prompt Assembler: `buildEffectiveSystemPrompt()`

Related implementations:

- [`src/utils/systemPrompt.ts`](../src/utils/systemPrompt.ts)

What really determines "what the final system prompt sent to the model looks like" is not `getSystemPrompt()`, but `buildEffectiveSystemPrompt()`.

Its comment already states the priority clearly:

```typescript
/**
 * 0. Override system prompt
 * 1. Coordinator system prompt
 * 2. Agent system prompt
 * 3. Custom system prompt
 * 4. Default system prompt
 * Plus appendSystemPrompt is always added at the end
 */
```

### 4.1 Override Priority

It can be translated into the following pseudocode:

```text
if overrideSystemPrompt:
    final = [overrideSystemPrompt]
else if coordinator mode:
    final = [coordinatorPrompt] + [appendPrompt?]
else:
    base =
      agentPrompt
      or customSystemPrompt
      or defaultSystemPrompt

    if proactive mode and agentPrompt exists:
        final = defaultSystemPrompt + ["# Custom Agent Instructions" + agentPrompt]
    else:
        final = [base]

    if appendSystemPrompt:
        final += [appendSystemPrompt]
```

Two points are most noteworthy here:

1. `customSystemPrompt` **does not append to the default prompt**, but directly replaces it.
2. `appendSystemPrompt` is basically always appended at the end, regardless of the preceding source.

These two rules determine that Claude Code's engineering distinction between "override" and "append" is very strict.

### 4.2 Actual Function

Below is the original function with the core logic:

```typescript
export function buildEffectiveSystemPrompt({
  mainThreadAgentDefinition,
  toolUseContext,
  customSystemPrompt,
  defaultSystemPrompt,
  appendSystemPrompt,
  overrideSystemPrompt,
}): SystemPrompt {
  if (overrideSystemPrompt) {
    return asSystemPrompt([overrideSystemPrompt])
  }

  if (feature('COORDINATOR_MODE') &&
      isEnvTruthy(process.env.CLAUDE_CODE_COORDINATOR_MODE) &&
      !mainThreadAgentDefinition) {
    return asSystemPrompt([
      getCoordinatorSystemPrompt(),
      ...(appendSystemPrompt ? [appendSystemPrompt] : []),
    ])
  }

  const agentSystemPrompt = mainThreadAgentDefinition
    ? mainThreadAgentDefinition.getSystemPrompt(...)
    : undefined

  if (agentSystemPrompt && proactiveActive) {
    return asSystemPrompt([
      ...defaultSystemPrompt,
      `\n# Custom Agent Instructions\n${agentSystemPrompt}`,
      ...(appendSystemPrompt ? [appendSystemPrompt] : []),
    ])
  }

  return asSystemPrompt([
    ...(agentSystemPrompt
      ? [agentSystemPrompt]
      : customSystemPrompt
        ? [customSystemPrompt]
        : defaultSystemPrompt),
    ...(appendSystemPrompt ? [appendSystemPrompt] : []),
  ])
}
```

This shows that in normal mode, the agent prompt can even **replace the default prompt**, rather than "adding some agent settings on top of the default prompt". This is a very strong role switch.

## 5. Context Injection Outside the Main Prompt: `getUserContext()` and `getSystemContext()`

Related implementations:

- [`src/context.ts`](../src/context.ts)
- [`src/utils/queryContext.ts`](../src/utils/queryContext.ts)

A very easily overlooked point in prompt management is:

**Some content is not a system prompt section, but a separate context.**

### 5.1 `getUserContext()`: User-Level Context

`getUserContext()` primarily returns two things:

1. `claudeMd`
2. `currentDate`

The source code logic is roughly:

```typescript
const claudeMd = shouldDisableClaudeMd
  ? null
  : getClaudeMds(filterInjectedMemoryFiles(await getMemoryFiles()))

return {
  ...(claudeMd && { claudeMd }),
  currentDate: `Today's date is ${getLocalISODate()}.`,
}
```

This shows:

- `CLAUDE.md` is not a hardcoded template in `prompts.ts`
- It is scanned, read, and concatenated at runtime and injected as user context
- The date is also not part of the main prompt text, but an independent field

Therefore, studying Claude Code's prompt cannot be limited to `constants/prompts.ts`; `context.ts` must also be considered.

### 5.2 `getSystemContext()`: System-Level Context

`getSystemContext()` primarily appends:

- Git status snapshot
- Cache breaker injection

Core logic:

```typescript
return {
  ...(gitStatus && { gitStatus }),
  ...(feature('BREAK_CACHE_COMMAND') && injection
    ? { cacheBreaker: `[CACHE_BREAKER: ${injection}]` }
    : {}),
}
```

This shows that the responsibility of system context is not "identity description", but providing **system state that must be known for this round of reasoning**.

In particular, `gitStatus` is very much like a "pre-context summary of the environment for the coding agent".

## 6. Runtime Entry Points: How External Prompts Enter the System

Related implementations:

- [`src/main.tsx`](../src/main.tsx)

This part determines why Claude Code is not just "built-in prompts", but an "externally orchestratable prompt runtime".

### 6.1 CLI Explicit Entry Points

`main.tsx` reads:

- `--system-prompt`
- `--system-prompt-file`
- `--append-system-prompt`
- `--append-system-prompt-file`

For example:

```typescript
let appendSystemPrompt = options.appendSystemPrompt;
if (options.appendSystemPromptFile) {
  if (options.appendSystemPrompt) {
    process.stderr.write(chalk.red('Error: Cannot use both ...'));
    process.exit(1);
  }
  const filePath = resolve(options.appendSystemPromptFile);
  appendSystemPrompt = readFileSync(filePath, 'utf8');
}
```

This means users or upper-layer products can:

- Completely replace the default system prompt
- Or only append a layer of policy at the end of the default prompt

These are two completely different levels of control.

### 6.2 Startup Automatic Addendum

Besides CLI parameters, the system also continues to add content to `appendSystemPrompt` during startup:

- tmux teammate addendum
- Claude in Chrome system prompt
- Claude in Chrome skill hint
- proactive mode prompt
- assistant addendum
- teammate custom agent instructions

For example, proactive mode directly appends:

```typescript
const proactivePrompt = `
# Proactive Mode

You are in proactive mode. Take initiative — explore, act, and make progress without waiting for instructions.

Start by briefly greeting the user.
...`
appendSystemPrompt = appendSystemPrompt
  ? `${appendSystemPrompt}\n\n${proactivePrompt}`
  : proactivePrompt
```

So `appendSystemPrompt` is not just "something the user occasionally manually adds", but a formal **appended instruction bus**.

## 7. Prompt Cache Engineering: Why Sections and Why Boundaries

Related implementations:

- [`src/constants/systemPromptSections.ts`](../src/constants/systemPromptSections.ts)
- [`src/constants/prompts.ts`](../src/constants/prompts.ts)

The most engineering-flavored aspect of this implementation is that it treats the prompt as a cache-managed object.

### 7.1 `systemPromptSection()`: Cacheable Section

```typescript
export function systemPromptSection(
  name: string,
  compute: ComputeFn,
): SystemPromptSection {
  return { name, compute, cacheBreak: false }
}
```

### 7.2 `DANGEROUS_uncachedSystemPromptSection()`: Explicitly Declares Cache Break

```typescript
export function DANGEROUS_uncachedSystemPromptSection(
  name: string,
  compute: ComputeFn,
  _reason: string,
): SystemPromptSection {
  return { name, compute, cacheBreak: true }
}
```

The meaning of this interface design is very direct:

- Default sections should all be cached
- If you want a certain prompt segment to be recalculated every round, you must explicitly declare it as "dangerous operation"

This is a very clear prompt cache discipline.

### 7.3 Resolution Logic

```typescript
export async function resolveSystemPromptSections(
  sections: SystemPromptSection[],
): Promise<(string | null)[]> {
  const cache = getSystemPromptSectionCache()

  return Promise.all(
    sections.map(async s => {
      if (!s.cacheBreak && cache.has(s.name)) {
        return cache.get(s.name) ?? null
      }
      const value = await s.compute()
      setSystemPromptSectionCacheEntry(s.name, value)
      return value
    }),
  )
}
```

In other words, what is cached here is the **section result**, not the entire large prompt string.

### 7.4 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY`

`prompts.ts` specifically defines:

```typescript
export const SYSTEM_PROMPT_DYNAMIC_BOUNDARY =
  '__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__'
```

Its purpose is not for the model to see, but for the caching system:

- Content before the boundary should remain as stable as possible
- Content after the boundary allows more session-level variation

This shows that Claude Code treats prompt prefix cache as a first-class engineering concern.

### 7.5 When Invalidation Occurs

`clearSystemPromptSections()` is called on paths like `/clear`, `/compact`, and worktree switching.

This indicates that the prompt cache is not permanent, but tied to "session lifecycle events":

- clear conversation
- compact conversation
- enter / exit worktree
- resume / restore session

## 8. How the Prompt Is Actually Assembled in the Main Session

Related implementations:

- [`src/screens/REPL.tsx`](../src/screens/REPL.tsx)
- [`src/commands/compact/compact.ts`](../src/commands/compact/compact.ts)
- [`src/utils/queryContext.ts`](../src/utils/queryContext.ts)

### 8.1 REPL Main Path

In REPL, you can see this critical chain:

```typescript
const [defaultSystemPrompt, userContext, systemContext] = await Promise.all([
  getSystemPrompt(...),
  getUserContext(),
  getSystemContext(),
])
const systemPrompt = buildEffectiveSystemPrompt({
  mainThreadAgentDefinition,
  toolUseContext,
  customSystemPrompt,
  defaultSystemPrompt,
  appendSystemPrompt
})
toolUseContext.renderedSystemPrompt = systemPrompt;
```

This is very important:

- The default prompt and user/system context are fetched in parallel
- The final system prompt is attached to `toolUseContext.renderedSystemPrompt`
- This field can later be reused by fork / subagent / resume logic

In other words, the prompt is not just "assembled temporarily before sending", but is a piece of state in the runtime that is persistently referenced.

### 8.2 The Compact Path Re-fetches a Cache-Safe Prompt

`/compact` does not directly use the current interface's prompt text for summarization; instead, it recalculates:

```typescript
const defaultSysPrompt = await getSystemPrompt(...)
const systemPrompt = buildEffectiveSystemPrompt({
  mainThreadAgentDefinition: undefined,
  toolUseContext: context,
  customSystemPrompt: context.options.customSystemPrompt,
  defaultSystemPrompt: defaultSysPrompt,
  appendSystemPrompt: context.options.appendSystemPrompt,
})
```

This shows that compact itself also depends on the prompt system, and it needs a **prompt prefix suitable for shared cache keys**.

### 8.3 Non-Interactive / Side Questions Can Also Rebuild the Prompt

[`src/utils/queryContext.ts`](../src/utils/queryContext.ts) also provides `fetchSystemPromptParts()` and `buildSideQuestionFallbackParams()`, showing:

- The prompt construction logic is extracted into a shared helper
- Even for side questions / print / SDK resume, it can reconstruct a prompt prefix consistent with the main session as much as possible

So here, prompt management is no longer UI layer logic, but part of the query infrastructure.

## 9. The Specialized Prompt Family: What Other Prompts Exist Beyond the Main Prompt

Related implementations:

- [`src/services/compact/prompt.ts`](../src/services/compact/prompt.ts)
- [`src/services/SessionMemory/prompts.ts`](../src/services/SessionMemory/prompts.ts)
- [`src/services/extractMemories/prompts.ts`](../src/services/extractMemories/prompts.ts)

Beyond the main session prompt, this project has many "specialized prompts".

### 9.1 Compact Prompt: Strong Constraints, No Tools, Only Produce Summaries

The compact prompt starts with hard constraints:

```typescript
const NO_TOOLS_PREAMBLE = `CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.
`
```

The style of this type of prompt is completely different from the main system prompt.

It does not define a long-term identity, but strongly constrains the output protocol in a single task:

- Forbid tools
- Restrict format
- Restrict turns
- Enforce summary structure

In other words, "prompt engineering" in Claude Code does not only serve the main agent, but also serves background operation protocols.

### 9.2 Session Memory Prompt: Only Use the Edit Tool to Update Notes

The default update prompt in `SessionMemory/prompts.ts` is also typical:

```typescript
Your ONLY task is to use the Edit tool to update the notes file, then stop.
Do not call any other tools.
...
- NEVER modify, delete, or add section headers
- NEVER modify or delete the italic _section description_ lines
- ONLY update the actual content that appears BELOW ...
```

This shows that session memory update is not "free-form summarization", but "a structured document maintenance task with template constraints".

### 9.3 Memory Extraction Prompt: Restricted Tool Set and Round Strategy

`extractMemories/prompts.ts` is not simply "help me extract memories", but clearly restricts:

- Available tools are only Read / Grep / Glob / Read-only Bash / Edit / Write
- MCP, Agent, and writable Bash are not allowed
- Must read in parallel first, then write in parallel
- Can only use the most recent messages
- Must not read source code again to verify

This means the background memory agent's behavior is not free-form model improvisation, but is written by the prompt into a lightweight protocol.

## 10. Observability: This Project Can Export Prompts for Inspection

Related implementations:

- [`src/services/api/dumpPrompts.ts`](../src/services/api/dumpPrompts.ts)
- [`src/commands/context/context-noninteractive.ts`](../src/commands/context/context-noninteractive.ts)
- [`src/utils/analyzeContext.ts`](../src/utils/analyzeContext.ts)

### 10.1 `dump-prompts`: Write API Requests to JSONL

`createDumpPromptsFetch()` intercepts requests and writes:

- init data
- system update
- user messages
- responses

To:

```text
~/.claude/dump-prompts/<session-or-agent-id>.jsonl
```

This shows that prompts are not just internal implicit state, but can be debugged, reviewed, and audited.

### 10.2 `/context` Can Count System Prompt Section Tokens

`analyzeContext.ts` splits the effective system prompt into named entries:

```typescript
const namedEntries = [
  ...effectiveSystemPrompt
    .filter(content => content.length > 0 &&
      content !== SYSTEM_PROMPT_DYNAMIC_BOUNDARY)
    .map(content => ({ name: extractSectionName(content), content })),
  ...Object.entries(systemContext)
    .filter(([, content]) => content.length > 0)
    .map(([name, content]) => ({ name, content })),
]
```

Then calculates tokens per segment.

This shows that Claude Code's prompt system has a very mature "operations perspective":

- Not only concerned with whether the prompt is correct
- But also how many tokens the prompt consumes
- Which segment is the most expensive
- Which segments should continue to be cached

## 11. Advantages and Costs of This Prompt Management Implementation

### 11.1 Advantages

1. **Composable**
   Default prompts, agent prompts, append prompts, userContext, systemContext, and specialized prompts can evolve in parallel.

2. **Cacheable**
   Section-based design + boundary gives prompt prefix cache an engineering handle.

3. **Extensible**
   New features don't require modifying a super-long string; only need to add a section or addendum.

4. **Debuggable**
   Through `dump-prompts`, `/context`, and token analysis, the real cost of prompts can be seen.

5. **Protocolizable**
   Compact, memory update, and memory extraction are all made into single-task protocols that are hard to deviate from.

### 11.2 Costs

1. **High learning curve**
   Reading only `prompts.ts` leads to incorrect conclusions; `systemPrompt.ts`, `context.ts`, and `main.tsx` must all be considered together.

2. **Complex override relationships**
   The combinations of `override`, `custom`, `agent`, `append`, `proactive`, and `coordinator` are already quite convoluted.

3. **Debugging difficulty shifted forward**
   Prompt issues are not necessarily template problems; they could be context injection, section cache, append addendum, or mode switching issues.

4. **Behavior depends on mode**
   The same system in REPL, compact, subagent, and SDK side-question modes will not have exactly the same prompt form.

## 12. Chapter Summary

If you only understand Claude Code's prompt management as "a big system prompt in `prompts.ts`", you will miss the most critical engineering part.

A more accurate statement is:

- `src/constants/prompts.ts` is responsible for defining the default main system prompt section collection
- `src/utils/systemPrompt.ts` is responsible for final priority composition
- `src/context.ts` is responsible for injecting runtime context
- `src/main.tsx` is responsible for integrating CLI and feature addendum
- `src/constants/systemPromptSections.ts` is responsible for caching and invalidation
- Multiple `services/*/prompts.ts` are responsible for specialized task prompt protocols

Therefore, Claude Code's prompt is not a single file, but a runtime.

This is also why it can simultaneously achieve:

- Main session sustainable operation
- Subtasks can switch prompt protocols
- Context cost is controllable
- Prompts can be exported, cached, and audited

From an engineering perspective, this implementation is no longer "writing prompts", but doing **prompt orchestration**.
