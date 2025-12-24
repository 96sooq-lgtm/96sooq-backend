# 96sooq - Mobile & Web App

A full-stack application with Python backend, React web app, and React Native mobile app, integrated with Supabase/Firebase.

## Project Structure

```
96sooq-backend/
├── backend/          # Python FastAPI backend
├── web/             # React web application
├── mobile/          # React Native mobile application
└── docs/            # Documentation
```

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+
- Supabase or Firebase account

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Web App Setup
```bash
cd web
npm install
npm start
```

### Mobile App Setup
```bash
cd mobile
npm install
npm run android  # or npm run ios
```

## Environment Variables

Create `.env` files in each directory with necessary credentials:
- Backend: `backend/.env`
- Web: `web/.env`
- Mobile: `mobile/.env`

## Documentation

See [docs/](docs/) for detailed setup and API documentation.