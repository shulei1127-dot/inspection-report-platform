## Goal

Design and initialize the minimal standalone `log-analyzer-service` project skeleton so the next implementation phase can start from a stable directory structure and module boundary.

## Scope

- define the recommended standalone service directory structure
- document layer responsibilities
- define initial configuration recommendations
- define parser migration strategy from the current platform parser
- initialize a minimal subdirectory skeleton without implementing the full analyzer business logic
- update project status to reflect the new scaffold

## Out Of Scope

- full analyzer implementation
- archive upload support
- shared contracts package
- parser feature expansion
- platform-side workflow changes

## Key Decisions

- create a top-level `log-analyzer-service/` subdirectory in the current repository as a scaffold
- keep the scaffold runnable at the health-check level only
- keep `POST /analyze` as a placeholder endpoint with an explicit not-implemented response
- include analyzer-local schema files so the future standalone service can evolve without importing platform internals
- keep v1 source mode limited to `directory`

## Verification Plan

- run `python3 -m compileall log-analyzer-service/app`
- review the scaffold structure against `docs/log_analyzer_api_v1.md`
- confirm placeholder files and configuration names are consistent with the documented API boundary
