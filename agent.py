"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        # richer state per planning.md
        "outfit_suggestions": {},    # mapping listing_id -> outfit string
        "fit_cards": {},             # mapping listing_id -> fit card string
        "errors": [],                # list of error dicts for observability
        "meta": {},                  # misc flags: wardrobe_empty, retries
        "last_action": None,
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # TODO: implement the planning loop
    session = _new_session(query, wardrobe)

    # Step 2: Parse the user's query into description, size, max_price
    import re

    q = (query or "").strip()
    size = None
    max_price = None

    # size: look for "size M" or "size: M"
    m_size = re.search(r"\bsize\s*[:=]?\s*([A-Za-z0-9\-]+)\b", q, flags=re.I)
    if m_size:
        size = m_size.group(1).strip()

    # price: prefer phrasing like "under $30", otherwise fall back to first $NN
    m_under = re.search(r"under\s*\$?(\d+(?:\.\d+)?)", q, flags=re.I)
    if m_under:
        try:
            max_price = float(m_under.group(1))
        except Exception:
            max_price = None
    else:
        m_dollar = re.search(r"\$\s*(\d+(?:\.\d+)?)", q)
        if m_dollar:
            try:
                max_price = float(m_dollar.group(1))
            except Exception:
                max_price = None

    # description: remove matched size/price tokens to leave a clean search phrase
    desc = q
    desc = re.sub(r"under\s*\$?\d+(?:\.\d+)?", "", desc, flags=re.I)
    desc = re.sub(r"\$\s*\d+(?:\.\d+)?", "", desc)
    desc = re.sub(r"\bsize\s*[:=]?\s*[A-Za-z0-9\-]+\b", "", desc, flags=re.I)
    desc = desc.strip(" ,.-")
    if not desc:
        # fallback to entire query if nothing remains
        desc = q

    session["parsed"] = {"description": desc, "size": size, "max_price": max_price}

    # Determine whether the user asked for styling-only
    styling_only = bool(re.search(r"\b(styl|style)ing\s*(only)?\b|just styling|only styling|styling-only|style-only|just style\b", q, flags=re.I))

    # Helper to record errors
    def _record_error(stage: str, message: str, retryable: bool = False):
        err = {"stage": stage, "message": message, "retryable": retryable, "attempts": 0}
        session["errors"].append(err)

    # If user requested styling-only, skip search and craft a pseudo-item from description
    if styling_only:
        session["last_action"] = "styling_only"
        pseudo = {
            "id": "pseudo-1",
            "title": session["parsed"]["description"],
            "description": session["parsed"]["description"],
            "category": "",
            "style_tags": [],
            "colors": [],
            "price": None,
            "platform": "",
        }
        session["selected_item"] = pseudo
        results = [pseudo]
        session["search_results"] = results
    else:
        # Step 3: Call search_listings with parsed parameters
        try:
            results = search_listings(session["parsed"]["description"], size=session["parsed"]["size"], max_price=session["parsed"]["max_price"])
            session["last_action"] = "search_listings"
        except Exception as e:
            _record_error("search_listings", str(e), retryable=True)
            session["error"] = f"search_listings failed: {e}"
            return session

        session["search_results"] = results

        # If no results, attempt one broadened retry per planning.md
        if not results:
            # prepare broadened params
            broadened = session["parsed"].copy()
            broadened_attempted = False
            if session["parsed"].get("max_price") is not None:
                try:
                    broadened["max_price"] = float(session["parsed"]["max_price"]) * 1.5
                    broadened_attempted = True
                except Exception:
                    broadened["max_price"] = None
            elif session["parsed"].get("size"):
                broadened["size"] = None
                broadened_attempted = True

            if broadened_attempted:
                try:
                    results = search_listings(broadened["description"], size=broadened.get("size"), max_price=broadened.get("max_price"))
                    session["meta"]["broadened"] = True
                    session["parsed"]["max_price"] = broadened.get("max_price")
                    session["parsed"]["size"] = broadened.get("size")
                    session["search_results"] = results
                except Exception as e:
                    _record_error("search_listings_broaden", str(e), retryable=True)

            if not results:
                session["error"] = (
                    "I couldn't find any listings matching that query. "
                    "Would you like me to broaden the price or remove the size filter?"
                )
                return session

        # select top result automatically
        session["selected_item"] = results[0]

    # At this point we have at least one selected_item (either real or pseudo)
    selected = session["selected_item"]

    # Step 5: For the top N results (default 1-2), call suggest_outfit and store suggestions
    N = min(2, len(session.get("search_results", []) or []))
    for idx in range(N):
        item = session["search_results"][idx]
        item_id = item.get("id") or f"idx-{idx}"
        try:
            outfit_text = suggest_outfit(item, wardrobe)
            session["outfit_suggestions"][item_id] = outfit_text
            session["last_action"] = "suggest_outfit"
            # flag wardrobe empty if applicable
            if isinstance(wardrobe, dict) and not (wardrobe.get("items") or []):
                session["meta"]["wardrobe_empty"] = True
        except Exception as e:
            _record_error("suggest_outfit", str(e), retryable=True)
            # continue to next item rather than aborting whole flow
            session["outfit_suggestions"][item_id] = ""

        # Step 6: For each outfit, attempt to create a fit card (retry once on descriptive failure)
        outfit_for_card = session["outfit_suggestions"].get(item_id, "")
        if not outfit_for_card or not outfit_for_card.strip():
            # no outfit to create card from — record and continue
            _record_error("create_fit_card", "Missing outfit details", retryable=False)
            session["fit_cards"][item_id] = ""
            continue

        try:
            card = create_fit_card(outfit_for_card, item)
        except Exception as e:
            _record_error("create_fit_card", str(e), retryable=True)
            session["fit_cards"][item_id] = ""
            continue

        # If card indicates missing outfit, retry once per planning.md
        if isinstance(card, str) and card.startswith("Cannot create fit card"):
            try:
                card_retry = create_fit_card(outfit_for_card, item)
                card = card_retry
            except Exception:
                card = None

        if not card:
            # fallback brief templated caption
            title = (item.get("title") or item.get("name") or "This piece")
            card = f"{title} — styled outfit: {outfit_for_card.splitlines()[0][:140]}"

        session["fit_cards"][item_id] = card

    # Populate top-level convenience fields for the single-item quick path
    # If there is at least one item processed, surface the first suggestion/card
    first_id = None
    if session["search_results"]:
        first = session["search_results"][0]
        first_id = first.get("id") or "idx-0"
    if first_id and session["outfit_suggestions"].get(first_id):
        session["outfit_suggestion"] = session["outfit_suggestions"][first_id]
    if first_id and session["fit_cards"].get(first_id):
        session["fit_card"] = session["fit_cards"][first_id]

    session["error"] = None
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
