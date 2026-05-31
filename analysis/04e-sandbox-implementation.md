# Chapter 7: Sandbox Technical Implementation Details and Runtime Mechanism

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter no longer stays at the "Claude Code has a sandbox toggle" level, but directly answers four implementation questions:

1. When exactly does a Bash command enter the sandbox
2. How the `permissions` / `sandbox` rules in the configuration file are translated into underlying isolation configuration
3. What is the relationship between the sandbox and the application-layer permission system, which judges first, and which provides fallback
4. What explicit sandbox escape protections exist in the code, rather than abstract notions of "being more secure"

This chapter is primarily based on these implementations:

- [`src/tools/BashTool/shouldUseSandbox.ts`](../src/tools/BashTool/shouldUseSandbox.ts)
- [`src/tools/BashTool/bashPermissions.ts`](../src/tools/BashTool/bashPermissions.ts)
- [`src/tools/BashTool/BashTool.tsx`](../src/tools/BashTool/BashTool.tsx)
- [`src/utils/Shell.ts`](../src/utils/Shell.ts)
- [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)
- [`src/utils/permissions/pathValidation.ts`](../src/utils/permissions/pathValidation.ts)
- [`src/components/permissions/SandboxPermissionRequest.tsx`](../src/components/permissions/SandboxPermissionRequest.tsx)
- [`src/components/sandbox/SandboxDoctorSection.tsx`](../src/components/sandbox/SandboxDoctorSection.tsx)

TL;DR:

The sandbox in this project is not a simple "wrap a bwrap around the call" feature, but a four-layer structure:

1. `shouldUseSandbox()` determines whether a given command should enter the sandbox
2. `convertToSandboxRuntimeConfig()` translates Claude Code's own settings semantics into filesystem and network restrictions that the sandbox runtime can understand
3. `bashPermissions.ts` combines "sandbox auto-allow" with explicit deny / ask rules, preventing the sandbox from bypassing the permission system
4. `Shell.ts` and `cleanupAfterCommand()` are responsible for actually wrapping the command in an isolated environment and performing host-level cleanup after the command finishes

Therefore, the sandbox in this project is not a peripheral auxiliary module, but a part of the Bash execution chain.

## 2. Overall Architecture: Not a Single Feature, but an Execution Chain

First, look at the overall flow:

```text
Model generates BashTool call
  -> shouldUseSandbox()
     -> false: go through normal Bash permission path
     -> true:
        -> bashPermissions.checkSandboxAutoAllow()
        -> Shell.ts
        -> SandboxManager.wrapWithSandbox()
        -> sandbox-runtime / bwrap / macOS runtime
        -> command execution
        -> cleanupAfterCommand()
        -> scrubBareGitRepoFiles()

settings.permissions / settings.sandbox
  -> convertToSandboxRuntimeConfig()
  -> affects wrapWithSandbox() runtime config
  -> also affects bashPermissions and pathValidation

Network unauthorized access
  -> SandboxPermissionRequest

Missing dependencies / unsupported platform
  -> SandboxDoctorSection
```

This diagram illustrates a key fact:

- The sandbox is not a second system independent of permissions
- It is the combined result of "command execution isolation" and "permission decision system"

If you only look at `sandbox-adapter.ts`, you might mistake it for just a config translator; but when you connect [`src/tools/BashTool/bashPermissions.ts`](../src/tools/BashTool/bashPermissions.ts) and [`src/utils/Shell.ts`](../src/utils/Shell.ts), you'll find it penetrates all three stages: command release, execution, and cleanup.

## 3. Step One: When Does a Command Enter the Sandbox

Related implementations:

- [`src/tools/BashTool/shouldUseSandbox.ts`](../src/tools/BashTool/shouldUseSandbox.ts)
- [`src/tools/BashTool/BashTool.tsx`](../src/tools/BashTool/BashTool.tsx)
- [`src/utils/Shell.ts`](../src/utils/Shell.ts)

