# NLP-First Campus Companion

**Project overview for team discussion**  
**Working academic title:** An NLP-Based Campus Information Assistant Using Intent Classification, Entity Extraction, and Semantic Query Construction

## The idea

Build a single campus application where students can ask questions in natural language and receive answers from structured campus information. Admins maintain that information through a separate workspace in the same application.

The project is intended for an NLP course. Its core contribution is a language-understanding pipeline that identifies what a student wants, extracts relevant details, resolves their meaning, and constructs a controlled database query. It will not rely on a generative LLM to interpret questions or fetch answers.

## The problem

Campus information is scattered across WhatsApp groups, college websites, club pages, timetables, and notices. Students need to know where to look, search multiple sources, and decide whether the information is current and applicable to them.

The proposed application brings selected information into one place and lets students ask for it in their own words.

Example questions include:

- “Which classroom has no scheduled booking right now?”
- “I am in second-year AIML. What relevant events can I attend this week?”
- “When are Professor Rao’s office hours tomorrow?”
- “Are there any free AI workshops on Friday?”
- “Which companies currently have applications open for students in my year?”

These questions require more than matching keywords: they involve dates, eligibility, campus-specific names, context, and ambiguous words such as “free.”

## Proposed first version

The broader vision is an all-in-one campus companion. The first version will focus on three information domains so the team can build and evaluate the NLP components properly.

| Domain | Supported information | Example |
| --- | --- | --- |
| Events | Topics, dates, eligibility, venues, costs, and registration deadlines | “Any AI workshops for second years this week?” |
| Rooms | Rooms with no scheduled booking during a requested interval, including capacity and location filters | “Find a classroom in B block from 2 to 3 PM.” |
| Faculty office hours | Published meeting hours and recorded exceptions | “When can I meet Professor Rao tomorrow?” |

Placement opportunities are a possible extension after the core system works.

## Student experience

Students sign in and provide basic academic context, such as department, year, and section. Optional interests can help rank relevant events. Students should be able to see and change the context used in an answer.

The student workspace includes:

- **Assistant and home:** Ask questions, view structured answer cards, and see relevant upcoming events.
- **Query history:** Reopen, continue, and delete previous conversations. Old answers retain their timestamps; current availability requires a fresh query.
- **Saved items:** Save events and useful records. Saved events reflect changes to their underlying details.
- **Profile:** Manage academic context and optional interests.

Answers should include useful details, their information source, and when the underlying record was last updated. An event answer could show its title, venue, eligibility, registration deadline, and a save action.

Basic conversational follow-ups are part of the proposed experience:

> Student: “What workshops are happening this week?”  
> Assistant: Shows matching workshops.  
> Student: “Only ones on Friday.”  
> Assistant: Retains the workshop filter and updates the date constraint.

Student analytics are secondary. Useful additions could include upcoming saved events and approaching registration deadlines; a large analytics dashboard is not required for the first version.

## Admin experience

Students and admins can use one login entry point, with access determined by their assigned role. Admin privileges must be controlled by the application.

Admins maintain:

- **Events:** Description, topic, eligibility, venue, timing, cost, registration deadline, and cancellation status.
- **Rooms:** Location, capacity, facilities, opening hours, and closures.
- **Timetables and bookings:** Recurring classes, one-off reservations, and cancellations.
- **Faculty office hours:** Published hours and temporary exceptions.

Admins enter bookings and closures; the system calculates room availability. Manually marking rooms “free” would become outdated quickly.

The first version can use a single admin role. Club coordinators managing their own events and faculty managing their own office hours are possible later additions.

## NLP approach

The proposed pipeline is:

```text
Student question + relevant conversation/profile context
                         |
                         v
              Text cleanup and normalization
                         |
                         v
          Intent classification and entity extraction
                         |
                         v
        Entity resolution and temporal interpretation
                         |
                         v
             Structured meaning representation
                         |
                         v
       Validate constraints / clarify missing information
                         |
                         v
            Parameterized database query builder
                         |
                         v
          Database results -> template-based answer
```

### Main components

1. **Text normalization:** Handle spelling variations, informal wording, abbreviations, and inconsistent campus names while preserving useful information such as room codes and times.
2. **Intent classification:** Identify operations such as finding events, finding available rooms, and finding faculty office hours.
3. **Entity extraction:** Identify dates, time intervals, departments, years, faculty names, locations, and event topics.
4. **Entity resolution:** Map expressions such as “AIML” and “AI & ML” to the same department record, and resolve faculty or building aliases.
5. **Temporal interpretation:** Convert expressions such as “tomorrow” and “this week” into concrete intervals using campus local time.
6. **Semantic interpretation:** Convert the extracted information into explicit filters and constraints, including eligibility and overlapping bookings.
7. **Dialogue handling:** Retain relevant filters during supported follow-ups and ask for clarification when the interpretation is ambiguous.

