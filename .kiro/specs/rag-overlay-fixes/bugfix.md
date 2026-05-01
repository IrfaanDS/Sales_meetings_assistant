# Bugfix Requirements Document

## Introduction

Four related bugs degrade the quality and correctness of the AI sales meeting assistant overlay. They span RAG retrieval logic, LLM prompt behaviour, response length calibration, and the visual rendering of the AI script panel. Together they cause the assistant to hallucinate product content when no docs are selected, narrate the host in third person, produce over-long responses to greetings, and display a hard-to-read wall of text in the overlay. All four must be fixed without breaking existing session behaviour, stealth mode, or streaming latency.

---

## Bug Analysis

### Bug 1 — RAG Document Leakage

#### Current Behavior (Defect)

1.1 WHEN a session is started with no product docs selected (`selected_docs = []`) THEN the system still runs the host profile search unconditionally, and any indexed content lacking a `source_type` field bleeds through into the product context block, causing the LLM to reference indexed material as if product docs were present.

1.2 WHEN `selected_docs` is an empty list and the LLM receives a non-empty `[CONTEXT]` block populated from unguarded or mis-tagged chunks THEN the system generates a product-referencing script despite the user having selected no product documents.

#### Expected Behavior (Correct)

2.1 WHEN `selected_docs` is an empty list THEN the system SHALL return an empty product context block (no product chunks injected into `[CONTEXT]`), while still allowing the host profile search to run normally.

2.2 WHEN `selected_docs` is an empty list and `[CONTEXT]` is therefore empty THEN the system SHALL instruct the LLM (via the prompt) that no product context is available, so it falls back to the Knowledge Gap Protocol rather than hallucinating from profile content.

#### Unchanged Behavior (Regression Prevention)

3.1 WHEN `selected_docs` contains one or more filenames THEN the system SHALL CONTINUE TO retrieve product chunks filtered to those filenames and inject them into `[CONTEXT]` as before.

3.2 WHEN a host profile document has been indexed THEN the system SHALL CONTINUE TO retrieve and inject host profile content into `[HOST PROFILE]` regardless of which product docs are selected.

3.3 WHEN `filter_docs` is a non-empty list passed to `store.search()` THEN the system SHALL CONTINUE TO filter results to only those filenames.

---

### Bug 2 — Persona/Profile Prompt Confusion

#### Current Behavior (Defect)

1.3 WHEN the LLM receives raw CV/resume text in `[HOST PROFILE]` under the current system prompt THEN the system produces responses that describe the host in third person (e.g. "John has 10 years of experience…") instead of speaking as the host.

1.4 WHEN the system prompt instructs the LLM to "embody the host" without explicit first-person constraints THEN the system conflates profile narration with product narration, reciting CV bullet points as if they were sales talking points.

#### Expected Behavior (Correct)

2.3 WHEN the LLM receives `[HOST PROFILE]` content THEN the system SHALL treat that content as voice and style calibration only — the LLM SHALL speak in first person ("I", "we") and SHALL NOT describe the host in third person or recite their background as biographical facts.

2.4 WHEN the host profile is used to ground credibility THEN the system SHALL express that credibility through first-person framing (e.g. "In my experience delivering X…") rather than third-person attribution.

#### Unchanged Behavior (Regression Prevention)

3.4 WHEN no host profile has been indexed THEN the system SHALL CONTINUE TO fall back to "No host profile provided." and generate a script without profile grounding.

3.5 WHEN the LLM uses `[HOST PROFILE]` for stylistic grounding THEN the system SHALL CONTINUE TO prioritise `[CONTEXT]` as the primary source for all technical claims.

---

### Bug 3 — Word Count Rigidity / Intent-Response Mismatch

#### Current Behavior (Defect)

1.5 WHEN the client utterance is a greeting or social exchange (e.g. "Hi, nice to meet you") THEN the system generates a 90–120 word scripted response, producing an unnaturally long reply for a simple social moment.

1.6 WHEN the client utterance is a short acknowledgment (e.g. "Got it", "Makes sense") THEN the system generates a full-length script regardless of the low-information content of the input.

#### Expected Behavior (Correct)

2.5 WHEN the classified intent is GREETING THEN the system SHALL generate a response of 1–2 sentences only (approximately 10–20 words).

2.6 WHEN the classified intent is a simple acknowledgment or social exchange THEN the system SHALL generate a short, natural response proportional to the input rather than a full 90–120 word script.

2.7 WHEN the classified intent is TECHNICAL, PRICING/BUDGET, TIMELINE/DELIVERY, OBJECTION/CONCERN, COMPETITION, or NEXT STEPS/CLOSE THEN the system SHALL generate a full 90–120 word narration-ready script as currently specified.

#### Unchanged Behavior (Regression Prevention)

3.6 WHEN the intent gatekeeper classifies a statement as high-intent (TRUE) THEN the system SHALL CONTINUE TO trigger a RAG query and generate a response.

