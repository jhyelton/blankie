# Spec Delta

## Purpose

Lets the owner install blankie on their own iPhone and keep it working without a paid Apple Developer Program membership. The process, including the recurring re-install after free signing expires, is written down so it can be repeated without guesswork.

## ADDED Requirements

### Requirement: Documented first-time install
The project SHALL include a runbook that takes a developer from a Mac with Xcode installed to blankie running on their iPhone using a free Apple ID. The runbook SHALL cover toolchain setup, Xcode signing with a personal team, enabling Developer Mode on the iPhone, trusting the developer certificate on the device, and building and installing a build that can be launched from the home screen.

#### Scenario: Following the runbook from scratch
- **WHEN** the owner follows the first-time install section step by step on their Mac and iPhone
- **THEN** blankie is installed on the iPhone and launches from its home-screen icon without the Mac attached

### Requirement: Installed build launches without a debugger
The build installed by the runbook SHALL launch and run normally from the iPhone home screen without being attached to a debugger or connected to the Mac.

#### Scenario: Launch while away from the Mac
- **WHEN** the iPhone is disconnected from the Mac and the owner taps the blankie icon
- **THEN** the app launches and plays audio normally

### Requirement: Documented 7-day re-install
The runbook SHALL describe how to recognize that the free-signing signature has expired and the exact steps to re-install. It SHALL state whether playback positions and downloaded episodes are kept across a re-install.

#### Scenario: Signature expired
- **WHEN** the app stops launching because its 7-day signature has expired and the owner follows the re-install section
- **THEN** blankie launches again, and the result matches what the runbook says about keeping playback positions and downloads

### Requirement: Documented limitations of free signing
The runbook SHALL list the known limitations of free Apple signing that affect daily use, including the 7-day expiry and any limits on the number of apps installed this way.

#### Scenario: Owner checks limitations
- **WHEN** the owner reads the limitations section
- **THEN** it lists the expiry period and the app-count limit for free provisioning
