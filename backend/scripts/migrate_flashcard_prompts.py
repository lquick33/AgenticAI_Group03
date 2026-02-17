"""
Script to migrate flashcard prompts to the new classification-based structure.

This script:
1. Fetches the existing flashcard-agent/card-generation prompt
2. Creates a base prompt (flashcard-agent/card-generation-base)
3. Creates classification-specific prompts that extend the base
4. Optionally keeps the old prompt as general for backward compatibility

Usage:
    python scripts/migrate_flashcard_prompts.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.observability import get_langfuse_client
from app.core.config import settings

OLD_PROMPT_NAME = "flashcard-agent/card-generation"
BASE_PROMPT_NAME = "flashcard-agent/card-generation-base"
PROMPT_LABEL = "production"

# Classification-specific additions
CLASSIFICATION_ADDITIONS = {
    "language_learning": """
**Language Learning Specific Instructions:**
- Focus on vocabulary, grammar rules, and translations
- Create cards for verb conjugations, word meanings, and usage examples
- Include pronunciation hints when relevant
- Use language-specific tags (e.g., "vocabulary", "grammar", "verb")
- For vocabulary cards: front = word/phrase, back = translation + example sentence
- For grammar cards: front = rule/question, back = explanation + examples

**Language Learning Examples:**
- Vocabulary: Front: "你好", Back: "Hello (Chinese greeting). Example: 你好，我是小明。"
- Grammar: Front: "When to use 的 vs 地?", Back: "的 for nouns, 地 for adverbs..."
""",
    "math": """
**Math Specific Instructions:**
- Focus on formulas, equations, proofs, and mathematical concepts
- Create cards for problem-solving steps and theorem applications
- Include step-by-step solutions when relevant
- Use math-specific tags (e.g., "formula", "theorem", "proof", "calculation")
- For formula cards: front = formula name/question, back = formula + explanation + example
- For concept cards: front = concept/question, back = definition + proof/derivation + application

**Math Examples:**
- Formula: Front: "What is the derivative of x²?", Back: "d/dx(x²) = 2x. This is the power rule..."
- Theorem: Front: "Pythagorean Theorem", Back: "a² + b² = c². In a right triangle..."
""",
    "business_administration": """
**Business Administration Specific Instructions:**
- Focus on business models, case studies, management concepts, and strategic thinking
- Create cards for business terminology and real-world applications
- Include case study examples when relevant
- Use business-specific tags (e.g., "strategy", "case_study", "management", "marketing")
- For concept cards: front = business concept/question, back = definition + real-world example
- For case study cards: front = case scenario, back = analysis + key takeaways

**Business Examples:**
- Concept: Front: "What is SWOT Analysis?", Back: "SWOT = Strengths, Weaknesses, Opportunities, Threats. Example: A company's SWOT..."
- Case Study: Front: "How did Company X enter market Y?", Back: "Company X used strategy Z because..."
""",
    "general": """
**General Instructions:**
- Create clear, concise flashcards covering key concepts
- Focus on understanding rather than memorization
- Include context and examples when helpful
- Use appropriate tags for categorization
"""
}


def get_existing_prompt_content(langfuse_client):
    """Fetch the existing flashcard prompt from Langfuse."""
    try:
        existing_prompt = langfuse_client.get_prompt(OLD_PROMPT_NAME, label=PROMPT_LABEL)
        
        # Extract prompt content
        if hasattr(existing_prompt, 'prompt'):
            return str(existing_prompt.prompt)
        elif hasattr(existing_prompt, 'messages') and existing_prompt.messages:
            # For chat prompts, get first message content
            first_msg = existing_prompt.messages[0]
            if isinstance(first_msg, dict):
                return first_msg.get('content', '')
            elif hasattr(first_msg, 'content'):
                return str(first_msg.content)
        else:
            # Try to compile with empty vars to get template
            try:
                return existing_prompt.compile()
            except:
                pass
        
        return None
    except Exception as e:
        print(f"⚠️  Could not fetch existing prompt: {e}")
        return None


def extract_base_prompt(full_prompt_content):
    """
    Extract base prompt from existing prompt.
    
    Removes subject-specific content and keeps common instructions.
    """
    if not full_prompt_content:
        return None
    
    # Try to identify and remove subject-specific sections
    # This is a heuristic - you may need to adjust based on your actual prompt structure
    base_prompt = full_prompt_content
    
    # Remove common subject-specific keywords/phrases if they exist
    subject_keywords = [
        "Language Learning", "language learning", "vocabulary", "grammar",
        "Math", "mathematical", "formula", "theorem",
        "Business", "business", "case study", "management"
    ]
    
    # For now, we'll use the full prompt as base
    # You can customize this extraction logic based on your prompt structure
    return base_prompt


def create_base_prompt(langfuse_client, base_content):
    """Create the base prompt in Langfuse."""
    print(f"\n🟡 Creating base prompt: {BASE_PROMPT_NAME}")
    
    # Check if already exists
    try:
        existing = langfuse_client.get_prompt(BASE_PROMPT_NAME, label=PROMPT_LABEL)
        print(f"⚠️  Base prompt already exists")
        response = input("   Do you want to update it? (y/n): ")
        if response.lower() != 'y':
            print("   Skipping base prompt creation")
            return False
    except Exception:
        pass
    
    # Create base prompt
    # Base prompt should contain common instructions
    base_prompt_content = """You are a flashcard generator that creates educational flashcards from lecture materials.

