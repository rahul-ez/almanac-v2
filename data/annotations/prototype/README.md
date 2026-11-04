# Synthetic intent prototype — engineering smoke data only

The 60 original frontend pilot drafts are preserved verbatim in frontend-pilot.original.jsonl from main commit bf479b913cf0a9fce5dad9f8cefdc8d7f7de87db. Their original annotation notes are preserved beside them. The canonical intent-only file uses those intent labels and adds 18 explicitly synthetic unsupported questions in three new families (transport, fees, hostel).

This is not collected student data, independent annotation, an academic final test set or proof of model generalization. Existing semantic annotations refer to frontend demo IDs and are NOT silently treated as backend gold labels. Only intent labels are used for prototype training/evaluation. The original unsupported group stays intact; its questions are not split apart to make metrics look better.

The splitter keeps connected paraphrase/conversation groups together, checks exact text duplicates and class coverage, records checksums and chooses a reproducible smoke split. With only three groups per supported class, approximately 70/15/15 is not achievable while covering every class in every partition; actual proportions must be reported. Training fits text preprocessing on train only, selects hyperparameters/rejection threshold on validation only, and reports the fixed smoke holdout once. Do not use these results as final academic numbers.

For the real study: obtain consent, anonymize student questions, validate labels/spans/normalized values and source records, independently double-label/adjudicate, expand families/dialogues, freeze a genuine final test split before tuning, and report actual errors/limitations. No human collection or review is claimed here.
