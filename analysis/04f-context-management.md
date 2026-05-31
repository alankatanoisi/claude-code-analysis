# Chapter 8: Context Management Mechanism

[Back to Table of Contents](../README.md)

---

## 1. Chapter Guide

In long-lived conversations and automation tasks, the LLM's context window is always a scarce resource. Claude Code does not simply employ a brute-force "discard history beyond the truncation point" approach; instead, it constructs a comprehensive set of monitoring, prediction, and auto-compact mechanisms.

This chapter delves into how the system dynamically calculates context consumption, how it triggers auto-compaction at the right moment, and how it preserves critical state during compaction while performing self-fusing and degradation in extreme cases (such as Prompt Too Long deadlock).

---

## 2. Context Quota Allocation and Baseline

### 2.1 Dynamic Context Window Boundary

The system does not open the entire model context window for the Agent to freely write into; instead, it performs strict reservation deductions.

**Actual source code** ([`src/utils/context.ts:18`](../src/utils/context.ts) and [`src/services/compact/autoCompact.ts:33`](../src/services/compact/autoCompact.ts)):

```typescript
// Default context window set to 200k (Claude 3 series default)
export const MODEL_CONTEXT_WINDOW_DEFAULT = 200_000

// For models supporting [1m] or feature-enabled models, use million-level context
export function has1mContext(model: string): boolean {
 return /\[1m\]/i.test(model)
}

// src/services/compact/autoCompact.ts
// Maximum output tokens reserved for the Summary API
const MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000

// Calculate effective available window: total window - tokens reserved for summary
export function getEffectiveContextWindowSize(model: string): number {
 const reservedTokensForSummary = Math.min(
 getMaxOutputTokensForModel(model),
 MAX_OUTPUT_TOKENS_FOR_SUMMARY,
)
 let contextWindow = getContextWindowForModel(model)

 // Support environment variable hard override
 const autoCompactWindow = process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW
 //...
 return contextWindow - reservedTokensForSummary
}
```

**Design highlights**:
To ensure that when the model needs to trigger auto-compaction, the API still has enough room to accommodate the original conversation history and the prompt for generating the summary, the system reserves up to 20k tokens of budget space (`MAX_OUTPUT_TOKENS_FOR_SUMMARY`) from the total context (e.g., 200k).

### 2.2 Max Output Tokens Efficiency Optimization

When sending requests to the API, the system applies a specific cap on `max_tokens` to improve server cluster utilization and optimize queuing speed (slot reservation).

```typescript
// src/utils/context.ts:18
// Capped default for slot-reservation optimization. BQ p99 output = 4,911
// tokens, so 32k/64k defaults over-reserve 8-16× slot capacity. With the cap
// enabled, <1% of requests hit the limit; those get one clean retry at 64k
export const CAPPED_DEFAULT_MAX_TOKENS = 8_000
export const ESCALATED_MAX_TOKENS = 64_000
```

This reveals a very engineering-oriented detail: although Claude 3.5 Sonnet supports 8k native output and can even be configured for longer, actual analysis shows that the business P99 output is around 4,911 tokens. Therefore, even if the model can handle more than 32k output, the system defaults to capping at `8_000`, which significantly reduces API layer slot reservation overhead. If truncation occurs, a clean retry at 64k is triggered.

---

## 3. Auto-Compact Trigger Strategy

Through the token consumption count obtained from each API call, the system maintains and monitors a loop that "triggers compaction upon reaching a threshold".

**Actual source code** ([`src/services/compact/autoCompact.ts:241`](../src/services/compact/autoCompact.ts)):

```typescript
export async function autoCompactIfNeeded(
 messages: Message[],
 toolUseContext: ToolUseContext,
 cacheSafeParams: CacheSafeParams,
 querySource?: QuerySource,
 tracking?: AutoCompactTrackingState,
 snipTokensFreed?: number,
): Promise<{ wasCompacted: boolean; compactionResult?: CompactionResult }> {
 
 // Circuit breaker: if consecutive compaction failures reach 3 times,
 // completely stop autocompact requests for this session.
 // Prevents futile repeated requests due to unrecoverable size overruns wasting large amounts of API quota
 if (tracking?.consecutiveFailures !== undefined &&
 tracking.consecutiveFailures >= MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES) {
 return { wasCompacted: false }
 }

 const model = toolUseContext.options.mainLoopModel
 const shouldCompact = await shouldAutoCompact(messages, model, querySource, snipTokensFreed)

 if (!shouldCompact) {
 return { wasCompacted: false }
 }

 try {
 const compactionResult = await compactConversation(
 messages,
 toolUseContext,
 cacheSafeParams,
 true, // suppressFollowUpQuestions
)
 return { wasCompacted: true, compactionResult, consecutiveFailures: 0 }
 } catch (error) {
 // Capture failure, update consecutive failure count to trigger Circuit Breaker
 const nextFailures = (tracking?.consecutiveFailures ?? 0) + 1
 return { wasCompacted: false, consecutiveFailures: nextFailures }
 }
}
```