The core decision function here is `shouldUseSandbox()`.

### 3.1 Original Implementation

**Actual source code** (excerpted from [`src/tools/BashTool/shouldUseSandbox.ts`](../src/tools/BashTool/shouldUseSandbox.ts)):

```ts
export function shouldUseSandbox(input: Partial<SandboxInput>): boolean {
  if (!SandboxManager.isSandboxingEnabled()) {
    return false
  }

  if (
    input.dangerouslyDisableSandbox &&
    SandboxManager.areUnsandboxedCommandsAllowed()
  ) {
    return false
  }

  if (!input.command) {
    return false
  }

  if (containsExcludedCommand(input.command)) {
    return false
  }

  return true
}
```

This implementation is very important because it turns "whether to enable sandbox" from a simple global config into the combined result of three factors: "global toggle + single tool call parameter + excludedCommands".

### 3.2 Can Be Rewritten as the Following Pseudocode

```text
if sandbox itself is unavailable:
  don't enter sandbox

if current call explicitly requests sandbox to be disabled
  and policy allows executing unsandboxed commands:
  don't enter sandbox

if there is no current command:
  don't enter sandbox

if command matches excludedCommands:
  don't enter sandbox

otherwise:
  enter sandbox
```

### 3.3 `excludedCommands` is a "Convenience Feature", Not a Security Boundary

This is stated very plainly in the source code:

```ts
// NOTE: excludedCommands is a user-facing convenience feature, not a security boundary.
// It is not a security bug to be able to bypass excludedCommands — the sandbox permission
// system (which prompts users) is the actual security control.
```

This means:

- `excludedCommands` is not designed as a security control point
- It simply tells the system "don't automatically sandbox this type of command"
- The real security boundary is still the permission system and the sandbox runtime itself

This is also a very engineering-oriented design: users can grant compatibility exemptions for `bazel`, `docker`, or certain local test commands, but cannot treat it as a trusted security rule language.

### 3.4 How the Decision Result Enters the Execution Chain

[`src/tools/BashTool/BashTool.tsx`](../src/tools/BashTool/BashTool.tsx) ultimately passes this boolean to the shell execution layer:

```ts
const shellCommand = await exec(command, abortController.signal, 'bash', {
  timeout: timeoutMs,
  preventCwdChanges,
  shouldUseSandbox: shouldUseSandbox(input),
  shouldAutoBackground
})
```

At [`src/utils/Shell.ts`](../src/utils/Shell.ts), it actually wraps a runtime layer:

```ts
if (shouldUseSandbox) {
  commandString = await SandboxManager.wrapWithSandbox(
    commandString,
    sandboxBinShell,
    undefined,
    abortSignal,
  )
}
```

In other words:

- `BashTool` is only responsible for the decision
- `Shell.ts` is responsible for actually turning the command into a "command inside the sandbox"

This is a clear separation of concerns.

## 4. Step Two: How Claude Code Settings Are Translated into Sandbox Configuration

Related implementations:

- [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)

The core function here is `convertToSandboxRuntimeConfig()`. It is not a simple field mapping; it performs a layer of "semantic translation".

### 4.1 This Function Does Not Do Merge, but Semantic Reinterpretation

First, look at the source entry point:

```ts
export function convertToSandboxRuntimeConfig(
  settings: SettingsJson,
): SandboxRuntimeConfig {
  const permissions = settings.permissions || {}

  const allowedDomains: string[] = []
  const deniedDomains: string[] = []

  const allowWrite: string[] = ['.', getClaudeTempDir()]
  const denyWrite: string[] = []
  const denyRead: string[] = []
  const allowRead: string[] = []
```

Two things are already apparent here:

1. Both `permissions` and `sandbox.*` configuration sets are incorporated into the runtime config
2. The runtime has a set of built-in initial rules, not entirely dependent on user configuration

For example:

- `allowWrite` defaults to include `.` and the Claude temp dir
- The settings file path is forcibly added to `denyWrite`

