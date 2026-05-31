# Chapter 5: Skills Mechanism Implementation Details and Operation

[Back to Table of Contents](../README.md)

---

## 1. Chapter Guide and TL;DR

Claude Code achieves platform-level extensibility through a **Skills mechanism**, whose core is combining Markdown files + YAML metadata + optional Bash scripts, providing a low-barrier way to inject domain capabilities into the AI.

Main source files:
- [`src/skills/loadSkillsDir.ts`](../src/skills/loadSkillsDir.ts) — Skill discovery, parsing, instantiation
- [`src/skills/bundledSkills.ts`](../src/skills/bundledSkills.ts) — Built-in bundled skills
- [`src/utils/promptShellExecution.ts`](../src/utils/promptShellExecution.ts) — Inline Shell execution in prompts

---

## 2. Three Sources of Skills

| Type | Source | Key `loadedFrom` Value |
|------|-------|------------------------|
| **File-based (filesystem skills)** | Local `.claude/skills/` directory and variants | `'skills'` / `'commands_DEPRECATED'` |
| **Bundled (built-in skills)** | Hardcoded in source, packaged by build process | `'bundled'` |
| **MCP Skills (protocol-mapped skills)** | Tool capabilities from MCP Server | `'mcp'` |

---

## 3. Skill Discovery: `getSkillDirCommands()`

**Actual source code** ([`src/skills/loadSkillsDir.ts:638`](../src/skills/loadSkillsDir.ts)):

```typescript
export const getSkillDirCommands = memoize(
  async (cwd: string): Promise<Command[]> => {
    const userSkillsDir    = join(getClaudeConfigHomeDir(), 'skills')  // ~/.claude/skills
    const managedSkillsDir = join(getManagedFilePath(), '.claude', 'skills')  // Policy-managed directory
    const projectSkillsDirs = getProjectDirsUpToHome('skills', cwd)   // Crawl up from project directory

    // --bare mode: skip auto-discovery, only load paths explicitly specified with --add-dir
    if (isBareMode()) {
      return additionalDirs.flatMap(dir =>
        loadSkillsFromSkillsDir(join(dir, '.claude', 'skills'), 'projectSettings')
      )
    }

    // Normal mode: load all sources in parallel
    const [managedSkills, userSkills, projectSkillsNested, additionalSkillsNested, legacyCommands] =
      await Promise.all([
        loadSkillsFromSkillsDir(managedSkillsDir, 'policySettings'),    // Policy-level skills
        loadSkillsFromSkillsDir(userSkillsDir,    'userSettings'),      // User-level skills
        Promise.all(projectSkillsDirs.map(dir =>
          loadSkillsFromSkillsDir(dir, 'projectSettings'))),            // Project-level skills (multi-directory)
        Promise.all(additionalDirs.map(dir =>
          loadSkillsFromSkillsDir(join(dir, '.claude', 'skills'), 'projectSettings'))), // --add-dir
        loadSkillsFromCommandsDir(cwd),                                 // Legacy /commands/ directory
      ])

    // Merge + deduplicate (inode level, prevent symlink duplicates)
    return deduplicateByRealpath([
      ...managedSkills, ...userSkills,
      ...projectSkillsNested.flat(),
      ...additionalSkillsNested.flat(),
      ...legacyCommands,
    ])
  }
)
```

**Key design points**:
- Wrapped with `memoize` — discovered only once per `cwd`, result cached
- `Promise.all` parallel — all sources read simultaneously
- Deduplication uses `fs.realpath` to get inode-level real paths, preventing symlinks from causing duplicate loads

---

## 4. Skill Parsing: Frontmatter Fields

Each `SKILL.md` file's YAML frontmatter is parsed via [`parseSkillFrontmatterFields()`](../src/skills/loadSkillsDir.ts):

```typescript
// src/skills/loadSkillsDir.ts:185
export function parseSkillFrontmatterFields(frontmatter: FrontmatterData): {
  name?:              string
  description?:       string | string[]
  when_to_use?:       string
  allowed_tools?:     string[]
  model?:             string
  effort?:            EffortValue     // Task estimation: 'low' | 'medium' | 'high'
  user_invocable?:    boolean         // false = only callable by the model internally, not appearing in REPL command list
  paths?:             string[]        // Conditional skill trigger paths (auto-activate on file change)
  version?:           string
  context?:           'inline' | 'fork'
  agent?:             string          // Bind to a specific agent type
  shell?:             'bash' | 'powershell'
} { ... }
```

**The `paths` field is the core magic**: Skills that declare `paths` are **Conditional Skills** — when the user operates on or modifies a file matching the glob pattern, the skill is automatically activated and injected into the context. This is a precise Hook subscription pattern.

---

## 5. Skill Instantiation: `createSkillCommand()`

**Actual source code** ([`src/skills/loadSkillsDir.ts:270`](../src/skills/loadSkillsDir.ts), simplified excerpt):

