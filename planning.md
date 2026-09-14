# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---
Purpose: FitFindr is a thrift shopping agent that searches listings based on a user's description. The agent then figures out how the item fits into the user's wardrobe and shares it with the user along with styling suggestions. 

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
It searches the mock listings dataset for items matching the description, optional size, and optional price ceiling.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords describing what the user is looking for
- `size` (str): size string to filter by 
- `max_price` (float): maximum price to filter by 

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of matching listing dicts, sorted by relevance (best match first).

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
Returns an empty list if nothing matches — does NOT raise an exception.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
When given a thrifted item and the user's wardrobe, it suggests 1–2 complete outfits.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): a listing dict (the item the user is considering buying)
- `wardrobe` (dict): a wardrobe dict with an 'items' key containing a list of wardrobe item dicts

**What it returns:**
<!-- Describe the return value -->
 A non-empty string with outfit suggestions.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the wardrobe is empty, offer general styling advice for the item rather than raising an exception or returning an empty string.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
It generates a short, shareable outfit caption for the thrifted find.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion string from suggest_outfit().
- `new_item` (dict): The listing dict for the thrifted item.

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence string usable as an Instagram/TikTok caption.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If the outfit is empty or missing, return a descriptive error message string — do NOT raise an exception.
---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The planning loop is a small deterministic state machine that inspects user intent, filled slot values, and intermediate tool outputs to decide the next action. The loop follows these high-level rules:

- Intent & slot analysis (first step): parse the user's request into slots such as `description` (what to search for), optional `size`, optional `max_price`, and `styling_only` flag (if the user only wants styling). If `description` or a search-related slot is present, the loop sets the next action to `search_listings`.

- Search stage: call `search_listings(description, size, max_price)`. After the call:
     - If results list is non-empty: mark `search_results` in state and set next action to `suggest_outfit` for the top N results (N=1–2 by default) unless the user explicitly requested only listings.
     - If results list is empty: prompt the user to broaden the query (raise `max_price`, relax `size`, or accept repro/newer items). The loop may retry `search_listings` once with broadened filters; if still empty, offer curated alternatives and stop the automated loop until user confirmation.

- Styling stage: call `suggest_outfit(new_item, wardrobe)` for each selected listing (or only the single chosen listing if the user picks one). After the call:
     - If a non-empty outfit string is returned: store it as `outfit_suggestion` and set next action to `create_fit_card`.
     - If the wardrobe is empty or no combos are found: `suggest_outfit` returns general styling advice; the loop still proceeds to `create_fit_card` using the general advice, but it also flags the session state with `wardrobe_empty` so the UI can prompt the user to add items.

- Fit card stage: call `create_fit_card(outfit, new_item)` to generate the shareable caption/card. If the returned card is valid (non-error string), the loop prepares the final payload to present to the user (listings + outfit(s) + card). If `create_fit_card` fails, the loop will retry once; on persistent failure, it substitutes a short templated caption and surfaces an option for the user to "Regenerate caption".

- User-driven branching: at any point the user can:
     - Request more listings → loop sets action back to `search_listings` with adjusted filters.
     - Select a specific listing to focus on → loop skips additional listing suggestions and proceeds to `suggest_outfit` for that item.
     - Ask for only styling and no search → loop skips `search_listings` and calls `suggest_outfit` directly with a user-provided item or image description.

- Termination conditions: the automated planning loop considers the interaction complete when one of the following is true:
     1. A valid fit card and at least one outfit suggestion have been generated and presented to the user (success path).
     2. The user explicitly cancels or requests a new search/refinement (the loop yields back to the user to get new slots).
     3. Persistent failures after retried attempts (e.g., repeated empty search after widening filters, or repeated caption generation failure) — in which case the loop presents fallbacks and stops automated retries.

Triggers:
- Primary trigger: presence of search-related slots → `search_listings`.
- Secondary trigger: a selected/returned listing → `suggest_outfit`.
- Final trigger: a valid outfit string → `create_fit_card`.

State transitions are driven by tool outputs and explicit user choices. The loop always records the current state (`query_slots`, `search_results`, `selected_item`, `outfit_suggestion`, `fit_card`, and `errors`) so subsequent decisions are simple conditional checks on those fields.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

The agent maintains a lightweight session state object for each user interaction. The state is held in memory for short-lived sessions and is serializable to JSON for persistence if the session needs to be resumed. Every tool call reads the minimal subset of state it needs and writes back only the fields that changed.

Core session state shape:

