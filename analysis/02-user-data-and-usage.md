# Chapter 2: From the User's Perspective — What Information Is Collected and How It Is Used

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter stands only from the user's perspective, not the developer's perspective, answering two questions:

1. What user information does the system actually touch.
2. What each type of information is used for.

**TL;DR**: What deserves the most attention is not just telemetry, but "the source code and work information that enters the model context" and "the long-term persisted transcript/memory".

## 2. Information Entering the Model API

Related implementations:

- [`src/services/api/claude.ts`](../src/services/api/claude.ts)
- [`src/context.ts`](../src/context.ts)
- [`src/utils/queryContext.ts`](../src/utils/queryContext.ts)
- [`src/utils/attachments.ts`](../src/utils/attachments.ts)

Content that enters the model context includes:

- User input
- Conversation history
- Tool execution results
- File snippets, code snippets, command output
- `CLAUDE.md` and memory files
- Git status snapshot
- Images, documents and other attachments
- MCP resource return content
- Plans, tasks, diagnostic information

The purpose of this information is:

- Generate responses
- Decide whether to call tools next
- Guide code editing
- Perform compaction and summarization
- Derive subagent context

In terms of sensitivity ranking, this part typically has higher risk than ordinary analytics.

## 3. Locally Persisted Information

Related implementations:

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)
- [`src/utils/settings/types.ts`](../src/utils/settings/types.ts)

The following is saved locally by default:

- transcript JSONL
- session metadata
- agent transcript
- subagent metadata
- Local user config, project config
- OAuth account cached information
- memory files

Specific uses:

- `--resume` to resume sessions
- Session search, title, tags
- Restore context continuity after compaction
- Provide raw material for memory extraction
- Make subagent states traceable

Noteworthy:

- `cleanupPeriodDays` retains transcripts by default
- Setting to `0` means do not retain transcripts, and clean up existing transcripts

## 4. Memory-Related Information

Related implementations:

- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)
- [`src/memdir/paths.ts`](../src/memdir/paths.ts)
- [`src/services/extractMemories/extractMemories.ts`](../src/services/extractMemories/extractMemories.ts)
- [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts)
- [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts)

Types of memory the system accumulates include:

- User preferences
- User role and background
- Project facts
- Reference information
- Current session summary
- Agent role memory
- Team shared memory

This information is used for:

- Subsequent prompt injection
- Related memory retrieval
- Compensating long history after compaction
- Agent long-term behavioral consistency
- Team shared project knowledge

From the user's perspective, this means the system is continuously forming a "long-term collaboration profile".

## 5. Analytics / Telemetry Collected Information

Related implementations:

- [`src/services/analytics/index.ts`](../src/services/analytics/index.ts)
- [`src/services/analytics/config.ts`](../src/services/analytics/config.ts)
- [`src/services/analytics/metadata.ts`](../src/services/analytics/metadata.ts)
- [`src/services/analytics/sink.ts`](../src/services/analytics/sink.ts)
- [`src/services/analytics/datadog.ts`](../src/services/analytics/datadog.ts)
- [`src/utils/user.ts`](../src/utils/user.ts)
- [`src/utils/fileOperationAnalytics.ts`](../src/utils/fileOperationAnalytics.ts)

The source code shows the project is making an effort to avoid sending "code body, original file paths" directly into general analytics, but still collects a fair amount of metadata:

- `deviceId`
- `sessionId`
- app version
- platform / arch / runtime / terminal / CI environment
- account UUID / organization UUID
- subscriptionType / rateLimitTier
- repo remote hash
- GitHub Actions metadata
- Tool usage events, error events, compact events, bridge events, memory events
- File path hash and content hash

Main uses:

- Product behavior analysis
- Stability and error monitoring
- Feature gate / experiment routing
- Usage scale statistics
- Internal issue diagnosis

The distinction here:

- This does NOT mean uploading full user source code to Datadog
- But it does form a fairly complete behavioral metadata profile

## 6. Account and Identity Information

Related implementations:

- [`src/utils/user.ts`](../src/utils/user.ts)
- [`src/utils/config.ts`](../src/utils/config.ts)
- [`src/services/oauth`](../src/services/oauth)
- [`src/services/mcp/auth.ts`](../src/services/mcp/auth.ts)

The project reads or caches:

- OAuth token
- accountUuid
- organizationUuid
- emailAddress
- organizationName / role
- Plan, quota and entitlement information

Uses include:

- Login authentication
- Plan and quota determination
- Grove, team memory, remote control entitlement verification
- Analytics dimension tagging

## 7. Information Touched by Team Memory Sync

Related implementations:

- [`src/services/teamMemorySync/index.ts`](../src/services/teamMemorySync/index.ts)
- [`src/services/teamMemorySync/watcher.ts`](../src/services/teamMemorySync/watcher.ts)
- [`src/memdir/teamMemPaths.ts`](../src/memdir/teamMemPaths.ts)

When team memory is enabled and the user meets OAuth conditions, the system will:

- Identify team memory namespace by repo
- Pull remote team memory to local
- Watch local directory
- Push local changes back to server

What is uploaded is not the entire repository, but the content within the team memory directory. However, this content may itself contain:

- Project workflows
- Internal network knowledge
- Operations paths
- Team constraints
- Special regulations

Although the project has added:

- Path traversal protection
- Secret scanner

Its essence remains "organization-level knowledge synchronization".

## 8. User-Initiated Additional Uploads

### 8.1 Transcript Sharing

Related implementations:

- [`src/components/FeedbackSurvey/submitTranscriptShare.ts`](../src/components/FeedbackSurvey/submitTranscriptShare.ts)

In feedback scenarios, users may actively upload:

- transcript
- subagent transcripts
- raw JSONL transcript

The code performs sanitization, but this still constitutes "session content upload".

### 8.2 Grove / Help Improve Claude

Related implementations:

- [`src/services/api/grove.ts`](../src/services/api/grove.ts)
- [`src/components/grove/Grove.tsx`](../src/components/grove/Grove.tsx)

The meaning of this feature from the user's perspective is very straightforward:

- Allow using chats and coding sessions to train or improve the model

Therefore, if the user does not wish their coding sessions to enter the training improvement pipeline, this capability should not be enabled.

## 9. Information in Remote / Bridge Scenarios

Related implementations:

- [`src/bridge/bridgeMain.ts`](../src/bridge/bridgeMain.ts)
- [`src/services/api/sessionIngress.ts`](../src/services/api/sessionIngress.ts)

In remote or bridge scenarios, the system also involves:

- Remote environment identifier
- Session ingress logs
- Remote session metadata
- Bridge state, heartbeat and session ID

This is not the default data plane for normal local mode, but once enabled, it significantly expands the scope of information flow.

## 10. Chapter Summary

From the user's perspective, the information touched by this project can be roughly divided into three layers:

1. Work context entering the model
2. Locally persisted transcript and memory
3. Telemetry, sync, sharing, remote and other additional uploads

The most critical factor is not any single log event, but the "long-term, recoverable, searchable, syncable" user work profile formed by the combination of these capabilities.
