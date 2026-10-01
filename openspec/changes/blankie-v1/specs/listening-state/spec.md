# Spec Delta

## Purpose

Tracks what the listener has heard and where they are, per logical episode. It provides quick bulk actions for setting up history on a new device, and re-listens that don't erase play history.

## ADDED Requirements

### Requirement: Played state and resume position per episode
The app SHALL keep a played flag and a resume position for every episode, keyed by the episode's stable ID. An episode SHALL become played automatically when playback reaches its end or passes the last 30 seconds. The listener SHALL be able to mark any episode played or unplayed by hand. Marking an episode unplayed SHALL keep its resume position.

#### Scenario: Finishing an episode
- **WHEN** playback passes the final 30 seconds of an episode
- **THEN** the episode is marked played

#### Scenario: State follows the episode, not the feed
- **WHEN** an episode was played from the public source and Patreon is connected later
- **THEN** the merged episode is still played

### Requirement: Mark series as played
Each series SHALL offer "Mark series as played", which marks every available episode in the series played in one action, and "Mark series as unplayed", which reverses it.

#### Scenario: Day-one setup
- **WHEN** the listener taps "Mark series as played" on "They Podcast"
- **THEN** every available episode in it is played, and the series shows no unplayed episodes

### Requirement: Mark everything before an episode as played
Each episode SHALL offer "Mark everything before this as played". After asking for confirmation, it SHALL mark as played every available episode in the catalog, in any series or group, whose air date is earlier than this episode's. The chosen episode itself SHALL NOT be changed.

#### Scenario: Caught up to a point
- **WHEN** the listener chooses "Mark everything before this as played" on "Mean Streets" (2026-08-16) and confirms
- **THEN** every available episode that aired before 2026-08-16 is played, and "Mean Streets" and later episodes are unchanged

#### Scenario: Cancelled
- **WHEN** the listener cancels the confirmation
- **THEN** nothing changes

### Requirement: Re-listen runs
Each series SHALL offer "Start re-listen". It starts a run through the series' available episodes in series order, starting from the first. The run SHALL track its own progress, meaning the count of run episodes finished during the run, and SHALL NOT change played flags when it starts.

Finishing the run's next episode SHALL count toward the run's progress and make the following run episode next. Finishing any other episode SHALL NOT change the run. The listener SHALL be able to end the run at any time. The run SHALL end automatically after its last episode. Only one run per series SHALL exist at a time.

#### Scenario: Start a re-listen of a finished series
- **WHEN** every episode of "They Podcast" is played and the listener starts a re-listen
- **THEN** the series shows re-listen progress "0/23" with the first episode as next, and every episode is still marked played

#### Scenario: Progress through the run
- **WHEN** the listener finishes the next episode in the run
- **THEN** progress becomes "1/23" and the following episode becomes next

#### Scenario: Episode outside the run order
- **WHEN** a run's next episode is episode 6 and the listener plays and finishes episode 12 of the same series
- **THEN** the run's progress and next episode are unchanged

#### Scenario: Run completes
- **WHEN** the listener finishes the last episode of the run
- **THEN** the run ends, and the series shows its normal unplayed count again

#### Scenario: Ending early
- **WHEN** the listener ends a run partway through
- **THEN** the run is discarded, and played flags and positions are unchanged
