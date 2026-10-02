# Spec Delta

## Purpose

Keeps incorrect, broken, or vandalized series data from reaching `main` and the app. It also makes the small number of expected mismatches visible for human review, and lets the owner check Patreon matching without exposing their private feed.

## ADDED Requirements

### Requirement: Schema validation
Every generated dataset SHALL be validated against the published JSON Schema before it is proposed. A dataset that fails validation SHALL NOT be proposed.

#### Scenario: Invalid dataset
- **WHEN** generation produces an episode without an air date
- **THEN** the run fails, reports the schema error, and opens or updates no pull request

### Requirement: Breakage and vandalism guardrails
Before proposing a dataset, the system SHALL compare it with the dataset currently on `main`. The run SHALL fail, without proposing anything, if any of these is true:
- the number of parsed wiki episode rows fell by more than 1% or by more than 5 rows
- any previously published episode ID disappeared
- any series lost episodes
- more than 5% of previously published episodes changed their series membership
- any previously published episode's public GUID or Patreon post ID hint changed to a different value

The owner SHALL be able to deliberately accept such changes by triggering the run manually with an explicit acceptance option. The pull request SHALL then list every guardrail that was overridden.

#### Scenario: Wiki table broken
- **WHEN** a wiki edit breaks the Episodes table and the parser finds 300 rows where there were 600
- **THEN** the run fails, reports the drop, and no pull request is opened

#### Scenario: Series loses episodes
- **WHEN** a wiki edit removes three episodes from "Podcastfellas"
- **THEN** the run fails and names the series and the missing episodes

#### Scenario: Wiki renumbers episodes
- **WHEN** a wiki edit swaps the numbers of two published episodes
- **THEN** each episode keeps its own ID, anchored by its public GUID, and no hint changes

#### Scenario: Deliberate acceptance
- **WHEN** the owner manually triggers the run with the acceptance option after confirming that a large wiki reorganization is correct
- **THEN** the pull request is opened, and its description lists each guardrail that was exceeded

### Requirement: Unmatched items reported for review
Each proposed update SHALL list, in its pull request description:
- every wiki episode from the main feed that has no public feed match
- every public feed item that no wiki episode matched

Items acknowledged in the overrides file SHALL be left out of these lists. Unmatched items SHALL NOT, on their own, fail the run.

#### Scenario: New unmatched item
- **WHEN** a new wiki row can't be matched to the public feed
- **THEN** the pull request lists it under unmatched wiki episodes, and the run succeeds

#### Scenario: Acknowledged item
- **WHEN** the feed item "Blank Check with Griffin & David Trailer" is acknowledged in overrides
- **THEN** it doesn't appear in the unmatched list

### Requirement: Human-edited changes are validated
Any pull request that changes the overrides file, the shared matching test cases, the schema, or the tool itself SHALL run the tool's tests and the schema validation, and SHALL report the result as a status check.

#### Scenario: Bad override in a PR
- **WHEN** a pull request adds an override referring to an episode ID that doesn't exist
- **THEN** the status check fails and names the override

### Requirement: No Patreon credentials in automation
Automated runs SHALL NOT use, require, or have access to any Patreon feed URL or Patreon credential.

#### Scenario: CI configuration
- **WHEN** the repository's automated workflows are inspected
- **THEN** none of them reference a Patreon feed URL or a secret holding one

### Requirement: Local Patreon matching check
The system SHALL provide a command, run only on the owner's machine, that:
- reads the Patreon feed URL from the operating system's secure credential store
- fetches the feed
- applies the same matching rules as everything else
- prints a report of Special Features episodes that matched, didn't match, and were ambiguous

The report and any error messages SHALL contain only episode titles, dates and dataset IDs. They SHALL NOT include any URL, feed content other than titles and dates, or credential. The command SHALL NOT write the feed to disk.

#### Scenario: Report contents
- **WHEN** the owner runs the local check with the feed URL stored in the credential store
- **THEN** the printed report lists matched, unmatched and ambiguous Special Features episodes by title, date and ID, and contains no occurrence of `http`

#### Scenario: Credential missing
- **WHEN** no feed URL is stored in the credential store
- **THEN** the command exits with an error explaining how to store it, and makes no network requests

#### Scenario: Fetch failure does not leak the URL
- **WHEN** fetching the feed fails (e.g. with an HTTP 403)
- **THEN** the error message gives the status but not the URL
