# Claude Code Source Code Analysis

## Background

At 4:23 AM EST on March 31, 2026, security researcher [Chaofan Shou](https://x.com/Fried_rice) posted a [tweet](https://x.com/Fried_rice/status/2038894956459290963?s=20) on X, discovering that in the Claude Code package published by Anthropic to npm, the official release did not delete source map files. This means Claude Code's complete TypeScript source code was fully leaked, containing 1,902 source files and 513,237 lines of code.

## Directory Structure

This repository is a collection of static analysis documents for the leaked Claude Code source code.

```text
claude-code-analysis/
├── README.md                        # This document (main index)
├── analysis/                        # Main analysis document directory
├── src.zip                          # Source code archive
└── src/                             # Source code (for analysis reference only)
```

## Overview

The analysis documents in this directory are compiled based on static reading of the `src/` source code, mainly exploring the following system design issues:

1. Software architecture design and program startup path.
2. Security analysis: Collection and usage of user information, potential security risks and preventive measures.
3. Agent Memory mechanism (multi-level storage and Session compression logic) and implementation details.
4. Capability extension mechanisms (Skills extension, Tool Call mechanism, MCP integration) technical implementation and operation methods.
5. Isolation mechanism: Design and implementation of Sandbox to prevent local operational risks.
6. Internal program architecture design and module characteristics.
7. UI breakdown: Component composition of the TUI console in `src/components/`.
8. Competitive comparison: Functional and architectural difference analysis with tools such as `Codex`, `Gemini CLI`, `Aider`, `Cursor`.
9. Source code evidence vs. external public information comparison.

Main system features:

- This project is a local code Agent platform with independent execution logic and closed-loop environment design.
- Core functionality includes a unified execution kernel, layered Memory system, and external extension support based on MCP and Skills.
- At the architectural defense level, the system employs local Sandbox isolation and Tool Call permission control measures.
- At the privacy level, the main channels involving data outflow include model context interaction, local persistent storage, and external component remote communication.

## Architecture at a Glance

```text
+---------------------------+
| CLI / Multiple Entrypoints|
| entrypoints/cli.tsx       |
| main.tsx                  |
+---------------------------+
            |
            v
+---------------------------+
| Init & Runtime Environment|
| init.ts / setup.ts        |
+---------------------------+
      |                |
      v                v
+----------------+   +---------------------------+
| Command &      |   | TUI / REPL Workbench      |
| Control Plane  |   | App / REPL / Messages     |
| commands.ts    |-->| / PromptInput             |
| PromptInput... |   +---------------------------+
+----------------+               |
                                 v
                      +---------------------------+
                      | Query / Agent Execution   |
                      | Kernel                    |
                      | query.ts / QueryEngine.ts |
                      +---------------------------+
                        |           |           |
                        v           v           v
              +---------------+ +-------------------+ +----------------------+
              | Tool/Perm     | | Transcript/Memory | | Platform Extension   |
              | Tool.ts       | | sessionStorage    | | Layer                |
              | orchestration | | memdir/SessionMem | | MCP/Plugin/Remote/   |
              +---------------+ +-------------------+ | Swarm                |
                        \______________   |   _______+----------------------+
                                       \  |  /
                                        \ v /
                              Flow back to execution kernel
```

## Chapter Index

### Part 1: Overall Architecture

- [Chapter 1: Software Architecture and Program Entry](./analysis/01-architecture-overview.md)

### Part 2: Security Analysis

- [Chapter 2 §1: User Information Collection and Usage — What Information the System Touches and How It's Used](./analysis/02-security-analysis.md#section-1-user-information-collection-and-usage)
- [Chapter 2 §2: Software Code Security Analysis — Risk Points and Attack Paths in the Source Code](./analysis/02-security-analysis.md#section-2-software-code-security-analysis)
- [Chapter 2 §3: Preventive Security Measures — Multi-layered Defenses Built by the System to Protect the Host](./analysis/02-security-analysis.md#section-3-preventive-security-measures)

### Part 3: Core Mechanisms

- [Chapter 3: How Agent Memory Works](./analysis/04-agent-memory.md)
- [Chapter 4: Skills Technical Implementation Details and Operation](./analysis/04c-skills-implementation.md)
- [Chapter 5: Tool Call Mechanism Implementation Details](./analysis/04b-tool-call-implementation.md)
- [Chapter 6: MCP Technical Implementation Details and Operation Mechanism](./analysis/04d-mcp-implementation.md)
- [Chapter 7: Sandbox Technical Implementation Details and Operation Mechanism](./analysis/04e-sandbox-implementation.md)
- [Chapter 8: Context Management Implementation Details](./analysis/04f-context-management.md)
- [Chapter 9: Prompt Management Mechanism and Implementation Details](./analysis/04g-prompt-management.md)
- [Chapter 10: Multi-Agent Mechanism and Implementation Details](./analysis/04h-multi-agent.md)
- [Chapter 11: Session Storage / Transcript / Resume Persistence Mechanism](./analysis/04i-session-storage-resume.md)

### Part 4: Program Architecture & Highlights

- [Chapter 12: Program Architecture and Highlights](./analysis/05-differentiators-and-comparison.md)

### Part 5: Extended Analysis

- [Chapter 13: Additional Exploration and Supplementary Findings](./analysis/06-extra-findings.md)
- [Chapter 14: Hidden Commands, Feature Flags and Easter Eggs](./analysis/11-hidden-features-and-easter-eggs.md)
- [Chapter 15: Negative Keyword Detection and Frustration Signal Mechanism](./analysis/06b-negative-keyword-analysis.md)

### Part 6: Component System Details

- [Component Details (1): Component Overview, Layering and Dependency Backbone](./analysis/components/01-component-architecture-overview.md)
- [Component Details (2): Core Interaction Components and Message/Input Main Pipeline](./analysis/components/02-core-interaction-components.md)
- [Component Details (3): Platform Capability Components and Control Plane Implementation](./analysis/components/03-platform-components.md)
- [Component Details (4): Component Index, Long-tail Components and Directory Mapping](./analysis/components/04-component-index.md)
- [Component Details (5): Core Component Function-level Implementation Walkthrough](./analysis/components/05-function-level-core-walkthrough.md)
- [Component Details (6): Platform Control Plane Function-level Implementation Walkthrough](./analysis/components/06-function-level-platform-walkthrough.md)
- [Component Details (7): Leaf Components and Sub-function Implementation Walkthrough](./analysis/components/07-function-level-leaf-walkthrough.md)

### Part 7: Competitive Comparison

- [Chapter 16: Competitive Comparison](./analysis/08-competitive-comparison.md)
- [Appendix A: External Comparison References](./analysis/08-reference-comparison-sources.md)

### Part 8: Evidence & References

- [Chapter 17: Code Evidence Index](./analysis/07-code-evidence-index.md)
- [Appendix B: src Detailed File Tree (with File Descriptions)](./analysis/10-src-file-tree.md)

### Part 9: Summary

- [Chapter 18: Conclusion and Summary](./analysis/09-final-summary.md)

---

## 声明

> **本项目仅供学术研究与技术学习使用。**
>
> 本仓库所有内容均为对公开信息的二次整理与分析。Claude Code 的所有权利归 [Anthropic](https://www.anthropic.com) 所有。
>
> 1. **无侵权意图**：本分析文档基于已在公共互联网上广泛流传的信息整理撰写，目的在于帮助开发者了解 AI Coding Agent 的安全边界、隐私设计与工程架构，属于正当的技术研究行为。
> 2. **禁止商业使用**：禁止将本仓库内容用于任何商业目的，或以此绕过、破坏 Claude Code 的安全机制与用户协议。
> 3. **免责声明**：本仓库作者不对因参考本文档而产生的任何直接或间接损失负责。如有任何合规疑虑，请以 Anthropic 官方文档与用户协议为准。
> 4. **如需删除**：若 Anthropic 认为本仓库内容侵犯其合法权益，请通过 Issue 联系，我们将在核实后第一时间进行删除处理。


## Star History

<a href="https://www.star-history.com/?repos=liuup%2Fclaude-code-analysis&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=liuup/claude-code-analysis&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=liuup/claude-code-analysis&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=liuup/claude-code-analysis&type=date&legend=top-left" />
 </picture>
</a>