### 4.2 Path Semantics Are Divided into Two Sets, Cannot Be Confused

This part is one of the most easily overlooked but actually most important implementation details in the current documentation.

The source code specifically writes two different parsing functions:

```ts
export function resolvePathPatternForSandbox(
  pattern: string,
  source: SettingSource,
): string

export function resolveSandboxFilesystemPath(
  pattern: string,
  source: SettingSource,
): string
```

They handle two types of paths respectively:

1. Paths in permission rules
2. Paths in `sandbox.filesystem.*`

The semantics of the two are different.

**Actual source code comments** (excerpted from [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)):

```ts
 * Claude Code uses special path prefixes in permission rules:
 * - `//path` → absolute from filesystem root
 * - `/path` → relative to settings file directory
```

And for `sandbox.filesystem.*`:

```ts
 * Unlike permission rules (Edit/Read), these settings use standard path semantics:
 * - `/path` → absolute path
 * - `~/path` → expanded to home directory
 * - `./path` or `path` → relative to settings file directory
```

This means:

- `permissions.allow = ["Edit(/foo)"]` has `/foo` relative to the settings root directory
- `sandbox.filesystem.allowWrite = ["/foo"]` has `/foo` as a true absolute path

If this point is not clarified, it's easy to misunderstand the entire sandbox behavior.

### 4.3 The Actual Construction Process of Filesystem Rules

The filesystem part of `convertToSandboxRuntimeConfig()` can be rewritten as the following pseudocode:

```text
Initialize:
  allowWrite = ['.', ClaudeTempDir]
  denyWrite = []
  denyRead = []
  allowRead = []

Built-in protection:
  Always deny writing settings.json / settings.local.json / managed settings drop-in
  Always deny writing .claude/skills
  Protect against both cwd / originalCwd

Git worktree compatibility:
  If currently in a worktree, add main repo path to allowWrite

add-dir compatibility:
  Inject additionalDirectories and session add-dir into allowWrite

Iterate over all setting sources:
  Extract Edit / Read rules from permissions.allow/deny
  Extract rules from sandbox.filesystem.allowWrite/denyWrite/allowRead/denyRead
  Resolve path semantics by source

Generate runtime config:
  filesystem = { allowWrite, denyWrite, allowRead, denyRead }
