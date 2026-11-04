# Frontend design direction

Reading this as a student campus workspace: clear, welcoming, and practical, with an indigo identity and a question-first home. The frontend-design skill guides the interface; a marketing landing page is not the product's primary job.

Tokens: white canvas `#ffffff`, ink `#353348`, secondary copy `#70677c`, dividers `#eceaf2`, indigo action `#5850bd`, and pale lavender `#f0edfa`. Warm sand and muted green identify room/faculty suggestions and event artwork; they do not compete with the primary action.

Manrope is hosted from the installed font package. One family handles navigation, questions, record details, and forms. Headings use a tighter scale; sources and limitations remain secondary but readable.

The desktop layout is a quiet sidebar, a compact top bar, and a constrained content column. The question composer is the first useful action. Three suggestion rows represent the three supported domains. Upcoming event artwork uses typography and simple geometry associated with AI, design, and programming. It is decorative and hidden from assistive technology.

```text
Sidebar | Identity / data mode
        | Greeting and question composer
        | Events / rooms / office-hour suggestions
        | Upcoming records with bookmark controls
```

Conversation answers become structured records with source/update metadata. Context chips explain the provenance of applied filters. Admin screens use searchable lists and dedicated forms; recurrence, coverage, and exceptions remain explicit fields rather than being hidden in a calendar.

The initial plan was reviewed for generic decoration. A stats dashboard, AI gradient orb, unrelated photography, and a decorative analytics panel would distract from the campus task, so the memorable visual element is the event artwork. Cards group actual records, not arbitrary paragraphs. Motion is limited to loading feedback and user-triggered interactions, with reduced-motion support.

The mobile layout changes to a modal navigation drawer, vertically arranged suggestions, and compact horizontal home-event cards. Native dialogs provide focus containment, Escape dismissal, and focus restoration. The interface also includes a skip link, semantic forms/tables, inline validation, status/error announcements, safe source protocols, and keyboard-visible focus styles. Screenshots are produced by the browser suite for design review.