```typescript
export function createSkillCommand({
  skillName, markdownContent, allowedTools,
  loadedFrom, baseDir, paths, shell, ...rest
}: SkillCommandOptions): Command {
  return {
    type: 'prompt',
    name: skillName,
    paths,   // Conditional skill trigger paths
    isHidden: !userInvocable,
    // ...

    // Core execution logic: getPromptForCommand triggers when the model invokes the skill
    async getPromptForCommand(args, toolUseContext) {
      let finalContent = markdownContent  // Raw Markdown content

      // 1. Expand CLI argument placeholders
      finalContent = substituteArguments(finalContent, args, true, argumentNames)

      // 2. Expand built-in variables (skill directory, session ID)
      if (baseDir) {
        const skillDir = baseDir.replace(/\\/g, '/')  // Windows path normalization
        finalContent = finalContent.replace(/\${CLAUDE_SKILL_DIR}/g, skillDir)
      }
      finalContent = finalContent.replace(/\${CLAUDE_SESSION_ID}/g, getSessionId())

      // 3. Execute prompt-embedded Shell commands (only for trusted sources, MCP sources skipped)
      if (loadedFrom !== 'mcp') {
        finalContent = await executeShellCommandsInPrompt(
          finalContent, toolUseContext, `/${skillName}`, shell
        )
      }

      return [{ type: 'text', text: finalContent }]
    },
  }
}
```

---

## 6. Inline Shell Execution: `executeShellCommandsInPrompt()`

This is the most ingenious feature of the Skills system: Shell commands can be embedded in the Markdown content. These commands are executed on the host machine before the skill is invoked, and the output replaces the Markdown text.

**Syntax example** (in `.claude/skills/my-skill/SKILL.md`):

```markdown
---
name: git-status-helper
description: View current Git status and provide suggestions
---

Current branch information:
!`git log --oneline -5`

Uncommitted changes:
!`git status --short`

Please analyze the current code state based on the above information.
```

**Actual source code** ([`src/utils/promptShellExecution.ts:69`](../src/utils/promptShellExecution.ts)):

```typescript
export async function executeShellCommandsInPrompt(
  text: string,
  context: ToolUseContext,
  slashCommandName: string,
  shell?: FrontmatterShell,
): Promise<string> {
  let result = text

  // Select execution tool: default is BashTool, frontmatter can specify PowerShell
  const shellTool = shell === 'powershell' && isPowerShellToolEnabled()
    ? getPowerShellTool()
    : BashTool

  // Scan two syntaxes: !`command` (inline) and ```!\ncommand\n``` (code block)
  const blockMatches  = text.matchAll(BLOCK_PATTERN)
  const inlineMatches = text.includes('!`') ? text.matchAll(INLINE_PATTERN) : []

  await Promise.all(
    [...blockMatches, ...inlineMatches].map(async match => {
      const command = match[1]?.trim()
      if (!command) return

      // 1. Permission check (goes through the same ToolPermission flow)
      const permissionResult = await hasPermissionsToUseTool(
        shellTool, { command }, context,
        createAssistantMessage({ content: [] }), '',
      )
      if (permissionResult.behavior !== 'allow') {
        throw new MalformedCommandError(`Permission denied: ${permissionResult.message}`)
      }

      // 2. Execute Shell command
      const { data } = await shellTool.call({ command }, context)

      // 3. Extract output and replace the original pattern
      const output = typeof toolResultBlock.content === 'string'
        ? toolResultBlock.content
        : formatBashOutput(data.stdout, data.stderr)

      // Note: Use function form to replace, preventing $& and other special replacement symbols from being contaminated by PowerShell output
      result = result.replace(match[0], () => output)
    })
  )

  return result
}
```

**Security cutoff**: The check `loadedFrom !== 'mcp'` is extremely critical — skills from MCP Server do not execute embedded Shell commands, preventing malicious remote servers from injecting RCE (Remote Code Execution) attacks via MCP. At the same time, all commands go through `hasPermissionsToUseTool` before execution, adhering to the same permission system.

---

## 7. Skill Loading Full Process Summary

```text
User directory / Project directory /.claude/skills/<skill-name>/SKILL.md
        │
        ▼
getSkillDirCommands(cwd)           ← Scan all skill directories in parallel, results memoized
        │
        ▼
loadSkillsFromSkillsDir(basePath)  ← Read directory, filter SKILL.md files
        │
        ▼
parseFrontmatter(content)          ← Parse YAML metadata
parseSkillFrontmatterFields(fm)    ← Extract name/paths/model/effort/... fields
        │
        ▼
createSkillCommand(fields)         ← Instantiate as Command object, plug into command system
        │
        ▼  (User invokes /<skill-name> or model selects autonomously)
getPromptForCommand(args, ctx)
  ├── substituteArguments()        ← Expand CLI parameters
  ├── Expand ${CLAUDE_SKILL_DIR}   ← Built-in variable substitution
  └── executeShellCommandsInPrompt() ← Execute embedded Shell (trusted sources only)
        │
        ▼
Final Prompt returned to the model (with real-time system state)
```

---

## 8. Design Summary

| Feature | Implementation |
|---------|---------------|
| Low-barrier extension | Markdown + YAML, no TypeScript required |
| Real-time system context | `!`command`` embedded Shell, prompt carries real environment information |
| Precise conditional triggering | `paths` field subscribes to file change Hooks, preventing cognitive overload |
| Security isolation | MCP sources skip Shell execution, all commands go through unified permission system |
| Composable | File-based / Bundled / MCP — three sources unified into `Command` objects |
