"""
Script to create the search-topic/intro-page-pick prompt in Langfuse.

Run once to seed the prompt so the Search Topic tool uses Langfuse for
intro-page selection. Variables: {{query}}, {{candidates_text}}.

Usage:
    cd Group3/backend && python scripts/create_intro_page_prompt.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.observability import get_langfuse_client
from app.core.config import settings

PROMPT_NAME = "search-topic/intro-page-pick"
PROMPT_LABEL = "production"

# Same content as INTRO_PAGE_LLM_PROMPT_FALLBACK but with Langfuse variables {{query}}, {{candidates_text}}
PROMPT_CONTENT = """The user wants to learn about: "{{query}}"

Below are candidate pages from their lecture materials. Each has: page number, material name, chapter/section title (if any), a short summary, and key terms.

{{candidates_text}}

Task: Which single page is the best **introduction / start** to learn this concept? Prefer:
- Section or chapter title slides that introduce the topic
- The first page of a block of related content (earlier page numbers when in doubt)
- Pages whose title or summary clearly introduces the concept

Return the page number (integer) of that page and a brief reason."""


def create_prompt():
    """Create the intro-page-pick prompt in Langfuse."""
    print(f"🟡 Creating Langfuse prompt: {PROMPT_NAME}")

    if not settings.LANGFUSE_ENABLED:
        print("❌ Error: Langfuse is not enabled (LANGFUSE_ENABLED=False)")
        return False

    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        print("❌ Error: Failed to initialize Langfuse client")
        return False

    try:
        existing = langfuse_client.get_prompt(PROMPT_NAME, label=PROMPT_LABEL)
        print(f"⚠️  Prompt already exists. Update it in the Langfuse UI if needed.")
        return True
    except Exception:
        pass

    try:
        if hasattr(langfuse_client, "create_prompt"):
            langfuse_client.create_prompt(
                name=PROMPT_NAME,
                prompt=PROMPT_CONTENT,
                labels=[PROMPT_LABEL],
                type="text",
            )
        elif hasattr(langfuse_client, "prompts") and hasattr(langfuse_client.prompts, "create"):
            langfuse_client.prompts.create(
                name=PROMPT_NAME,
                prompt=PROMPT_CONTENT,
                labels=[PROMPT_LABEL],
                type="text",
            )
        else:
            print("⚠️  Cannot create prompt programmatically. Create in Langfuse UI:")
            print(f"   Name: {PROMPT_NAME}")
            print("   Variables: query, candidates_text")
            return False
        print(f"✅ Created prompt: {PROMPT_NAME}")
        return True
    except Exception as e:
        print(f"❌ Error creating prompt: {e}")
        return False


if __name__ == "__main__":
    success = create_prompt()
    sys.exit(0 if success else 1)
