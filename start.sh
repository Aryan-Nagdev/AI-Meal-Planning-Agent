#!/bin/bash
# Quick start script for AI Meal Planner
# Run from the meal_planner/ root directory

echo "================================================"
echo "  🍽️  AI Meal Planner - Quick Start"
echo "================================================"

# Backend
echo ""
echo "▶ Setting up backend..."
cd backend
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -r requirements.txt -q

if [ -f ".env.example" ] && [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  ⚠️  Created .env — add your ANTHROPIC_API_KEY in backend/.env"
fi

echo "  ✅ Backend dependencies installed"
echo "  ▶ Starting backend on http://localhost:8000 ..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Frontend
echo ""
echo "▶ Setting up frontend..."
cd frontend
npm install --silent
echo "  ✅ Frontend dependencies installed"
echo "  ▶ Starting frontend on http://localhost:3000 ..."
npm start &
FRONTEND_PID=$!
cd ..

echo ""
echo "================================================"
echo "  ✅ Both servers started!"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo "================================================"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Servers stopped.'" SIGINT SIGTERM
wait
