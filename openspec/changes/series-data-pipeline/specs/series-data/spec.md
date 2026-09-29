# Spec Delta

## Purpose

Provides blankie with an accurate, versioned dataset that says which Blank Check episodes belong to which miniseries and in what order. It's derived from the community fan wiki, because the podcast feeds don't contain this information.

## ADDED Requirements

### Requirement: Dataset contents
The system SHALL publish a single JSON dataset (`series.json`) that conforms to a published JSON Schema and contains:
- a schema version and a generation timestamp
- source attribution
- a list of series
- a collection of episodes

Each series SHALL have:
- a stable ID
- its display title as used by the wiki (e.g. "Podcastfellas")
- its subject (e.g. a director's name or a franchise)
- a category: `star-wars`, `director`, `special-features` or `other`
- a link to its wiki page
- an ordered list of episode IDs

Each episode SHALL have:
- a stable ID
- its wiki title
- its air date
- which feed it originates from: `main` or `special-features`
- its wiki episode number, when the wiki provides one
- the IDs of every series it belongs to, which may be zero or more

#### Scenario: Episode in one series
- **WHEN** the wiki lists "After Hours" (9/27/2026) under the series "Podcastfellas"
- **THEN** the dataset contains an episode for it with air date 2026-09-27, feed `main`, and a series list containing the Podcastfellas series ID, and the Podcastfellas series lists that episode

#### Scenario: Episode in several series
- **WHEN** a Special Features row lists two series for one episode (e.g. a series and "Patreon Standalones")
- **THEN** the episode lists both series IDs, and both series include the episode

#### Scenario: Standalone episode
- **WHEN** a wiki row has no series
- **THEN** the dataset still contains the episode, with an empty series list

### Requirement: Series order follows the wiki, including later releases
A series' episode list SHALL be in air-date order. It SHALL include every episode the wiki assigns to that series, including new releases that aired years after the rest of the run.

#### Scenario: New release joins an old series
- **WHEN** the wiki assigns "Disclosure Day" (2026) to the Spielberg series "Pod Me If You Cast"
- **THEN** "Disclosure Day" appears in that series' episode list after all of its earlier episodes

#### Scenario: Interleaved new release
- **WHEN** "The Odyssey" airs between two episodes of the Andrew Stanton series and the wiki assigns it to the Christopher Nolan series
- **THEN** it appears in the Nolan series and not in the Stanton series

### Requirement: Stable episode IDs
Each episode ID SHALL be derived when the episode is first published, from its air date and normalized wiki title (for example `2026-09-27:after-hours`). Once published, it SHALL NOT change in later regenerations, even if the wiki later corrects that episode's title or date. Episode IDs SHALL be unique within the dataset.

#### Scenario: Wiki corrects a title
- **WHEN** a published episode's wiki title is later corrected (e.g. "The Podtastic Two" → "The Podcastic Two")
- **THEN** the regenerated dataset keeps the original episode ID and updates the episode's title field

#### Scenario: Duplicate ID
- **WHEN** two different wiki rows would produce the same episode ID
- **THEN** generation fails with an error naming both rows

### Requirement: Feed match hints
For each episode matched to an item in the public feed, the dataset SHALL include that item's GUID and title as hints. For each Special Features episode whose wiki row links to a Patreon post, the dataset SHALL include the Patreon post ID as a hint. The dataset SHALL NOT contain any audio or enclosure URLs, or any Patreon feed URL.

#### Scenario: Public match hint
- **WHEN** the wiki row "After Hours" (9/27/2026) matches the public feed item "After Hours with Alison Sivitz"
- **THEN** the episode's hints include that item's GUID and title

#### Scenario: Patreon post hint
- **WHEN** a Special Features wiki row links to `https://www.patreon.com/posts/mortal-kombat-ii-158692113`
- **THEN** the episode's hints include Patreon post ID `158692113`

### Requirement: Overrides
The system SHALL apply a hand-edited overrides file after parsing the wiki and before validation. Overrides SHALL support:
- correcting an episode's title or air date
- pinning an episode to a specific public feed GUID
- adding or removing an episode's membership in a series
- excluding a wiki row entirely
- acknowledging a known unmatched wiki row or feed item

An override that refers to an episode or feed item that doesn't exist SHALL be reported as an error.

#### Scenario: Correct a wiki typo
- **WHEN** the wiki dates "Space Jam" as 9/30/3018 and an override corrects it to 2018-09-30
- **THEN** the dataset uses 2018-09-30 and the episode matches its public feed item

#### Scenario: Stale override
- **WHEN** an override refers to an episode ID that isn't in the dataset
- **THEN** generation fails and names the stale override

### Requirement: Attribution
The dataset SHALL identify its source as the Blank Check fan wiki. It SHALL include the wiki's license (CC BY-SA) and a license URL, and link each series to its wiki page.

#### Scenario: Attribution present
- **WHEN** any consumer reads `series.json`
- **THEN** it can find the source name, license, license URL, and a wiki link for every series

### Requirement: Publication and update cadence
The dataset SHALL be published from the repository's `main` branch at a stable URL that can be fetched without authentication. It SHALL be regenerated automatically once a week and on demand. Each regeneration that changes the dataset SHALL be proposed as a pull request, not committed directly to `main`. A regeneration that changes nothing SHALL NOT open a pull request.

#### Scenario: Weekly update with changes
- **WHEN** the weekly run finds that the wiki added a new episode
- **THEN** a pull request is opened, or the existing update PR is refreshed, containing the updated `series.json`

#### Scenario: Weekly update without changes
- **WHEN** the weekly run produces a dataset identical to the one on `main`, apart from the generation timestamp
- **THEN** no pull request is opened or updated

#### Scenario: App fetch
- **WHEN** a client requests the published URL without credentials
- **THEN** it receives the current `series.json` from `main`
