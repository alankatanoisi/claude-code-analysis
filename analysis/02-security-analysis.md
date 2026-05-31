# Chapter 2: Security Analysis

[Back to Table of Contents](../README.md)

---

## Chapter Guide

This chapter provides a comprehensive analysis of Claude Code from a security perspective, answering three questions:

1. **What user information does the system collect, and how is it used?**
2. **What security risk points exist in the code itself? How is the source code written?**
3. **What defenses has the system built to protect the user's machine?**

> **For beginners**: Reading this chapter doesn't require any security background. Whenever code is involved, we will first explain in plain language "what this code does", then explain "why it's related to security".

---

## Section 1: User Information Collection and Usage

Claude Code touches and records various types of user data during operation. We break it down into three layers, from "most covert" to "most obvious".

### 1.1 Layer 1: Work Context Entering the Model (Most Covert, Highest Risk)

**Related source files**:
- [`src/services/api/claude.ts`](../src/services/api/claude.ts)
- [`src/context.ts`](../src/context.ts)
- [`src/utils/queryContext.ts`](../src/utils/queryContext.ts)
- [`src/utils/attachments.ts`](../src/utils/attachments.ts)

This layer is the easiest to overlook but often carries the highest risk. Every time a user talks to Claude, the following content is packaged into the "context" and sent to Anthropic's model API:

| Content Type | Specifics Included | Sensitivity Level |
|----------|----------|----------|
| User input | All conversation content | High |
| Conversation history | All back-and-forth of the current session | High |
| Tool execution results | Command output, file read content | **Extremely high** |
| Files and code snippets | Current edited file content | Extremely high |
| Git status snapshot | diff, commit information | High |
| `CLAUDE.md` and memory files | User custom instructions and long-term memory | High |
| Images, document attachments | Screenshots, PDFs, etc. | Medium~High |
| MCP resource content | Results returned by third-party tools | Uncertain |

**Plain explanation**: Imagine you have an assistant with an open microphone. Every time you speak, they not only remember what you said, but also "report" the documents on your desk, the code on your computer screen, and the results of your recent terminal commands to the backend server. This is how context works.

**Why this layer is most dangerous**: Because users usually only notice "is there data being uploaded", while ignoring "what is being sent to the model". Anthropic's server doesn't receive a single telemetry event — it receives the complete work context including source code, command output, and file content.

---

### 1.2 Layer 2: Local Persistent Storage

**Related source files**:
- [`src/utils/sessionStorage.ts`](../src/utils/sessionStorage.ts)
- [`src/utils/settings/types.ts`](../src/utils/settings/types.ts)

The system saves a large amount of information to local disk, which persists even after the program exits:

- **transcript JSONL**: Complete record of each conversation, similar to a chat history database
- **session metadata**: Session title, tags, time and other metadata
- **agent transcript**: Independent record of sub-agent runs
- **Local user config and project config**: All your settings under the `.claude/` directory
- **OAuth account cache**: Logged-in account credentials
- **memory files**: "Long-term memory" extracted by the system from conversation history

**An important detail**: The config option `cleanupPeriodDays` controls transcript retention time, **and the default is not 0**, meaning conversation history accumulates locally over time. Set it to `0` to stop retention and clean up existing records.

For privacy-sensitive scenarios, you can disable transcript persistence via the CLI argument `--no-session-persistence` or config `cleanupPeriodDays: 0`.

---

### 1.3 Layer 3: Long-term Memory Accumulation

**Related source files**:
- [`src/memdir/memdir.ts`](../src/memdir/memdir.ts)
- [`src/services/extractMemories/extractMemories.ts`](../src/services/extractMemories/extractMemories.ts)
- [`src/services/SessionMemory/sessionMemory.ts`](../src/services/SessionMemory/sessionMemory.ts)
- [`src/tools/AgentTool/agentMemory.ts`](../src/tools/AgentTool/agentMemory.ts)

This is the most "silent" layer. The system automatically extracts key information from past conversations, writes it to memory files, and injects it into the model's prompt at the start of every future conversation.

Types of memory include:

- User preferences and habits
- User identity background (position, language, tech stack)
- Key facts about the current project
- Reference information and constraints
- Current session summary
- Agent role memory
- Team shared memory

**Plain analogy**: This is equivalent to the assistant quietly keeping a "little notebook about you". Every time you start speaking, they flip through this notebook first, responding based on what they've previously learned about you. From the user's perspective, this means the system is continuously building a "long-term collaboration profile" that persists across sessions.

