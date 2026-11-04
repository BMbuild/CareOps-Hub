CareOps Hub

CareOps Hub is a lightweight healthcare implementation management platform designed to connect technical issue tracking with implementation project progress.

Built as a two-week MVP for the Pursuit L2 Cycle 4 Capstone Project, CareOps Hub helps implementation teams identify blockers, track milestones, and assess deployment readiness through a shared system.

Project Team
Sarah – Implementation Workspace
Brahim – Product Workspace
Problem Statement

Healthcare software implementation teams often manage implementation milestones and technical issues in separate systems. This can create communication gaps, delay decisions, and make it difficult to determine whether a deployment is truly ready.

CareOps Hub provides a shared view of:

Product issues
Implementation milestones
Technical blockers
Deployment readiness

By connecting these areas, teams can better understand how unresolved issues impact implementation progress.

Product Vision

CareOps Hub provides a single source of truth for:

Product Managers tracking technical issues
Implementation Project Managers tracking deployment progress

The platform surfaces blockers and calculates implementation readiness using deterministic business rules.

MVP Features
Product Workspace (Brahim)
Create and manage product features
Create and track technical issues
Assign issue severity:
Low
Medium
Critical
Update issue status:
Open
In Progress
Resolved
Associate issues with features
Link issues to implementation milestones
Implementation Workspace (Sarah)
View implementation project details
Create milestones
Edit milestones
Assign milestone owners
Set milestone due dates
Track milestone progress
View linked technical issues
Identify implementation blockers
Display implementation readiness
Readiness Rules
Not Ready

An implementation is considered Not Ready when:

At least one unresolved Critical issue is linked to a milestone

OR

At least one required milestone remains incomplete
Ready

An implementation is considered Ready only when:

No unresolved Critical issues are linked to milestones

AND

All required milestones have been completed
Important Note

Readiness is an informational indicator only.

The system does not authorize or automate healthcare software go-live decisions. Final deployment approval remains the responsibility of a human project manager.

Technology Stack
Frontend
HTML
CSS
JavaScript
Backend
Python
FastAPI
Database
Local Development
SQLite
Production
PostgreSQL
ORM
SQLAlchemy
Source Control
GitHub
Deployment
Render
Architecture
Plain Text
┌────────────────────┐
│ Product Workspace │
└─────────┬──────────┘
│
▼
┌────────────────────┐
│ FastAPI Backend │
└─────────┬──────────┘
│
▼
┌────────────────────┐
│ PostgreSQL / SQLite│
└────────────────────┘
▲
│
┌─────────┴──────────┐
│Implementation WS │
└────────────────────┘

Both workspaces use the same backend and database to ensure data consistency.

Project Structure
Plain Text
careops-hub/
│
├── backend/
│ ├── app/
│ ├── models/
│ ├── routes/
│ ├── services/
│ └── main.py
│
├── frontend/
│ ├── product/
│ │ ├── product.html
│ │ ├── product.css
│ │ └── product.js
│ │
│ └── implementation/
│ ├── implementation.html
│ ├── implementation.css
│ └── implementation.js
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── database.db
Environment Variables

Create a .env file in the project root.

Example:

Plain Text
env isn’t fully supported. Syntax highlighting is based on Plain Text.
ANTHROPIC_API_KEY=your_api_key_here
 
DATABASE_URL=sqlite:///careops.db

Production Example:

Plain Text
env isn’t fully supported. Syntax highlighting is based on Plain Text.
ANTHROPIC_API_KEY=your_api_key_here
 
DATABASE_URL=postgresql://username:password@host/database
 
Security
Never Commit Secrets

The following files should never be committed:

Plain Text
.env
.env.local
database.db
*.sqlite3

Store all API keys and database credentials in environment variables.

If an API key is accidentally committed:

Remove it from Git history.
Revoke the exposed key.
Generate a new key immediately.
Installation
Clone Repository
Shell
git clone https://github.com/your-org/careops-hub.git
 
cd careops-hub
Create Virtual Environment
Shell
python -m venv venv
Activate Environment

Windows:

Shell
venv\Scripts\activate

Mac/Linux:

Shell
source venv/bin/activate
 
Install Dependencies
Shell
pip install -r requirements.txt
Run Development Server
Shell
uvicorn backend.main:app --reload

Application:

Plain Text
http://localhost:8000

API Documentation:

Plain Text
http://localhost:8000/docs
Core User Journey
Product Manager creates a Critical technical issue.
Issue is linked to an implementation milestone.
Implementation Workspace displays the issue as a blocker.
Readiness becomes Not Ready.
Product Manager resolves the issue.
Remaining milestones are completed.
Readiness recalculates automatically.
Status changes to Ready.
Acceptance Criteria
Product Workspace
Create features
Create technical issues
Update issue severity
Update issue status
Link issues to milestones
Persist data
Implementation Workspace
View implementation project
Create milestones
Update milestones
Assign owners
Assign due dates
View blockers
View readiness status
Integration
Critical issue causes Not Ready
Resolving critical issue removes blocker
Incomplete milestones prevent Ready
Completed milestones and no critical blockers produce Ready
Data remains consistent across both workspaces
Non-Goals

The MVP does not include:

Real patient data
EHR integrations
AI-generated deployment decisions
Automated go-live approvals
Advanced analytics
Email notifications
SMS notifications
Enterprise authentication
Multi-facility implementations
Real-time collaboration
Success Metrics
Metric	TargetUsability	3/3 testers complete core workflow
Blocker Visibility	3/3 testers identify blockers in under 30 seconds
Readiness Accuracy	10/10 readiness scenarios pass
Data Persistence	10/10 persistence tests pass
Deployment Reliability	Successful hosted demo
Definition of Done

CareOps Hub is complete when:

Both workspaces function independently
Both workspaces connect to the shared backend
Issue-to-milestone linking works
Readiness rules behave correctly
Data persists after restart
Acceptance criteria pass
Application is deployed
Public demo URL is available
Final demonstration workflow succeeds
License

This project was created for educational purposes as part of the Pursuit Software Engineering Fellowship and is not intended for production healthcare use.
