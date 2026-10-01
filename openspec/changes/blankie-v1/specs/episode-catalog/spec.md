# Spec Delta

## Purpose

Turns the connected feeds and the published series dataset into one catalog where each real episode appears exactly once. Each episode has a stable identity, knows which series it belongs to, and knows the best available audio source.

## ADDED Requirements

### Requirement: Series dataset loading
The app SHALL load the series dataset from its published URL. It SHALL keep the last successfully loaded copy on the device, and SHALL include a copy with the app for use before any download succeeds. If the downloaded dataset has a schema version the app doesn't support, the app SHALL keep using the previous copy.

#### Scenario: First launch offline
- **WHEN** the app is opened for the first time with no network connection
- **THEN** series grouping comes from the copy included with the app

#### Scenario: Unsupported schema version
- **WHEN** the published dataset's schema version is newer than the app supports
- **THEN** the app keeps using its cached copy and shows that an app update is needed for the latest series data

### Requirement: One logical episode per dataset episode
The app SHALL match every feed item to dataset episodes using the shared episode-matching rules, and the app's implementation SHALL pass the shared matching test cases. All feed items that match the same dataset episode SHALL appear as one episode, identified by the dataset's episode ID.

#### Scenario: Public and ad-free copies merge
- **WHEN** both feeds are connected and contain "Taxi Driver with Tracy Letts" and "Taxi Driver with Tracy Letts (Ad-Free)"
- **THEN** the catalog contains a single "Taxi Driver" episode

#### Scenario: Patreon exclusive matched by post ID
- **WHEN** a Patreon feed item's GUID equals a dataset episode's Patreon post ID hint
- **THEN** that item becomes that episode's source, whatever its title

### Requirement: Preferred audio source
When an episode is available from more than one feed, the app SHALL play the Patreon ("Ad-Free") source. If the Patreon source isn't available, it SHALL fall back to the public source. A downloaded copy SHALL be played instead of streaming, whichever feed it was downloaded from.

#### Scenario: Both sources available
- **WHEN** an episode exists in both feeds
- **THEN** playing or downloading it uses the Patreon source

#### Scenario: Downloaded before Patreon was connected
- **WHEN** an episode was downloaded from the public feed and Patreon is connected later
- **THEN** playback uses the downloaded file, and removing the download and downloading again gets the Patreon copy

#### Scenario: Patreon disconnected
- **WHEN** Patreon is disconnected
- **THEN** the same episode plays from the public source and keeps its played state and position

### Requirement: Episodes available only in the dataset are hidden
The app SHALL NOT list a dataset episode that has no source in any connected feed. For example, Patreon exclusives aren't listed when Patreon isn't connected, and neither are wiki-only live events. A series with no available episodes SHALL NOT be listed.

#### Scenario: Public-only listener
- **WHEN** only the public feed is connected
- **THEN** Special Features series such as "RoboCop" are not shown

### Requirement: Feed items not in the dataset
A feed item that doesn't match any dataset episode SHALL still appear in the catalog, with an identity derived from its feed and GUID:
- Items published **after** the dataset's newest episode air date SHALL be placed in a "New, not yet sorted" group.
- Older unmatched items SHALL be placed in an "Other" group.

When a later dataset update matches such an item, the app SHALL move the item's played state and position to the dataset episode.

#### Scenario: New Sunday episode
- **WHEN** a new episode is published and the dataset hasn't been updated yet
- **THEN** it appears in "New, not yet sorted" and can be played

#### Scenario: Dataset catches up
- **WHEN** the listener has half-played an unsorted episode and a dataset update then assigns it to a series
- **THEN** the episode moves to its series, keeping its played state and position
