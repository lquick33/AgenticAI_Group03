"""
Script to create the material-classifier/classification prompt in Langfuse.

This script creates the prompt programmatically using the Langfuse SDK.
Run this script once to set up the prompt in your Langfuse instance.

Usage:
    python scripts/create_classification_prompt.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.observability import get_langfuse_client
from app.core.config import settings

PROMPT_NAME = "material-classifier/classification"
PROMPT_LABEL = "production"

PROMPT_CONTENT = """Analyze the following lecture material and classify it into one of these categories:

**Categories:**
- language_learning: Materials focused on vocabulary, grammar, translations, language practice, verb conjugations, pronunciation guides, language-specific terminology
- math: Materials with formulas, equations, proofs, mathematical concepts, derivatives, integrals, theorems, mathematical notation, problem sets
- business_administration: Materials covering business models, case studies, management concepts, strategy, marketing, financial terms, organizational behavior
- general: General educational materials without specific domain focus, mixed content, or content that doesn't clearly fit the above categories

**Material Content:**

Page Summaries:
{{page_summaries}}

Key Terms: {{key_terms}}

**Instructions:**
1. Analyze the page summaries and key terms to identify the primary domain
2. Look for domain-specific indicators:
   - Language learning: vocabulary lists, grammar rules, translations, verb forms, language exercises
   - Math: mathematical formulas, equations, proofs, calculus, algebra, geometry concepts
   - Business: case studies, business models, management theories, marketing strategies, financial concepts
3. Determine the most appropriate category
4. Provide a confidence score (0.0 to 1.0) based on how clearly the material fits the category
5. Provide brief reasoning (1-2 sentences) explaining your classification choice

**Output Format:**
You must respond with a valid JSON object matching this exact structure:
{
  "category": "one of: language_learning, math, business_administration, or general",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation (1-2 sentences)"
}

**Examples:**

Example 1 (Language Learning):
Input: Summaries mention "verb conjugation", "vocabulary list", "grammar rules"
Output: {"category": "language_learning", "confidence": 0.95, "reasoning": "Material contains vocabulary lists, grammar rules, and verb conjugations typical of language learning courses."}

Example 2 (Math):
Input: Summaries mention "derivative", "integral", "theorem", "proof"
Output: {"category": "math", "confidence": 0.98, "reasoning": "Material focuses on mathematical concepts including derivatives, integrals, and proofs, clearly indicating a mathematics course."}

Example 3 (Business):
Input: Summaries mention "case study", "business model", "marketing strategy"
Output: {"category": "business_administration", "confidence": 0.92, "reasoning": "Content includes case studies, business models, and marketing strategies typical of business administration courses."}

Example 4 (General):
Input: Summaries are mixed or don't clearly indicate a specific domain
Output: {"category": "general", "confidence": 0.65, "reasoning": "Material contains mixed content without a clear focus on a specific academic domain."}

Now classify the provided material:"""


def create_prompt():
    """Create the classification prompt in Langfuse."""
    print(f"🟡 Creating Langfuse prompt: {PROMPT_NAME}")
    
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
    
    try:
        # Check if prompt already exists
        try:
            existing_prompt = langfuse_client.get_prompt(PROMPT_NAME, label=PROMPT_LABEL)
            print(f"⚠️  Prompt '{PROMPT_NAME}' with label '{PROMPT_LABEL}' already exists")
            response = input("   Do you want to update it? (y/n): ")
            if response.lower() != 'y':
                print("   Skipping prompt creation")
                return False
        except Exception:
            # Prompt doesn't exist, which is fine - we'll create it
            pass
        
        # Create or update the prompt
        # Note: Langfuse SDK v3+ uses create_prompt() method
        # The exact API may vary, so we'll try different approaches
        
        try:
            # Try using the client's prompt creation method
            # This depends on the Langfuse SDK version
            if hasattr(langfuse_client, 'create_prompt'):
                result = langfuse_client.create_prompt(
                    name=PROMPT_NAME,
                    prompt=PROMPT_CONTENT,
                    labels=[PROMPT_LABEL],
                    type="text"  # Text prompt, not chat
                )
                print(f"✅ Successfully created prompt: {PROMPT_NAME}")
                return True
            elif hasattr(langfuse_client, 'prompts'):
                # Alternative API structure
                result = langfuse_client.prompts.create(
                    name=PROMPT_NAME,
                    prompt=PROMPT_CONTENT,
                    labels=[PROMPT_LABEL],
                    type="text"
                )
                print(f"✅ Successfully created prompt: {PROMPT_NAME}")
                return True
            else:
                print("⚠️  Warning: Langfuse client doesn't have create_prompt method")
                print("   This might be due to SDK version differences")
                print("   Please create the prompt manually in Langfuse UI:")
                print(f"   - Name: {PROMPT_NAME}")
                print(f"   - Label: {PROMPT_LABEL}")
                print(f"   - Type: Text")
                print(f"   - Content: See langfuse_prompts/material-classifier-classification.md")
                return False
        except AttributeError as e:
            print(f"⚠️  Warning: {e}")
            print("   The Langfuse SDK version might not support programmatic prompt creation")
            print("   Please create the prompt manually in Langfuse UI")
            print(f"   See: backend/langfuse_prompts/material-classifier-classification.md")
            return False
        except Exception as e:
            print(f"❌ Error creating prompt: {e}")
            print("   Please create the prompt manually in Langfuse UI")
            print(f"   See: backend/langfuse_prompts/material-classifier-classification.md")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Langfuse Prompt Creation Script")
    print("=" * 60)
    print()
    
    success = create_prompt()
    
    print()
    if success:
        print("✅ Prompt creation completed successfully!")
        print(f"   You can now use the prompt '{PROMPT_NAME}' in your application")
    else:
        print("⚠️  Prompt creation failed or skipped")
        print("   Please create the prompt manually in Langfuse UI")
        print("   See: backend/langfuse_prompts/material-classifier-classification.md")
    
    print("=" * 60)
