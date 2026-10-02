# Spec Delta

## MODIFIED Requirements

### Requirement: Shared matching test cases are the source of truth
The repository SHALL contain a language-neutral JSON file of matching test cases. It SHALL have normalization cases (input title → expected normalized form) and match cases (a wiki episode plus candidate feed items → the expected matched item, or no match). Normalization and matching SHALL be implemented once, in a single shared implementation. Every consumer, including the series-data tool and the app, SHALL use that implementation and SHALL NOT keep its own copy of these rules. The shared implementation SHALL pass every case in the test case file. Every new mismatch discovered in real data and fixed in code SHALL be added to the file as a case.

#### Scenario: Implementation conformance
- **WHEN** the shared implementation's test suite runs
- **THEN** it loads the shared test case file and fails if any case produces a different result

#### Scenario: One implementation for every consumer
- **WHEN** the series-data tool and the app each match a wiki episode against the same feed items
- **THEN** both get their result from the same shared implementation, so the results are identical

## ADDED Requirements

### Requirement: Feed publication dates
A feed item's publication date SHALL be the calendar date of its `pubDate` in the time zone offset that the `pubDate` states. It SHALL NOT be converted to UTC or to the device's time zone first. Every consumer SHALL use this same rule when it compares a feed item with an episode's air date.

#### Scenario: Late-evening release in a negative offset
- **WHEN** a feed item's `pubDate` is `Sun, 27 Sep 2026 23:30:00 -0700`
- **THEN** its publication date is 2026-09-27, not 2026-09-28

#### Scenario: Named zone
- **WHEN** a feed item's `pubDate` is `Mon, 28 Sep 2026 04:00:00 GMT`
- **THEN** its publication date is 2026-09-28
