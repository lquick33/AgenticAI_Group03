# Langfuse Prompt: material-classifier/classification

## Prompt Name
`material-classifier/classification`

## Prompt Type
Text (not chat)

## Label
`production`

## Variables
- `page_summaries`: Aggregated summaries from lecture pages (first 10 pages)
- `key_terms`: Comma-separated list of key terms from all pages (first 50 terms)

## Prompt Content

```
Analyze the following lecture material and classify it into one of these categories:

**Categories:**
- language_learning: Materials focused on vocabulary, grammar, translations, language practice, verb conjugations, pronunciation guides, language-specific terminology
- math: Materials with formulas, equations, proofs, mathematical concepts, derivatives, integrals, theorems, mathematical notation, problem sets
- business_administration: Materials covering business models, case studies, management concepts, strategy, marketing, financial terms, organizational behavior
- computer_science: Materials covering algorithms, data structures, programming, software engineering, operating systems, databases, computer architecture, networking, theoretical computer science
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
  "category": "one of: language_learning, math, business_administration, computer_science, or general",
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

Now classify the provided material:
```

## Instructions for Creating in Langfuse

1. Log into your Langfuse dashboard
2. Navigate to **Prompts** section
3. Click **Create Prompt** or **New Prompt**
4. Set the following:
   - **Name**: `material-classifier/classification`
   - **Type**: `Text` (not Chat)
   - **Label**: `production`
5. Paste the prompt content above into the prompt editor
6. Add variables:
   - `page_summaries` (type: String)
   - `key_terms` (type: String)
7. Save the prompt

## Testing

After creating the prompt, you can test it with sample data:

**Test Input:**
- `page_summaries`: "This lecture covers verb conjugations in Spanish. We learn about regular and irregular verbs. Practice exercises include vocabulary matching."
- `key_terms`: "verb, conjugation, vocabulary, grammar, Spanish, irregular, regular"

**Expected Output:**
```json
{
  "category": "language_learning",
  "confidence": 0.95,
  "reasoning": "Material focuses on language learning with verb conjugations, vocabulary, and grammar rules specific to Spanish."
}
```

## Notes

- The prompt uses `{{variable_name}}` syntax for Langfuse variable interpolation
- The structured output will be parsed by the `MaterialClassification` Pydantic model
- If the prompt fails to load, the code falls back to a hardcoded version in `_get_fallback_classification_prompt()`
