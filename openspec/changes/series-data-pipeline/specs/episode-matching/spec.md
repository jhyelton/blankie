# Spec Delta

## Purpose

Defines a single set of rules for recognizing that a wiki episode and a podcast feed item are the same episode. The rules are expressed as shared test cases, so every implementation (the series-data tool and the app) behaves identically.

## ADDED Requirements

### Requirement: Shared matching test cases are the source of truth
The repository SHALL contain a language-neutral JSON file of matching test cases. It SHALL have normalization cases (input title → expected normalized form) and match cases (a wiki episode plus candidate feed items → the expected matched item, or no match). Every implementation of episode matching SHALL pass every case in that file. Every new mismatch discovered in real data and fixed in code SHALL be added to the file as a case.

#### Scenario: Implementation conformance
- **WHEN** any implementation's test suite runs
- **THEN** it loads the shared test case file and fails if any case produces a different result

### Requirement: Title normalization
Normalization SHALL:
- remove HTML markup
- fold accented characters to their unaccented form
- lowercase
- remove apostrophes and quotation marks
- remove the exact suffix "(Ad-Free)"
- collapse every run of other non-alphanumeric characters to a single separator
- trim leading and trailing separators

Normalization SHALL NOT remove other parenthetical suffixes, because they distinguish separate episodes (e.g. "(Bite-Free Version)", "(Sunglasses Edition)").

#### Scenario: Ad-free copy
- **WHEN** normalizing "After Hours with Alison Sivitz (Ad-Free)"
- **THEN** the result equals the normalization of "After Hours with Alison Sivitz"

#### Scenario: Punctuation and tab variants
- **WHEN** normalizing "Alice Doesnt Live Here Anymore" and "Alice Doesn't Live Here Anymore"
- **THEN** both produce the same result
- **AND WHEN** normalizing "You Were Never Really Here\twith Sean Clements" (containing a tab)
- **THEN** the result is the same as with a single space

#### Scenario: Markup removed
- **WHEN** normalizing `<span class="avatar">Avatarland</span>/The Second Blank Check Mailbag`
- **THEN** the result contains no markup, and "avatarland" and "the second blank check mailbag" are separated by a single separator

#### Scenario: Distinct editions preserved
- **WHEN** normalizing "Spreadmaster's Delight 3: Decade-of-Dreams Warriors (Bite-Free Version)" and the same title without the suffix
- **THEN** the two results differ

### Requirement: Matching a wiki episode to a feed item
A feed item SHALL be a candidate for a wiki episode when both of these hold:
- its publication date is within 3 days of the episode's air date
- its normalized title equals the episode's normalized title, or starts with it followed by a separator (so guest suffixes like "with Tracy Letts" are allowed), or matches after removing a leading "the"

If there's exactly one candidate, that's the match. If there are several, the closest date wins, then a candidate whose normalized title equals the episode's (directly or after removing a leading "the") wins over one that only starts with it, then the longest title overlap. If a tie remains, or there are no candidates, the result SHALL be "no match". The matcher SHALL NOT guess.

An exact GUID or Patreon post ID hint SHALL take precedence over title and date matching, including another episode's title match to the same feed item.

#### Scenario: Guest suffix
- **WHEN** matching the wiki episode "Taxi Driver" (8/30/2026) against feed item "Taxi Driver with Tracy Letts" published 2026-08-30
- **THEN** it matches

#### Scenario: Leading article difference
- **WHEN** matching the wiki episode "The Silence of the Lambs" (1/12/2020) against feed item "Silence of the Lambs with Emily St. James" published 2020-01-12
- **THEN** it matches

#### Scenario: Date outside window
- **WHEN** a feed item has the same normalized title but was published 10 days away from the wiki air date
- **THEN** it is not a candidate

#### Scenario: Ambiguous
- **WHEN** two feed items within the date window match equally well
- **THEN** the result is "no match"

#### Scenario: Exact title beats an edition
- **WHEN** matching the wiki episode "Spreadmaster's Delight 3: Decade-of-Dreams Warriors" against that exact title and "Spreadmaster's Delight 3: Decade-of-Dreams Warriors (Bite-Free Version)", both published the same day
- **THEN** it matches the exact title

#### Scenario: Hint wins
- **WHEN** an episode has a Patreon post ID hint and a feed item's GUID equals that post ID
- **THEN** that item is the match, regardless of title differences
