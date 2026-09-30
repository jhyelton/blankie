# Spec Delta

## Purpose

Lets the listener keep full-length episodes on the device so they can listen without a network connection. Downloads carry on even when the app is backgrounded.

## ADDED Requirements

### Requirement: Download an episode in the background
The system SHALL download an episode's audio file to local device storage. The download SHALL continue while the app is in the background or the device is locked, and SHALL follow HTTP redirects from the episode's URL.

#### Scenario: Download completes while backgrounded
- **WHEN** the listener starts downloading an episode of at least 150 MB and then locks the device
- **THEN** the download completes without the app being brought to the foreground, and the file is available the next time the app is opened

### Requirement: Report download progress
The system SHALL show download progress while an episode downloads. Progress SHALL use the size reported by the HTTP response, because feed enclosure sizes may be missing or zero. If no size is known, the system SHALL show indeterminate progress.

#### Scenario: Feed reports zero length
- **WHEN** an episode whose feed enclosure length is `0` is downloading and the server reports a content length
- **THEN** the displayed progress advances from 0% to 100% based on the server-reported size

### Requirement: Play downloaded episodes offline
The system SHALL play a fully downloaded episode with no network connection, including background playback and system media controls.

#### Scenario: Offline playback
- **WHEN** an episode has been downloaded and the device is in airplane mode
- **THEN** the listener can start, pause, seek, and resume the episode, and it continues playing with the screen locked

### Requirement: Recover from interrupted downloads
If a download fails or is interrupted, the system SHALL NOT treat a partially downloaded file as playable. The listener SHALL be able to retry the download.

#### Scenario: Network lost mid-download
- **WHEN** connectivity is lost partway through a download
- **THEN** the episode is not marked as downloaded, and the listener can retry the download once connectivity returns
