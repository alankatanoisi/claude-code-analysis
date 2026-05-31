# Chapter 7: MCP Technical Implementation Details and Operation Mechanism

[Back to Table of Contents](../README.md)

---

## 1. Chapter Guide

MCP (Model Context Protocol) is an open standard led by Anthropic that allows AI models to uniformly access external tools and data sources. Claude Code deeply integrates MCP, supporting four transport protocols, a complete authentication system, and concurrency safety management.

Main source files:
- [`src/services/mcp/client.ts`](../src/services/mcp/client.ts) — MCP client core
- [`src/services/mcp/auth.ts`](../src/services/mcp/auth.ts) — OAuth authentication and Step-up detection
- [`src/services/mcp/mcpStringUtils.ts`](../src/services/mcp/mcpStringUtils.ts) — Tool naming rules
- [`src/utils/mcpWebSocketTransport.ts`](../src/utils/mcpWebSocketTransport.ts) — WebSocket transport layer

---

## 2. Tool Naming Rules

When all MCP tools are unified into the tool pool, their names are normalized via `buildMcpToolName()`:

```typescript
// src/services/mcp/mcpStringUtils.ts
export function buildMcpToolName(serverName: string, toolName: string): string {
  return `mcp__${serverName}__${toolName}`
  // Examples:
  //   mcp__filesystem__read_file
  //   mcp__puppeteer__screenshot
  //   mcp__ide__getDiagnostics
}
```

This consistent naming format allows MCP tools in the tool pool to maintain a unified schema with built-in tools, and the model does not need to distinguish their source.

---

## 3. Connection Management: `connectToServer()`

**Actual source code** ([`src/services/mcp/client.ts:595`](../src/services/mcp/client.ts)):

```typescript
// Wrapped with memoize: same server config only creates one connection
export const connectToServer = memoize(
  async (
    name: string,
    serverRef: ScopedMcpServerConfig,
    serverStats?: { totalServers: number; stdioCount: number; ... },
  ): Promise<MCPServerConnection> => {
    let transport

    // Select transport layer based on serverRef.type
    if (serverRef.type === 'sse') {
      const authProvider = new ClaudeAuthProvider(name, serverRef)
      transport = new SSEClientTransport(serverRef.url, {
        authProvider,
        fetch: wrapFetchWithTimeout(
          wrapFetchWithStepUpDetection(createFetchWithInit(), authProvider)
        ),
      })
    } else if (serverRef.type === 'ws' || serverRef.type === 'ws-ide') {
      transport = new WebSocketTransport(serverRef.url)
    } else if (serverRef.type === 'http' || serverRef.type === 'streamable-http') {
      transport = new StreamableHTTPClientTransport(serverRef.url, {
        fetch: wrapFetchWithTimeout(createClaudeAiProxyFetch(baseFetch)),
      })
    } else {  // Default: stdio
      transport = new StdioClientTransport({
        command: serverRef.command,
        args: serverRef.args,
        env: serverRef.env,
      })
    }

    const client = new Client({ name: 'claude-code', version: ... })
    await client.connect(transport)
    return { client, transport, ... }
  },
  getServerCacheKey  // Cache key = name + JSON(serverRef)
)
```

Comparison of four transport protocols:

| Type | Use Case | Underlying Transport |
|------|----------|---------------------|
| `stdio` | Local process (most common) | `StdioClientTransport` |
| `sse` / `sse-ide` | Remote HTTP long connection | `SSEClientTransport` |
| `ws` / `ws-ide` | Long-lived WebSocket channel (IDE integration) | `WebSocketTransport` |
| `http` / `streamable-http` | HTTP + claude.ai proxy | `StreamableHTTPClientTransport` |

---

## 4. Timeout Control: `wrapFetchWithTimeout()`

**Actual source code** ([`src/services/mcp/client.ts:492`](../src/services/mcp/client.ts)):

