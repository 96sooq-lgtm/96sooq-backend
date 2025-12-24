# Setup Guide

## Backend Setup (Python + FastAPI)

### 1. Create Virtual Environment
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Supabase/Firebase credentials
```

### 4. Run Server
```bash
python main.py
# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

## Supabase/Firebase Setup

### Using Supabase:
1. Create project at https://supabase.com
2. Get URL and API key from Settings
3. Create tables for your data model
4. Add Row Level Security (RLS) policies


## Common Environment Variables

```
# Backend
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

