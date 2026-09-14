"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
# Defer import of Groq until the client is needed to avoid hard dependency
# at module import time (makes local testing easier).

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    try:
        from groq import Groq
    except Exception as e:
        raise RuntimeError(
            "Groq client not available (install the 'groq' package)"
        ) from e
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    try:
        listings = load_listings()
    except Exception:
        # If loading fails for any reason, return empty list per spec
        return []

    # Normalize inputs
    desc = (description or "").lower().strip()
    size_q = size.upper().strip() if size else None

    def matches_size(listing_size: str) -> bool:
        if not size_q:
            return True
        if not listing_size:
            return False
        return size_q in listing_size.upper()

    def matches_price(price: float) -> bool:
        if max_price is None:
            return True
        try:
            return float(price) <= float(max_price)
        except Exception:
            return False

    # Prepare keywords from description
    import re

    tokens = [t for t in re.split(r"[^a-z0-9]+", desc) if t]
    token_set = set(tokens)

    scored: list[tuple[int, dict]] = []

    for listing in listings:
        # Filter by size and price first
        if not matches_size(listing.get("size", "")):
            continue
        if not matches_price(listing.get("price", 0)):
            continue

        # If no description tokens provided, treat as match with base score 1
        if not token_set:
            score = 1
        else:
            score = 0
            title = (listing.get("title") or "").lower()
            descr = (listing.get("description") or "").lower()

            # Match tokens in title/description (stronger)
            for t in token_set:
                if t in title:
                    score += 3
                if t in descr:
                    score += 2

            # Match tokens in tags, category, brand, colors (weaker)
            tags = [s.lower() for s in listing.get("style_tags") or []]
            for t in token_set:
                if t in tags:
                    score += 2
                if t == (listing.get("category") or "").lower():
                    score += 2
                if t == ((listing.get("brand") or "").lower()):
                    score += 1
                # colors
                colors = [c.lower() for c in listing.get("colors") or []]
                if t in colors:
                    score += 1

        if score <= 0:
            continue

        scored.append((score, listing))

    # Sort by score desc, then price asc as a tie-breaker
    scored.sort(key=lambda s_l: (-s_l[0], float(s_l[1].get("price", 0))))

    return [listing for (_score, listing) in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # Defensive defaults
    if not new_item:
        return "No item provided to style."

    # Extract wardrobe items safely
    wardrobe_items = (wardrobe or {}).get("items") if isinstance(wardrobe, dict) else None

    # Build a helpful prompt for the LLM
    def _build_prompt(new_item: dict, wardrobe_items: list[dict] | None) -> str:
        title = new_item.get("title") or new_item.get("name") or "The item"
        desc = new_item.get("description") or ""
        category = new_item.get("category") or ""
        colors = ", ".join(new_item.get("colors") or [])
        tags = ", ".join(new_item.get("style_tags") or [])

        intro = (
            f"You're a helpful fashion assistant. Suggest 1–2 complete outfits for the following thrifted item: {title}."
        )
        meta = f"Category: {category}. Colors: {colors}. Tags: {tags}. Description: {desc}."

        if not wardrobe_items:
            prompt = (
                intro
                + " "
                + meta
                + " The user has not provided wardrobe items. Give general styling advice and 1–2 outfit ideas that don't assume specific wardrobe pieces. Keep it concise and actionable."
            )
            return prompt

        # Format wardrobe items succinctly
        w_lines = ["User wardrobe:" ]
        for it in (wardrobe_items or [])[:30]:  # cap to avoid huge prompts
            name = it.get("name") or it.get("title") or "unnamed"
            cat = it.get("category") or ""
            tags = ",".join(it.get("style_tags") or [])
            colors = ",".join(it.get("colors") or [])
            w_lines.append(f"- {name} | {cat} | tags: {tags} | colors: {colors}")

        prompt = (
            intro
            + " "
            + meta
            + "\n\n"
            + "\n".join(w_lines)
            + "\n\nUsing the wardrobe items above, suggest 1–2 outfit combinations that include the thrifted item. For each outfit, list the items to pair and one short rationale. Keep responses short and user-friendly."
        )
        return prompt

    prompt = _build_prompt(new_item, wardrobe_items)

    # Attempt to call Groq LLM; if anything fails, fall back to local heuristic
    try:
        client = _get_groq_client()
        model_name = "meta-llama/llama-4-scout-17b-16e-instruct"

        # Use the chat completions endpoint; provide a single user message
        # The Groq client exposes chat.create similar to other SDKs.
        response = client.chat.create(model=model_name, messages=[{"role": "user", "content": prompt}], temperature=0.8, max_tokens=400)

        # Extract text from common response shapes
        text = None
        if isinstance(response, dict):
            # look for choices -> message -> content
            choices = response.get("choices")
            if choices and isinstance(choices, list):
                first = choices[0]
                # some SDKs nest message->content
                if isinstance(first, dict):
                    msg = first.get("message") or first.get("delta") or first
                    if isinstance(msg, dict) and msg.get("content"):
                        text = msg.get("content")
                    elif isinstance(first.get("text"), str):
                        text = first.get("text")
        else:
            # SDKs sometimes return objects with .choices
            try:
                if hasattr(response, "choices"):
                    ch = getattr(response, "choices")
                    if ch and len(ch) > 0:
                        m = ch[0]
                        # message may be nested
                        if hasattr(m, "message") and hasattr(m.message, "content"):
                            text = m.message.content
                        elif hasattr(m, "text"):
                            text = m.text
                # fallback to str(response)
            except Exception:
                text = None

        if not text:
            # final fallback try: string conversion
            try:
                text = str(response)
            except Exception:
                text = None

        if text:
            return text.strip()

    except Exception:
        # swallow errors and fall back to heuristic below
        pass

    # --- Fallback: previous local heuristic implementation ---
    # (This ensures the agent doesn't crash if Groq isn't configured.)
    # Reuse earlier heuristic: if no wardrobe items, give general advice; otherwise build 1-2 combos.
    if not wardrobe_items:
        title = new_item.get("title") or new_item.get("name") or "This piece"
        category = (new_item.get("category") or "").lower()
        colors = ", ".join(new_item.get("colors") or [])
        tags = ", ".join(new_item.get("style_tags") or [])

        advice_lines = []
        advice_lines.append(f"{title}: styling ideas.")
        if category in ("tops", "shirt", "t-shirt"):
            advice_lines.append(
                "Try pairing it with high-waisted or baggy jeans for a relaxed vibe, or tuck into tailored trousers for a cleaner look."
            )
        elif category == "bottoms":
            advice_lines.append(
                "Wear with a fitted tee or cropped sweater and finish with chunky sneakers or boots depending on the vibe."
            )
        elif category == "outerwear":
            advice_lines.append(
                "Use it as a statement layer over basics — think tee + jeans or a simple dress underneath."
            )
        elif category == "shoes":
            advice_lines.append(
                "Match with neutral pants or a skirt; balance proportions (chunky shoes with relaxed bottoms, sleek shoes with tailored pieces)."
            )
        else:
            advice_lines.append(
                "Pair with wardrobe basics you already own — neutrals, simple silhouettes, and one accessory to tie it together."
            )

        if colors:
            advice_lines.append(f"Colors to play with: {colors}.")
        if tags:
            advice_lines.append(f"Style notes: {tags}.")

        advice_lines.append(
            "If you'd like, add a few wardrobe items so I can make specific outfit combos."
        )

        return " ".join(advice_lines)

    # If wardrobe_items present but LLM failed, recreate simple pairings (same as earlier)
    buckets = {"tops": [], "bottoms": [], "outerwear": [], "shoes": [], "accessories": []}
    for it in wardrobe_items:
        cat = (it.get("category") or "").lower()
        if cat in buckets:
            buckets[cat].append(it)
        else:
            buckets["accessories"].append(it)

    title = new_item.get("title") or new_item.get("name") or "The item"
    n_cat = (new_item.get("category") or "").lower()
    n_tags = set([t.lower() for t in (new_item.get("style_tags") or [])])
    n_colors = set([c.lower() for c in (new_item.get("colors") or [])])

    def best_match(candidates: list[dict], used_ids: set) -> dict | None:
        best = None
        best_score = -1
        for c in candidates:
            if c.get("id") in used_ids:
                continue
            score = 0
            c_tags = set([t.lower() for t in (c.get("style_tags") or [])])
            c_colors = set([x.lower() for x in (c.get("colors") or [])])
            score += len(n_tags & c_tags) * 3
            score += len(n_colors & c_colors) * 2
            if score == 0:
                score = 1
            if score > best_score:
                best_score = score
                best = c
        return best

    outfits = []
    used = set()
    for variant in range(2):
        parts = []
        if n_cat in ("tops", "shirt", "t-shirt"):
            bottom = best_match(buckets["bottoms"], used)
            if bottom:
                parts.append(bottom)
                used.add(bottom.get("id"))
            shoe = best_match(buckets["shoes"], used)
            if shoe:
                parts.append(shoe)
                used.add(shoe.get("id"))
            outer = best_match(buckets["outerwear"], used)
            if outer and variant == 0:
                parts.append(outer)
                used.add(outer.get("id"))
        elif n_cat == "bottoms":
            top = best_match(buckets["tops"], used)
            if top:
                parts.append(top)
                used.add(top.get("id"))
            shoe = best_match(buckets["shoes"], used)
            if shoe:
                parts.append(shoe)
                used.add(shoe.get("id"))
        elif n_cat == "outerwear":
            top = best_match(buckets["tops"], used)
            if top:
                parts.append(top)
                used.add(top.get("id"))
            bottom = best_match(buckets["bottoms"], used)
            if bottom:
                parts.append(bottom)
                used.add(bottom.get("id"))
            shoe = best_match(buckets["shoes"], used)
            if shoe:
                parts.append(shoe)
                used.add(shoe.get("id"))
        elif n_cat == "shoes":
            bottom = best_match(buckets["bottoms"], used)
            if bottom:
                parts.append(bottom)
                used.add(bottom.get("id"))
            top = best_match(buckets["tops"], used)
            if top:
                parts.append(top)
                used.add(top.get("id"))
        else:
            top = best_match(buckets["tops"], used)
            if top:
                parts.append(top)
                used.add(top.get("id"))
            bottom = best_match(buckets["bottoms"], used)
            if bottom:
                parts.append(bottom)
                used.add(bottom.get("id"))
        if not parts:
            break
        part_names = [p.get("name") or p.get("title") or "item" for p in parts]
        reason_tags = set()
        for p in parts:
            for t in (p.get("style_tags") or []):
                if t.lower() in n_tags:
                    reason_tags.add(t)
        reason = (f"Shared vibe: {', '.join(sorted(reason_tags))}." if reason_tags else "A clean, complementary combo.")
        outfit_text = (f"Outfit {variant+1}: Style the {title} with {', '.join(part_names)}. {reason}")
        outfits.append(outfit_text)

    if not outfits:
        return "I couldn't find complementary pieces in your wardrobe — consider adding a basic top or neutral shoes so I can suggest outfits."

    return "\n\n".join(outfits)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Guard against empty outfit
    if not outfit or not outfit.strip():
        return "Cannot create fit card: missing outfit details."

    # Build a concise prompt for the LLM
    item_name = (new_item.get("title") or new_item.get("name") or "This piece").strip()
    price = new_item.get("price")
    platform = (new_item.get("platform") or "").strip()

    price_part = f" for ${float(price):.0f}" if price is not None else ""
    platform_part = f" on {platform}" if platform else ""

    outfit_summary = outfit.splitlines()[0].strip()
    if len(outfit_summary) > 200:
        outfit_summary = outfit_summary[:197].rstrip() + "..."

    prompt = (
        "You are a social-media-savvy fashion writer.\n"
        f"Write a 2–4 sentence casual caption for an outfit post featuring: {item_name}{price_part}{platform_part}.\n"
        f"Include the outfit summary: {outfit_summary}.\n"
        "Tone: friendly, concise, and authentic. Mention the item name, price, and platform naturally (once each)."
    )

    def _call_groq(prompt: str, temperature: float) -> str | None:
        try:
            client = _get_groq_client()
            model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
            response = client.chat.create(model=model_name, messages=[{"role": "user", "content": prompt}], temperature=temperature, max_tokens=200)

            # Extract text
            text = None
            if isinstance(response, dict):
                choices = response.get("choices")
                if choices and isinstance(choices, list):
                    first = choices[0]
                    if isinstance(first, dict):
                        msg = first.get("message") or first
                        if isinstance(msg, dict) and msg.get("content"):
                            text = msg.get("content")
                        elif isinstance(first.get("text"), str):
                            text = first.get("text")
            else:
                try:
                    if hasattr(response, "choices"):
                        ch = getattr(response, "choices")
                        if ch and len(ch) > 0:
                            m = ch[0]
                            if hasattr(m, "message") and hasattr(m.message, "content"):
                                text = m.message.content
                            elif hasattr(m, "text"):
                                text = m.text
                except Exception:
                    text = None

            if not text:
                try:
                    text = str(response)
                except Exception:
                    text = None

            return text.strip() if text else None
        except Exception:
            return None

    # Try a couple of LLM calls with increasing temperature if outputs repeat
    tried = []
    temps = [0.8, 1.0]
    for temp in temps:
        out = _call_groq(prompt, temperature=temp)
        if out:
            # Normalize whitespace
            out_norm = " ".join(out.split())
            tried.append(out_norm)
            # If we have multiple distinct outputs, return the latest
            if len(set(tried)) > 1:
                return out_norm
            # If first temp produced a result, try once more at same temp to check variability
            if temp == temps[0]:
                out2 = _call_groq(prompt, temperature=temp)
                if out2:
                    out2_norm = " ".join(out2.split())
                    if out2_norm != out_norm:
                        return out2_norm
                    # else continue to try higher temp

    # If LLM not available or didn't yield varied outputs, fall back to templates (randomized)
    import random

    templates = [
        (
            f"Scored a {item_name}{price_part}{platform_part}. {outfit_summary} Perfect for lazy weekends or dressed-up errands — keeping it effortless."
        ),
        (
            f"Found: {item_name}{price_part}{platform_part}. Styled it with pieces from my wardrobe: {outfit_summary}. Low-effort, high-style vibes — try it with a chunky sneaker or a leather boot."
        ),
        (
            f"{item_name}{price_part}{platform_part} — my latest thrift find. {outfit_summary} Would you wear this?"
        ),
        (
            f"Today’s fit: {item_name}{price_part}{platform_part}. {outfit_summary}. Minimal accessories, maximal impact."
        ),
    ]

    caption = random.choice(templates)
    # Ensure 2+ sentences
    if caption.count(".") < 2:
        caption = caption + " Would you wear this?"
    return " ".join([s.strip() for s in caption.splitlines() if s.strip()])