```typescript
export function wrapFetchWithTimeout(baseFetch: FetchLike): FetchLike {
  return async (url: string | URL, init?: RequestInit) => {
    const method = (init?.method ?? 'GET').toUpperCase()

    // GET requests do not have a timeout — SSE is a long-lived GET, cannot be cut off by timeout
    if (method === 'GET') return baseFetch(url, init)

    // Uses setTimeout instead of AbortSignal.timeout()
    // Reason: AbortSignal.timeout() has a memory leak in Bun (~2.4KB per request lingering before GC)
    const controller = new AbortController()
    const timer = setTimeout(
      c => c.abort(new DOMException('The operation timed out.', 'TimeoutError')),
      MCP_REQUEST_TIMEOUT_MS,
      controller,
    )
    timer.unref?.()  // Does not prevent process exit

    try {
      const response = await baseFetch(url, { ...init, signal: controller.signal })
      clearTimeout(timer)
      return response
    } catch (error) {
      clearTimeout(timer)
      throw error
    }
  }
}
```

**Engineering detail**: The comments directly explain why the simpler `AbortSignal.timeout()` is not used — this is a targeted workaround for a known memory leak issue in the Bun runtime.

---

## 5. Description Length Limit

```typescript
// src/services/mcp/client.ts:218
// Comment: OpenAPI-generated MCP servers have been observed dumping 15-60KB
// of endpoint docs into tool.description; this caps the p95 tail without losing the intent.
const MAX_MCP_DESCRIPTION_LENGTH = 2048
```

This constant applies during the tool list conversion stage: all tool descriptions exceeding 2048 characters are forcibly truncated, preventing (from OpenAPI-derived MCP services) overly long documentation from filling up the model's Context Window.

---

## 6. Concurrent Connection Control

```typescript
// src/services/mcp/client.ts:552
export function getMcpServerConnectionBatchSize(): number {
  // Can be overridden via environment variable, default 3 concurrent (local)
  return parseInt(process.env.MCP_SERVER_CONNECTION_BATCH_SIZE || '', 10) || 3
}

function getRemoteMcpServerConnectionBatchSize(): number {
  // Remote connections default to 20 concurrent (network IO, higher concurrency value)
  return parseInt(process.env.MCP_REMOTE_SERVER_CONNECTION_BATCH_SIZE || '', 10) || 20
}
```

Connection concurrency is controlled via `pMap(servers, connectToServer, { concurrency: batchSize })`, preventing a large number of MCP connections from causing a freeze at startup.

---

## 7. Authentication Cache: Preventing "Auth Avalanche"

**Problem background**: If a Token becomes invalid, 100 concurrent tool sub-calls will simultaneously detect 401/403 and all initiate Token refresh requests — forming an "auth avalanche."

**Solution**: Use a local file cache to record authentication failures ([`src/services/mcp/client.ts:259`](../src/services/mcp/client.ts)):

```typescript
type McpAuthCacheData = Record<string, { timestamp: number }>

// Cache file path: ~/.claude/mcp-needs-auth-cache.json
function getMcpAuthCachePath(): string { ... }

// Read (Promise result memoized, preventing concurrent reads from duplicating fs.readFile)
function getMcpAuthCache(): Promise<McpAuthCacheData> {
  authCachePromise ??= readFile(getMcpAuthCachePath(), 'utf-8')
    .then(data => jsonParse(data) as McpAuthCacheData)
    .catch(() => ({}))
  return authCachePromise
}

// Write: mark a serverId as authentication failed
function setMcpAuthCacheEntry(serverId: string): void {
  // Asynchronous write, does not block caller
}

// Check: if the service is known to need authentication within 15 minutes, directly return needs-auth without retry
async function isMcpAuthCached(serverId: string): Promise<boolean> {
  const cache = await getMcpAuthCache()
  const entry = cache[serverId]
  if (!entry) return false
  const MCP_AUTH_CACHE_TTL_MS = 15 * 60 * 1000  // 15 minutes
  return Date.now() - entry.timestamp < MCP_AUTH_CACHE_TTL_MS
}
```