For example, “Any ML workshops for second years this week?” could produce the following intermediate representation:

```json
{
  "intent": "find_events",
  "filters": {
    "event_type": "workshop",
    "topic": "machine_learning",
    "student_year": 2,
    "date_range": "current_week"
  }
}
```

Here, `current_week` is illustrative shorthand; it must be resolved to actual date boundaries before executing the query. The application maps validated fields to predefined query-building logic rather than generating unrestricted SQL.

## What makes this a core NLP project?

The academic work will center on an annotated campus-query corpus, language-understanding models, semantic interpretation, and experimental evaluation.

| Syllabus topic | Planned contribution |
| --- | --- |
| Data acquisition and annotated corpora | Collect and label student questions |
| Normalization, tokenization, and regular expressions | Process informal queries, room codes, and time expressions |
| Information extraction and NER | Extract campus entities and query constraints |
| Term weighting and text classification | Build a TF–IDF-based intent-classification baseline |
| Semantics and ambiguity | Represent query meaning and distinguish meanings such as cost versus availability |
| Conversational agents | Support clarification and constrained follow-up questions |
| Transfer learning and transformers | Optionally compare a pretrained encoder classifier against the traditional baseline |

A pretrained encoder used for classification or entity extraction is compatible with the NLP-first approach. It is an optional experiment, not a dependency on a generative LLM service. A limited grammar-based parser could also be explored if it adds value; the system does not need to parse unrestricted English.

## Data and evaluation

The project needs two distinct datasets:

- **Campus records:** Structured events, room bookings, and faculty office hours used to answer questions.
- **Annotated questions:** Natural-language examples labeled with intents, entity spans, normalized values, and expected structured interpretations.

Start with curated campus records entered through admin forms or imported from controlled files. If real records are unavailable, clearly labeled demonstration data can support development. Automatic ingestion from WhatsApp and arbitrary websites is outside the initial scope.

Question data should include paraphrases, abbreviations, typos, multiple constraints, ambiguous questions, unsupported requests, and short follow-up conversations. Keep near-duplicate paraphrases together when splitting training and test data.

Evaluate:

- **Intent classification:** Macro F1.
- **Entity extraction:** Entity-level precision, recall, and F1.
- **Normalization:** Accuracy of resolved names, dates, and times.
- **Semantic interpretation:** Match against expected structured queries.
- **End-to-end behavior:** Correct result sets and appropriate clarification or unsupported-query responses.

Compare a simple rule-based or keyword baseline with the proposed hybrid pipeline. Analyze failures by component so the results explain where the system succeeds and where it needs improvement.

## Important behavior and boundaries

- A room with no scheduled booking is not guaranteed to be physically empty. Answers must state the scheduling-based meaning of availability.
- A faculty member having no class does not imply meeting availability. Use published office hours and recorded exceptions.
- Event relevance and eligibility are separate: an interesting event may still be restricted to another year or department.
- Distinguish “no matching results,” “information unavailable,” “ambiguous question,” and “unsupported request.”
- Keep query histories private to the student and provide deletion controls. Academic evaluation should use anonymized question data.

## Suggested delivery sequence

1. Define supported intents, entity types, database records, and annotation guidelines.
2. Populate demonstration campus records and collect an initial labeled question dataset.
3. Build and evaluate the baseline NLP pipeline independently of the interface.
4. Connect validated structured interpretations to database queries.
5. Build the student assistant and admin management screens.
6. Add clarification and follow-up support, run comparative experiments, and document errors and limitations.

The frontend, backend, database, and model libraries remain open for team discussion. Technology choices should support the NLP experiments and a manageable working demonstration.

## Questions for team review

- Are the three proposed domains manageable within our deadline?
- Which real campus records can we obtain and keep current?
- Can we collect enough varied student questions for a meaningful evaluation?
- Should the model comparison include a pretrained encoder, or focus on traditional and rule-based methods?
- How should we divide ownership of the dataset, NLP pipeline, backend, interface, and evaluation?

The intended outcome is a working application where admins publish dependable campus information and students retrieve it in their own words, supported by a measurable NLP pipeline.