- `session_id` (str): unique id for the interaction.
- `query_slots` (dict): parsed user slots such as `{ description, size, max_price, styling_only, preferences }`.
- `last_action` (str): name of the last tool invoked (`intent_parse`, `search_listings`, `suggest_outfit`, `create_fit_card`).
- `search_results` (list[dict]): ordered list of listing dicts returned by `search_listings`.
- `selected_item` (dict | None): the listing dict the user selected or the top candidate when auto-selected.
- `outfit_suggestions` (dict): map from `listing_id`→`outfit_string` (or general advice string).
- `fit_cards` (dict): map from `listing_id`→`fit_card_string` (generated caption/card).
- `errors` (list[dict]): chronological list of transient errors with `{ stage, code, message, attempts }`.
- `meta` (dict): timestamps, retry counters, UI hints (e.g., `wardrobe_empty: true`).

How tools read/write state:

- Before calling a tool, the planner extracts only the fields required by that tool and passes them as explicit parameters (no tool reads global state implicitly).
- After the tool returns, the planner validates the output and merges results into the session state. 
- Tools may also return structured diagnostics that the planner writes into `errors` and may use to decide retries.

State lifecycle and persistence:

- Session start: the planner creates `session_id` and an empty state object, stores initial `query_slots` parsed from user input.
- During the loop, the state is updated in-place after every tool call. The planner increments per-stage retry counters and records timestamps for observability.
- By the end of interaction, the final state is either discarded (short sessions) or persisted with a TTL so the user can resume or view history. Persisted state includes `query_slots`, `selected_item`, `fit_cards`, and `meta` but excludes large blobs unless necessary.

Design notes:

- Explicit parameter passing simplifies testing and isolates tools for mocking.
- Storing multiple `outfit_suggestions` and `fit_cards` keyed by `listing_id` lets the UI show side-by-side options and avoid re-running expensive steps.
- Keep the state schema stable and backwards-compatible; include a `schema_version` in `meta` if changing formats later.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Returns an empty list |
| suggest_outfit | Wardrobe is empty | Offer general styling advice for the item rather than raising an exception or returning an empty string|
| create_fit_card | Outfit input is missing or incomplete | Return a descriptive error message string |

Detailed retry and fallback policies

General rules
- Retry policy: for transient failures (IO errors, LLM timeouts), the planner will retry the failing tool once (max_retries = 1) before performing a fallback. Each retry increments the `attempts` counter in `session['errors']` for observability.
- Backoff: on LLM calls use a short exponential backoff before retrying.
- Error logging: every error is appended to `session['errors']` with `{ stage, code, message, attempts, retryable }`.
- User-visible guidance: when automated recovery fails, present clear next steps to the user (e.g., "No listings found — broaden your price range?").

Tool-specific handling

- `search_listings`
     - Failure modes: zero results.
     - Agent response: If results are empty: automatically suggest a single broadened search (increase `max_price` by a configurable factor, drop `size` constraint, or enable repro items) and retry once. If still empty, present curated alternatives and ask the user whether to continue.
     - Example of user-facing message: "I couldn't find any items matching that filter. Want me to broaden the price or drop size?"

- `suggest_outfit`
     - Failure modes: wardrobe empty
     - Agent response: If `wardrobe['items']` is empty: return general styling advice and set `session['meta']['wardrobe_empty'] = true` so the UI prompts the user to add items.
     - Example of user-facing message: "I don't see any items in your wardrobe. I can still give general styling suggestions for this piece. Would you like those now, or would you prefer to add items to your wardrobe first?"

- `create_fit_card`
     - Failure modes: missing outfit input
     - Agent response:  If `outfit` is empty or whitespace, then return a descriptive error string such as "Cannot create fit card: missing outfit details." and prompt the user to ask for styling or provide wardrobe items.
     - Example of user-facing message: "I couldn't create a fit card because I don't have the outfit details. Would you like me to generate styling suggestions first or provide more info about your wardrobe so I can build one?"


---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off. 
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

Below are both a Mermaid flowchart and a compact ASCII diagram showing the planning loop, tool triggers, state updates, and error paths.