```

### 4.4 Original Function Snippet: Extracting Filesystem Rules from Permission Rules

```ts
for (const source of SETTING_SOURCES) {
  const sourceSettings = getSettingsForSource(source)

  if (sourceSettings?.permissions) {
    for (const ruleString of sourceSettings.permissions.allow || []) {
      const rule = permissionRuleValueFromString(ruleString)
      if (rule.toolName === FILE_EDIT_TOOL_NAME && rule.ruleContent) {
        allowWrite.push(
          resolvePathPatternForSandbox(rule.ruleContent, source),
        )
      }
    }

    for (const ruleString of sourceSettings.permissions.deny || []) {
      const rule = permissionRuleValueFromString(ruleString)
      if (rule.toolName === FILE_EDIT_TOOL_NAME && rule.ruleContent) {
        denyWrite.push(resolvePathPatternForSandbox(rule.ruleContent, source))
      }
      if (rule.toolName === FILE_READ_TOOL_NAME && rule.ruleContent) {
        denyRead.push(resolvePathPatternForSandbox(rule.ruleContent, source))
      }
    }
  }
}
```

The key point here is not "iterating and extracting rules", but:

- It does not just read merged settings; it processes each source individually via `SETTING_SOURCES`
- This is because path resolution depends on the source; `/foo` from different sources needs to map to different settings root directories

In other words, the source here is not metadata, but part of the path semantics.

### 4.5 Network Rules Are Not Independent Configuration, But Derived from `WebFetch` Permission Rules

The source code's logic for extracting network domains is also straightforward:

```ts
for (const ruleString of permissions.allow || []) {
  const rule = permissionRuleValueFromString(ruleString)
  if (
    rule.toolName === WEB_FETCH_TOOL_NAME &&
    rule.ruleContent?.startsWith('domain:')
  ) {
    allowedDomains.push(rule.ruleContent.substring('domain:'.length))
  }
}
```

This shows that Claude Code does not completely separate "network permissions" from "WebFetch permissions", but rather:

- Converts application-layer rules like `WebFetch(domain:example.com)`
- Into a network allowlist that the sandbox runtime can recognize

The result of this approach is that upper-layer tool permissions and underlying network isolation remain consistent, rather than each operating independently.

### 4.6 `allowManagedDomainsOnly` is a Stronger Policy Constraint

Related implementations:

- [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)
- [`src/components/permissions/SandboxPermissionRequest.tsx`](../src/components/permissions/SandboxPermissionRequest.tsx)

The source code specifically provides:

```ts
export function shouldAllowManagedSandboxDomainsOnly(): boolean {
  return (
    getSettingsForSource('policySettings')?.sandbox?.network
      ?.allowManagedDomainsOnly === true
  )
}
```

Its meaning is not "prefer managed domains by default", but:

- Once the policy enables this option
- The sandbox's network allowlisting can only come from managed / policy sources
- The runtime ask callback will also be wrapped to directly deny temporary allowlisting

The initialization implementation is very clear:

```ts
const wrappedCallback: SandboxAskCallback | undefined = sandboxAskCallback
  ? async (hostPattern: NetworkHostPattern) => {
      if (shouldAllowManagedSandboxDomainsOnly()) {
        return false
      }
      return sandboxAskCallback(hostPattern)
    }
  : undefined
```

This effectively blocks "temporary allowance at the user interaction layer".

## 5. Step Three: What Built-in Escape Protections Exist in the Code

Related implementations:

- [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)
- [`src/utils/Shell.ts`](../src/utils/Shell.ts)

If you only understand the sandbox as "restricting read/write directories", you would underestimate the security strength of this implementation. There are multiple places that are clearly patches targeting real attack paths.

### 5.1 Settings Files and `.claude/skills` Are Forcibly Added to denyWrite

This section in the source code is very critical:

```ts
const settingsPaths = SETTING_SOURCES.map(source =>
  getSettingsFilePathForSource(source),
).filter((p): p is string => p !== undefined)
denyWrite.push(...settingsPaths)
denyWrite.push(getManagedSettingsDropInDir())

