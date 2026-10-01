# Spec Delta

## Purpose

Connects blankie to Blank Check's public feed and, optionally, the listener's private Patreon feed. The private feed URL is treated as a credential throughout.

## ADDED Requirements

### Requirement: Public feed is available by default
The app SHALL subscribe to the public Blank Check feed without any setup, so a new install shows the public catalog after its first refresh.

#### Scenario: First launch
- **WHEN** the app is opened for the first time with a network connection
- **THEN** it fetches the public feed and shows its episodes, with no setup step

### Requirement: Adding the Patreon feed
The app SHALL let the listener paste a Patreon feed URL in settings. Before saving it, the app SHALL check that the URL uses HTTPS and returns a valid podcast RSS feed. If the check fails, the app SHALL show an error that doesn't include the URL and SHALL NOT save it.

#### Scenario: Valid Patreon URL
- **WHEN** the listener pastes a working Patreon feed URL and saves it
- **THEN** the app confirms it's connected and the next catalog includes Patreon episodes

#### Scenario: Invalid URL
- **WHEN** the listener pastes a URL that returns an error or isn't RSS
- **THEN** the app shows an error such as "Couldn't read that feed (HTTP 403)" without showing the URL, and nothing is saved

### Requirement: Patreon URL is stored and handled as a secret
The app SHALL store the Patreon feed URL only in the platform's secure credential storage. It SHALL NOT write the URL, or any enclosure URL from the Patreon feed, to logs, crash reports, analytics, exported files, or on-screen error messages. After saving, the app SHALL show the URL only in a masked form.

#### Scenario: Viewing settings
- **WHEN** the listener opens settings after connecting Patreon
- **THEN** the feed is shown as connected with a masked identifier, and the full URL is not displayed

#### Scenario: Fetch error
- **WHEN** refreshing the Patreon feed fails
- **THEN** the error shown or logged contains the status or reason but not the URL

### Requirement: Removing the Patreon feed
The app SHALL let the listener disconnect the Patreon feed. Disconnecting SHALL delete the stored URL. Episodes available only from Patreon SHALL disappear from the catalog, and their downloaded files and queued downloads SHALL be deleted. Listening state for all episodes SHALL be kept.

#### Scenario: Disconnect
- **WHEN** the listener disconnects Patreon
- **THEN** the URL is removed from secure storage, Patreon-only episodes and series disappear, their downloads are deleted, and played state for main-feed episodes is unchanged

#### Scenario: Reconnect keeps history
- **WHEN** the listener later reconnects the same Patreon feed
- **THEN** Patreon-only episodes reappear with their earlier played state and positions

### Requirement: Refreshing
The app SHALL refresh all connected feeds, and the series dataset, when it's opened or brought to the foreground, and when the listener pulls to refresh. It SHALL show the time of the last successful refresh. If a refresh fails, the app SHALL keep showing the last successfully loaded data.

#### Scenario: Offline launch
- **WHEN** the app is opened with no network connection
- **THEN** it shows the catalog from the last successful refresh and indicates that it's offline

#### Scenario: New episode appears
- **WHEN** a new episode has been published and the listener pulls to refresh
- **THEN** the new episode appears in the catalog