**General Instructions:**
- Create 1-2 flashcards per page based on content complexity
- Front side should be a clear question or prompt
- Back side should contain the answer with context
- Use appropriate tags for categorization
- Consider conversation context when available
- Include visual snippets when relevant

**Output Format:**
You must respond with a valid JSON object matching this structure:
{
  "cards": [
    {
      "front": "question or prompt",
      "back": "answer with context",
      "tags": ["tag1", "tag2"]
    }
  ]
}

**Page Information:**
- Summary: {{summary}}
- Key Terms: {{key_terms}}
- Exam Questions: {{exam_questions}}
- Diagram Description: {{diagram_description}}
- Conversation Context: {{conversation_context}}
- Course ID: {{course_id}}
- Material ID: {{material_id}}
- Page Number: {{page_number}}
{{snippet_image_url}}"""
    
    try:
        if hasattr(langfuse_client, 'create_prompt'):
            langfuse_client.create_prompt(
                name=BASE_PROMPT_NAME,
                prompt=base_prompt_content,
                labels=[PROMPT_LABEL],
                type="text"
            )
            print(f"✅ Successfully created base prompt")
            return True
        elif hasattr(langfuse_client, 'prompts'):
            langfuse_client.prompts.create(
                name=BASE_PROMPT_NAME,
                prompt=base_prompt_content,
                labels=[PROMPT_LABEL],
                type="text"
            )
            print(f"✅ Successfully created base prompt")
            return True
        else:
            print("⚠️  Cannot create prompt programmatically")
            print(f"   Please create manually: {BASE_PROMPT_NAME}")
            return False
    except Exception as e:
        print(f"❌ Error creating base prompt: {e}")
        return False


def create_classification_prompt(langfuse_client, classification, addition):
    """Create a classification-specific prompt that extends the base."""
    prompt_name = f"flashcard-agent/card-generation-{classification}"
    print(f"\n🟡 Creating prompt: {prompt_name}")
    
    # Check if already exists
    try:
        existing = langfuse_client.get_prompt(prompt_name, label=PROMPT_LABEL)
        print(f"⚠️  Prompt already exists")
        response = input("   Do you want to update it? (y/n): ")
        if response.lower() != 'y':
            print("   Skipping")
            return False
    except Exception:
        pass
    
    # Create prompt that extends base
    prompt_content = f"""{{{{base_prompt_content}}}}
{addition}"""
    
    try:
        if hasattr(langfuse_client, 'create_prompt'):
            langfuse_client.create_prompt(
                name=prompt_name,
                prompt=prompt_content,
                labels=[PROMPT_LABEL],
                type="text"
            )
            print(f"✅ Successfully created {classification} prompt")
            return True
        elif hasattr(langfuse_client, 'prompts'):
            langfuse_client.prompts.create(
                name=prompt_name,
                prompt=prompt_content,
                labels=[PROMPT_LABEL],
                type="text"
            )
            print(f"✅ Successfully created {classification} prompt")
            return True
        else:
            print("⚠️  Cannot create prompt programmatically")
            print(f"   Please create manually: {prompt_name}")
            return False
    except Exception as e:
        print(f"❌ Error creating {classification} prompt: {e}")
        return False


def migrate_prompts():
    """Main migration function."""
    print("=" * 60)
    print("Flashcard Prompt Migration Script")
    print("=" * 60)
    print()
    
    # Check if Langfuse is enabled
    if not settings.LANGFUSE_ENABLED:
        print("❌ Error: Langfuse is not enabled (LANGFUSE_ENABLED=False)")
        print("   Please enable Langfuse in your .env file")
        return False
    
    # Get Langfuse client
    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        print("❌ Error: Failed to initialize Langfuse client")
        print("   Please check your LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env")
        return False
    
    # Fetch existing prompt
    print(f"📥 Fetching existing prompt: {OLD_PROMPT_NAME}")
    existing_content = get_existing_prompt_content(langfuse_client)
    
    if existing_content:
        print(f"✅ Found existing prompt ({len(existing_content)} characters)")
        print("\n   The existing prompt will be used as reference.")
        print("   You can optionally keep it as 'general' for backward compatibility.")
    else:
        print("⚠️  Could not fetch existing prompt (may not exist yet)")
        print("   Will create new prompts from template")
    
    # Create base prompt
    base_success = create_base_prompt(langfuse_client, existing_content)
    
    if not base_success:
        print("\n⚠️  Base prompt creation failed or skipped")
        print("   Classification prompts will still be created but may not work correctly")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Create classification-specific prompts
    print("\n" + "=" * 60)
    print("Creating Classification-Specific Prompts")
    print("=" * 60)
    
    results = {}
    for classification, addition in CLASSIFICATION_ADDITIONS.items():
        success = create_classification_prompt(langfuse_client, classification, addition)
        results[classification] = success
    
    # Summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Base prompt: {'✅ Created' if base_success else '❌ Failed/Skipped'}")
    for classification, success in results.items():
        status = "✅ Created" if success else "❌ Failed/Skipped"
        print(f"{classification}: {status}")
    
    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("1. Review the prompts in Langfuse UI")
    print("2. Customize classification-specific prompts as needed")
    print("3. Test flashcard generation with different material classifications")
    print("\nNote: The old prompt 'flashcard-agent/card-generation' is still available")
    print("      for backward compatibility. You can delete it after testing.")
    
    return True


if __name__ == "__main__":
    try:
        success = migrate_prompts()
        if success:
            print("\n✅ Migration completed!")
        else:
            print("\n⚠️  Migration had issues - check output above")
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
