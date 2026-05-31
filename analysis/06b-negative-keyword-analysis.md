# Chapter 15: Negative Keyword Detection and Frustration Signal Mechanism

[Back to Table of Contents](../README.md)

## 1. Chapter Guide

This chapter specifically answers a seemingly small but highly product-oriented question:

**Why does the source code have a function that regex-matches words like `wtf`, `this sucks`, `damn it`?**

TL;DR:

This code is NOT a security filter, content moderator, or user input interceptor.

Its main purpose is:

1. Quickly label user input with a "negative sentiment/dissatisfaction" tag when submitting a prompt
2. Write this label into the telemetry event `tengu_input_prompt`
3. Serve as a lightweight signal for product analysis and experience evaluation, helping identify "is the user frustrated or dissatisfied"

Looking further, this code does not exist in isolation; it works in conjunction with a higher-level product pipeline:

- One layer is **input-level lightweight keyword tagging**
- One layer is **session-level frustration detection**
- Ultimately may lead to **feedback survey / transcript sharing**

So its real positioning is not "text processing technique" but rather part of **product telemetry + frustration sensing**.

This chapter is primarily based on these implementations:

- [`src/utils/userPromptKeywords.ts`](../src/utils/userPromptKeywords.ts)
- [`src/utils/processUserInput/processTextPrompt.ts`](../src/utils/processUserInput/processTextPrompt.ts)
- [`src/utils/processUserInput/processSlashCommand.tsx`](../src/utils/processUserInput/processSlashCommand.tsx)
- [`src/screens/REPL.tsx`](../src/screens/REPL.tsx)
- [`src/components/FeedbackSurvey/useFeedbackSurvey.tsx`](../src/components/FeedbackSurvey/useFeedbackSurvey.tsx)
- [`src/components/FeedbackSurvey/submitTranscriptShare.ts`](../src/components/FeedbackSurvey/submitTranscriptShare.ts)
- [`src/commands/insights.ts`](../src/commands/insights.ts)

## 2. First Look at the Original Function: What Does It Actually Do

Related implementation:

- [`src/utils/userPromptKeywords.ts`](../src/utils/userPromptKeywords.ts)

The original function is as follows:

```typescript
export function matchesNegativeKeyword(input: string): boolean {
  const lowerInput = input.toLowerCase()

  const negativePattern =
    /\b(wtf|wth|ffs|omfg|shit(ty|tiest)?|dumbass|horrible|awful|piss(ed|ing)? off|piece of (shit|crap|junk)|what the (fuck|hell)|fucking? (broken|useless|terrible|awful|horrible)|fuck you|screw (this|you)|so frustrating|this sucks|damn it)\b/

  return negativePattern.test(lowerInput)
}
```

Looking at just the function body, what it does is very simple:

```text
Input string
  -> Lowercase
  -> Regex match against a set of negative/complaint words
  -> Return true / false
```

In other words, it does NOT:

- Modify the prompt
- Block prompt submission
- Downgrade model responses
- Trigger any permission denials
- Directly pop up UI

It is simply a boolean checker.

## 3. Where This Code Is Actually Used

Related implementation:

- [`src/utils/processUserInput/processTextPrompt.ts`](../src/utils/processUserInput/processTextPrompt.ts)

The only direct call site for this function is in `processTextPrompt()`:

```typescript
const isNegative = matchesNegativeKeyword(userPromptText)
const isKeepGoing = matchesKeepGoingKeyword(userPromptText)
logEvent('tengu_input_prompt', {
  is_negative: isNegative,
  is_keep_going: isKeepGoing,
})
```

This code is critical because it shows:

1. `matchesNegativeKeyword()` occurs **right as user input enters the system**
2. Its output is only written into an analytics event
3. It is paired with `matchesKeepGoingKeyword()`

This indicates the authors consider it a type of **input intent tag**, not control flow logic.

### 3.1 Where It Sits in the Pipeline

The `processTextPrompt()` pipeline is roughly:

```text
User enters text
  -> Generate promptId
  -> Record OTEL user_prompt
  -> Compute is_negative / is_keep_going
  -> logEvent('tengu_input_prompt', ...)
  -> Construct UserMessage
  -> Normal flow into query
```

In other words, keyword matching happens early, but it does not alter subsequent query logic.

### 3.2 Slash Commands Lack This Tag

This is an interesting detail.

In [`src/utils/processUserInput/processSlashCommand.tsx`](../src/utils/processUserInput/processSlashCommand.tsx), slash commands also log the same event:

```typescript
logEvent('tengu_input_prompt', {});
```

But here there is no `is_negative` or `is_keep_going`.

This suggests the product assumption is:

- Natural language prompts are worth sentiment and intent tagging
- Slash commands are more like structured commands, where text sentiment analysis is unnecessary

## 4. Why This Regex Exists: A Product Perspective

