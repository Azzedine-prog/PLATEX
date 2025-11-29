# PLATEX Usage & Installation Guide

## Quickstart
- **Linux/macOS:** `./setup_platform.sh`
- **Windows (double-click):** run `setup_platform.bat` (auto-launches PowerShell with the right flags).
- **Windows (PowerShell, Admin):** `./setup_platform.ps1`
- Open http://localhost:3000 for backend health; compilation service at http://localhost:7000. If Docker Desktop just installed, launch it once so containers can start.

## Workflow
1. Start stack: `docker compose up -d`.
2. Submit compilation via backend `/compile` endpoint with `main` and `files` map.
3. Read response for `pdf` (base64) and parsed `log` entries.
4. Use WebSockets (`/socket.io`) for collaborative edits and event streaming.

## Troubleshooting
- **Docker not running:** Start Docker Desktop (Windows) or daemon (Linux/macOS).
- **Port conflicts:** Adjust `docker-compose.yml` port mappings (3000/7000) and re-run `docker compose up -d`.
- **Missing dependencies:** Run the platform setup script again; it validates Docker and Node.js.

## Windows Notes
- Requires Docker Desktop with WSL2 backend enabled.
- Ensure PowerShell execution policy allows running the installer: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`.

## Next Steps
- Add frontend and desktop wrappers pointing to the backend URL.
- Extend CI workflow to publish Docker images to your registry.