denyWrite.push(resolve(originalCwd, '.claude', 'skills'))
if (cwd !== originalCwd) {
  denyWrite.push(resolve(cwd, '.claude', 'skills'))
}
```

This means the system does not just protect "code files", but protects Claude's own control plane:

- Settings files cannot be secretly modified by commands inside the sandbox
- `.claude/skills` cannot be poisoned either

Why is `.claude/skills` worth special protection? The source code comment explains clearly:

```ts
// Skills have the same privilege level
// (auto-discovered, auto-loaded, full Claude capabilities)
```

In other words, once writing to the skills directory is allowed, it essentially allows commands to inject high-privilege capabilities that will be automatically loaded in the future.

### 5.2 Specialized Cleanup for Git Bare Repo Escape

This is the most representative "real-world attack surface protection" in the entire sandbox system.

Source code comment:

```ts
// SECURITY: Git's is_git_directory() treats cwd as a bare repo if it has
// HEAD + objects/ + refs/. An attacker planting these (plus a config with
// core.fsmonitor) escapes the sandbox when Claude's unsandboxed git runs.
```

This comment almost writes out the attack chain:

1. A command inside the sandbox plants fake bare repo files in cwd
2. Later, Claude executes some git commands on the host without sandbox
3. Git treats the current directory as a repo
4. Malicious configurations like `core.fsmonitor` are consumed by the host's git
5. Escalation from "writing files inside the sandbox" to "executing malicious logic on the host"

The corresponding implementation is divided into two steps:

Step one, during config construction, try to add existing critical paths directly to `denyWrite`:

```ts
const bareGitRepoFiles = ['HEAD', 'objects', 'refs', 'hooks', 'config']
for (const dir of cwd === originalCwd ? [originalCwd] : [originalCwd, cwd]) {
  for (const gitFile of bareGitRepoFiles) {
    const p = resolve(dir, gitFile)
    try {
      statSync(p)
      denyWrite.push(p)
    } catch {
      bareGitRepoScrubPaths.push(p)
    }
  }
}
```

Step two, for paths that "didn't exist at config time but were planted after execution", synchronously clean them up after command execution:

```ts
function scrubBareGitRepoFiles(): void {
  for (const p of bareGitRepoScrubPaths) {
    try {
      rmSync(p, { recursive: true })
    } catch {
      // ENOENT is the expected common case
    }
  }
}
```

And this cleanup is hooked into `cleanupAfterCommand()`:

```ts
cleanupAfterCommand: (): void => {
  BaseSandboxManager.cleanupAfterCommand()
  scrubBareGitRepoFiles()
}
```

Then triggered by [`src/utils/Shell.ts`](../src/utils/Shell.ts) when the command finishes:

```ts
if (shouldUseSandbox) {
  SandboxManager.cleanupAfterCommand()
}
```

This shows that the sandbox's security boundary is not "done once inside the isolated environment", but:

- Before execution: construct restrictions
- During execution: runtime isolation
- After execution: host-level residual cleanup

This is protection from a complete attack chain perspective, not a single-invocation perspective.

## 6. Step Four: How the Sandbox and Permission System Are Coupled

Related implementations:

- [`src/tools/BashTool/bashPermissions.ts`](../src/tools/BashTool/bashPermissions.ts)
- [`src/utils/permissions/pathValidation.ts`](../src/utils/permissions/pathValidation.ts)

This layer is the most easily misunderstood: many people assume "since it's already in the sandbox, there's no need for a permission prompt." The source code does not implement it that way.

### 6.1 `autoAllowBashIfSandboxed` Does Not Blindly Allow

The main logic of [`src/tools/BashTool/bashPermissions.ts`](../src/tools/BashTool/bashPermissions.ts) has this section:

```ts
if (
  SandboxManager.isSandboxingEnabled() &&
  SandboxManager.isAutoAllowBashIfSandboxedEnabled() &&
  shouldUseSandbox(input)
) {
  const sandboxAutoAllowResult = checkSandboxAutoAllow(
    input,
    appState.toolPermissionContext,
  )
  if (sandboxAutoAllowResult.behavior !== 'passthrough') {
    return sandboxAutoAllowResult
  }
}
```

Note the meaning here:

- Only under the triple condition of "sandbox enabled + autoAllowBashIfSandboxed enabled + current command will actually enter sandbox"
- Will it enter the auto-allow branch

### 6.2 Before Auto-Allow, It Still Respects Explicit Deny / Ask

The implementation of `checkSandboxAutoAllow()` is very clear:

```ts
// Check for explicit deny/ask rules on the full command
const { matchingDenyRules, matchingAskRules } = matchingRulesForInput(...)