This type of code is most easily misunderstood as "model behavior control logic," when in reality it's more like experience analysis infrastructure.

The reasons for its existence can be summarized into four engineering purposes.

### 4.1 Identifying Obvious Frustrated/Complaint Input

Words like:

- `wtf`
- `wth`
- `this sucks`
- `so frustrating`
- `damn it`
- `piece of shit`

These are not ordinary task descriptions; they read more like immediate user feedback on product state.

This kind of signal is extremely valuable for product teams because it often indicates:

- The user thinks Claude Code just made a mistake
- The user finds the current interaction frustrating or annoying
- The user is losing patience

And these signals may not appear through explicit feedback buttons.

### 4.2 Providing a Cheap, Stable Label for Backend Analysis

Compared to using a model to classify "is the user angry" every time, this regex approach has several practical advantages:

1. Low cost
   No extra API calls needed.
2. Low latency
   Local synchronous computation completes instantly.
3. Stable
   Same input always produces same result, unaffected by model variance.
4. Easy to aggregate
   Can be directly grouped in telemetry by boolean field.

So this is more like a **cheap frustration heuristic**.

### 4.3 Serving as a Precursor Signal for a More Complex Experience System

Looking at `matchesNegativeKeyword()` alone, it only tags.

But across the whole product, "is the user frustrated" is clearly a larger analytical dimension.

For example, in [`src/commands/insights.ts`](../src/commands/insights.ts), satisfaction labels include:

```typescript
frustrated: 'Frustrated',
dissatisfied: 'Dissatisfied',
likely_satisfied: 'Likely Satisfied',
satisfied: 'Satisfied',
happy: 'Happy',
```

And the facet extraction prompt explicitly gives examples:

```text
"this is broken", "I give up" → frustrated
```

This shows "frustrated users" is a formal analysis dimension, not something thrown together.

### 4.4 Providing Trigger Conditions for Feedback Collection and Quality Improvement

In the REPL, there is a critical comment:

```typescript
// Frustration detection: show transcript sharing prompt after detecting frustrated messages
const frustrationDetection = useFrustrationDetection(...)
```

And then in the UI rendering:

```typescript
{frustrationDetection.state !== 'closed' && <FeedbackSurvey ... />}
```

This indicates the system clearly has a product pipeline:

```text
Frustration detected
  -> Show feedback / transcript share prompt
  -> Upload transcript when user allows
  -> Used to improve Claude Code
```

Although `useFrustrationDetection`'s source file was not found in the extracted `src/`, the REPL wiring and transcript sharing trigger are sufficient evidence this pipeline exists.

## 5. Its Relationship with Transcript Sharing

Related implementations:

- [`src/components/FeedbackSurvey/useFeedbackSurvey.tsx`](../src/components/FeedbackSurvey/useFeedbackSurvey.tsx)
- [`src/components/FeedbackSurvey/submitTranscriptShare.ts`](../src/components/FeedbackSurvey/submitTranscriptShare.ts)
- [`src/screens/REPL.tsx`](../src/screens/REPL.tsx)

### 5.1 Transcript Sharing Is a Formal Product Path

`submitTranscriptShare.ts` defines:

```typescript
export type TranscriptShareTrigger =
  | 'bad_feedback_survey'
  | 'good_feedback_survey'
  | 'frustration'
  | 'memory_survey'
```

Note there is a trigger explicitly called **`frustration`**.

This is not speculation; it's an official enum value.

### 5.2 Bad/Good Survey Is Already an Explicit Pipeline

In `useFeedbackSurvey.tsx`, when a user selects `good` or `bad`, it further triggers a transcript prompt, and upon consent calls:

```typescript
const result = await submitTranscriptShare(messagesRef.current, trigger_0, appearanceId_2);
```

In other words, the product already has a mature "feedback -> transcript upload" mechanism.

Since `TranscriptShareTrigger` already includes `frustration`, combined with the explicit `useFrustrationDetection(...)` in the REPL, we can infer:

- `matchesNegativeKeyword()` is likely one of the early lightweight inputs for frustration signals
- A higher-level frustration detection then decides whether to show transcript sharing

### 5.3 Transcript Sharing Uploads Complete Content

This also explains why the product cares about frustration.

`submitTranscriptShare()` uploads data that includes not just:

- Normalized transcript

But also:

- Subagent transcripts
- Raw JSONL transcript (with size protection)
- Trigger
- Version
- Platform

This shows it's not just "click unsatisfied" -- it's about reviewing an entire problematic session.

## 6. What It Does NOT Do: Avoiding Overinterpretation

This section is important because this code can easily be read too far.

### 6.1 It Is NOT Content Moderation

From the call chain, it does NOT:

- Block profanity
- Reject requests
- Modify user input
- Trigger security policies

If it were a moderation or safety classifier, the call site would not just be `logEvent(...)`.

