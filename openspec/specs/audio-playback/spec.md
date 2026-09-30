# audio-playback Specification

## Purpose

Lets the listener play long podcast episodes reliably on their phone. That means playback continues when the app is backgrounded or the screen is locked, is controllable from system surfaces and headphones, and always resumes where the listener left off.

## Requirements

### Requirement: Play an episode from a stream or a local file
The system SHALL play an episode's audio from its remote URL (streaming) or from a previously downloaded local file. Remote URLs that redirect SHALL be followed.

#### Scenario: Stream a remote episode
- **WHEN** the listener starts playback of an episode that has not been downloaded and the device is online
- **THEN** audio begins playing from the episode's remote URL

#### Scenario: Play a downloaded episode
- **WHEN** the listener starts playback of an episode that has been downloaded
- **THEN** audio plays from the local file, not the remote URL

### Requirement: Continue playback in the background
The system SHALL keep playing audio while the app is in the background or the device screen is locked, for the full length of an episode of at least 3 hours.

#### Scenario: Screen locked during playback
- **WHEN** audio is playing and the listener locks the device
- **THEN** audio continues playing without interruption

#### Scenario: Switching to another app
- **WHEN** audio is playing and the listener switches to another app that does not play audio
- **THEN** audio continues playing

#### Scenario: Long session while locked
- **WHEN** the listener starts an episode and leaves the device locked for 60 minutes
- **THEN** audio is still playing at approximately the 60-minute mark

### Requirement: System media controls
While an episode is loaded, the system SHALL publish it to the OS media controls (lock screen and Control Center) with the episode title, show name, artwork, duration, and current position. The system SHALL respond to play, pause, skip forward 30 seconds, skip back 15 seconds, and scrubbing from those controls.

#### Scenario: Lock screen shows the episode
- **WHEN** an episode is playing and the device is locked
- **THEN** the lock screen shows the episode title, show name, artwork, and a progress bar that advances

#### Scenario: Pause and resume from the lock screen
- **WHEN** the listener taps pause and then play on the lock screen
- **THEN** audio pauses and then resumes from the same position

#### Scenario: Skip from the lock screen
- **WHEN** the listener taps skip forward on the lock screen
- **THEN** playback position advances by 30 seconds
- **AND WHEN** the listener taps skip back
- **THEN** playback position moves back by 15 seconds

#### Scenario: Scrub from the lock screen
- **WHEN** the listener drags the lock-screen progress bar to a new position
- **THEN** playback continues from that position

### Requirement: Headphone and remote controls
The system SHALL respond to play/pause commands from wired and Bluetooth headphones and other remote-control sources such as a car stereo.

#### Scenario: Bluetooth headphone play/pause
- **WHEN** the listener uses the play/pause gesture on connected Bluetooth headphones
- **THEN** playback toggles between playing and paused

### Requirement: Handle audio interruptions and route changes
The system SHALL pause playback when another audio source interrupts it, such as a phone call or Siri. It SHALL resume automatically after the interruption ends if the OS indicates playback should resume. It SHALL pause, and not resume automatically, when the active output route is removed, such as when headphones are disconnected.

#### Scenario: Phone call interruption
- **WHEN** an episode is playing and a phone call arrives and then ends
- **THEN** playback pauses during the call and resumes afterward from where it paused

#### Scenario: Headphones disconnected
- **WHEN** an episode is playing through headphones and the headphones are disconnected
- **THEN** playback pauses and does not continue through the phone speaker

### Requirement: Persist and restore playback position
The system SHALL persist the current playback position of the loaded episode at least every 10 seconds while playing, and immediately on pause, seek, or the app moving to the background. When the episode is loaded again, including after the app was terminated, playback SHALL start from the last persisted position.

#### Scenario: Resume after pausing
- **WHEN** the listener pauses an episode at 1:12:30 and later presses play
- **THEN** playback resumes at 1:12:30

#### Scenario: Resume after the app is terminated
- **WHEN** the listener is playing an episode, the app is terminated (by the user or the OS), and the listener relaunches the app and presses play
- **THEN** playback resumes within 10 seconds of where it was when the app was terminated
