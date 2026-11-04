# Frontend demo walkthrough

Run `npm ci` and `npm run dev` in `frontend/`. Open `http://127.0.0.1:5173`. The banner labels fictional demo records and the fixed clock: 4 November 2026, 10:00 AM Asia/Kolkata.

1. Choose **Use student demo**, then **Sign in**. The home shows upcoming events and the three supported question domains. Open an event title for full details and source/update information.
2. Ask **Any workshops this week?**, then **Only Friday**. The second answer retains the workshop filter, changes the date, and explains context origins.
3. Bookmark **Build something with AI**. Open **Saved items**, reload, and verify the record remains saved. Reopen the conversation and check the bookmark reflects its current saved state.
4. Start a new conversation and ask **Professor Rao office hours tomorrow**. Choose **Dr. Anil Rao**. The answer is a published concrete interval, not inferred from a teaching timetable.
5. Ask **Find a room in B Block**, then **Today from 2 to 3 PM**. B-204 is available according to bookings; the preceding booking ends at 14:00. B-102 is excluded by its maintenance closure. The answer does not guarantee physical vacancy.
6. Ask **A room in A Block today from 2 to 3 PM**. Coverage is missing, so the answer says information is unavailable. Ask **What is the weather?** for an unsupported response. Ask **Any quantum events this week?** for a zero-match demo case.
7. Edit **My profile** and save. Reload to confirm persistence. Edit again and navigate away to demonstrate the unsaved-change dialog. A question override changes that request rather than the permanent profile.
8. In **Conversations**, delete a conversation and confirm it disappears. A second student (`ananya@campus.demo`, same demo password) has a separate history and saved list.
9. Sign out. Choose **Use admin demo**, then **Sign in**. Create a published event with a title, description, type, venue, valid dates after the fixed clock, eligibility, cost, and source. Return to the student account and find it through an event question.
10. Save that event, then edit its status as admin to cancelled. Student saved items show cancellation; the old conversation retains its timestamped original answer. Refreshing the query uses current records.
11. Explore rooms, bookings, closures, faculty, office hours, exceptions, and aliases. Try a reversed interval or a conflicting booking; errors are shown beside fields. Archive a record with confirmation.

The automated suite also exercises API outages, response validation, safe retries across reloads, session expiry/draft preservation, all assistant fixtures, all admin forms, keyboard focus, and narrow screens. Live-mode tests intercept the API; they do not establish real backend readiness.
