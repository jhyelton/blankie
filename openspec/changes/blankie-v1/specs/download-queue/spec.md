# Spec Delta

## Purpose

Lets the listener keep chosen episodes, or a whole series, on the device for offline listening. The listener decides what gets downloaded, and a simple queue keeps downloads from overwhelming the network or storage.

## ADDED Requirements

### Requirement: Download a single episode
Every available episode SHALL offer "Download". A downloaded episode SHALL be playable offline. Every downloaded episode SHALL offer "Remove download".

#### Scenario: Download one episode
- **WHEN** the listener taps "Download" on an episode
- **THEN** the episode enters the download queue, and when it completes it is marked as downloaded

### Requirement: Download a series
Each series SHALL offer "Download series":
- If a re-listen run is active, it queues the remaining episodes of the run, in run order.
- Otherwise it queues every unplayed available episode of the series, in series order.

Episodes that are already downloaded or already queued SHALL be skipped.

#### Scenario: Queue unplayed episodes
- **WHEN** the listener taps "Download series" on a series with 6 unplayed episodes, 1 of them already downloaded
- **THEN** 5 episodes are added to the queue in series order

#### Scenario: Queue a re-listen
- **WHEN** a re-listen run is at episode 5 of 23 and the listener taps "Download series"
- **THEN** episodes 5 through 23 of the run are queued, apart from any already downloaded

### Requirement: Limited-concurrency queue
Queued downloads SHALL be processed first-in, first-out, with at most 2 downloads active at a time. The queue SHALL survive app restarts. The listener SHALL be able to view the queue, cancel a queued or active download, and cancel all downloads. A failed download SHALL be retried automatically up to 3 times. After that it SHALL be shown as failed with a retry action. Downloads SHALL continue while the app is in the background, as proven by `episode-download`.

#### Scenario: Large series queued
- **WHEN** 19 episodes are queued
- **THEN** only 2 download at a time, and the rest wait in order

#### Scenario: App restarted mid-queue
- **WHEN** the app is terminated while downloads are queued and then relaunched
- **THEN** the queue resumes with the remaining episodes

#### Scenario: Cancel
- **WHEN** the listener cancels an active download
- **THEN** it stops, any partial file is removed, and the next queued episode starts

### Requirement: Network policy
By default, downloads SHALL run only on Wi-Fi. When the device isn't on Wi-Fi, queued downloads SHALL wait. A setting SHALL allow downloads over cellular.

#### Scenario: Leaving Wi-Fi
- **WHEN** downloads are active and the device switches from Wi-Fi to cellular with the cellular setting off
- **THEN** downloads pause and resume automatically when Wi-Fi returns

### Requirement: Removing played downloads
By default, the app SHALL delete an episode's downloaded file when the episode becomes played. A setting SHALL turn this off. An episode that's part of an active re-listen run SHALL NOT be deleted until the run has passed it.

#### Scenario: Auto-remove after playing
- **WHEN** a downloaded episode finishes and is marked played, with the setting on
- **THEN** its file is deleted, and the episode can be streamed or downloaded again

#### Scenario: Setting off
- **WHEN** the setting is off and a downloaded episode is marked played
- **THEN** the file is kept
