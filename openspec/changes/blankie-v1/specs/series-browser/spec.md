# Spec Delta

## Purpose

Makes the miniseries the main way to browse. At a glance, the listener can see which series have episodes they haven't heard, which series they're re-listening to, and what's new.

## ADDED Requirements

### Requirement: Home series list
The home screen SHALL list every series that has at least one available episode, plus a "Standalones" group for available episodes that belong to no series. Items SHALL be ordered by the air date of their newest available episode, newest first. When "New, not yet sorted" contains episodes, it SHALL appear above all series. The "Other" group SHALL appear last.

Each series SHALL show:
- its title and subject (e.g. "Podcastfellas: Martin Scorsese")
- its number of available episodes
- the air date of its newest episode
- either its unplayed count or, if a re-listen is in progress, its re-listen progress

#### Scenario: Airing series on top
- **WHEN** the newest available episode belongs to "Podcastfellas"
- **THEN** "Podcastfellas" is the first series on the home screen, below "New, not yet sorted" if that group has episodes

#### Scenario: Unplayed badge
- **WHEN** a series has 8 available episodes and 6 are played
- **THEN** the series shows "2 unplayed"

#### Scenario: Re-listen shown instead of unplayed
- **WHEN** the listener is 5 episodes into a re-listen of a 23-episode series
- **THEN** the series shows re-listen progress "5/23" instead of an unplayed count

### Requirement: Filter to series with unplayed episodes
The home screen SHALL offer a filter that shows only series and groups with unplayed episodes or a re-listen in progress.

#### Scenario: Filter on
- **WHEN** the listener turns on the filter
- **THEN** fully played series without a re-listen in progress are hidden

### Requirement: Series detail
Opening a series SHALL show its available episodes in series order, as given by the dataset. For each episode it SHALL show the title, air date, duration, played state, resume progress, download state, and whether it's the next episode in a re-listen. The series actions SHALL be available here (see `listening-state` and `download-queue`).

#### Scenario: Later release in order
- **WHEN** the listener opens the Spielberg series and the dataset orders "Disclosure Day" last
- **THEN** "Disclosure Day" appears last

#### Scenario: Episode in several series
- **WHEN** an episode belongs to two series
- **THEN** it appears in both series' detail lists with the same played state
