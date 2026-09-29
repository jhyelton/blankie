# Spec Delta

## Purpose

Keeps listening flowing through a series without having to go back to the app between episodes, and lets the listener set a comfortable playback speed.

## ADDED Requirements

### Requirement: Auto-advance within the series
When an episode finishes, the app SHALL start the next episode in the series the listener started playback from:
- If a re-listen run is active in that series, the next episode is the run's next episode.
- Otherwise it's the next unplayed available episode after the finished one, in series order.

If there is no next episode, or playback was started from "New, not yet sorted", "Standalones" or "Other", playback SHALL stop. Auto-advance SHALL work while the device is locked, and the lock screen SHALL show the new episode.

#### Scenario: Next unplayed in series
- **WHEN** the listener finishes "Mean Streets" in "Podcastfellas", and "Alice Doesn't Live Here Anymore" is the next unplayed episode in that series
- **THEN** "Alice Doesn't Live Here Anymore" starts playing, including while the device is locked

#### Scenario: Played episodes skipped
- **WHEN** the episode after the finished one is already played and no re-listen is active
- **THEN** that episode is skipped, and the next unplayed episode plays

#### Scenario: Re-listen order
- **WHEN** a re-listen run is active and the listener finishes the run's current episode
- **THEN** the run's next episode plays, even though it's already marked played

#### Scenario: Started from a group
- **WHEN** the listener finishes an episode started from "New, not yet sorted"
- **THEN** playback stops

#### Scenario: Multi-series episode
- **WHEN** an episode belongs to two series and was started from series A
- **THEN** the next episode is chosen from series A

### Requirement: Next episode can be played offline
When the next episode has been downloaded, auto-advance SHALL play it from the device. When it hasn't been downloaded and the device is offline, playback SHALL stop and show that the next episode needs a connection.

#### Scenario: Offline, next not downloaded
- **WHEN** the device is offline and the next episode isn't downloaded
- **THEN** playback stops after the current episode and indicates why

### Requirement: Playback speed
The app SHALL offer a playback speed from 0.8× to 2.0× in 0.1 steps. The setting SHALL apply to all episodes, persist across launches, and take effect immediately during playback.

#### Scenario: Speed persists
- **WHEN** the listener sets the speed to 1.3× and relaunches the app
- **THEN** playback runs at 1.3×

#### Scenario: Change during playback
- **WHEN** the listener changes the speed while an episode is playing
- **THEN** the new speed applies immediately without restarting the episode