**Effect**: If a Server's authentication fails, all subsequent calls to it within 15 minutes are short-circuited and return `needs-auth`, without consuming additional Tokens or network requests.

---

## 8. Session Expiry Detection and Reconnection

```typescript
// src/services/mcp/client.ts:193
export function isMcpSessionExpiredError(error: Error): boolean {
  const httpStatus = (error as Error & { code?: number }).code
  if (httpStatus !== 404) return false
  // MCP specification: Server returns HTTP 404 + JSON-RPC error code -32001 when session expires
  return (
    error.message.includes('"code":-32001') ||
    error.message.includes('"code": -32001')
  )
}
```

When a session expiry is detected, the system clears the connection cache (`connectToServer.cache.clear()`) and re-invokes `connectToServer()` to establish a new connection.

---

## 9. IDE Tool Whitelist

IDE integration (`ws-ide`) can push LSP diagnostics, code context, and other information to Claude, but not all IDE tools are allowed:

```typescript
// src/services/mcp/client.ts:569
const ALLOWED_IDE_TOOLS = [
  'mcp__ide__getDiagnostics',
  'mcp__ide__getOpenEditorFiles',
  // ... only a few high-privilege tools pass through the whitelist
]

function isIncludedMcpTool(tool: Tool): boolean {
  // non-IDE tools are all allowed; IDE tools are only allowed if on the whitelist
  return !tool.name.startsWith('mcp__ide__') || ALLOWED_IDE_TOOLS.includes(tool.name)
}
```

---

## 10. claude.ai Proxy-Specific Handling

```typescript
// src/services/mcp/client.ts:372
export function createClaudeAiProxyFetch(innerFetch: FetchLike): FetchLike {
  return async (url, init) => {
    const response = await innerFetch(url, init)
    // If claude.ai returns 401 (Token expired), actively trigger OAuth Token Refresh and retry
    if (response.status === 401) {
      await refreshOAuthToken()
      return innerFetch(url, { ...init, headers: { ...getUpdatedAuthHeaders() } })
    }
    return response
  }
}
```

This wrapper function specifically handles OAuth expiry issues at the claude.ai endpoint, allowing HTTP MCP connections to continue without requiring the user to manually re-login.

---

## 11. Tool Pool Integration

After MCP tools are loaded, they are merged into the unified tool pool via `assembleToolPool()` along with built-in tools:

```typescript
// src/tools.ts (pseudo code)
export function assembleToolPool(
  permissionContext: ToolPermissionContext,
  mcpTools: Tool[],
): Tool[] {
  const builtinTools = getTools(permissionContext)
  return [
    ...builtinTools,                           // Built-in tools first
    ...mcpTools.filter(isIncludedMcpTool),     // MCP tool whitelist filter
  ]
    .sort((a, b) => a.name.localeCompare(b.name))  // Sort
    .filter(deduplicateByName())                    // Deduplicate (built-in preferred)
}
```

To the model, whether a tool comes from built-in or MCP, it is just an instance of the `Tool` interface — the Schema is completely identical.

---

## 12. Summary

| Mechanism | Implementation Details |
|-----------|----------------------|
| Connection establishment | `connectToServer()` memoized, 4 transport protocols, OAuth support |
| Timeout control | `wrapFetchWithTimeout()` uses `setTimeout` to avoid Bun memory leak |
| Description truncation | `MAX_MCP_DESCRIPTION_LENGTH = 2048`, prevents context explosion |
| Concurrency control | `pMap` limits concurrency, local 3 / remote 20 |
| Auth avalanche protection | 15-minute Auth Cache, one failure short-circuits subsequent requests to the same Server |
| Session reconnection | Detects HTTP 404 + JSON-RPC -32001, automatically clears cache and reconnects |
| IDE isolation | `isIncludedMcpTool()` whitelist controls boundary of IDE push capabilities |
