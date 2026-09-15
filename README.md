# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

Your README submission must document each tool's name, inputs, and return value. **These must exactly match your actual function signatures in `tools.py`.** Your documented interfaces will be checked against your actual function signatures in `tools.py` — if the parameter count or types contradict what's in the code, you may not receive full credit for that tool.

---
## Demo

Watch the project demo: https://www.loom.com/share/22d88cd5f2e545ca8bd03cb8dee3bee1

---
## Interaction Walkthrough

**User query:** "vintage graphic tee under $30, size M"

Step 1 - tool called: `search_listings`
- Tool: `search_listings(description, size, max_price)`
- Input: `description="vintage graphic tee"`, `size="M"`, `max_price=30.0`
- Why this tool: locate thrift listings that match the user's intent and constraints
- Output: a list of matching listing dicts (sorted by score).
     - `{ 'id': 'listing-012', 'title': 'Vintage Band Tee', 'price': 24.0, 'size': 'M', 'platform': 'depop', ... }`

Step 2 - tool called: `suggest_outfit`
- Tool: `suggest_outfit(new_item, wardrobe)`
- Input: `new_item` = top listing dict, `wardrobe` = `get_example_wardrobe()`
- Why this tool: produce 1–2 outfit combinations that use the thrifted item together with existing wardrobe pieces
- Output:
     - "Outfit 1: Style the Vintage Band Tee with high-waisted mom jeans and white sneakers. Shared vibe: casual, vintage."

Step 3 - tool called: `create_fit_card`
- Tool: `create_fit_card(outfit, new_item)`
- Input: the outfit string from step 2 and the selected listing dict
- Why this tool: produce a short social caption the user can copy/share
- Output: 
     - "Scored a Vintage Band Tee for $24 on depop. Styled it with mom jeans and white sneakers — effortless weekend vibes."

Final output to user:
- Selected item: "Vintage Band Tee" — $24 — depop
- Outfit suggestion: "Style the Vintage Band Tee with high-waisted mom jeans and white sneakers."
- Fit card (shareable caption): "Scored a Vintage Band Tee for $24 on depop. Styled it with mom jeans and white sneakers — effortless weekend vibes."
---

## Error Handling and Fail Points

<!-- For each tool, describe the specific failure mode and what your agent does in response.
     This maps to the error handling section of the rubric (F5-C1). -->

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | Data loading, parsing error, or no matches for strict filters | If `load_listings()` raises, the function returns an empty list (safe failure). If no matches are found, the agent will attempt one broadened retry. If it is still empty, `run_agent` sets `session['error']` to a helpful message and returns early. |
     - Concrete example from testing: running the no-results path in `agent.py` with the query "designer ballgown size XXS under $5" yields the agent error: "I couldn't find any listings matching that query. Would you like me to broaden the price or remove the size filter?"

| `suggest_outfit` | LLM/Groq client unavailable, or LLM call errors / timeouts. | The function attempts to call the Groq LLM when configured. If that fails, it falls back to a local heuristic that (a) returns general styling advice when the wardrobe is empty, or (b) selects complementary wardrobe items via simple tag/color matching. The agent treats `suggest_outfit` errors as non-fatal for other items (errors are recorded in `session['errors']` and processing continues for other candidates). |

| `create_fit_card` | Missing/empty `outfit` input or LLM failures that return no useful text. | If `outfit` is empty or whitespace, `create_fit_card` returns the string: "Cannot create fit card: missing outfit details,".  If the LLM is not available or does not produce a varied caption, `create_fit_card` uses small local templates and returns a deterministic caption. |
     - Concrete example from testing: calling `create_fit_card('', results[0])` prints: `Cannot create fit card: missing outfit details.` (see quick test in repository).

---

## Spec Reflection

<!-- Answer both questions with at least 2–3 sentences each. -->

- **One way planning.md helped during implementation:**

     Planning.md helped me flesh out and understand the design of the retry and fallback behavior before coding. This made it easy to implement `run_agent` in small, testable steps and allowed me to decide which failures should be retryable or final.

- **One divergence from your spec, and why:**

     I used easy, rule-based fallbacks and templates when the LLM or external services aren't available so the app always responds. That keeps behavior predictable during testing even if external APIs fail.

     Why this divergence: prioritizing deterministic behavior and offline testability reduces flaky failures during grading and local development, avoids added cost and latency of external APIs during routine tests, and makes the app's responses reproducible for evaluation.

---
## AI Usage
- Instance 1: Implementing `suggest_outfit` (Tool 2):
      - What I gave the AI: I gave the AI the "Tool 2" section from `planning.md` (the docstring/spec for `suggest_outfit`) and asked for a code-level implementation.
 
      - What it produced: a draft implementation for `suggest_outfit` that included building a Groq prompt, calling the chat endpoint, extracting text, and a suggested fallback heuristic.
 
      - What I changed/overrode before using it: I reviewed and edited the generated code. I tightened exception handling, limited wardrobe input to 30 items, adjusted prompt phrasing, and integrated the finalized fallback heuristic into `tools.suggest_outfit` so it never crashes the agent.

- Instance 2: Implementing `create_fit_card` (Tool 3):
      - What I gave the AI: I gave the AI the "Tool 3" section from `planning.md` (the docstring/spec for `create_fit_card`) and asked for a code-level implementation.
 
      - What it produced: a draft implementation that called the Groq chat endpoint, extracted message content, and suggested retry/temperature strategies plus example caption templates.
 
      - What I changed/overrode before using it: I edited the returned code and added deterministic local templates as a hard fallback, enforced caption formatting rules (2+ sentences, include price/platform once), and normalized/truncated outputs before storing.

---
## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