### 6.2 It Is NOT Model Prompt Enhancement

This boolean value is not injected into prompts, nor does it enter tool permission branches.

So it is NOT telling the model:

- "The user is angry now"
- "Please be more cautious"
- "Switch to a more soothing response style"

At least from the current source evidence, there is no such usage.

### 6.3 It Is NOT a Complete Frustration Detection System

It is only a lightweight input-level heuristic.

The real frustration detection likely also incorporates:

- Session message sequence
- Recent assistant output
- Whether a survey is already showing
- Whether there is an active prompt

From the REPL's `useFrustrationDetection(messages, isLoading, hasActivePrompt, ...)` signature, it's clearly much more complex than a single regex.

## 7. Why Regex Instead of Model Classification

From an engineering perspective, using regex here is reasonable.

### 7.1 This Is a Real-Time Input Path

`processTextPrompt()` sits on the main path of user prompt submission.

If model inference were needed here to determine "are you unhappy," it would introduce:

- Extra latency
- Extra cost
- Expanded privacy surface
- Unstable results

Regex can achieve near-zero-cost real-time results.

### 7.2 The Product Only Needs a Coarse Signal, Not Semantic Perfection

The problem being solved here is not NLP precision classification, but rather:

"Is there obviously negative sentiment vocabulary in this user input?"

For this coarse-grained question, regex is sufficient.

### 7.3 It Forms a Contrast with `matchesKeepGoingKeyword()`

In the same file there is also:

```typescript
export function matchesKeepGoingKeyword(input: string): boolean {
  ...
  const keepGoingPattern = /\b(keep going|go on)\b/
  return keepGoingPattern.test(lowerInput)
}
```

This shows the file's positioning is:

**Extract a small number of high-value intent signals from user prompts into simple labels.**

One label for negative sentiment,
One label for continue-execution intent.

This is a very typical product instrumentation design.

## 8. Reconstructing the Full Product Pipeline with Pseudocode

Below is pseudocode closer to the source code semantics.

### 8.1 Input Tagging Layer

```text
on user text prompt:
    userPromptText = extractText(input)

    isNegative = matchesNegativeKeyword(userPromptText)
    isKeepGoing = matchesKeepGoingKeyword(userPromptText)

    logEvent("tengu_input_prompt", {
        is_negative: isNegative,
        is_keep_going: isKeepGoing
    })

    continue normal query flow
```

### 8.2 Higher-Level Frustration Pipeline

```text
during REPL runtime:
    frustrationDetection = useFrustrationDetection(messages, ...)

    if frustrationDetection decides user looks frustrated:
        show feedback survey / transcript share prompt

    if user agrees:
        submitTranscriptShare(messages, trigger="frustration", ...)
```

### 8.3 Overall Structure Diagram

```text
User enters text
   |
   v
matchesNegativeKeyword()
   |
   +--> is_negative = true/false
   |
   v
logEvent('tengu_input_prompt', { is_negative })
   |
   v
Normal flow into query / session
   |
   v
Higher-level frustration detection
   |
   +--> If user is clearly frustrated
           |
           v
      FeedbackSurvey / TranscriptSharePrompt
           |
           v
      submitTranscriptShare(trigger='frustration')
```

## 9. Advantages and Costs of This Design

### 9.1 Advantages

1. **Simple**
   Can obtain a highly valuable product signal using just local regex.

2. **Cheap**
   Zero additional model cost, zero additional network requests.

3. **Sufficiently Stable**
   For input with obviously profane or complaining tone, matching results are predictable.

4. **Easy to Aggregate**
   `is_negative` is well-suited as a stratification dimension for funnels, retention, failed sessions, and feedback conversion rates.

### 9.2 Costs

1. **Limited Recall**
   Users may express dissatisfaction without using these words, e.g., "This is completely wrong," which may not match.

2. **False Positives Exist**
   Words in quotes, code, or quoted context may also trigger matches.

3. **Poor Language Coverage**
   This regex almost exclusively covers English profanity and colloquial expressions.

4. **Cannot Replace True Session-Level Judgment**
   Negative words in a single input don't necessarily mean the user is truly frustrated with the entire session.

## 10. Chapter Summary

The presence of `matchesNegativeKeyword()` in the source code is fundamentally not because Claude Code wants to "censor user language," but because it needs a low-cost, real-time **negative experience signal**.

From the code evidence, three points can be clearly confirmed:

1. This function is currently directly used for telemetry tagging in `processTextPrompt()`
2. It does not block input or directly change model behavior
3. It is conceptually coherent with the higher-level frustration / transcript sharing product pipeline

So the real reason this function exists can be summarized in one sentence:

**Claude Code needs to identify early whether "the user is cursing at it, whether they're already annoyed," and turn these signals into part of the product analysis and feedback collection system.**