3.7 WHEN the intent gatekeeper classifies a statement as low-intent (FALSE) THEN the system SHALL CONTINUE TO suppress the RAG query entirely.

3.8 WHEN the intent is RELATIONSHIP/TRUST THEN the system SHALL CONTINUE TO produce a human, empathetic response — the length calibration for this intent SHALL be shorter than a full technical script (approximately 2–4 sentences).

---

### Bug 4 — Overlay Script Readability

#### Current Behavior (Defect)

1.7 WHEN `append_script_chunk` is called during streaming THEN the system concatenates raw HTML into a single unstyled paragraph, producing a wall of text with no visual separation between the trigger query and the AI response.

1.8 WHEN a new RAG response arrives THEN the system appends it after the previous response in the same label, stacking all prior responses rather than replacing them.

1.9 WHEN the right pane renders the AI response THEN the system uses the same small, low-contrast `TranscriptionLabel` style as the transcript pane, making the script hard to read at a glance.

#### Expected Behavior (Correct)

2.8 WHEN a new RAG query begins THEN the system SHALL clear the previous response and display only the current trigger query and its AI response — prior responses SHALL NOT stack.

2.9 WHEN the trigger query is displayed THEN the system SHALL render it with clear visual separation from the AI response body (distinct colour, label, or divider).

2.10 WHEN the AI response streams in THEN the system SHALL render it with larger font size, adequate line-height, and high-contrast text colour suitable for quick reading during a live meeting.

2.11 WHEN the right pane layout is updated THEN the system SHALL use a clean, single-column, minimal design consistent with professional copilot tools.

#### Unchanged Behavior (Regression Prevention)

3.9 WHEN the overlay is active THEN the system SHALL CONTINUE TO maintain transparent window background, WDA_EXCLUDEFROMCAPTURE stealth affinity, WindowTransparentForInput, and low-latency streaming of tokens to the UI.

3.10 WHEN `finalize_script_chunk` is called THEN the system SHALL CONTINUE TO trigger the opacity fade-in animation to signal response completion.

3.11 WHEN the user resizes the overlay via the resize handle THEN the system SHALL CONTINUE TO resize both panes correctly.

---

## Bug Condition Summary

### Bug 1 — RAG Document Leakage

```pascal
FUNCTION isBugCondition_1(X)
  INPUT: X of type SessionConfig
  OUTPUT: boolean
  RETURN X.selected_docs = []
END FUNCTION

// Fix Checking
FOR ALL X WHERE isBugCondition_1(X) DO
  result ← stream_ask'(X)
  ASSERT result.ctx_block = "" AND result.profile_block IS ALLOWED
END FOR

// Preservation Checking
FOR ALL X WHERE NOT isBugCondition_1(X) DO
  ASSERT stream_ask(X).ctx_block = stream_ask'(X).ctx_block
END FOR
```

### Bug 2 — Persona/Profile Prompt Confusion

```pascal
FUNCTION isBugCondition_2(X)
  INPUT: X of type LLMResponse
  OUTPUT: boolean
  RETURN X contains third-person host references (e.g. "[HostName] has...")
END FUNCTION

// Fix Checking
FOR ALL X WHERE isBugCondition_2(X) DO
  result ← generate_script'(X)
  ASSERT result uses first-person only AND does NOT describe host in third person
END FOR
```

### Bug 3 — Word Count Rigidity

```pascal
FUNCTION isBugCondition_3(X)
  INPUT: X of type ClientUtterance
  OUTPUT: boolean
  RETURN X.intent IN ["GREETING", "ACKNOWLEDGMENT", "RELATIONSHIP/TRUST"]
END FUNCTION

// Fix Checking
FOR ALL X WHERE isBugCondition_3(X) DO
  result ← generate_script'(X)
  IF X.intent = "GREETING" THEN ASSERT word_count(result) <= 20
  IF X.intent = "ACKNOWLEDGMENT" THEN ASSERT word_count(result) <= 40
END FOR

// Preservation Checking
FOR ALL X WHERE NOT isBugCondition_3(X) DO
  ASSERT 90 <= word_count(generate_script'(X)) <= 120
END FOR
```

### Bug 4 — Overlay Script Readability

```pascal
FUNCTION isBugCondition_4(X)
  INPUT: X of type ScriptRenderEvent
  OUTPUT: boolean
  RETURN X is a new RAG response arriving after a prior response exists
END FUNCTION

// Fix Checking
FOR ALL X WHERE isBugCondition_4(X) DO
  result ← render_script'(X)
  ASSERT result shows only current query+response AND prior responses are cleared
END FOR

// Preservation Checking
FOR ALL X WHERE NOT isBugCondition_4(X) DO
  ASSERT stealth_affinity(result) = TRUE
  ASSERT window_transparent_for_input(result) = TRUE
  ASSERT streaming_latency(result) IS unchanged
END FOR
```
