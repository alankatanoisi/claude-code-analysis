# Chapter 14: Hidden Commands, Feature Flags, and Easter Eggs

[Back to Table of Contents](../README.md)

[Previous Chapter: Deep Findings and Edge Case Analysis](./06-extra-findings.md)

## 1. Chapter Guide

The preceding chapters focused more on backbone architecture, memory, component systems, and platform capabilities. This chapter specifically answers another question:

Beyond the explicitly surfaced features, what "unpublished capabilities, internal version differences, experimental toggles, and brand easter eggs" are hidden in this project?

My conclusion is: this codebase is not simply "writing TODOs that might be used later." It clearly contains:

- A layer of compilation-time branching between internal and external builds.
- A layer of compile-time toggle system heavily using `feature(...)`.
- A layer of hidden commands already wired into the main program.
- A layer of pure `stub` placeholder commands.
- A layer of well-productized brand personification capabilities, e.g., `buddy`, `Clawd`, `stickers`, `passes`.

## 2. First Look at the Overall Mechanism: How "Hidden Capabilities" Are Concealed

There are three core mechanisms:

1. `process.env.USER_TYPE === 'ant'` — internal build identity check.
2. `feature('...')` — `bun:bundle` compile-time toggles.
3. `isHidden` / `isEnabled` in command objects.

Evidence is found in:

- [`src/commands.ts`](../src/commands.ts)
- [`src/types/command.ts`](../src/types/command.ts)
- [`src/utils/undercover.ts`](../src/utils/undercover.ts)

This can be summarized in a plain text diagram:

```text
Source capabilities
    |
    +-- Compile-time branching
    |      |
    |      +-- USER_TYPE === ant
    |      |      -> Injects internal only commands
    |      |
    |      +-- feature('...')
    |             -> Determines whether to compile command/module into output
    |
    +-- Runtime branching
           |
           +-- isEnabled()
           |      -> Depends on account type, platform, experiment gate, env vars
           |
           +-- isHidden
                  -> Even if present, doesn't appear in help / typeahead
```

The command system itself explicitly states that `isHidden` means "whether to hide from typeahead/help" — see [`src/types/command.ts`](../src/types/command.ts).

## 3. Hidden Commands Divided into Three Layers

### 3.1 Internal-Only Commands