```mermaid
flowchart TD
  User["User query"] --> Planner["Planning Loop"]

  Planner --> Search["search_listings(description, size, max_price)"]
  Search -->|results = []| NoResults["[ERROR] No listings found\n→ ask to broaden filters / return to user"]
  Search -->|results = [item,...]| Select["Session: selected_item = results[0]"]

  Select --> Outfit["suggest_outfit(selected_item, wardrobe)"]
  Outfit -->|outfit found| Card["create_fit_card(outfit_suggestion, selected_item)"]
  Outfit -->|no outfit / wardrobe empty| Advice["Return general styling advice; set wardrobe_empty flag"]

  Card -->|success| Return["Return session (search_results, outfit_suggestions, fit_card)"]
  Card -->|error| CardRetry["Retry create_fit_card once\n→ on persistent failure: use templated caption"]
  CardRetry --> Return

  NoResults --> Return
  Advice --> Card

  %% user-driven branching
  Planner -.->|user selects item| Select
  Planner -.->|user requests more listings| Search
  Planner -.->|user asks styling-only| Outfit

  style User fill:#f9f,stroke:#333,stroke-width:1px
  style Planner fill:#fffbcc,stroke:#333
  style Search fill:#cfe9ff
  style Outfit fill:#cfe9ff
  style Card fill:#cfe9ff
  style NoResults fill:#ffd6d6
  style Return fill:#e6ffe6
```

Compact ASCII diagram:

User query
     │
     ▼
Planning Loop ───────────────────────────────────────────┐
     │                                                    │
     ├─► search_listings(description, size, max_price)    │
     │       │ results=[]                                 │
     │       ├──► [ERROR] "No listings found..." → return │
     │       │                                            │
     │       │ results=[item, ...]                        │
     │       ▼                                            │
     │   Session: selected_item = results[0]              │
     │       │                                            │
     ├─► suggest_outfit(selected_item, wardrobe)          │
     │       │                                            │
     │   Session: outfit_suggestion = "..."               │
     │       │                                            │
     └─► create_fit_card(outfit_suggestion, selected_item)│
               │                                            │
          Session: fit_card = "..."                        │
               │                                            └─ error path returns here
               ▼
          Return session (search_results, outfits, fit_card)


---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
1) Implement `search_listings`
- Tool: GitHub Copilot / local LLM (for in-editor code suggestions) and manual coding review. 
- Input to AI: the `Tool 1` spec from this file, the `utils/data_loader.load_listings()` signature, and sample listing entries from `data/listings.json`.
- Expected output: a Python function `search_listings(description, size=None, max_price=None)` that loads listings, filters by `size` and `max_price`, scores items by keyword overlap with `description`, drops zero-score items, and returns a sorted list of listing dicts.
- Verification: write unit tests that call `search_listings` for 3 queries (e.g., "vintage graphic tee", "leather jacket size M under $50", and a query expected to return no results). Confirm correct ordering, filtering, and empty-list behavior. Mock `load_listings()` if needed.

2) Implement `suggest_outfit`
- Tool: LLM (ChatGPT or Claude) for prompt engineering and for generating example outputs; implementation is a thin wrapper in Python that formats prompts and calls the configured LLM client (or a local stub for tests).
- Input to AI: `Tool 2` spec, `planning.md` wardrobe examples, and several representative `new_item` dicts from `data/listings.json`.
- Expected output: a wrapper `suggest_outfit(new_item, wardrobe)` that returns a human-readable outfit suggestion string; if `wardrobe['items']` is empty, returns a general styling paragraph.
- Verification: unit tests where the LLM call is mocked to return controlled responses; assertions check non-empty output, presence of referenced wardrobe item names when wardrobe provided, and correct fallback when wardrobe empty.

3) Implement `create_fit_card`
- Tool: LLM (ChatGPT or Claude) to design the prompt template; wrapper implemented in Python to call the LLM client.
- Input to AI: `Tool 3` spec, `outfit` examples returned by `suggest_outfit`, and style guidelines (2–4 sentences, social-media tone).
- Expected output: `create_fit_card(outfit, new_item)` returns a 2–4 sentence caption string. On empty/incomplete input, returns a descriptive error string (no exception).
- Verification: mock LLM responses in unit tests to verify length, tone, and error handling. Add a small integration test calling `suggest_outfit` (mock LLM) then `create_fit_card` to assert end-to-end flow.

**Milestone 4 — Planning loop and state management:**

4) Implement the Planning Loop / Orchestrator
- Tool: GitHub Copilot + ChatGPT for synthesizing the state machine into code, but implement and test locally in `agent.py`.
- Input to AI: the completed `Planning Loop`, `State Management`, and `Architecture` sections of this file (the full spec and diagrams). Ask AI to produce a clear pseudocode template for the loop and then translate it into a Python implementation that uses the three tool functions.
- Expected output: an orchestrator function `run_planning_loop(session, user_input, wardrobe)` that parses `user_input` into `query_slots`, calls `search_listings` when appropriate, populates `session` with `search_results`, calls `suggest_outfit` for the top items or a selected item, then calls `create_fit_card`, handling retries and error flags as specified.
- Verification: unit tests and integration tests using mocks for the LLM-based tools. Test cases include: success path (listings→outfit→card), empty-search path (no results → user prompt), wardrobe-empty path (returns general advice → card), and LLM failure path (simulate LLM errors and confirm retries/fallbacks).

