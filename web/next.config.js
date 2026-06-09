/** @type {import('next').NextConfig} */
const nextConfig = {
  // API calls from the frontend go to the FastAPI backend.
  // In production: set NEXT_PUBLIC_API_URL to the Railway web service URL.
  // In development: FastAPI runs at localhost:8000.
};

module.exports = nextConfig;