`commands.ts` has a very direct list: `INTERNAL_ONLY_COMMANDS`. The comment is also very straightforward, called "Commands that get eliminated from the external build" — see [`src/commands.ts#L224`](../src/commands.ts#L224).

This list includes:

- `backfillSessions`
- `breakCache`
- `bughunter`
- `commit`
- `commitPushPr`
- `ctx_viz`
- `goodClaude`
- `issue`
- `initVerifiers`
- `mockLimits`
- `bridgeKick`
- `version`
- `resetLimits`
- `onboarding`
- `share`
- `summary`
- `teleport`
- `antTrace`
- `perfIssue`
- `env`
- `oauthRefresh`
- `debugToolCall`
- `agentsPlatform`
- `autofixPr`

Among these, another batch depends on `feature(...)` or internal identity to be loaded, such as:

- `ultraplan`
- `subscribePr`
- `agentsPlatform`

See corresponding code at [`src/commands.ts#L48`](../src/commands.ts#L48), [`src/commands.ts#L62`](../src/commands.ts#L62), [`src/commands.ts#L225`](../src/commands.ts#L225).

This shows that the project does not "happen to have internal scripts left in the code," but maintains internal commands as first-class citizens, merely stripped in external builds.

### 3.2 Hidden but Still Real Commands

There is another category that is not a `stub`, but a proper command deliberately hidden from help.

Typical examples:

- [`heapdump`](../src/commands/heapdump/index.ts): Description is "Dump the JS heap to ~/Desktop", but `isHidden: true`, see [`src/commands/heapdump/index.ts#L3`](../src/commands/heapdump/index.ts#L3)
- [`rate-limit-options`](../src/commands/rate-limit-options/index.ts): Comment directly says "Hidden from help - only used internally", see [`src/commands/rate-limit-options/index.ts#L15`](../src/commands/rate-limit-options/index.ts#L15)
- [`output-style`](../src/commands/output-style/index.ts): Deprecated but still retains hidden entry, see [`src/commands/output-style/index.ts#L3`](../src/commands/output-style/index.ts#L3)
- [`thinkback-play`](../src/commands/thinkback-play/index.ts): Comment states "Hidden command that just plays the animation", called by thinkback skill after generation completes, see [`src/commands/thinkback-play/index.ts#L4`](../src/commands/thinkback-play/index.ts#L4)

These commands are more like "internal workflow nodes" or "debug/transition compatibility entries," not completely unimplemented functionality.

### 3.3 Pure Stub Placeholder Commands

Another category is truly just placeholders. Many command directories contain only one line:

```js
export default { isEnabled: () => false, isHidden: true, name: 'stub' };
```

Typical files include:

- [`src/commands/good-claude/index.js`](../src/commands/good-claude/index.js)
- [`src/commands/share/index.js`](../src/commands/share/index.js)
- [`src/commands/summary/index.js`](../src/commands/summary/index.js)
- [`src/commands/onboarding/index.js`](../src/commands/onboarding/index.js)
- [`src/commands/bughunter/index.js`](../src/commands/bughunter/index.js)
- [`src/commands/oauth-refresh/index.js`](../src/commands/oauth-refresh/index.js)
- [`src/commands/ctx_viz/index.js`](../src/commands/ctx_viz/index.js)
- [`src/commands/teleport/index.js`](../src/commands/teleport/index.js)
- [`src/commands/break-cache/index.js`](../src/commands/break-cache/index.js)
- [`src/commands/ant-trace/index.js`](../src/commands/ant-trace/index.js)
- [`src/commands/backfill-sessions/index.js`](../src/commands/backfill-sessions/index.js)
- [`src/commands/issue/index.js`](../src/commands/issue/index.js)
- [`src/commands/autofix-pr/index.js`](../src/commands/autofix-pr/index.js)
- [`src/commands/perf-issue/index.js`](../src/commands/perf-issue/index.js)

The meaning of this group is usually:

- The external source snapshot does not provide the real implementation.
- But the command name and wiring point are preserved.
- The real implementation is either in an internal repository, replaced by the build process, or already decommissioned but the interface point remains.

Therefore, names like `good-claude` do carry a hint of easter egg flair, but based on the current snapshot, it looks more like an "internal interface phantom" than a complete feature.

## 4. `feature(...)` Shows the Project Has a Full Experiment/Cut Matrix

I scanned `src/` and found **89 different `feature(...)` toggles**. This is not a handful of scattered if-checks, but a complete compile-time toggle system.

Representative toggles include:

- Interaction & product capabilities: `VOICE_MODE`, `BUDDY`, `BRIDGE_MODE`, `TERMINAL_PANEL`, `QUICK_SEARCH`
- Agent / collaboration: `FORK_SUBAGENT`, `COORDINATOR_MODE`, `TEAMMEM`, `AGENT_MEMORY_SNAPSHOT`
- Memory / compact: `EXTRACT_MEMORIES`, `REACTIVE_COMPACT`, `CACHED_MICROCOMPACT`
- Platform extensions: `WORKFLOW_SCRIPTS`, `MCP_RICH_OUTPUT`, `MCP_SKILLS`, `WEB_BROWSER_TOOL`
- Internal product lines: `KAIROS`, `KAIROS_BRIEF`, `KAIROS_DREAM`, `KAIROS_GITHUB_WEBHOOKS`
- Experimental & observability: `PERFETTO_TRACING`, `ENHANCED_TELEMETRY_BETA`, `SLOW_OPERATION_LOGGING`
- More aggressive or internal capability names: `ULTRAPLAN`, `TORCH`, `LODESTONE`, `CHICAGO_MCP`

This matrix is especially evident at the command layer. For example:

- `VOICE_MODE` introduces `/voice`, see [`src/commands.ts#L80`](../src/commands.ts#L80)
- `ULTRAPLAN` introduces `ultraplan`, see [`src/commands.ts#L104`](../src/commands.ts#L104)
- `BUDDY` introduces `buddy`, see [`src/commands.ts#L118`](../src/commands.ts#L118)
- `BRIDGE_MODE` introduces bridge capabilities, see [`src/commands.ts#L73`](../src/commands.ts#L73)

This layer would be well-suited for creating a "toggle matrix table," as it can answer three questions:

1. Which capabilities already exist in the source code.
2. Which capabilities are only enabled in internal or experimental builds.
3. Which capabilities are not fully aligned with the feature boundaries described in public documentation.

## 5. Beta Headers Are Also Important Clues

Another valuable clue is not commands but beta headers.
[`src/constants/betas.ts`](../src/constants/betas.ts) directly lists a set of capability names and dates:

- `context-1m-2025-08-07`
- `web-search-2025-03-05`
- `fast-mode-2026-02-01`
- `token-efficient-tools-2026-03-28`
- `advisor-tool-2026-03-01`
- `afk-mode-2026-01-31`
- `cli-internal-2026-02-09`

See [`src/constants/betas.ts#L3`](../src/constants/betas.ts#L3).

These strings indicate at least two things:

- The project and upstream model capabilities negotiate through explicit beta header protocols.
- Some capabilities that may not be highly visible on the product surface today already have stable interface positions in the code.

A cautious inference should be made here:

- "Code has beta headers" does NOT equal "you can use this capability in the public version today."
- But it at least indicates that these capabilities are not pure concepts; they have entered the engineering wiring stage.

## 6. The Real "Easter Eggs" Are in the buddy / Clawd / stickers Layer

### 6.1 Buddy Is Not a Joke — It's a Complete Personification Subsystem

The `buddy` related code is not thin. The most critical part is in [`src/buddy/prompt.ts`](../src/buddy/prompt.ts):

- It explicitly tells the main model: there is a small creature sitting beside the input box that occasionally comments in a bubble.
- When the user directly addresses this creature by name, the main model should "step back," reply in one line or less, and not speak for it.

See [`src/buddy/prompt.ts#L7`](../src/buddy/prompt.ts#L7).

This shows it is not just welcome copy, but a "secondary character" design that has entered the conversation protocol layer.

### 6.2 Companion's "Skeleton" and "Soul" Are Stored Separately

[`src/buddy/companion.ts`](../src/buddy/companion.ts) shows that this system is not as simple as "randomly generating a little pet." It splits the companion into two layers:

- `bones`: Deterministic skeleton, containing `rarity`, `species`, `eye`, `hat`, `shiny`, `stats`
- `soul`: Model-generated soul, containing `name`, `personality`
- When persisting, only `soul + hatchedAt` is saved; on load, `bones` are re-rolled using the user ID

See [`src/buddy/companion.ts#L78`](../src/buddy/companion.ts#L78) and [`src/buddy/types.ts#L103`](../src/buddy/types.ts#L103).

This design is noteworthy because it solves three things simultaneously:

- The companion is stable for the same user, not changing species on every restart
- Changing the `SPECIES` list or renaming species won't corrupt old save data
- Users cannot manually modify their config to pretend to be `legendary`

The code even states this explicitly: `Bones never persist` — see [`src/buddy/companion.ts#L124`](../src/buddy/companion.ts#L124).

More specifically, this "hatching" process is:

- `companionUserId()` prefers `oauthAccount.accountUuid`, then `userID`, then falls back to `anon` — see [`src/buddy/companion.ts#L119`](../src/buddy/companion.ts#L119)
- Uses `userId + "friend-2026-401"` as the hashing seed — see [`src/buddy/companion.ts#L78`](../src/buddy/companion.ts#L78)
- Feeds into a small seeded PRNG `mulberry32()` — see [`src/buddy/companion.ts#L14`](../src/buddy/companion.ts#L14)
- Then rolls rarity, species, eye, hat, shiny, stats in a fixed order — see [`src/buddy/companion.ts#L83`](../src/buddy/companion.ts#L83)

This means: what is truly "unique per user buddy" is only the name and personality; the complete deterministic body archetype can be fully reconstructed from static source, including the 18 species, eyes, hats, and stat roll rules listed below.

### 6.3 Rarity, Eyes, Hats, and Stats Have a Complete Gacha Roll System

Corresponding type definitions are in [`src/buddy/types.ts`](../src/buddy/types.ts):

- Rarity: `common`, `uncommon`, `rare`, `epic`, `legendary`
- Species: 18 total: `duck`, `goose`, `blob`, `cat`, `dragon`, `octopus`, `owl`, `penguin`, `turtle`, `snail`, `ghost`, `axolotl`, `capybara`, `cactus`, `robot`, `rabbit`, `mushroom`, `chonk`
- Eyes: `·`, `✦`, `×`, `◉`, `@`, `°`
- Hats: `none`, `crown`, `tophat`, `propeller`, `halo`, `wizard`, `beanie`, `tinyduck`
- Stats: `DEBUGGING`, `PATIENCE`, `CHAOS`, `WISDOM`, `SNARK`

See [`src/buddy/types.ts#L1`](../src/buddy/types.ts#L1).

Some details are clearly beyond "just for fun":

- Rarity weights are explicitly hardcoded: `60 / 25 / 10 / 4 / 1` — see [`src/buddy/types.ts#L126`](../src/buddy/types.ts#L126)
- `common` wears no hat; non-`common` rolls a hat from the pool — see [`src/buddy/companion.ts#L87`](../src/buddy/companion.ts#L87)
- `shiny` probability is fixed at `1%` — see [`src/buddy/companion.ts#L88`](../src/buddy/companion.ts#L88)
- Stats are not evenly distributed; they follow a "one peak, one weak point, rest scattered" pattern, and rarity raises the stat floor — see [`src/buddy/companion.ts#L51`](../src/buddy/companion.ts#L51)

This means the buddy system already has a very lightweight "collectible game" syntax.

One particularly interesting comment: one species name would collide with the "model codename canary," so the code deliberately uses `String.fromCharCode` to dynamically construct all species names, avoiding string literals in the bundle — see [`src/buddy/types.ts#L4`](../src/buddy/types.ts#L4). This is no longer an ordinary UI easter egg; it's "easter egg coexisting with internal security constraints."

### 6.4 It Also Has Complete Launch Timing, Discovery Mechanisms, and Interaction Loop

`buddy` is not just hidden in code; it has a fairly complete deployment path:

- From April 1, 2026 to April 7, 2026, if the local date falls within the teaser window and the user hasn't hatched a companion yet, a rainbow-colored `/buddy` prompt appears on startup for 15 seconds — see [`src/buddy/useBuddyNotification.tsx#L8`](../src/buddy/useBuddyNotification.tsx#L8)
- Starting April 2026, `isBuddyLive()` returns true, indicating the command itself is considered officially launched — see [`src/buddy/useBuddyNotification.tsx#L14`](../src/buddy/useBuddyNotification.tsx#L14)
- The input box highlights `/buddy` keywords in rainbow colors — see [`src/buddy/useBuddyNotification.tsx#L79`](../src/buddy/useBuddyNotification.tsx#L79) and [`src/components/PromptInput/PromptInput.tsx#L728`](../src/components/PromptInput/PromptInput.tsx#L728)
- In the footer, if `companion` is selected, pressing Enter submits `/buddy` — see [`src/components/PromptInput/PromptInput.tsx#L1788`](../src/components/PromptInput/PromptInput.tsx#L1788)

One point that must be honestly stated:

- `commands.ts` clearly registers `./commands/buddy/index.js` — see [`src/commands.ts#L118`](../src/commands.ts#L118)
- But the current leaked `src/` directory does not contain this implementation file

So regarding all sub-actions of the `/buddy` command itself, we cannot reconstruct them 100%. But from the surrounding state flags and UI behavior, at least we can confirm it involves hatching, and there is also a `/buddy pet` interaction action, because the comment for `companionPetAt` directly says "Timestamp of last /buddy pet" — see [`src/state/AppStateStore.ts#L170`](../src/state/AppStateStore.ts#L170).

### 6.5 Runtime Interaction Is Not Static Decoration — It's a Complete Small State Machine

This layer is primarily scattered across [`src/buddy/CompanionSprite.tsx`](../src/buddy/CompanionSprite.tsx), [`src/screens/REPL.tsx`](../src/screens/REPL.tsx), [`src/utils/config.ts`](../src/utils/config.ts):

- The companion has a permanent rendering slot, occupying width to the right of the input box — see [`src/buddy/CompanionSprite.tsx#L167`](../src/buddy/CompanionSprite.tsx#L167)
- On narrow terminals, it degrades to a single-line `face + name/quip` mode — see [`src/buddy/CompanionSprite.tsx#L225`](../src/buddy/CompanionSprite.tsx#L225)
- On wide terminals, it renders the full ASCII sprite with a 500ms tick idle/fidget/blink animation sequence — see [`src/buddy/CompanionSprite.tsx#L18`](../src/buddy/CompanionSprite.tsx#L18) and [`src/buddy/CompanionSprite.tsx#L242`](../src/buddy/CompanionSprite.tsx#L242)
- If petted, there's about a 2.5-second heart float animation — see [`src/buddy/CompanionSprite.tsx#L19`](../src/buddy/CompanionSprite.tsx#L19)
- If speaking, a speech bubble appears, disappearing after about 10 seconds, with the last ~3 seconds in fade — see [`src/buddy/CompanionSprite.tsx#L17`](../src/buddy/CompanionSprite.tsx#L17)
- In non-fullscreen mode, the bubble is positioned to the left of the sprite; in fullscreen mode, the bubble floats to the bottom-right overlay layer — see [`src/buddy/CompanionSprite.tsx#L277`](../src/buddy/CompanionSprite.tsx#L277)
- When the user scrolls through the transcript, the bubble is dismissed to avoid blocking content — see [`src/screens/REPL.tsx#L1297`](../src/screens/REPL.tsx#L1297)
- Speech content comes from `fireCompanionObserver(...)`, called after each query round completes — see [`src/screens/REPL.tsx#L2803`](../src/screens/REPL.tsx#L2803)

Here is a second point that must be cautiously stated:

- `AppStateStore`'s comment reads `friend observer (src/buddy/observer.ts)` — see [`src/state/AppStateStore.ts#L168`](../src/state/AppStateStore.ts#L168)
- But `src/buddy/observer.ts` is also missing from the current directory

Therefore, we can confirm "it gives a companion reaction after each conversation round," but the specific prompt and filtering rules for the reaction cannot be fully reconstructed from this leaked directory.

### 6.6 Reconstructing Every Buddy Prototype

Strictly speaking, static source can only fully reconstruct "each body archetype," not each user's unique name and personality (the latter is model-generated `soul`). But for the determinable parts, all 18 species can be reconstructed one by one.

The following gallery is based on frame 0 of [`src/buddy/sprites.ts`](../src/buddy/sprites.ts), uniformly using `◉` for eyes, omitting the uniform hat slot at the top; real runtime will also overlay different eye types, hats, and 3-frame animation.

```text
duck
    __
  <(◉ )___
   (  ._>
    `--´

goose
     (◉>
     ||
   _(__)_
    ^^^^

blob
   .----.
  ( ◉  ◉ )
  (      )
   `----´

cat
   /\_/\
  ( ◉   ◉)
  (  ω  )
  (")_(")

dragon
  /^\  /^\
 <  ◉  ◉  >
 (   ~~   )
  `-vvvv-´

octopus
   .----.
  ( ◉  ◉ )
  (______)
  /\/\/\/\

owl
   /\  /\
  ((◉)(◉))
  (  ><  )
   `----´

penguin
  .---.
  (◉>◉)
 /(   )\
  `---´

turtle
   _,--._
  ( ◉  ◉ )
 /[______]\
  ``    ``

snail
 ◉    .--.
  \  ( @ )
   \_`--´
  ~~~~~~~

ghost
   .---.
  / ◉  ◉ \
  |      |
  ~`~``~`~

axolotl
}~(______)~{
}~(◉ .. ◉)~{
  ( .--. )
  (_/  \_)

capybara
  n______n
 ( ◉    ◉ )
 (   oo   )
  `------´

cactus
 n  ____  n
 | |◉  ◉| |
 |_|    |_|
   |    |

robot
   .[||].
  [ ◉  ◉ ]
  [ ==== ]
  `------´

rabbit
   (\__/)
  ( ◉  ◉ )
 =(  ..  )=
  (")__(")

mushroom
 .-o-OO-o-.
(__________)
   |◉  ◉|
   |____|

chonk
  /\    /\
 ( ◉    ◉ )
 (   ..   )
  `------´
```

If you further look at [`renderFace(...)`](../src/buddy/sprites.ts#L303), you'll see that different species not only have "different big sprites," but even the single-line face in narrow terminal mode was individually designed:

- `duck` / `goose` is `(${eye}>`
- `cat` is `=${eye}ω${eye}=`
- `dragon` is `<${eye}~${eye}>`
- `octopus` is `~(${eye}${eye})~`
- `axolotl` is `}${eye}.${eye}{`
- `robot` is `[${eye}${eye}]`

This shows the team didn't just make a "random pet sticker"; they treated buddy as a complete collectible, identifiable, interactive companion UI system.

### 6.7 Clawd Is Clickable and Interactive

The `Clawd` in `LogoV2` is not a static logo.
[`src/components/LogoV2/AnimatedClawd.tsx`](../src/components/LogoV2/AnimatedClawd.tsx) explicitly implements:

- Click to trigger animation
- Actions include crouch-jump wave
- Or look left-right look-around

See [`src/components/LogoV2/AnimatedClawd.tsx#L27`](../src/components/LogoV2/AnimatedClawd.tsx#L27) and [`src/components/LogoV2/AnimatedClawd.tsx#L49`](../src/components/LogoV2/AnimatedClawd.tsx#L49).

These details are completely unnecessary for the main capabilities, but they matter for product character, so they are very typical of "engineered easter eggs."

### 6.8 `/stickers` Directly Leads to a Merch Page

`/stickers` is not a joke command either.
It directly opens `https://www.stickermule.com/claudecode` — see [`src/commands/stickers/stickers.ts#L4`](../src/commands/stickers/stickers.ts#L4).

This shows the team treats physical merchandise as part of the product system, integrated into the command interface.

### 6.9 `passes` / Guest Passes / Referral Upsell Also Carry a Distinct "Product Easter Egg Feel"

[`src/components/LogoV2/GuestPassesUpsell.tsx`](../src/components/LogoV2/GuestPassesUpsell.tsx) will:

- Check guest passes eligibility cache
- Control upsell display count
- Show "3 guest passes at /passes"
- Or show "Share Claude Code and earn ... extra usage"

See [`src/components/LogoV2/GuestPassesUpsell.tsx#L22`](../src/components/LogoV2/GuestPassesUpsell.tsx#L22) and [`src/components/LogoV2/GuestPassesUpsell.tsx#L57`](../src/components/LogoV2/GuestPassesUpsell.tsx#L57).

This part is not a "hidden command," but it's very much like a semi-hidden operational entry at the product level.

## 7. There's Another Topic Worth Special Mention: Undercover Mode

While the previous sections are more like easter eggs or experimental features, `undercover` reveals a strong internal product culture.

[`src/utils/undercover.ts`](../src/utils/undercover.ts) logic is:

- In public / open-source repositories, the internal build enters undercover mode by default
- Automatically adds safety instructions to prevent commit messages or PRs from leaking internal codenames, version numbers, project names, Slack channels, short links
- Even explicitly forbids writing "Claude Code" or revealing being AI

See [`src/utils/undercover.ts#L1`](../src/utils/undercover.ts#L1).

This shows the project has a clear design for "how to disguise the internal agent's identity in public collaboration scenarios."
It's not an easter egg, but it reveals more about the organizational form and real usage scenarios behind this project than any easter egg could.

## 8. Chapter Conclusions

The conclusions about "what else can be analyzed" can be distilled into four points:

1. What's most worth further investigation is not scattered easter eggs, but the "hidden commands + feature flags + beta headers" hidden capability matrix.
2. True easter eggs are mainly concentrated in the `buddy`, `Clawd`, `stickers`, `passes` layer.
3. `undercover`, `INTERNAL_ONLY_COMMANDS`, and numerous `stub` commands indicate there is a clear and systematic layering between the public and internal versions of this project.
4. The most valuable "hidden information" in this codebase is not a single joke command, but how it engineeringly maintains simultaneously:
   - An externally releasable version
   - An internal experimental version
   - Brand personification experience
   - Security and organizational boundaries

## 9. Three Best Follow-up Topics for Deeper Exploration

1. `feature(...)` full toggle matrix: organize all 89 toggles by subsystem into a table.
2. Hidden and internal command index: determine one by one whether each is truly implemented, half-implemented, or a pure `stub`.
3. Buddy / Clawd / Passes deep dive: dedicated topic on "personification design and product easter egg system."