if (matchingDenyRules[0] !== undefined) {
  return { behavior: 'deny', ... }
}
```

And it also specifically handles compound commands:

```ts
const subcommands = splitCommand(command)
if (subcommands.length > 1) {
  for (const sub of subcommands) {
    const subResult = matchingRulesForInput(...)
    if (subResult.matchingDenyRules[0] !== undefined) {
      return { behavior: 'deny', ... }
    }
    firstAskRule ??= subResult.matchingAskRules[0]
  }
}
```

This reflects a mature security decision order:

1. First check if the full command hits an explicit deny
2. Then check if each subcommand of a compound command hits deny / ask
3. Only when there are no explicit rules, return:

```ts
return {
  behavior: 'allow',
  decisionReason: {
    type: 'other',
    reason: 'Auto-allowed with sandbox (autoAllowBashIfSandboxed enabled)',
  },
}
```

In other words, the sandbox's auto-allow is merely "default allow", not "override existing deny rules".

### 6.3 File Path Permissions Also Read the Sandbox Allowlist

[`src/utils/permissions/pathValidation.ts`](../src/utils/permissions/pathValidation.ts) has a key function:

```ts
export function isPathInSandboxWriteAllowlist(resolvedPath: string): boolean {
  if (!SandboxManager.isSandboxingEnabled()) {
    return false
  }
  const { allowOnly, denyWithinAllow } = SandboxManager.getFsWriteConfig()
  ...
}
```

Then, in `isPathAllowed()`, there is a section specifically treating the sandbox write allowlist as an additional auto-allow condition:

```ts
if (
  operationType !== 'read' &&
  !isInWorkingDir &&
  isPathInSandboxWriteAllowlist(resolvedPath)
) {
  return {
    allowed: true,
    decisionReason: {
      type: 'other',
      reason: 'Path is in sandbox write allowlist',
    },
  }
}
```

This implementation is very interesting because it shows:

- Sandbox configuration not only affects "whether Bash is isolated"
- But also inversely affects the application-layer path permission decisions

The direct benefit of this approach is:

- The user has already explicitly allowed `/tmp/claude/` in the sandbox configuration
- So commands like `echo foo > /tmp/claude/x.txt` don't need an additional permission prompt

This is a design where "underlying isolation state feeds back to upper-layer interaction".

## 7. Step Five: How Initialization, Dependency Detection, and Hot Update Work

Related implementations:

- [`src/utils/sandbox/sandbox-adapter.ts`](../src/utils/sandbox/sandbox-adapter.ts)
- [`src/components/sandbox/SandboxDoctorSection.tsx`](../src/components/sandbox/SandboxDoctorSection.tsx)

### 7.1 Sandbox Is Not Simply Checking `sandbox.enabled`

The source code's `isSandboxingEnabled()`:

```ts
function isSandboxingEnabled(): boolean {
  if (!isSupportedPlatform()) {
    return false
  }

  if (checkDependencies().errors.length > 0) {
    return false
  }

  if (!isPlatformInEnabledList()) {
    return false
  }

  return getSandboxEnabledSetting()
}
```

This means "settings wrote `sandbox.enabled: true`" and "actually running in sandbox mode" are not the same thing. In between, there are also:

- Whether the current platform is supported
- Whether runtime dependencies are complete
- Whether it is restricted by the `enabledPlatforms` list

### 7.2 `failIfUnavailable` Reflects a Strict Security Mode

The source code has:

```ts
function isSandboxRequired(): boolean {
  const settings = getSettings_DEPRECATED()
  return (
    getSandboxEnabledSetting() &&
    (settings?.sandbox?.failIfUnavailable ?? false)
  )
}
```

This shows:

- By default, when sandbox is unavailable, it can degrade gracefully
- But if the user explicitly requires `failIfUnavailable`, then sandbox upgrades from "enhanced security" to "mandatory condition"

### 7.3 Clearly Indicates "Why Sandbox Is Not Actually Enabled"

This part is also done very carefully.

The source code's `getSandboxUnavailableReason()` does not just return `true/false`, but gives specific reasons, such as:

- Platform not supported
- WSL1 instead of WSL2
- Missing dependencies
- Current platform not in the `enabledPlatforms` list

On the UI side, [`src/components/sandbox/SandboxDoctorSection.tsx`](../src/components/sandbox/SandboxDoctorSection.tsx) displays dependency errors and warnings:

```ts
const depCheck = SandboxManager.checkDependencies()
const hasErrors = depCheck.errors.length > 0
const hasWarnings = depCheck.warnings.length > 0
```

This is not just a "UX optimization"; it is avoiding a very dangerous situation:

- The user thinks they have enabled sandbox
- But in reality, dependencies are missing and commands never enter the sandbox
- Yet the system does not tell them

The source code comment directly calls this a security footgun, which is an accurate assessment.

### 7.4 Configuration Hot Update is Not Restart-Based, but Runtime-Level Update

Key code during initialization:

```ts
settingsSubscriptionCleanup = settingsChangeDetector.subscribe(() => {
  const settings = getSettings_DEPRECATED()
  const newConfig = convertToSandboxRuntimeConfig(settings)
  BaseSandboxManager.updateConfig(newConfig)
})
```

And the explicit refresh function:

```ts
function refreshConfig(): void {
  if (!isSandboxingEnabled()) return
  const settings = getSettings_DEPRECATED()
  const newConfig = convertToSandboxRuntimeConfig(settings)
  BaseSandboxManager.updateConfig(newConfig)
}
```

This shows that the sandbox config is not assembled once, but can be updated within a session.

In other words, Claude Code does not require:

- Changing settings
- Exiting the CLI
- Restarting for changes to take effect

It allows real-time tightening/loosening of configuration and synchronizes changes to the underlying runtime.

## 8. Step Six: How User Interaction Is Presented During Network Unauthorized Access

Related implementations:

- [`src/components/permissions/SandboxPermissionRequest.tsx`](../src/components/permissions/SandboxPermissionRequest.tsx)

The sandbox manages not only the filesystem but also the network. For network access beyond the allowlist, there is a separate permission dialog on the UI side.

Its title is very straightforward:

```ts
<PermissionDialog title="Network request outside of sandbox">
```

The available options include:

- `Yes`
- `Yes, and don't ask again for <host>`
- `No, and tell Claude what to do differently`

