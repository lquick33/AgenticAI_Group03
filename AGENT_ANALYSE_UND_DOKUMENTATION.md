# Agent-Analyse und Projekt-Dokumentation

## Übersicht

Dieses Dokument analysiert die aktuellen Agenten im Lernkompanien-Projekt, beschreibt deren Funktionsweise, die Projektarchitektur und den Bezug zu den Anforderungen aus der Aufgabenstellung.

**Erstellt am**: 2026-01-26  
**Projekt**: Lernkompanien (Adaptive Learning Assistant)  
**Kurs**: Agentic Artificial Intelligence

---

## Inhaltsverzeichnis

1. [Projekt-Übersicht](#projekt-übersicht)
2. [Aktuelle Agenten-Architektur](#aktuelle-agenten-architektur)
3. [Detaillierte Agent-Beschreibungen](#detaillierte-agent-beschreibungen)
4. [Projektstruktur und Aufbau](#projektstruktur-und-aufbau)
5. [Bezug zu den Aufgabenanforderungen](#bezug-zu-den-aufgabenanforderungen)
6. [Agentic Characteristics Analyse](#agentic-characteristics-analyse)
7. [Technische Implementierung](#technische-implementierung)
8. [Zusammenfassung und Ausblick](#zusammenfassung-und-ausblick)

---

## Projekt-Übersicht

### Problemstellung

**Lernkompanien** ist ein KI-gestütztes Lernökosystem, das Studierende nicht nur administrativ (Planung) sondern auch inhaltlich (Tutoring) und psychologisch (Proaktivität) unterstützt. Das System passt sich dynamisch an den tatsächlichen Lernfortschritt und die Persönlichkeit des Nutzers an.

### Kernfunktionen

1. **Intelligente Inhaltsanalyse**: Multimodale Analyse von Vorlesungsfolien (PDF → Bild → GPT-4o Vision)
2. **Proaktive Kalenderverwaltung**: Google Calendar Integration mit automatischer Lernplanung
3. **KI-Tutor**: Erklärt Vorlesungsmaterialien, beantwortet Fragen, prüft Verständnis
4. **Quiz-Generierung**: Automatische Erstellung von Verständnisfragen
5. **Flashcard-Generierung**: Anki-kompatible Karteikarten aus Vorlesungsmaterial
6. **Adaptive Plananpassung**: Überwachung des Lernfortschritts und automatische Anpassung

### Technologie-Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14/15 (App Router, TypeScript)
- **AI Orchestration**: LangGraph für Agent State Machines
- **AI Framework**: LangChain für LLM-Integration und Tools
- **LLM Provider**: Google Gemini (primär), OpenAI GPT-4o (Vision)
- **Datenbank**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Observability**: Langfuse für Prompt-Management und Tracing

---

## Aktuelle Agenten-Architektur

### Agent-Übersicht

Das Projekt implementiert derzeit **3 Hauptagenten**:

1. **TutorAgent** (`backend/app/agents/tutor/tutor_agent.py`)
   - Hauptagent für Studiersitzungen
   - Erklärt Vorlesungsmaterialien
   - Beantwortet Fragen
   - Erstellt Quizzes bei Bedarf

2. **QuizGeneratorAgent** (`backend/app/agents/quiz/quiz_generator_agent.py`)
   - Subagent für Quiz-Generierung
   - Wird vom TutorAgent aufgerufen
   - Erstellt 3-8 Verständnisfragen pro Thema

3. **FlashcardGeneratorAgent** (`backend/app/agents/flashcards/flashcard_agent.py`)
   - Generiert Anki-kompatible Flashcards
   - Verarbeitet Seitenanalysen und Konversationshistorie
   - Exportiert CSV-Format für Anki

### Architektur-Pattern

Alle Agenten folgen dem **BaseAgent Pattern**:

```
BaseAgent (Abstract Base Class)
├── TutorAgent
├── QuizGeneratorAgent
└── FlashcardGeneratorAgent
```

**Kernkomponenten von BaseAgent**:
- `_build_graph()`: Abstrakte Methode zum Erstellen des LangGraph-Graphen
- `compile_graph()`: Kompiliert Graph mit Checkpointer und Store
- `run()` / `arun()`: Synchrone/asynchrone Ausführung
- `stream()`: Streaming-Ausführung
- `checkpointer`: Optional für Persistenz
- `store`: Optional für langfristige Erinnerungen

---

## Detaillierte Agent-Beschreibungen

### 1. TutorAgent

#### Zweck und Verantwortlichkeiten

Der **TutorAgent** ist der Hauptagent für Studiersitzungen. Er unterstützt Studierende beim Verstehen von Vorlesungsmaterialien durch:

- **Kontextbewusste Erklärungen**: Nutzt strukturierte Seitenanalysen aus der Datenbank
- **Interaktive Q&A**: Beantwortet Fragen zur aktuellen Folie
- **Verständnisprüfung**: Fragt nach, ob Themen verstanden wurden
- **Quiz-Erstellung**: Erstellt automatisch Quizzes bei Abschluss eines Unterthemas

#### State Schema

```python
class TutorState(MessagesState):
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    user_id: Optional[str] = None
    course_material_summary: Optional[dict] = None
```

**Erweitert `MessagesState`** für automatisches Message-Handling mit `add_messages` Reducer.

#### Graph-Struktur

```
START → agent (call_model) → should_continue
                              ├─→ tools (ToolNode) → agent (Loop)
                              └─→ END
```

**Nodes**:
1. **`call_model`**: Ruft LLM mit aktuellen Messages auf
   - Truncated Message History (letzte 10 Messages)
   - System Message mit Kontext (Seite, Material-ID)
   - State-Injection für Tools (material_id, current_page, user_id)
   
2. **`tools`**: StateAwareToolNode
   - Führt Tool-Calls aus
   - Injiziert automatisch State-Werte (material_id, current_page, user_id)
   - Verhindert Halluzinationen von IDs durch LLM

3. **`should_continue`**: Conditional Routing
   - Prüft ob Tools aufgerufen werden sollen
   - Spezialbehandlung für `create_quiz`: Graph endet nach Quiz-Erstellung

#### Tools

Der TutorAgent hat Zugriff auf **3 Tools**:

1. **`get_page_analysis`** (`app/tools/page_analysis_tool.py`)
   - Ruft strukturierte Seitenanalyse aus `page_analyses` Tabelle ab
   - Parameter: `course_material_id`, `page_number`, `user_id`
   - Rückgabe: JSON mit `summary`, `key_terms`, `exam_questions`, `diagram_description`

2. **`get_course_material_summary`** (`app/tools/course_material_tool.py`)
   - Ruft globale Kursübersicht ab
   - Parameter: `course_material_id`, `user_id`
   - Rückgabe: Zusammenfassung aller Themen des Kurses

3. **`create_quiz`** (`app/tools/quiz_tool.py`)
   - Erstellt Quiz für abgeschlossenes Unterthema
   - Parameter: `start_page`, `end_page`, `course_material_id`, `user_id`
   - Ruft intern `QuizGeneratorAgent` auf
   - Speichert Quiz in Datenbank
   - Rückgabe: Quiz-ID und Quiz-Daten

#### Persönlichkeitsanpassung

Der TutorAgent unterstützt **Personalisierung**:

- **Sprache**: Deutsch (Standard) oder Englisch
- **Persönlichkeit**:
  - `formality`: "formal" | "informal" | "balanced"
  - `humor`: "none" | "light" | "moderate"
  - `encouragement`: "reserved" | "moderate" | "enthusiastic"

**Prompt-Management**: System-Prompts werden aus **Langfuse** geladen:
- Prompt-Name: `tutor-agent/system-prompt-{language}`
- Label: `production`
- Type: `chat`

#### Message History Management

**Sliding Window Approach**:
- Maximal 10 Messages im Kontext (SystemMessage + letzte 9 Messages)
- Verhindert Token-Explosion bei langen Konversationen
- Tool-Call-Paare bleiben zusammen (AIMessage + ToolMessages)

#### Besonderheiten

1. **State-Aware Tool Injection**: 
   - `StateAwareToolNode` injiziert automatisch `material_id`, `current_page`, `user_id`
   - LLM muss diese Parameter nicht explizit angeben
   - Verhindert Fehler durch fehlende IDs

2. **Gemini API Kompatibilität**:
   - `_fix_incomplete_tool_calls()`: Validiert Message-Ordnung
   - Gemini erfordert strikte Reihenfolge: HumanMessage → AIMessage (tool_calls) → ToolMessages
   - Entfernt unvollständige Tool-Call-Paare

3. **Quiz-Erstellung Flow**:
   - Nach `create_quiz` Tool-Call endet Graph automatisch
   - Verhindert, dass Agent nach Quiz-Erstellung noch schreibt
   - Quiz wird im Frontend angezeigt, Agent wartet auf User-Input

#### Observability

- **Langfuse Integration**: 
  - Automatisches Tracking via `CallbackHandler`
  - Metadata: `user_id`, `session_id` (material_id), `material_id`, `current_page`
  - Run-Name: `tutor-agent/llm-call`

---

### 2. QuizGeneratorAgent

#### Zweck und Verantwortlichkeiten

Der **QuizGeneratorAgent** ist ein **Subagent**, der vom TutorAgent über das `create_quiz` Tool aufgerufen wird. Er generiert Verständnisfragen (3-8 Fragen) für einen Seitenbereich.

#### State Schema

```python
class QuizGeneratorState(MessagesState):
    page_analyses: List[Dict[str, Any]]  # Required
    topic: str  # Required
    start_page: int  # Required
    end_page: int  # Required
    course_material_id: Optional[str] = None
    user_id: Optional[str] = None
    quiz_data: Optional[QuizData] = None
```

#### Graph-Struktur

```
START → generate (generate_node) → END
```

**Einfacher linearer Graph**: Nur ein Node für Quiz-Generierung.

#### Node: `generate_node`

**Funktionsweise**:

1. **State-Validierung**:
   - Prüft ob `page_analyses`, `topic`, `start_page`, `end_page` vorhanden sind
   - Wirft `QuizStateError` bei fehlenden Feldern

2. **Context-Building**:
   - Baut Kontext aus `page_analyses` auf
   - Format: "Seite X: Zusammenfassung: ... Wichtige Begriffe: ..."

3. **Structured Output**:
   - Nutzt `llm.with_structured_output(QuizData)`
   - Pydantic-Modell `QuizData` für Validierung
   - Garantiert korrektes JSON-Format

4. **Quiz-Validierung**:
   - Prüft Frage-Anzahl (3-8 Fragen)
   - Prüft Schwierigkeitsverteilung:
     - Mindestens 1 leichte Frage
     - Mindestens 1 mittlere Frage
     - Mindestens 1 schwere Frage
   - Prüft jede Frage:
     - Genau 4 Antwortmöglichkeiten (A, B, C, D)
     - `correct_answer` muss in `options` sein
     - Erklärung muss vorhanden sein

5. **Fehlerbehandlung**:
   - `QuizStateError`: Fehlende State-Felder
   - `QuizValidationError`: Validierungsfehler
   - `QuizGenerationError`: Unerwartete Fehler

#### Quiz-Anforderungen

**Schwierigkeitsverteilung**:
- **Leicht** (1-2 Fragen): Grundverständnis, Definitionen
- **Mittel** (1 Frage): Anwendung, Zusammenhänge
- **Schwer** (mindestens 1 Frage): Tiefes Verständnis, Analyse, Synthese

**Fragen-Typen** (bevorzugt):
- Anwendungsfragen: "Wie würde man X in Situation Y anwenden?"
- Verständnisfragen: "Warum funktioniert X auf diese Weise?"
- Analysefragen: "Was wäre das Ergebnis, wenn man X ändert?"
- Synthesefragen: "Wie hängen X und Y zusammen?"

**Vermeidet**:
- Reine Faktenfragen ohne Kontext
- Auswendiglern-Fragen
- Fragen zu nicht behandelten Themen

#### Prompt-Management

- **Langfuse Integration**:
  - Prompt-Name: `quiz-generator/system-prompt-{language}`
  - Label: `production`
  - Type: `chat`
  - Fallback-Prompt wenn Langfuse nicht verfügbar

#### Observability

- **Langfuse Tracing**:
  - Run-Name: `quiz-generator-agent/structured-generation`
  - Span: `quiz-generator-agent/graph-execution`
  - Metadata: `topic`, `start_page`, `end_page`, `page_range`, `course_material_id`

---

### 3. FlashcardGeneratorAgent

#### Zweck und Verantwortlichkeiten

Der **FlashcardGeneratorAgent** generiert Anki-kompatible Flashcards aus Vorlesungsmaterialien. Er ist ein **LangGraph-Agent** mit State-Persistenz und Resumability.

#### State Schema

```python
class FlashcardState(MessagesState):
    course_material_id: str
    user_id: str
    course_id: str
    page_analyses: List[Dict[str, Any]]
    snippets_by_page: Dict[int, Dict[str, Any]]
    current_page_index: int = 0
    processed_page_indices: List[int] = []
    skipped_page_indices: List[int] = []
    all_cards: List[Dict[str, Any]] = []
    current_page_analysis: Optional[Dict[str, Any]] = None
    current_page_messages: List[Dict[str, Any]] = []
    current_snippet_url: Optional[str] = None
    save_to_db: bool = False
    task_id: Optional[str] = None
```

#### Graph-Struktur

```
START
  ↓
initialize_node (load page_analyses, snippets)
  ↓
check_more_pages (conditional)
  ├─→ yes: process_page_node
  │     ↓
  │   skip_decision_node
  │     ↓ (conditional)
  │   ├─→ skip: update_progress_node → check_more_pages (loop)
  │   └─→ generate: get_context_node
  │         ↓
  │       generate_cards_node
  │         ↓
  │       update_progress_node → check_more_pages (loop)
  └─→ no: save_cards_node → END
```

**Nodes**:
1. **`initialize_node`**: Lädt alle Seitenanalysen und Snippets aus der Datenbank
2. **`process_page_node`**: Setzt Kontext für aktuelle Seite
3. **`skip_decision_node`**: LLM entscheidet ob Seite übersprungen werden soll
4. **`get_context_node`**: Ruft Konversationsnachrichten und Snippet-URL ab
5. **`generate_cards_node`**: Generiert Flashcards für aktuelle Seite
6. **`update_progress_node`**: Aktualisiert State und inkrementiert Index
7. **`save_cards_node`**: Speichert Flashcards in Datenbank (wenn `save_to_db=True`)

#### Funktionsweise

**LangGraph-basierter Workflow**:

1. **Initialisierung**: Lädt alle Seitenanalysen und Snippets vorab
2. **Seitenverarbeitung (Loop)**:
   - Für jede Seite:
     - **Skip-Decision**: LLM entscheidet ob Seite übersprungen werden soll
       - Nutzt `llm.with_structured_output(PageSkipDecision)`
       - Prompt aus Langfuse: `flashcard-agent/skip-decision`
     - **Context-Abruf**: Ruft Konversationsnachrichten und Snippet-URL ab
     - **Card-Generation**: Generiert 1-2 Flashcards pro Seite
       - Nutzt `llm.with_structured_output(FlashcardGenerationResult)`
       - Prompt aus Langfuse: `flashcard-agent/card-generation`
       - Input:
         - Seitenanalyse (summary, key_terms, exam_questions, diagram_description)
         - Konversationskontext (letzte 3 Q&A-Paare)
         - Optional: Snippet-Image-URL (für Vision-Input)
3. **Speicherung**: Optional: Speichert Flashcards in Datenbank
4. **Rückgabe**: Liste von Flashcard-Dicts mit `front`, `back`, `tags`, `source_page_analysis_id`

#### Hauptmethode: `generate_flashcards`

**API-Signatur** (rückwärtskompatibel):
```python
def generate_flashcards(
    self,
    course_material_id: str,
    user_id: str,
    course_id: str,
    save_to_db: bool = False,
    task_id: Optional[str] = None,
    thread_id: Optional[str] = None,  # Neu: Für Resumability
) -> List[Dict[str, Any]]
```

**Workflow**:
1. Erstellt initialen State mit Parametern
2. Generiert oder verwendet `thread_id` für Checkpointing
3. Ruft Graph mit `graph.invoke()` auf
4. State wird nach jedem Node automatisch gespeichert (Checkpointer)
5. Rückgabe: `all_cards` aus finalem State

#### Resumability

**Checkpointing**:
- State wird nach jedem Node automatisch gespeichert
- Bei Fehler kann Task mit gleichem `thread_id` fortgesetzt werden
- Verhindert Datenverlust bei langen Tasks (100+ Seiten)

**Beispiel**:
```python
# Erste Ausführung
agent = FlashcardGeneratorAgent(checkpointer=MemorySaver())
cards = agent.generate_flashcards(
    course_material_id="mat-1",
    user_id="user-1",
    course_id="course-1",
    thread_id="task-123"  # Eindeutige Thread-ID
)

# Bei Fehler: Resume mit gleichem thread_id
cards = agent.generate_flashcards(
    course_material_id="mat-1",
    user_id="user-1",
    course_id="course-1",
    thread_id="task-123"  # Gleiche Thread-ID → Resume von Checkpoint
)
```

#### Konversationskontext

**Relevante Messages**:
- User-Fragen (enthält "?" oder "verstehe"/"erkläre")
- Assistant-Antworten nach User-Fragen
- Letzte 3 Q&A-Paare (6 Messages)

**Zweck**: Flashcards berücksichtigen Verständnisschwierigkeiten aus der Konversation.

#### Observability

- **Langfuse Integration**:
  - **Graph-Level**: Span `flashcard-generator-agent/graph-execution`
  - **Node-Level**: Metadata für jeden Node
  - **LLM-Calls**: Operation `skip_decision` oder `card_generation`
  - Metadata: `user_id`, `session_id` (material_id), `material_id`, `course_id`, `page_number`

#### Vorteile der LangGraph-Implementierung

1. **State Persistence**: Automatisches Checkpointing nach jedem Node
2. **Resumability**: Kann von Checkpoint fortgesetzt werden
3. **Bessere Observability**: Node-Level Tracing in Langfuse
4. **Konsistente Architektur**: Gleiches Pattern wie TutorAgent, QuizGeneratorAgent
5. **Graph-Visualisierung**: Kann in LangGraph Studio visualisiert werden
6. **Fehlerbehandlung**: Graceful degradation auf Node-Level
7. **Zukunftserweiterungen**: Einfach Tools, Conditional Logic, Streaming hinzufügen

#### Detaillierte Logik-Analyse

##### Workflow Graph Struktur

Der Agent verwendet einen LangGraph-Workflow mit folgender Struktur:

```
START → initialize → classify → [check_more_pages]
                                    ↓
                              ┌─────┴─────┐
                              │           │
                          continue      done
                              │           │
                              ↓           ↓
                        process_page   save_cards
                              ↓           │
                        skip_decision    │
                              ↓           │
                    ┌─────────┴─────────┐ │
                    │                   │ │
                  skip              generate │
                    │                   │ │
                    ↓                   ↓ │
              update_progress    get_context │
                    │                   │ │
                    │              generate_cards │
                    │                   │ │
                    └──────────┬────────┘ │
                               ↓          │
                        update_progress   │
                               ↓          │
                    [check_more_pages]    │
                               ↓          │
                          ┌────┴────┐     │
                          │         │     │
                      continue    done    │
                          │         │     │
                          └─────────┴─────┘
                               ↓
                              END
```

##### Detaillierte Node-Logik

**1. initialize_node** (Zeilen 185-230)
- **Zweck**: Lädt alle Seitenanalysen und Snippets aus der Datenbank
- **Logik**:
  - Ruft alle Seitenanalysen für das Material ab via `get_all_page_analyses_for_material()`
  - Lädt visuelle Snippets via `get_snippets_for_material()`
  - Organisiert Snippets nach Seitenzahl in `snippets_by_page` Dict
  - Initialisiert Fortschritts-Tracking-Arrays (processed, skipped, all_cards)
  - Setzt `current_page_index` auf 0

**2. classify_node** (Zeilen 232-286)
- **Zweck**: Klassifiziert Materialtyp (language_learning, math, business_administration, general)
- **Logik**:
  - **Cache-Check**: Prüft zuerst Datenbank auf vorhandene Klassifizierung
  - **On-Demand-Generierung**: Falls nicht gecacht, generiert Klassifizierung via LLM
  - **Aggregation**: Sammelt Summaries und Key Terms von allen Seiten
  - **LLM-Call**: Nutzt `MaterialClassification` Structured Output
  - **Speicherung**: Speichert Klassifizierung in Datenbank für zukünftige Nutzung
  - **Fehlerbehandlung**: Bei Fehler weiter ohne Klassifizierung (non-blocking)

**3. process_page_node** (Zeilen 434-461)
- **Zweck**: Setzt Kontext für aktuelle Seite
- **Logik**:
  - Holt Seitenanalyse bei `current_page_index`
  - Extrahiert Seitenzahl
  - Setzt `current_page_analysis` im State
  - Setzt seiten-spezifischen Kontext zurück (messages, snippet_url)

**4. skip_decision_node** (Zeilen 463-531)
- **Zweck**: Entscheidet ob aktuelle Seite übersprungen werden soll (Intro/Titel/TOC-Seiten)
- **Logik**:
  - Extrahiert `summary` und `key_terms` aus Seitenanalyse
  - **Prompt-Laden**: Holt Skip-Decision-Prompt aus Langfuse (mit Fallback)
  - **LLM-Entscheidung**: Nutzt `skip_decision_llm` mit Structured Output (`PageSkipDecision`)
  - **Entscheidung**: Gibt `{skip: bool, reason: str}` zurück
  - **State-Update**: Falls skip=true, fügt aktuellen Index zu `skipped_page_indices` hinzu
  - **Fehlerbehandlung**: Standardmäßig nicht überspringen bei Fehler

**5. should_skip_routing** (Zeilen 533-548)
- **Zweck**: Bedingtes Routing basierend auf Skip-Entscheidung
- **Logik**:
  - Prüft ob `current_page_index` in `skipped_page_indices` ist
  - Gibt `"skip"` zurück → geht zu `update_progress`
  - Gibt `"generate"` zurück → geht zu `get_context`

**6. get_context_node** (Zeilen 550-597)
- **Zweck**: Ruft Konversationsnachrichten und Snippet-URL für aktuelle Seite ab
- **Logik**:
  - **Messages**: Ruft Konversationshistorie für die Seite ab via `get_messages_for_page()`
  - **Snippet-URL**: Prüft `snippets_by_page` für aktuelle Seitenzahl
  - **URL-Generierung**: Falls Snippet existiert, holt öffentliche URL via `get_snippet_public_url()`
  - **State-Update**: Setzt `current_page_messages` und `current_snippet_url`

**7. generate_cards_node** (Zeilen 599-715)
- **Zweck**: Generiert Flashcards für aktuelle Seite via LLM
- **Logik**:
  - Extrahiert Seiteninhalt: summary, key_terms, exam_questions, diagram_description
  - **Konversationskontext**: Filtert Messages für relevante Q&A-Paare (letzte 6 Messages)
  - **Prompt-Laden**: Holt Card-Generation-Prompt aus Langfuse
  - **Vision-Input**: Falls Snippet-URL existiert, inkludiert Bild in Message-Content
  - **LLM-Call**: Nutzt `card_generation_llm` mit Structured Output (`FlashcardGenerationResult`)
  - **Card-Formatierung**: Konvertiert LLM-Output zu Dict-Format mit `source_page_analysis_id`
  - **Akkumulation**: Fügt Cards zu `all_cards` im State hinzu
  - **Fehlerbehandlung**: Bei Fehler weiter mit leeren Cards für diese Seite

**8. update_progress_node** (Zeilen 717-747)
- **Zweck**: Aktualisiert Fortschritts-Tracking und geht zur nächsten Seite
- **Logik**:
  - Fügt aktuellen Index zu `processed_page_indices` hinzu (falls nicht übersprungen)
  - Inkrementiert `current_page_index` um 1
  - Löscht seiten-spezifischen Kontext (analysis, messages, snippet_url)
  - Loggt Fortschritt

**9. save_cards_node** (Zeilen 749-773)
- **Zweck**: Speichert alle akkumulierten Flashcards am ENDE der Generierung
- **Wichtig**: Dieser Node läuft NUR wenn alle Seiten verarbeitet wurden (nicht inkrementell!)
- **Logik**:
  - Prüft `save_to_db` Flag
  - Falls true und Cards existieren:
    1. Dedupliziert gegen bestehende Anki-Cards (wenn aktiviert)
    2. Fügt alle Cards zu Anki hinzu (Batch-Add via AnkiConnect)
    3. Cached Cards in `flashcard_cache` Tabelle
  - Falls Backend während Generierung (0-99%) abstürzt: Cards sind NICHT in Anki!

**10. check_more_pages** (Zeilen 417-432)
- **Zweck**: Bedingtes Routing um zu prüfen ob noch Seiten vorhanden sind
- **Logik**:
  - Vergleicht `current_page_index` mit `len(page_analyses)`
  - Gibt `"continue"` zurück falls mehr Seiten → Loop zurück zu `process_page`
  - Gibt `"done"` zurück falls alle verarbeitet → geht zu `save_cards`

##### Entscheidungspunkte

**Skip-Decision-Logik**:
- **Input**: Seiten-Summary und Key Terms
- **LLM**: Nutzt Structured Output um zu entscheiden ob Seite Intro/Titel/TOC ist
- **Output**: Boolean Skip-Flag mit Begründung
- **Auswirkung**: Übersprungene Seiten generieren keine Cards, werden aber getrackt

**Card-Generation-Logik**:
- **Input-Quellen**:
  1. Seitenanalyse (summary, key_terms, exam_questions, diagram_description)
  2. Konversationshistorie (gefiltert für relevante Q&A)
  3. Visuelle Snippets (falls verfügbar, als Vision-Input gesendet)
  4. Material-Klassifizierung (verfügbar im Prompt-Kontext)
- **LLM**: Nutzt Structured Output um 1-2 Cards pro Seite zu generieren
- **Output**: Liste von Cards mit front, back, tags und source_page_analysis_id

##### State Management

**State Persistence**:
- Nutzt **PostgresSaver** (falls DATABASE_URL konfiguriert) oder **MemorySaver** (Fallback)
- State wird nach jedem Node automatisch gecheckpointed
- Ermöglicht **Resumability**: Fehlgeschlagene Tasks können von letztem Checkpoint mit `thread_id` fortgesetzt werden

**Wichtige Einschränkungen**:
- **Cards werden NICHT inkrementell gespeichert**: Während der Generierung (0-99%) befinden sich Cards nur im LangGraph State, nicht in Anki
- **Task-Status ist flüchtig**: Task-Metadaten (status, progress) werden im Speicher gehalten und gehen bei Backend-Neustart verloren
- **Keine automatische Wiederaufnahme**: Bei Absturz bleiben LangGraph-Checkpoints erhalten, aber die Task-Wiederaufnahme erfordert manuellen Aufruf mit derselben `thread_id`
- **Generierte Cards bei Absturz verloren**: Wenn das Backend bei 80% abstürzt, sind die generierten Cards nicht in Anki gespeichert

**Fortschritts-Tracking**:
- `current_page_index`: Aktuelle Seite die verarbeitet wird
- `processed_page_indices`: Erfolgreich verarbeitete Seiten
- `skipped_page_indices`: Seiten die übersprungen wurden
- `all_cards`: Akkumulierte Flashcards

##### Integration Points

**API Endpoint Flow**:
1. **POST `/api/flashcards/generate`**:
   - Validiert User und Material-Ownership
   - Erstellt Background-Task via `FlashcardTaskService`
   - Gibt task_id sofort zurück (HTTP 202)

2. **Task Execution** (`FlashcardTaskService._run_task`):
   - Initialisiert Agent mit Checkpointer
   - Ruft `generate_flashcards_with_progress()` mit Progress-Callback auf
   - Aktualisiert Task-Fortschritt in Echtzeit
   - Speichert Flashcards in Datenbank nach Generierung
   - Baut .apkg-Datei für Download

3. **Progress Tracking**:
   - Task-Service empfängt Fortschritts-Updates via Callback
   - Aktualisiert Task-Objekt (progress, processed_pages, cards_generated)
   - Frontend pollt `/api/flashcards/status/{task_id}` für Updates

##### Prompt Management

**Langfuse Integration**:
- Prompts werden aus Langfuse mit Label "production" geladen
- Drei Prompts:
  1. `material-classifier/classification`: Für Materialtyp-Klassifizierung
  2. `flashcard-agent/skip-decision`: Für Seiten-Skip-Entscheidungen
  3. `flashcard-agent/card-generation`: Für Flashcard-Generierung
- **Fallback**: Falls Langfuse nicht verfügbar, nutzt hardcodierte Prompts
- **Fehlerbehandlung**: Wirft RuntimeError falls Langfuse erforderlich aber nicht verfügbar

**Prompt-Variablen**:
- **Skip Decision**: `summary`, `key_terms`
- **Card Generation**: `summary`, `key_terms`, `exam_questions`, `diagram_description`, `conversation_context`, `course_id`, `material_id`, `page_number`, `snippet_image_url`
- **Classification**: Aggregierte `page_summaries`, `key_terms`

##### Vision Input Handling

**Snippet Processing**:
- Snippets werden pro Seite in `initialize_node` geladen
- Jede Seite kann mehrere Snippets haben (bis zu `MAX_SNIPPETS_PER_PAGE`)
- Snippet-URLs werden in `get_context_node` abgerufen
- **Vision Input**: Falls Snippet existiert, wird Bild in LLM-Message als `image_url` Content inkludiert
- **HTML Embedding**: Prompt instruiert LLM Bilder in Card-Back mit `<img>` Tags einzubetten

##### Fehlerbehandlungs-Strategie

**Graceful Degradation**:
- **Klassifizierungs-Fehler**: Weiter ohne Klassifizierung (non-blocking)
- **Skip-Decision-Fehler**: Standardmäßig nicht überspringen (verarbeitet Seite)
- **Card-Generation-Fehler**: Weiter mit leeren Cards für diese Seite
- **Snippet-URL-Fehler**: Weiter ohne Bild
- **Datenbank-Save-Fehler**: Loggt Warning aber macht weiter

**State Recovery**:
- Checkpointing ermöglicht manuelle Recovery von Fehlern (nicht automatisch!)
- Kann mit gleichem `thread_id` fortgesetzt werden
- **Wichtig**: Task-Status (pending/running/completed) ist flüchtig und geht bei Restart verloren
- LangGraph-State bleibt in PostgreSQL erhalten, aber generierte Cards sind erst bei 100% in Anki

##### Performance-Überlegungen

**Recursion Limit**:
- Gesetzt auf `10 * page_count` um große PDFs zu handhaben
- Verhindert dass Standard-Limit von 25 große Materialien blockiert

**Async Execution**:
- Task-Service läuft Generierung in Background-Thread (`asyncio.to_thread`)
- API gibt sofort mit task_id zurück
- Fortschritt wird via Callbacks getrackt

**Batch Processing**:
- Verarbeitet Seiten sequenziell (eine nach der anderen)
- Cards werden im State akkumuliert bis zum Abschluss
- **Anki-Speicherung erfolgt NUR am Ende (100%)** - nicht inkrementell während der Generierung
- Datenbank-Save passiert einmal am Ende (falls `save_to_db=True`)

##### Datenfluss-Zusammenfassung

```
Page Analyses (DB) → initialize_node → classify_node
                                              ↓
                                    process_page_node
                                              ↓
                                    skip_decision_node
                                              ↓
                                    [skip?] → get_context_node
                                              ↓
                                    generate_cards_node
                                              ↓
                                    update_progress_node
                                              ↓
                                    [more pages?] → save_cards_node
                                              ↓
                                    all_cards → Database/APKG
```

---

## Projektstruktur und Aufbau

### Verzeichnisstruktur

```
backend/
├── app/
│   ├── agents/              # Agent-Implementierungen
│   │   ├── base.py          # BaseAgent (Abstract Base Class)
│   │   ├── tutor/
│   │   │   └── tutor_agent.py
│   │   ├── quiz/
│   │   │   └── quiz_generator_agent.py
│   │   └── flashcards/
│   │       └── flashcard_agent.py
│   ├── tools/               # LangChain Tools
│   │   ├── page_analysis_tool.py
│   │   ├── course_material_tool.py
│   │   └── quiz_tool.py
│   ├── services/            # Business Logic
│   │   ├── analyzer.py      # LLM-Setup (Gemini, GPT-4o)
│   │   ├── storage.py       # Datenbank-Operationen
│   │   ├── quiz_service.py  # Quiz-Services
│   │   ├── flashcard_service.py
│   │   └── observability.py # Langfuse Integration
│   ├── api/                 # FastAPI Endpoints
│   │   └── endpoints.py     # Chat-Endpoints
│   ├── models/              # Pydantic Schemas
│   │   └── schemas.py
│   └── core/                # Konfiguration
│       └── config.py
```

### Datenbank-Schema (Kern-Tabellen)

**`page_analyses`** (Kern-Tabelle):
- Speichert strukturierte JSON-Analysen von GPT-4o Vision
- Felder: `course_material_id`, `page_number`, `analysis_data` (JSONB)
- `analysis_data` enthält: `summary`, `key_terms`, `exam_questions`, `diagram_description`

**`conversations`**:
- Chat-Sitzungen mit `session_type` (study, planning, general)
- Verknüpft mit `user_id`, `course_id`, `course_material_id`

**`messages`**:
- Einzelne Chat-Nachrichten
- Verknüpft mit `conversation_id`, optional `page_analysis_id`

**`quizzes`**:
- Generierte Quizzes mit `quiz_data` (JSONB)
- Verknüpft mit `course_material_id`, `user_id`, `start_page`, `end_page`

**`flashcards`**:
- Generierte Flashcards
- Verknüpft mit `course_id`, optional `source_page_analysis_id`

### API-Endpoints

**Chat-Endpoints** (`/api/chat/`):

1. **`POST /chat/initiate`**:
   - Startet neue Studiersitzung
   - Parameter: `material_id`, `page_number`, `user_id`
   - Ruft TutorAgent auf
   - Streamt Begrüßung und Erklärung der aktuellen Folie

2. **`POST /chat/message`**:
   - Sendet Nachricht in bestehender Sitzung
   - Parameter: `material_id`, `message`, `user_id`
   - Ruft TutorAgent mit Thread-ID auf
   - Streamt Antwort

**Interner Flow**:
```
Frontend → FastAPI Endpoint → TutorAgent (LangGraph) → Tools → Services → Supabase
```

### State Management

**Checkpointer**:
- `MemorySaver` (In-Memory) für Entwicklung
- Persistiert Konversationshistorie pro Thread-ID
- Thread-ID = `conversation_id` aus Supabase

**Store** (optional):
- Langfristige Erinnerungen (noch nicht implementiert)
- Könnte für User-Präferenzen, Lernmuster genutzt werden

---

## Bezug zu den Aufgabenanforderungen

### Anforderungen aus `assignment_description.md`

#### 1. Projekt-Scope

✅ **Erfüllt**: 
- **Real-world Problem**: Lernunterstützung für Studierende
- **Agentic Characteristics**: Autonomie, Reaktivität, Proaktivität (siehe Abschnitt "Agentic Characteristics")
- **Tools**: 3 Tools (page_analysis, course_material_summary, create_quiz)
- **Memory**: Checkpointer für Konversationshistorie, Store für langfristige Erinnerungen (vorbereitet)

#### 2. Repository Setup

✅ **Erfüllt**:
- Git Repository vorhanden
- Team-Mitglieder arbeiten im selben Repository
- Branches für Features (`feature/louis-branch`)

#### 3. Individual Contributions

⚠️ **Zu prüfen**:
- Git History muss individuelle Commits zeigen
- Jeder Student muss eigene Commits mit korrektem Git-Config haben

#### 4. Final Submission Requirements

**1. Complete Git Repository**:
- ✅ Repository vorhanden
- ⚠️ Git History muss vollständig sein (inkl. `.git` Ordner)

**2. Final Report** (`report.md`):
- ⚠️ Muss noch erstellt/aktualisiert werden
- Muss "Individual Contribution Log" enthalten

**3. Working Code**:
- ✅ Code ist funktional
- ✅ README vorhanden (`PROJECT_PLAN.md`, `AGENT_DEVELOPMENT_RULES.md`)
- ⚠️ Demo/Beispiel-Usage könnte dokumentiert werden

### Evaluation Criteria

#### 1. Technical Implementation

✅ **Qualität und Funktionalität**:
- LangGraph für Agent State Machines
- LangChain für LLM-Integration
- Strukturierte Tools mit Pydantic
- Error Handling mit Custom Exceptions

✅ **Appropriate Use of Tools**:
- 3 Tools für verschiedene Zwecke
- State-Aware Tool Injection
- Tool-Routing durch LLM

✅ **Memory**:
- Checkpointer für Konversationshistorie
- Store für langfristige Erinnerungen (vorbereitet)

✅ **Code Quality**:
- Type Hints überall
- Docstrings für alle Funktionen
- Logging für Debugging
- Strukturierte Fehlerbehandlung

#### 2. Documentation & Report

⚠️ **Zu erledigen**:
- Final Report (`report.md`) muss erstellt werden
- Sollte folgende Abschnitte enthalten:
  - Executive Summary
  - Introduction & Problem Statement
  - System Architecture
  - Implementation Details
  - Evaluation & Challenges
  - Theoretical Foundations (Agentic Characteristics)
  - Ethical Considerations
  - Conclusion & Future Work
  - Individual Contribution Log

#### 3. Collaboration & Individual Contributions

⚠️ **Zu prüfen**:
- Git History muss individuelle Beiträge zeigen
- Jeder Student muss Commits mit eigenem Account haben

#### 4. Final Presentation

- ⚠️ Präsentation muss vorbereitet werden
- Sollte Agent-Funktionalität demonstrieren

---

## Agentic Characteristics Analyse

### 1. Autonomy (Autonomie)

**Definition**: Agent operiert ohne direkte menschliche Intervention und trifft eigene Entscheidungen.

**Implementierung im Projekt**:

✅ **Moderate Autonomie**:

- **Tool-Auswahl**: TutorAgent entscheidet autonom, welche Tools verwendet werden
  - Beispiel: Agent kann `get_page_analysis` aufrufen, wenn User nach Folieninhalt fragt
  - Beispiel: Agent kann `create_quiz` aufrufen, wenn Unterthema abgeschlossen ist

- **Quiz-Erstellung**: TutorAgent entscheidet autonom, wann ein Quiz erstellt wird
  - Keine explizite User-Anfrage nötig
  - Agent erkennt Abschluss eines Unterthemas

- **Kontext-Switching**: Agent passt Erklärungen an aktuellen Kontext an
  - Nutzt `current_page` aus State
  - Lädt relevante Seitenanalyse automatisch

**Einschränkungen**:
- Agent kann keine neuen Aufgaben initiieren (benötigt User-Input)
- Agent kann keine externen Systeme modifizieren (außer Datenbank)
- Agent kann keine Kalender-Events erstellen (noch nicht implementiert)

**Beispiele**:
```python
# Agent entscheidet autonom, Tool zu verwenden
if user_asks_about_page:
    agent.calls_tool("get_page_analysis", page_number=current_page)

# Agent entscheidet autonom, Quiz zu erstellen
if subtopic_completed:
    agent.calls_tool("create_quiz", start_page=5, end_page=10)
```

### 2. Social Ability (Soziale Fähigkeit)

**Definition**: Agent interagiert mit anderen Agenten oder Menschen.

**Implementierung im Projekt**:

✅ **Hohe soziale Fähigkeit**:

- **Human-Computer Interaction**: 
  - TutorAgent kommuniziert direkt mit Studierenden
  - Unterstützt natürliche Sprache (Deutsch, Englisch)
  - Persönlichkeitsanpassung (formality, humor, encouragement)

- **Agent-to-Agent Communication**:
  - TutorAgent ruft QuizGeneratorAgent über `create_quiz` Tool auf
  - TutorAgent nutzt FlashcardGeneratorAgent (indirekt über Services)

- **Proaktive Kommunikation** (geplant):
  - Agent kann proaktive Nachrichten senden
  - "Hey, laut deinem Plan ist heute Statistik dran. Sollen wir starten?"

**Einschränkungen**:
- Keine direkte Agent-to-Agent Kommunikation (nur über Tools/Services)
- Keine Multi-Agent-Koordination (noch nicht implementiert)

**Beispiele**:
```python
# Agent kommuniziert mit User
agent.respond("Diese Folie erklärt das Konzept X. Möchtest du mehr Details?")

# Agent ruft anderen Agent auf
quiz_agent = QuizGeneratorAgent()
quiz_data = quiz_agent.generate_quiz(start_page=5, end_page=10)
```

### 3. Reactiveness (Reaktivität)

**Definition**: Agent nimmt Umwelt wahr und reagiert auf Änderungen.

**Implementierung im Projekt**:

✅ **Sehr hohe Reaktivität**:

- **User-Input**: Agent reagiert sofort auf User-Nachrichten
  - Streaming-Responses für sofortiges Feedback
  - Kontextbewusste Antworten basierend auf aktueller Seite

- **Tool-Ergebnisse**: Agent reagiert auf Tool-Outputs
  - Beispiel: Wenn `get_page_analysis` keine Daten findet, erklärt Agent das
  - Beispiel: Wenn `create_quiz` erfolgreich ist, informiert Agent den User

- **State-Änderungen**: Agent reagiert auf State-Updates
  - `current_page` ändert sich → Agent lädt neue Seitenanalyse
  - `material_id` ändert sich → Agent lädt neue Kursübersicht

- **Fehlerbehandlung**: Agent reagiert auf Fehler
  - Tool-Fehler werden als ToolMessage zurückgegeben
  - Agent erklärt Fehler dem User
  - Graph endet nicht bei Fehlern (graceful degradation)

**Beispiele**:
```python
# Agent reagiert auf Tool-Ergebnis
page_analysis = tool.get_page_analysis(page_number=5)
if page_analysis.get("error"):
    agent.respond("Diese Seite wurde noch nicht analysiert. Möchtest du, dass ich sie analysiere?")
else:
    agent.respond(f"Hier ist die Zusammenfassung: {page_analysis['summary']}")

# Agent reagiert auf State-Änderung
if state["current_page"] != previous_page:
    agent.loads_page_analysis(state["current_page"])
    agent.provides_page_summary()
```

### 4. Proactiveness (Proaktivität)

**Definition**: Agent zeigt zielgerichtetes Verhalten und ergreift Initiative.

**Implementierung im Projekt**:

✅ **Moderate Proaktivität**:

- **Quiz-Erstellung**: Agent erstellt proaktiv Quizzes
  - Erkennt Abschluss eines Unterthemas
  - Erstellt Quiz ohne explizite User-Anfrage
  - Beispiel: "Wir haben das Thema X abgeschlossen. Hier ist dein Quiz!"

- **Seiten-Erklärungen**: Agent erklärt proaktiv neue Folien
  - Bei Seitenwechsel wird automatisch Zusammenfassung gegeben
  - Agent fragt nach Verständnis ("Verstehst du, warum X passiert?")

- **Kontext-Aware Responses**: Agent nutzt Kontext proaktiv
  - Lädt Kursübersicht für bessere Antworten
  - Verweist auf vorherige Themen

**Einschränkungen**:
- Agent kann keine neuen Aufgaben initiieren (benötigt User-Input)
- Keine proaktive Kalender-Planung (noch nicht implementiert)
- Keine proaktiven Benachrichtigungen (noch nicht implementiert)

**Beispiele**:
```python
# Agent erstellt proaktiv Quiz
if topic_completed:
    agent.calls_tool("create_quiz", start_page=5, end_page=10)
    agent.respond("Wir haben das Thema X abgeschlossen. Hier ist dein Quiz!")

# Agent erklärt proaktiv neue Folie
if page_changed:
    agent.loads_page_analysis(new_page)
    agent.respond(f"Auf dieser Folie geht es um {summary}. Lass mich das erklären...")
```

### 5. Continual Learning (Kontinuierliches Lernen)

**Definition**: Agent lernt über Zeit und passt Verhalten basierend auf Erfahrung an.

**Implementierung im Projekt**:

⚠️ **Begrenztes Lernen**:

- **Konversationshistorie**: Agent nutzt Konversationshistorie für Kontext
  - Checkpointer speichert alle Messages
  - Agent kann auf vorherige Fragen/Antworten verweisen
  - Beispiel: "Wie du vorhin gefragt hast, funktioniert X so..."

- **Flashcard-Generierung**: Berücksichtigt Verständnisschwierigkeiten
  - Analysiert Konversationsnachrichten
  - Generiert Flashcards basierend auf User-Fragen

**Einschränkungen**:
- Kein echtes kontinuierliches Lernen (keine Gewichts-Updates)
- Keine Feedback-Loops (User-Feedback wird nicht gespeichert)
- Keine Anpassung der Prompts basierend auf Erfolg/Misserfolg

**Mögliche Erweiterungen**:
- User-Feedback speichern (thumbs up/down)
- Erfolgreiche Tool-Call-Patterns in Knowledge Base speichern
- Prompt-Optimierung basierend auf Erfolgsrate

**Beispiele**:
```python
# Agent nutzt Konversationshistorie
history = agent.get_conversation_history(thread_id)
if "user_asked_about_X" in history:
    agent.respond("Wie du vorhin gefragt hast, funktioniert X so...")

# Flashcard-Generator nutzt Verständnisschwierigkeiten
conversation_context = get_messages_for_page(page_id)
# Generiert Flashcards, die auf User-Fragen eingehen
```

---

## Technische Implementierung

### LangGraph State Machines

**Pattern**: Alle Agenten nutzen LangGraph für State Management

**Vorteile**:
- Klare State-Transitions
- Persistenz durch Checkpointer
- Conditional Routing
- Tool-Integration

**Beispiel (TutorAgent)**:
```python
workflow = StateGraph(state_schema=TutorState)
workflow.add_node("agent", self.call_model)
workflow.add_node("tools", self.tool_node)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    self.should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "agent")  # Loop
```

### Tool-Integration

**Pattern**: State-Aware Tool Injection

**Problem**: LLM könnte falsche IDs halluzinieren

**Lösung**: `StateAwareToolNode` injiziert automatisch State-Werte

```python
class StateAwareToolNode(ToolNode):
    def invoke(self, input: TutorState, config=None) -> TutorState:
        # Injiziert material_id, current_page, user_id aus State
        # Verhindert Halluzinationen
```

### Prompt Engineering

**Pattern**: Langfuse für Prompt-Management

**Vorteile**:
- Zentrale Prompt-Verwaltung
- Versionierung (production, staging)
- A/B Testing möglich
- Observability

**Beispiel**:
```python
langfuse_prompt = langfuse_client.get_prompt(
    "tutor-agent/system-prompt-de",
    label="production",
    type="chat"
)
compiled_prompt = langfuse_prompt.compile(
    formality_text=formality_text,
    humor_text=humor_text,
    encouragement_text=encouragement_text
)
```

### Observability

**Pattern**: Langfuse für Tracing

**Tracking**:
- Token Usage (automatisch via CallbackHandler)
- Model Parameters
- Input/Output Messages
- Latency
- Errors

**Metadata**:
```python
metadata = {
    "langfuse_user_id": user_id,
    "langfuse_session_id": material_id,
    "material_id": material_id,
    "current_page": current_page,
    "agent_name": "TutorAgent"
}
```

### Error Handling

**Pattern**: Custom Exceptions + Graceful Degradation

**Custom Exceptions**:
- `QuizStateError`: Fehlende State-Felder
- `QuizValidationError`: Validierungsfehler
- `QuizGenerationError`: Unerwartete Fehler

**Graceful Degradation**:
- Tools geben Fehler als JSON zurück (nicht als Exception)
- Agent erklärt Fehler dem User
- Graph endet nicht bei Fehlern

---

## Zusammenfassung und Ausblick

### Aktuelle Implementierung

**Stärken**:
- ✅ Klare Agent-Architektur mit BaseAgent Pattern
- ✅ LangGraph für State Management
- ✅ Strukturierte Tools mit Pydantic
- ✅ Persönlichkeitsanpassung
- ✅ Observability mit Langfuse
- ✅ Error Handling

**Schwächen**:
- ⚠️ Begrenztes kontinuierliches Lernen
- ⚠️ Keine proaktive Kalender-Planung (geplant)
- ⚠️ Keine Multi-Agent-Koordination
- ⚠️ Final Report noch nicht erstellt

### Bezug zu Aufgabenanforderungen

**Erfüllt**:
- ✅ Real-world Problem
- ✅ Agentic Characteristics (Autonomie, Reaktivität, Proaktivität, soziale Fähigkeit)
- ✅ Tools und Memory
- ✅ LangGraph für Agent Orchestration
- ✅ Code Quality

**Zu erledigen**:
- ⚠️ Final Report (`report.md`)
- ⚠️ Individual Contribution Log
- ⚠️ Präsentation vorbereiten
- ⚠️ Git History prüfen (individuelle Commits)

### Nächste Schritte

1. **Final Report erstellen**:
   - Alle Abschnitte aus `report.md` Template ausfüllen
   - Individual Contribution Log hinzufügen
   - Evaluation & Challenges dokumentieren

2. **Git History prüfen**:
   - Sicherstellen, dass alle Commits individuell sind
   - Git-Config für jeden Student prüfen

3. **Präsentation vorbereiten**:
   - Demo der Agent-Funktionalität
   - Architektur-Diagramm
   - Code-Beispiele

4. **Erweiterungen** (optional):
   - Proaktive Kalender-Planung
   - Multi-Agent-Koordination
   - Kontinuierliches Lernen mit Feedback-Loops

---

## Anhang

### Agent-Übersichtstabelle

| Agent | Type | Graph | Tools | Memory | Observability |
|-------|------|-------|-------|--------|--------------|
| TutorAgent | LangGraph | ReAct-Loop | 4 | Checkpointer | Langfuse |
| QuizGeneratorAgent | LangGraph | Linear | 0 | Checkpointer | Langfuse |
| FlashcardGeneratorAgent | LangGraph | Loop | 0 | Checkpointer | Langfuse |

### Tool-Übersichtstabelle

| Tool | Agent | Input | Output | Purpose |
|------|-------|-------|--------|---------|
| get_page_analysis | TutorAgent | material_id, page_number, user_id | JSON (summary, key_terms, ...) | Seitenanalyse abrufen |
| get_course_material_summary | TutorAgent | material_id, user_id | JSON (summary) | Kursübersicht abrufen |
| create_quiz | TutorAgent | start_page, end_page, material_id, user_id | JSON (quiz_id, quiz_data) | Quiz erstellen |

### State-Schema-Übersicht

| Agent | State Schema | Erweitert | Zusätzliche Felder |
|-------|--------------|-----------|-------------------|
| TutorAgent | TutorState | MessagesState | current_page, material_id, user_id, course_material_summary |
| QuizGeneratorAgent | QuizGeneratorState | MessagesState | page_analyses, topic, start_page, end_page, quiz_data |
| FlashcardGeneratorAgent | FlashcardState | MessagesState | page_analyses, snippets_by_page, current_page_index, all_cards, processed_page_indices, skipped_page_indices |

---

**Dokument erstellt am**: 2026-01-26  
**Version**: 1.0  
**Autor**: AI Assistant (basierend auf Code-Analyse)
