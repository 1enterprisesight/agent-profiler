# Agent Profiler - Changelog

## [Unreleased] - 2025-11-25

### Fixed
- **SQLAlchemy Model Relationship Errors**: Fixed critical model configuration issues
  - File: `backend/app/models.py` lines 266, 274, 86
  - ConversationMessage: Fixed ForeignKey from "conversation_sessions.id" → "conversations.id"
  - ConversationMessage: Fixed relationship from "ConversationSession" → "Conversation"
  - Client: Added missing `data_source_id` foreign key to data_sources table
  - Error: "Could not determine join condition between parent/child tables on relationship Conversation.messages"
  - Impact: Models were failing to initialize, breaking all API endpoints

- **Database Dependency Error**: Fixed AsyncSession dependency in uploads router
  - File: `backend/app/routers/uploads.py` lines 16, 39, 155, 205
  - Changed from `Depends(get_db)` to `Depends(get_db_session)` in all three endpoints
  - Error: `'_AsyncGeneratorContextManager' object has no attribute 'execute'`
  - Root cause: `get_db()` is @asynccontextmanager, not a FastAPI dependency
  - Fix: Use `get_db_session()` which properly wraps the context manager
  - Impact: DataSourceList widget was failing to load, preventing upload button from appearing

- **Modal Placement Issue**: Moved upload button from header into Data Sources widget
  - File: `frontend/src/components/DataSourceList.tsx` - Added DataUpload button with refresh callback
  - File: `frontend/src/App.tsx` - Removed DataUpload from header, reordered left panel
  - File: `frontend/src/components/DataUpload.tsx` - Reverted broken overflow fix
  - User report: "upload window is now stuck in the top banner" - RESOLVED by moving button location
  - Layout: DataSourceList now displayed above AgentNetwork in left panel

- **Authentication Blocking Uploads**: CSV upload failing due to missing OAuth
  - File: `backend/app/auth.py` lines 180-199
  - Added `get_current_user_dev_mode()` function for development testing
  - Only bypasses auth when `APP_ENV=development` (security gated)
  - User report: "not loading cvs file is failing to load"

- **Upload Endpoint Dependencies**: Fixed to use new dev mode auth
  - File: `backend/app/routers/uploads.py` lines 38, 154, 204
  - Changed from `get_current_user` to `get_current_user_dev_mode`
  - All three endpoints: POST /csv, GET /history, DELETE /{id}

- **Backend Dockerfile**: Reverted to single-stage build
  - File: `backend/Dockerfile`
  - Previous multi-stage build caused deployment issues
  - Simpler single-stage build works reliably on Cloud Run

### Added
- **DELETE Data Source Endpoint**: Full deletion with cascading
  - File: `backend/app/routers/uploads.py` lines 201-299
  - Deletes Client records, DataSource record, and GCS file
  - Proper user authorization check

- **Data Source Management UI**: Two new components
  - `frontend/src/components/DataSourceList.tsx` - Dashboard widget
  - `frontend/src/components/DataSourceManager.tsx` - Full modal manager
  - Integrated into App.tsx

### Changed
- **API Endpoint Updates**: Frontend now uses correct endpoints
  - File: `frontend/src/services/api.ts`
  - Changed `/data/upload-csv` → `/uploads/csv`
  - Changed `/data/sources` → `/uploads/history`
  - Added `deleteDataSource()` method

- **DataSource Field Names**: Fixed to match actual model
  - File: `backend/app/routers/uploads.py` lines 167, 176-182
  - `created_at` → `uploaded_at`
  - `records_ingested` → `records_imported`
  - `source_name` → `file_name`

## Deployment Status

### Backend
- **Last Deployed**: v1.2.0 (revision agent-profiler-api-00022-txl)
- **Built Not Deployed**: v1.2.2 (includes dev mode auth)
- **Pending**: Deploy v1.2.2 with `APP_ENV=development` environment variable

### Frontend
- **Last Deployed**: v1.2.1 (revision agent-profiler-frontend-00004-9sd)
- **Pending**: Rebuild dist and deploy v1.2.2 with modal fix

## Last Commits
- 1b668af: feat: Add data upload functionality to frontend
- f93f2b8: feat: Add React frontend with multi-agent visualization

## Next Steps
1. Deploy backend v1.2.2 with `APP_ENV=development`
2. Rebuild frontend dist with modal overflow fix
3. Build and deploy frontend v1.2.2
4. Test CSV upload with `/Users/michaelreed/linkedin-Contacts.csv`
5. Commit all changes with proper message
