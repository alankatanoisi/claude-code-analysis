# Chapter 3: How to Avoid or Reduce Information Collection — From the User's Perspective

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter discusses not "whether zero collection is theoretically possible", but "what users can actually do to reduce the exposure surface".

**TL;DR**: If a user wants to minimize exposure, they need to control three things simultaneously:

1. Don't let sensitive content enter the model context
2. Don't let transcript / memory persist long-term
3. Don't enable sync, telemetry, sharing and remote capabilities

## 2. First Distinguish Three Types of Risk

To avoid information collection, at least distinguish between:

1. `Content sent to the model`
2. `Content persisted locally`
3. `Content uploaded to external services`

Many people only focus on category 3, but for coding agents, category 1 is typically more sensitive.

## 3. Most Effective Technical Avoidance Actions

### 3.1 Disable Telemetry and Non-essential Network

Related implementations:

- [`src/utils/privacyLevel.ts`](../src/utils/privacyLevel.ts)

Available methods:

- `DISABLE_TELEMETRY`
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`

Difference in effect:

- `DISABLE_TELEMETRY`: Primarily disables telemetry/analytics
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`: More strict, disables non-essential network capabilities

If the goal is "minimize network egress", the latter is more effective.

### 3.2 Disable Transcript Persistence

Related implementations:

- [`src/main.tsx`](../src/main.tsx)
- [`src/utils/settings/types.ts`](../src/utils/settings/types.ts)
- [`src/bootstrap/state.ts`](../src/bootstrap/state.ts)

Available methods:

- CLI: `--no-session-persistence`
- Setting: `cleanupPeriodDays: 0`

Benefits:

- No recoverable transcript generated
- Reduces chances of session being reused for memory, resume, share

### 3.3 Turn Off Auto Memory

Related implementations:

- [`src/memdir/paths.ts`](../src/memdir/paths.ts)

Available methods:

- `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`
- `settings.autoMemoryEnabled = false`
- `--bare` / SIMPLE mode

Benefits:

- No longer automatically extract long-term memory
- Reduces "long-term user profile accumulation"
- Reduces subsequent automatic memory injection into prompts

### 3.4 Do Not Enable Team Memory

Reason:

- Team memory triggers directory watching, pull, push, server sync

Related implementations:

- [`src/services/teamMemorySync/index.ts`](../src/services/teamMemorySync/index.ts)
- [`src/services/teamMemorySync/watcher.ts`](../src/services/teamMemorySync/watcher.ts)

If the user or team does not want project knowledge to be continuously synced, this capability should be disabled.

### 3.5 Do Not Enable Remote / Bridge / Transcript Share

These features all expand the system boundary:

- `remote-control` / bridge: Expands session control plane and remote data plane
- transcript share: Directly uploads session content

For privacy-sensitive scenarios, these should be disabled by default.

## 4. Behavioral Avoidance Suggestions

Even if all telemetry is turned off, if the user directly hands sensitive information to the model, the risk still exists.

Suggestions:

- Don't paste keys, tokens, or private certificates directly into prompts
- Don't send entire `.env`, production config, or customer data files into the context
- Don't let the agent scan large directories containing sensitive materials
- Don't write sensitive knowledge into auto memory or team memory
- Don't process sensitive projects with Grove enabled

## 5. Governance Suggestions for Teams and Enterprises

If this is a team usage scenario, individual developer manual habits are not sufficient to ensure containment. A unified strategy should be adopted:

- Disable auto memory by default
- Disable team memory by default
- Set `cleanupPeriodDays` to `0` or a very short value
- Enable `essential-traffic` by default
- Prohibit remote / bridge
- Use isolated repositories, sanitized mirrors, or temporary worktrees to run the agent

## 6. A Realistic Assessment

If the user's actual goal is:

- Code never leaves the local machine
- Never enters the model
- No long-term memory formed
- No trace left for recovery

Then this type of product is inherently unsuitable as a default working method.

The usage mode closest to this goal can only be:

- `--bare`
- no telemetry
- no persistence
- no auto memory
- no team memory
- no remote
- Strictly control input context

In other words, this project can "reduce the exposure surface", but it is not a "zero-collection first" architecture.

## 7. Chapter Summary

The most practical avoidance path for users is:

1. First disable network and telemetry
2. Then disable transcript and memory
3. Finally control your own input behavior

If only step 1 is done while ignoring steps 2 and 3, the privacy benefits will be far lower than expected.
