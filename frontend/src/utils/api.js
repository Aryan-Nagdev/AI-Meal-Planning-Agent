import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const api  = axios.create({ baseURL: BASE });

export const generatePlan  = (data) => api.post('/api/plan',    data).then(r => r.data);
export const replan        = (data) => api.post('/api/replan',  data).then(r => r.data);
export const getRecipe     = (meal_name, ingredients) =>
  api.post('/api/recipe',  { meal_name, ingredients }).then(r => r.data);
export const getSimilar    = (meal_name, top_n = 4) =>
  api.post('/api/similar', { meal_name, top_n }).then(r => r.data);
export const chat          = (message, plan_context) =>
  api.post('/api/chat',    { message, plan_context }).then(r => r.data);
export const getStats      = () => api.get('/api/stats').then(r => r.data);