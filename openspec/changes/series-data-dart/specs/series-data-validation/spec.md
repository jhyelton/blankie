# Spec Delta

## MODIFIED Requirements

### Requirement: Human-edited changes are validated
Any pull request that changes the overrides file, the shared matching test cases, the schema, the tool itself, or the shared matching implementation SHALL run the tests of the tool and of the shared implementation, plus the schema validation. It SHALL report the result as a status check.

#### Scenario: Bad override in a PR
- **WHEN** a pull request adds an override referring to an episode ID that doesn't exist
- **THEN** the status check fails and names the override

#### Scenario: Matching change breaks a shared case
- **WHEN** a pull request changes the shared matching implementation so that one of the shared test cases gives a different result
- **THEN** the status check fails and names the case
