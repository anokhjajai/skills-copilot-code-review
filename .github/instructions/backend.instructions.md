---
applyTo: "src/backend/**/*.py,src/app.py"
---

## Backend Guidelines

- All API endpoints must be defined in the `routers` folder.
- Load example database content from the `database.py` file.
- Log full error details on the server, and return appropriate HTTP status codes with sanitized, user-facing error messages to the frontend (do not expose stack traces or internal system details).
- Ensure all APIs are explained in the documentation.
- Verify changes in the backend are reflected in the frontend (`src/static/**`). If possible breaking changes are found, mention them to the developer.