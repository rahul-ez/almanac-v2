# Annotation workstream

`pilot.synthetic.jsonl` contains 60 agent-authored **synthetic drafts**, not collected student questions. `dialogues.synthetic.json` adds six dialogue drafts. No independent annotation, adjudication, train/test assignment, or model evaluation has been claimed. Regenerate with `npx tsx scripts/create-pilot.ts` from `frontend/`.

Before using these for training, Person B and Person A should review the meaning representation and extend the language variety. The current paraphrases are deliberately grouped and too repetitive to establish generalization. Do not report their scores as independent student-query evaluation.

Collection protocol:

1. Explain the academic purpose, obtain consent, and ask students for varied questions across the three supported domains. Collect unsupported questions, typos, abbreviations, and short follow-ups too.
2. Remove names and identifying information about the person asking. Public faculty names are canonical campus entities; student identity is not an annotation feature.
3. Record provenance, language, original text, intent, exact character spans, normalized values, explicit filters, expected ambiguity/clarification, fixed clock and timezone, and seed version.
4. Label only words present in the original question as spans. Profile and conversation values belong in context with provenance. Use inclusive start and exclusive end offsets. Preserve original text after annotation.
5. Treat event cost, student eligibility, topical relevance, scheduled availability, and physical vacancy as distinct concepts. Unknown eligibility or coverage cannot imply a positive answer.
6. Annotate multi-turn sequences together. Keep all turns and near-duplicate paraphrases in the same group for splitting.
7. Have two people independently label at least 15–20% of the pilot. Record both versions and adjudication reasons before expanding collection. Synthetic drafts do not count as a second annotation.
8. Person B freezes group-based split manifests, approximately 70/15/15 after checking class coverage. Keep final test data out of iterative debugging and threshold/rule tuning.

Normalization examples: `this week` is Monday 00:00 through the next Monday 00:00 in campus time; at the fixture clock that is `[2026-11-02T00:00+05:30, 2026-11-09T00:00+05:30)`. `Professor Rao` has two candidates. A room interval of 14:00–15:00 does not overlap a booking ending at 14:00. Priya Nair's 5 November replacement is 15:00–16:00.

Target after pilot review: 400–600 questions, roughly 100 or more per supported domain, unsupported/ambiguous examples, and 30–50 short dialogues. Real collection and independent review require the team; the frontend implementation does not supply consent or measured NLP accuracy.