5) Prompt engineering and canned examples
- Tool: ChatGPT / Claude for creating robust prompt templates and example LLM responses used in tests and docs.
- Input: typical listing JSON, wardrobe JSON, and the desired output format for outfits and fit cards. Produce a small prompt library (examples + negative examples) stored in `prompts/` or inline constants.
- Expected output: tested prompt templates used by `suggest_outfit` and `create_fit_card` with clear instructions and examples for the LLM.
- Verification: run a few live queries against the chosen LLM with the prompt templates and inspect outputs to ensure they match expected structure; add recorded golden responses in tests.

6) Testing, CI, and mocks
- Tool: Local test runner (pytest) with LLM calls replaced by deterministic mocks. Use Copilot to suggest test scaffolding if helpful.
- Input: the implemented functions and the test descriptions above.
- Expected output: a test suite that validates functional behavior without requiring networked LLM calls; separate optional integration tests exercise real LLM calls guarded by environment flags.
- Verification: all unit tests pass locally. Integration tests may run manually and are optional for CI.

Notes on tool selection and safety:
- Prefer local code generation suggestions from GitHub Copilot when writing deterministic logic (filters, scoring, state updates). Use hosted LLMs (ChatGPT/Claude) only for natural language generation and prompt design.
- Always mock external LLM calls in unit tests; do limited live testing with an API key stored in environment variables for integration checks.
- Keep prompts and expected outputs versioned along with the code so behavior is reproducible.

Milestone mappings:
- Milestone 3 → implement `search_listings`, `suggest_outfit`, `create_fit_card` (unit tests + mocks).
- Milestone 4 → implement `run_planning_loop`, state persistence, retries, and integration tests.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1: Discover Listings**
<!-- What does the agent do first? Which tool is called? With what input? -->

Parse user intent and slots (e.g., description="vintage graphic tee", max_price=30, size if provided) then call search_listings(description, max_price, size, style_tags).

Returns a ranked list of listings (id, title, price, size, images, url, tags). 
 
If zero results, ask to broaden filters (raise price, include repro), offer curated alternatives, or retry.
 
If API error, retry once then show friendly error + cached picks.

search_listings():
     1. Load all listings with load_listings().
     2. Filter by max_price and size (if provided).
     3. Score each remaining listing by keyword overlap with `description`.
     4. Drop any listings with a score of 0 (no relevant matches).
     5. Sort by score, highest first, and return the listing dicts.

**Step 2: Generate Styling**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

For the chosen/top listings, call suggest_outfit(new_item, wardrobe_summary, occasion/temperature) to produce outfit options {items, rationale, confidence}. 

If the user hasn't chosen, automatically run for top 1–2 matches and present options. 

If wardrobe is empty, return general styling tips for the item and prompt to add wardrobe items.

If no compatible combos, suggest alterations/marketplace alternatives.

On service failure: fall back to template rulebook suggestions.

suggest_outfit():
     1.Check whether wardrobe['items'] is empty.
     2. If empty: call the LLM with a prompt for general styling ideas (what kinds of items pair well, what vibe it suits, etc.).
     3. If not empty: format the wardrobe items into a prompt and ask the LLM to suggest specific outfit combinations using the new item and named pieces from the wardrobe.
     4. Return the LLM's response as a string.

**Step 3: Build and Present Result**
<!-- Continue until the full interaction is complete -->

Call create_fit_card(outfit, new_item, user_notes) to produce a shareable card payload (title, images, price, buy_link, outfit_items, style_text). 

If images or fields are missing, use placeholders and include a text fallback.

If generation fails, show a compact textual summary and offer "Retry card".

create_fit_card():
     1. Guard against an empty or whitespace-only outfit string.
     2. Build a prompt that gives the LLM the item details and the outfit, and asks for a caption matching the style guidelines above.
     3. Call the LLM and return the response.

**Final output to user:**
<!-- What does the user actually see at the end? -->
Final UI to user: concise listing bullets + top outfit(s) with one-line rationales + a visual fit card and CTAs (Save outfit, Open listing, Broaden search, Retry).