---

### 1.4 Layer 4: Telemetry Data

**Related source files**:
- [`src/services/analytics/index.ts`](../src/services/analytics/index.ts)
- [`src/services/analytics/config.ts`](../src/services/analytics/config.ts)
- [`src/services/analytics/metadata.ts`](../src/services/analytics/metadata.ts)
- [`src/services/analytics/sink.ts`](../src/services/analytics/sink.ts)
- [`src/services/analytics/datadog.ts`](../src/services/analytics/datadog.ts)
- [`src/utils/user.ts`](../src/utils/user.ts)

Telemetry refers to usage statistics that the system actively sends to external services (such as Datadog). The data collected by Claude Code includes:

| Field | Description |
|------|------|
| `deviceId` | Device unique identifier |
| `sessionId` | Current session identifier |
| app version / platform / arch | Software and system version information |
| terminal / CI environment | Runtime environment type |
| account UUID / org UUID | Account and organization identifier |
| subscriptionType / rateLimitTier | Subscription type and rate limit tier |
| repo remote hash | Hash identifier of remote repository (not original text) |
| tool usage events | Which tools were called and how many times |
| file path hash / content hash | Hash fingerprint of files (not original text) |

**Key design point**: There is a notable TypeScript type marker in the source code:

```typescript
// src/services/analytics/index.ts
export type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS = never
```

This is a "developer protocol type": any string to be reported to the telemetry backend must be explicitly type-cast by the developer, writing `as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS`, which is equivalent to a manual signature stating "I confirm this data does not contain original code or file paths".

This shows the engineering team **consciously** tries to avoid sending raw source code into telemetry. However, this doesn't mean no sensitive metadata is collected — behavioral statistics, hash fingerprints, account identifiers, etc., are still continuously reported.

---

### 1.5 Layer 5: Team Memory Sync and Upload

**Related source files**:
- [`src/services/teamMemorySync/index.ts`](../src/services/teamMemorySync/index.ts)
- [`src/services/teamMemorySync/watcher.ts`](../src/services/teamMemorySync/watcher.ts)
- [`src/memdir/teamMemPaths.ts`](../src/memdir/teamMemPaths.ts)

When the user enables Team Memory, the system will:

1. Identify the team memory namespace by repo
2. Pull team memory from the server to local
3. Watch for file changes in the local memory directory
4. Automatically push local changes back to Anthropic's server

The uploaded content is not the code repository itself, but knowledge entries from the team memory directory — however, these entries may themselves contain sensitive content such as project workflows, internal knowledge bases, operational paths, and team regulations.

The system incorporates client-side secret scanning at this step (see Section 3 for details), but the essence remains "organization-level knowledge synchronization". Be mindful of information boundaries when enabling this feature.

---

### 1.6 Layer 6: User-Initiated Content Upload

**Related source files**:
- [`src/components/FeedbackSurvey/submitTranscriptShare.ts`](../src/components/FeedbackSurvey/submitTranscriptShare.ts)
- [`src/services/api/grove.ts`](../src/services/api/grove.ts)
- [`src/components/grove/Grove.tsx`](../src/components/grove/Grove.tsx)

This part is the most transparent, but still worth understanding:

- **Transcript Sharing**: When users submit feedback, the system may upload session records (including raw JSONL data) to Anthropic. The code performs some sanitization, but it still constitutes session content upload.
- **Grove / "Help Improve Claude"**: If users enable this feature, their coding sessions and conversations may be used for model training and improvement. This feature has the broadest collection scope and directly impacts model training data. If privacy-sensitive, it should be disabled by default.

---

### 1.7 Comprehensive Information Usage Assessment

From the user's perspective, the three types of information usage are as follows:

```
| Layer            | Information Type       | Purpose                          |
├─────────────────────────────────────────────────────────────────────┤
| Model context    | Source code, commands,  | Generate responses, write code,   |
|                  | files                  | decide tool calls                 |
| Local storage    | transcript, memory     | Session resume, long-term memory  |
|                  |                        | injection                         |
| Telemetry        | Behavioral metadata,   | Product analysis, stability       |
|                  | hashes                 | monitoring, experiment routing    |
| Cloud sync       | Team memory            | Organization knowledge sharing    |
| Active upload    | transcript, sessions   | Model training, feedback analysis |
```

**The most critical conclusion**: The real risk is not a single data point being logged, but the **information diffusion boundary** formed by the combination of "work context entering the model + local long-term memory + external sync capability".

