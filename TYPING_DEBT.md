# Typing debt: unresolved import allowlist

This file tracks temporary entries in `[tool.ty.analysis].allowed-unresolved-imports`.

| Module pattern | Why it is currently allowed | Import locations (examples) | Planned fix |
| --- | --- | --- | --- |
| `enve.**` | Optional runtime dependency tied to Ansys installation layout | `src/ansys/dynamicreporting/core/common_utils.py`, `src/ansys/dynamicreporting/core/utils/report_utils.py`, `src/ansys/dynamicreporting/core/serverless/adr.py` | Replace dynamic import paths with a stable import adapter and package-level typing stubs. |
| `enve_common.**` | Optional newer packaging variant for the same runtime module family | `src/ansys/dynamicreporting/core/serverless/adr.py` | Normalize import resolution through one compatibility module with typed surface. |
| `reports.**` | External Django app modules loaded from ADR installation, not from this package | `src/ansys/dynamicreporting/core/utils/geofile_processing.py`, `src/ansys/dynamicreporting/core/serverless/template.py` | Introduce typed protocol/wrapper APIs for required engine calls and reduce direct imports. |
| `ceireports.**` | External Django settings/helpers loaded from ADR installation | `src/ansys/dynamicreporting/core/serverless/adr.py`, `src/ansys/dynamicreporting/core/serverless/item.py`, `src/ansys/dynamicreporting/core/serverless/template.py` | Move external imports behind typed helper functions and add import-time validation. |
| `ceiversion.**` | External version utility module from ADR/Ansys runtime | `src/ansys/dynamicreporting/core/utils/report_utils.py` | Replace direct module import with typed version-provider abstraction. |
| `data.**` | External Django app namespace from ADR installation | `src/ansys/dynamicreporting/core/serverless/adr.py`, `src/ansys/dynamicreporting/core/serverless/item.py`, `src/ansys/dynamicreporting/core/serverless/template.py` | Create typed local facades for required models/utilities and phase out direct namespace imports. |
| `ensight.**` | Optional EnSight runtime integration, unavailable in standard dev environments | `src/ansys/dynamicreporting/core/utils/report_objects.py`, `src/ansys/dynamicreporting/core/utils/report_remote_server.py` | Guard and isolate EnSight-specific code paths behind typed feature gates. |