The system sets up a dual guarantee:
1. **Buffer threshold**: triggers compaction with `13_000` tokens of headroom (`AUTOCOMPACT_BUFFER_TOKENS`) before the context is nearly full.
2. **Circuit breaker**: `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES` controls against futile compaction attempts in extreme cases (e.g., a single super-large image from the user exceeds the context), preventing infinite error loops (data shows this small check saves approximately 250K deadlock API calls per day across the platform).

---

## 4. Compression and Context Reverse Reconstruction Mechanism

When we compress the preceding Messages, what the Agent fears most is not forgetting early, but **losing external resource files loaded midway and open tools**. Therefore, `compactConversation` handles significant "context reconstruction" actions.

### 4.1 Cleaning Up Multimedia and Low-Value Payloads

Before handing off to the Forked Agent for summarization, non-critical material is first dehydrated to ensure the Summary API itself does not OOM due to excessive size:

```typescript
// src/services/compact/compact.ts:145
export function stripImagesFromMessages(messages: Message[]): Message[] {
 // Remove panel images sent by the user, files returned by Tool, etc.
 // Replace all { type: 'image' } / { type: 'document' } with equivalent text hints [image] 
}

// Remove attachments that will be fully compensated in the post-compact phase,
// preventing secondary summarization from causing hallucinations
export function stripReinjectedAttachments(messages: Message[]): Message[] {
 // e.g., remove skill_discovery and other attachments
}
```

### 4.2 API Prompt Cache Reuse

This is also an extremely clever detail. The summarization is performed in a Forked Agent (different from the main path), but the official implementation chooses to share the prompt cache.

```typescript
// src/services/compact/compact.ts:435
// Forked Agent borrows the main conversation context's Prompt Cache.
// Tests (January 2026) prove this borrowing mechanism saves significant
// head-filling token overhead required for each compaction
const promptCacheSharingEnabled = getFeatureValue_CACHED_MAY_BE_STALE(
 'tengu_compact_cache_prefix',
 true,
)
```

### 4.3 PTL Defense (Prompt Too Long Fallback)

If all the above measures still cause the summarization service to report a `Prompt Too Long` error:

```typescript
// src/services/compact/compact.ts:462
// CC-1180: If the compact request itself also exceeds the limit, peel the onion.
// Peel off 20% of old groups at a time and retry. This is the last "lifeline",
// albeit lossy, it can rescue a locked session.
const truncated = ptlAttempts <= MAX_PTL_RETRIES
 ? truncateHeadForPTLRetry(messagesToSummarize, summaryResponse)
 : null
```

### 4.4 State Restart Point Compensation (State Re-injection)

Once the summarization is complete, the originally long message list is condensed into a very short `Summary Message`. But the Agent's understanding of subsequent work must not be broken.

```typescript
// src/services/compact/compact.ts:517
// ===== State Re-injection Compensation Zone =====

// 1. Retrieve and re-add files just viewed via FileReadTool that haven't lost their cache (with truncation limit)
const fileAttachments = createPostCompactFileAttachments(preCompactReadFileState,...)

// 2. Re-add ongoing Plan / Skill
const planAttachment = createPlanAttachmentIfNeeded(context.agentId)
const skillAttachment = createSkillAttachmentIfNeeded(context.agentId)

// 3. Re-send the eliminated Deferred Delta tool protocol back to the model as messages
for (const att of getDeferredToolsDeltaAttachment(...)) {
 postCompactFileAttachments.push(createAttachmentMessage(att))
}
```

**In summary, the true picture of context smoothly navigating through "compaction" is:**
`[System boundary declaration]` + `[Condensed text summary]` + `[Truncated content of files being viewed]` + `[Plan in progress]` + `[Full declarations of still-active MCP Servers and Tools]`.

This mechanism ensures that the large model has freed up the verbose old text history, yet still remains "at the workstation with the tools just used" like a long-running Agent, completely seamlessly connecting to the next round of input.