---

## Section 2: Software Code Security Analysis

This section analyzes security risk points present in the source code, as well as potential attack paths for attackers.

### 2.1 Prompt Injection Attacks

**Risk description**: Claude Code can read files, web pages, and content returned by MCP tools, and embed this content into the model's context. If external content contains carefully crafted "instructions", the model may be tricked into executing an attacker's commands.

This type of attack is known as **Prompt Injection**, and is especially dangerous in the AI coding agent scenario: an attacker can hide instructions in the code comments of an open-source repository. When the user asks Claude to read this code, Claude may be induced to perform malicious actions.

**A more covert variant — Unicode steganography attacks**: Attackers can use invisible Unicode characters (invisible to the human eye but recognizable by the model) to hide instructions within ordinary text.

**The source code's countermeasures**:

```typescript
// src/utils/sanitization.ts

export function partiallySanitizeUnicode(prompt: string): string {
  let current = prompt
  let previous = ''
  let iterations = 0
  const MAX_ITERATIONS = 10

  while (current !== previous && iterations < MAX_ITERATIONS) {
    previous = current

    // Step 1: NFKC normalization — unifies characters that "look like A but are composite characters"
    current = current.normalize('NFKC')

    // Step 2: Remove dangerous Unicode category characters  
    current = current.replace(/[\p{Cf}\p{Co}\p{Cn}]/gu, '')

    // Step 3: Explicitly remove known dangerous ranges (double protection)
    current = current
      .replace(/[\u200B-\u200F]/g, '')   // Zero-width characters
      .replace(/[\u202A-\u202E]/g, '')   // Directional formatting characters (can be used for text reversal deception)
      .replace(/[\u2066-\u2069]/g, '')   // Direction isolation characters
      .replace(/[\uFEFF]/g, '')          // BOM (Byte Order Mark)
      .replace(/[\uE000-\uF8FF]/g, '')   // Private Use Area characters

    iterations++
  }
  return current
}
```

