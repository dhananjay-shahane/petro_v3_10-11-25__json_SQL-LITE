# Petrophysics Workspace - Setup Guide

## Running on Windows, Mac, or Linux

This application works on all operating systems! The path handling has been configured to work seamlessly across platforms.

### Development Mode

1. **Install Dependencies:**
   ```bash
   npm install
   ```

2. **Start Development Server:**
   ```bash
   npm run dev
   ```
   
   This will:
   - Start Flask API server on port 5001
   - Start Vite frontend on port 5000
   - Open your browser to http://localhost:5000

### Production Mode

1. **Build the Application:**
   ```bash
   npm run build
   ```

2. **Start Production Server:**
   ```bash
   bash production.sh
   ```

## Project Structure

- **Frontend (Vite + React)**: Runs on port 5000
- **Backend (Flask API)**: Runs on port 5001
- **Workspace**: `petrophysics-workplace/` folder stores all project data

## API Endpoints

- `GET /api/workspace/info` - Get workspace information
- `GET /api/directories/list?path=<path>` - List directories
- `POST /api/projects/create` - Create new project
- `POST /api/wells/create-from-las` - Upload LAS file
- `GET /api/wells/list?projectPath=<path>` - List wells in project

## Cross-Platform Path Handling

The application automatically handles:
- **Windows**: `C:\petrophysics-workplace\project`
- **Mac/Linux**: `/home/user/petrophysics-workplace/project`

All paths are normalized internally for compatibility.

## Features

- Dockable window management system
- LAS file import and well log visualization
- Cross-plot and log plot generation
- Project and well management
- Data browser and exploration tools

## Troubleshooting

### API Errors on Windows
If you see API path errors, the application will automatically fallback to the workspace root. The path validation now supports both Windows and Unix-style paths.

### Port Already in Use
If port 5000 or 5001 is in use:
- Edit `dev.sh` to change `FLASK_PORT` variable
- Update `vite.config.ts` proxy target accordingly
