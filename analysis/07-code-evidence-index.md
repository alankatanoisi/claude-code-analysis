# Chapter 17: Code Evidence Index

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter does not provide expanded analysis; it only serves as an evidence index for easy navigation from the table of contents to the source code.

## 2. Entry and Startup Pipeline

- [`src/entrypoints/cli.tsx`](../src/entrypoints/cli.tsx)
- [`src/main.tsx`](../src/main.tsx)
- [`src/entrypoints/init.ts`](../src/entrypoints/init.ts)
- [`src/setup.ts`](../src/setup.ts)
- [`src/replLauncher.tsx`](../src/replLauncher.tsx)
- [`src/screens/REPL.tsx`](../src/screens/REPL.tsx)

## 3. Query / Agent Core

- [`src/query.ts`](../src/query.ts)
- [`src/QueryEngine.ts`](../src/QueryEngine.ts)
- [`src/utils/queryContext.ts`](../src/utils/queryContext.ts)
- [`src/constants/prompts.ts`](../src/constants/prompts.ts)
- [`src/context.ts`](../src/context.ts)

## 4. Tools and Permissions

- [`src/tools.ts`](../src/tools.ts)
- [`src/Tool.ts`](../src/Tool.ts)
- [`src/services/tools/toolOrchestration.ts`](../src/services/tools/toolOrchestration.ts)
- [`src/utils/permissions/permissionSetup.ts`](../src/utils/permissions/permissionSetup.ts)

## 5. State and UI

- [`src/state/AppStateStore.ts`](../src/state/AppStateStore.ts)
- [`src/state/store.ts`](../src/state/store.ts)
- [`src/interactiveHelpers.tsx`](../src/interactiveHelpers.tsx)

## 6. Transcript / Persistence / Session Recovery

- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)
- [`src/services/api/sessionIngress.ts`](../src/services/api/sessionIngress.ts)
- [`src/utils/settings/types.ts`](../src/utils/settings/types.ts)
- [`src/utils/gracefulShutdown.ts`](../src/utils/gracefulShutdown.ts)

## 7. Memory System

- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)
- [`src/memdir/paths.ts`](../src/memdir/paths.ts)
- [`src/memdir/findRelevantMemories.ts`](../src/memdir/findRelevantMemories.ts)
- [`src/memdir/teamMemPaths.ts`](../src/memdir/teamMemPaths.ts)
- [`src/services/extractMemories/extractMemories.ts`](../src/services/extractMemories/extractMemories.ts)
- [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts)
- [`src/services/compact/sessionMemoryCompact.ts`](../src/services/compact/sessionMemoryCompact.ts)
- [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts)
- [`src/tools/AgentTool/agentMemorySnapshot.ts`](../src/tools/AgentTool/agentMemorySnapshot.ts)
- [`src/tools/AgentTool/loadAgentsDir.ts`](../src/tools/AgentTool/loadAgentsDir.ts)

## 8. Analytics / Privacy / Feedback

- [`src/services/analytics/index.ts`](../src/services/analytics/index.ts)
- [`src/services/analytics/config.ts`](../src/services/analytics/config.ts)
- [`src/services/analytics/metadata.ts`](../src/services/analytics/metadata.ts)
- [`src/services/analytics/sink.ts`](../src/services/analytics/sink.ts)
- [`src/services/analytics/datadog.ts`](../src/services/analytics/datadog.ts)
- [`src/utils/privacyLevel.ts`](../src/utils/privacyLevel.ts)
- [`src/utils/user.ts`](../src/utils/user.ts)
- [`src/utils/fileOperationAnalytics.ts`](../src/utils/fileOperationAnalytics.ts)
- [`src/services/api/grove.ts`](../src/services/api/grove.ts)
- [`src/components/grove/Grove.tsx`](../src/components/grove/Grove.tsx)
- [`src/components/FeedbackSurvey/submitTranscriptShare.ts`](../src/components/FeedbackSurvey/submitTranscriptShare.ts)

## 9. MCP / Remote / Swarm / Team Memory

- [`src/services/mcp/client.ts`](../src/services/mcp/client.ts)
- [`src/services/mcp/auth.ts`](../src/services/mcp/auth.ts)
- [`src/entrypoints/mcp.ts`](../src/entrypoints/mcp.ts)
- [`src/bridge/bridgeMain.ts`](../src/bridge/bridgeMain.ts)
- [`src/utils/swarm/backends/registry.ts`](../src/utils/swarm/backends/registry.ts)
- [`src/utils/swarm/spawnInProcess.ts`](../src/utils/swarm/spawnInProcess.ts)
- [`src/services/teamMemorySync/index.ts`](../src/services/teamMemorySync/index.ts)
- [`src/services/teamMemorySync/watcher.ts`](../src/services/teamMemorySync/watcher.ts)

## 10. Chapter Summary

The purpose of this index chapter is to separate "conclusions" from "evidence." The preceding chapters are for narrative, while this chapter is for tracing and verification.