**For beginners**:
- Characters like `\u200B` are "zero-width characters" — completely invisible on screen but present in text data
- Attackers have used these characters to hide malicious instructions in MCP tool return values (HackerOne vulnerability report #3086545)
- `normalize('NFKC')` unifies characters that "look like normal letters but are actually special Unicode variants" to prevent bypasses
- The entire cleaning process loops until the text stops changing (max 10 iterations), preventing nested obfuscation

This cleaning function also has a recursive version `recursivelySanitizeUnicode` that can handle all string fields in nested structures like JSON objects and arrays, ensuring any return value from MCP tools is sanitized.

---

### 2.2 Shell Command Injection

**Risk description**: Claude Code can execute Bash/PowerShell commands. If an attacker can make the model generate command strings containing malicious payloads, they could hijack the host machine.

**The source code's countermeasures — dangerous pattern blacklist**:

```typescript
// src/utils/permissions/dangerousPatterns.ts

export const DANGEROUS_BASH_PATTERNS: readonly string[] = [
  // Code interpreters (can run arbitrary code)
  'python', 'python3', 'node', 'deno', 'ruby', 'perl', 'php',
  // Package runners
  'npx', 'bunx', 'npm run', 'yarn run',
  // Shells
  'bash', 'sh', 'zsh', 'fish',
  // Dangerous operators
  'eval', 'exec', 'env', 'xargs', 'sudo',
  // Remote execution
  'ssh',
]
```

The function of this "dangerous pattern" list: in **Auto Mode**, if permission rules are configured as broad authorizations like `Bash(python:*)` or `Bash(node:*)`, the system automatically revokes these rules. The reason is that such rules are equivalent to "allowing AI to run arbitrary Python/Node scripts without restriction", with a danger level comparable to system administrator privileges.

The corresponding detection function:

```typescript
// src/utils/permissions/permissionSetup.ts

export function isDangerousBashPermission(
  toolName: string,
  ruleContent: string | undefined,
): boolean {
  if (toolName !== BASH_TOOL_NAME) return false

  // Empty rule or * wildcard = allow all commands = extremely dangerous
  if (ruleContent === undefined || ruleContent === '' || ruleContent === '*') {
    return true
  }

  for (const pattern of DANGEROUS_BASH_PATTERNS) {
    if (content === `${pattern}:*`) return true  // "python:*" matches any python command
    if (content === `${pattern}*`) return true   // "python*" matches python, python3, etc.
    if (content === `${pattern} *`) return true  // "python *" matches python + any args
  }
  return false
}
```

**For beginners**: Suppose the user configured permission `Bash(python:*)`, meaning "let Claude auto-approve all commands starting with python". But this gives the AI unlimited rights to run Python scripts — it can read/write any file and make network requests. When the system detects such rules, it temporarily removes them before entering auto mode (`stripDangerousPermissionsForAutoMode`), and restores them after exiting auto mode (`restoreDangerousPermissions`).

---

### 2.3 Git Escape Attack

**Risk description**: This is a very sophisticated multi-stage attack. Some commands are executed inside the Claude Code sandbox, but certain Git operations occur outside the sandbox (on the host machine). Attackers can:

1. Create a "bare Git repository" directory structure inside the sandbox (including `HEAD`, `objects/`, `refs/`)
2. Inject a `core.fsmonitor` configuration with malicious hooks into this fake repository
3. Trigger the malicious hooks when the user executes commands like `git log` on the host (outside the sandbox)

**The source code's countermeasures**:

```typescript
// src/utils/sandbox/sandbox-adapter.ts

function scrubBareGitRepoFiles(directory: string): void {
  // After command execution completes, force scan and clean up implanted Git bare repo files
  // Specifically cleans: HEAD, objects/, refs/ and other core Git directories
}
```

This function runs after every sandbox command execution, eliminating the possibility of multi-stage Git escape at its source.

---

### 2.4 Untrusted Input from MCP Servers

**Risk description**: MCP (Model Context Protocol) allows third-party servers to provide tool capabilities to Claude. This means an untrusted MCP server can:

- Return "tool results" containing malicious instructions
- Use the Prompt Injection techniques mentioned above to manipulate Claude

The source code's defenses at this layer are multi-layered:
1. `recursivelySanitizeUnicode` cleans all Unicode dangerous characters from MCP return content
2. An independent permission authentication system (`src/services/mcp/auth.ts`) controls MCP tool access
3. The sandbox restricts file write operations triggered by MCP to a whitelist of paths

---

## Section 3: Preventive Security Measures

This section outlines the multi-layered defenses built by Claude Code to protect the user's machine.

### 3.1 Dual Permission Gates: Application Layer + System Layer

Claude Code uses a "dual gate" architecture, so even if one layer is breached, the other remains effective:

```
AI issues command
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  First Gate: Tool Permission (application logic      │
│  interception)                                       │
│  File: src/utils/permissions/permissionSetup.ts      │
│  Function: Determine if the AI's desired operation   │
│  has been explicitly allowed by the user             │
│  Interception: Pop-up confirmation in the            │
│  conversation, user can choose to reject             │
└─────────────────────────────────────────────────────┘
    │(if passed)
    ▼
┌─────────────────────────────────────────────────────┐
│  Second Gate: Sandbox (system-level isolation)       │
│  File: src/utils/sandbox/sandbox-adapter.ts          │
│  Function: Even if the AI's command obtains          │
│  permission, it can only execute in an isolated      │
│  environment                                         │
│  Interception: Kernel-level Namespace isolation,     │
│  cannot bypass file and network boundaries              │
└─────────────────────────────────────────────────────┘
    │(final execution)
    ▼
   Restricted execution environment
```

---

### 3.2 Sandbox Technology Details

**Related source files**: [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)

The sandbox is the underlying infrastructure of the entire security system.

**Underlying engines**:

| Operating System | Technology Used | Principle |
|----------|----------|------|
| Linux / WSL2 | `bubblewrap (bwrap)` + `socat` | Kernel Namespace isolation |
| macOS | Native sandbox framework | macOS system call sandbox |

**For beginners — Namespace isolation**: Linux Namespace is a kernel feature that gives a process a completely independent view of the filesystem, network, process table, etc. Even if a program inside the sandbox frantically writes to `/etc/passwd`, the real file on the host is completely unaffected — because the sandboxed process literally cannot "see" the real `/etc/passwd`.

**Whitelist-driven fine-grained control**: The sandbox doesn't lock the AI in a dark room with no permissions. Instead, it precisely controls "which paths can be read/written, which domains can be accessed".

```typescript
// sandbox-adapter.ts core conversion logic (pseudo-code)
function convertToSandboxRuntimeConfig(permissions) {
  return {
    filesystem: {
      allowWrite: [...paths explicitly allowed by user for writing],
      denyWrite:  [...system core paths, e.g. ~/.claude/settings.json],
      allowRead:  [...paths explicitly allowed by user for reading],
      denyRead:   [...sensitive config paths]
    },
    network: {
      allowedDomains:  [...allowed domains extracted from WebFetchTool rules],
      deniedDomains:   [...denied domains],
      allowManagedOnly: [...enterprise managed mode — only managed domains allowed]
    }
  }
}
```

**Built-in protection whitelist**: Even if the user's own config has issues, the sandbox automatically protects:
- `~/.claude/settings.json` (main config not tampered with)
- `.claude/` settings file in the current working directory
- `.claude/skills/` skills directory

**Hot-reload synchronization**: The system watches host config file changes via `settingsChangeDetector`. When the user modifies permission configuration during runtime, the sandbox's in-memory config is also synchronized in real-time via `refreshConfig()` — the AI cannot exploit the time window of "config has changed but sandbox still uses old rules" to escape.

---

### 3.3 Permission Mode Hierarchy

**Related source files**:
- [`src/utils/permissions/PermissionMode.ts`](../src/utils/permissions/PermissionMode.ts)
- [`src/utils/permissions/permissionSetup.ts`](../src/utils/permissions/permissionSetup.ts)

The system defines multiple permission modes, from strictest to most permissive:

| Mode | Description | Use Case |
|------|------|----------|
| `default` | Ask for confirmation before every operation | Daily use, safest |
| `acceptEdits` | Auto-approve file edits, commands still need confirmation | Light automation |
| `plan` | Only allow planning, no write operations | Plan review |
| `auto` | Classifier automatically determines safety, safe ones auto-execute | Efficient development |
| `bypassPermissions` | Skip all permission checks (dangerous!) | CI/CD, test scripts |

**Important protection for `bypassPermissions`**: This is the most dangerous mode. The source code has two layers of protection:

```typescript
// src/utils/permissions/bypassPermissionsKillswitch.ts

// Protection 1: Statsig remote kill switch (organization-level control)
const growthBookDisableBypassPermissionsMode =
  checkStatsigFeatureGate_CACHED_MAY_BE_STALE('tengu_disable_bypass_permissions_mode')

// Protection 2: Local settings disable
const settingsDisableBypassPermissionsMode =
  settings.permissions?.disableBypassPermissionsMode === 'disable'
```

This means organizations can forcibly disable `bypassPermissions` mode via remote policy (Statsig switch) or local configuration. Even if the user passes `--dangerously-skip-permissions` on the command line, it will be ignored and the user will be notified.

---

### 3.4 Client-Side Secret Scanner

**Related source files**: [`src/services/teamMemorySync/secretScanner.ts`](../src/services/teamMemorySync/secretScanner.ts)

To prevent users from accidentally uploading API keys, access tokens, and other sensitive credentials to the Team Memory service, the system has a built-in comprehensive regex-based secret scanner — scanning content before it leaves the local machine.

The scanned secret types cover major platforms. Here are some excerpted rules:

```typescript
// src/services/teamMemorySync/secretScanner.ts

const SECRET_RULES: SecretRule[] = [
  // AWS access keys (starting with AKIA/ASIA, etc.)
  { id: 'aws-access-token',
    source: '\\b((?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16})\\b' },

  // Anthropic's own API Key (compile-time concatenation to avoid hard-coded secrets appearing in code)
  { id: 'anthropic-api-key',
    source: `\\b(${ANT_KEY_PFX}03-[a-zA-Z0-9_\\-]{93}AA)(?:...)` },

  // GitHub Personal Access Token
  { id: 'github-pat', source: 'ghp_[0-9a-zA-Z]{36}' },

  // OpenAI API Key
  { id: 'openai-api-key',
    source: '\\b(sk-(?:proj|svcacct|admin)-...' },

  // Stripe, Shopify, Slack, npm, PyPI, and 30+ other credential patterns
  // ... (full list in source code)

  // Private key files (PEM format)
  { id: 'private-key',
    source: '-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY...' },
]
```

**Engineering highlights**:
1. **Scan results don't return matched text**: The `scanForSecrets` function returns "which rule was hit", not the original secret text, preventing the scan itself from becoming an information leak channel
2. **Redact rather than reject**: The `redactSecrets` function can replace secrets with `[REDACTED]` instead of throwing an error and discarding, maintaining context readability
3. **Special handling for Anthropic's own keys**: `ANT_KEY_PFX` is constructed at runtime via string concatenation `['sk', 'ant', 'api'].join('-')`, preventing the key prefix literal from appearing in the bundled bundle file (preventing false positives from automated scanning tools)

---

### 3.5 Telemetry Data Privacy Isolation Design

**Related source files**:
- [`src/services/analytics/index.ts`](../src/services/analytics/index.ts)
- [`src/utils/privacyLevel.ts`](../src/utils/privacyLevel.ts)

**Hierarchical privacy control**:

```typescript
// src/utils/privacyLevel.ts

type PrivacyLevel = 'default' | 'no-telemetry' | 'essential-traffic'

export function getPrivacyLevel(): PrivacyLevel {
  if (process.env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC) {
    return 'essential-traffic'  // Strictest: disable all non-essential network
  }
  if (process.env.DISABLE_TELEMETRY) {
    return 'no-telemetry'       // Disable telemetry, keep auto-updates etc.
  }
  return 'default'              // Full functionality enabled
}
```

Three levels description:

| Level | Disabled Content |
|------|----------|
| `default` | Full functionality enabled |
| `no-telemetry` | Disable Datadog, 1P event logging, feedback surveys |
| `essential-traffic` | On top of no-telemetry, additionally disable auto-updates, Grove, Release Notes, Model Capabilities fetching, etc. |

**PII routing protection**: Before telemetry data is sent, PII (Personal Identifiable Information) related fields are routed to access-controlled dedicated BigQuery columns, rather than appearing in the general Datadog log stream:

```typescript
// src/services/analytics/index.ts

// Fields prefixed with _PROTO_ are PII-marked fields, appearing only in
// access-controlled 1P export channels. Must be stripped via stripProtoFields
// before sending to Datadog
export function stripProtoFields<V>(
  metadata: Record<string, V>,
): Record<string, V> {
  // Remove all fields starting with _PROTO_ before sending to Datadog
}
```

**MCP tool name sanitization**: MCP tool names follow the format `mcp__<server>__<tool>`, where the server name may expose the user's private MCP server configuration (considered moderately sensitive PII). Before reporting, it's replaced with the generic label `mcp_tool`:

```typescript
// src/services/analytics/metadata.ts

export function sanitizeToolNameForAnalytics(toolName: string) {
  if (toolName.startsWith('mcp__')) {
    return 'mcp_tool'  // Don't expose user's MCP server names
  }
  return toolName
}
```

---

### 3.6 Path Security Validation

**Related source files**:
- [`src/utils/permissions/pathValidation.ts`](../src/utils/permissions/pathValidation.ts)
- [`src/utils/permissions/filesystem.ts`](../src/utils/permissions/filesystem.ts)

The system performs defensive validation on all file path operations to prevent **Path Traversal** attacks — an attack technique that bypasses restricted directories using paths like `../../etc/passwd`.

Team Memory sync path protection in `secretScanner.ts` has dedicated path traversal prevention, ensuring that even if MCP or AI attempts to operate on paths like `../../../important_file`, they will be intercepted.

---

## Chapter Summary

Claude Code's security architecture can be understood as a set of concentric circles:

```
                    ┌──────────────────────────────────┐
                    │   Telemetry privacy isolation +    │  ← Data egress defense
                    │   Secret scanning                  │
                 ┌──┼──────────────────────────────────┼──┐
                 │  │     Permission mode hierarchy      │  │ ← Policy defense
              ┌──┼──┼──────────────────────────────────┼──┼──┐
              │  │  │  Tool Permission application layer │  │  │ ← Application defense
              │  │  │  interception                      │  │  │
           ┌──┼──┼──┼──────────────────────────────────┼──┼──┼──┐
           │  │  │  │     Sandbox system-level isolation  │  │  │  │ ← Foundation defense
           │  │  │  │  Unicode sanitization / path        │  │  │  │
           │  │  │  │  validation                         │  │  │  │
           └──┼──┼──┼──────────────────────────────────┼──┼──┼──┘
              └──┼──┼──────────────────────────────────┼──┼──┘
                 └──┼──────────────────────────────────┼──┘
                    └──────────────────────────────────┘
                                   │
                              Host (protected)
```

**Overall assessment**:
- Claude Code is **by no means** a zero-risk product — the context entering the model is the largest information leakage surface, which is a structural characteristic of this type of product and cannot be avoided by simply disabling telemetry
- However, the engineering team has invested considerable effort in security protection: dual permission gates, sandbox isolation, secret scanning, Unicode sanitization, dangerous pattern interception, and other mechanisms all have solid source code implementations
- For users, **the most effective security measure** is: understanding what content enters the model context, and actively controlling the boundaries of what is input
