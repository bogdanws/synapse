const apiBaseUrlFromEnv = import.meta.env.VITE_API_BASE_URL

export const API_BASE_URL = apiBaseUrlFromEnv ?? 'http://localhost:8000'