But if `allowManagedDomainsOnly` is enabled, the "don't ask again" option is removed:

```ts
const managedDomainsOnly = shouldAllowManagedSandboxDomainsOnly()
...
!managedDomainsOnly ? [yes-dont-ask-again] : []
```

This further validates the earlier assessment:

- Policy does not only affect the runtime config
- It also constrains the choices available to the user on the UI

## 9. A More Accurate Understanding: What Role Does the Sandbox Play in This Project

At this point, a more accurate definition can be given:

### 9.1 It Is Not a Docker-Style "Black Box Container"

The sandbox in this project is more like a "policy-based isolation layer built around the Bash execution chain", characterized by:

- Directly generating runtime config from Claude Code's settings / permissions
- Allowing linkage with the application-layer permission system
- Having post-processing logic specifically designed for CLI workflows, such as bare repo scrub
- Feeding the sandbox's allowlist back to path validation

This is completely different from "spinning up a container and running commands".

### 9.2 It Is Not the Only Security Boundary

The source code repeatedly states this:

- `excludedCommands` is not a security boundary
- Auto-allow still respects explicit deny / ask
- Path validation and permission rules are still preserved

Therefore, a more accurate statement is:

- The sandbox is responsible for OS-level isolation
- The permission system is responsible for application-layer rule expression and user confirmation
- The two reference each other and complement each other

## 10. Chapter Summary

The core conclusions of this chapter are four:

1. The entry point of the sandbox is not in `sandbox-adapter.ts`, but in `shouldUseSandbox()` making routing decisions for each Bash command
2. The essence of `convertToSandboxRuntimeConfig()` is not field mapping, but translating Claude Code's own permission semantics into runtime filesystem and network restrictions
3. `bashPermissions.ts` does not treat "entering sandbox" as a free pass, but first respects explicit deny / ask, then proceeds with auto-allow
4. This implementation explicitly considers real escape paths, such as settings poisoning, skills injection, Git bare repo residual escape, and performs host-level cleanup after execution

Therefore, Claude Code's sandbox is not a peripheral security plugin, but an execution security infrastructure deeply coupled with Bash, permissions, settings, UI, and cleanup logic.
