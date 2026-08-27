# LifePulse AI - Production Deployment Guide

This document explains how to manually deploy the LifePulse AI platform to a production environment.

## 1. Current Architecture
- **Frontend**: React + Vite SPA.
- **Backend**: Python FastAPI.
- **Databases**: PostgreSQL (primary store) and Redis (caching/websockets).

## 2. Containerization Status
- The **Backend, PostgreSQL, and Redis** are fully containerized using Docker Compose.
- The **Frontend** is designed to be built via Node.js and hosted on a static provider (like Vercel). It is *not* included in the Docker Compose setup to maintain independent scalability.

## 3. Local Development
For local development, simply use:
```bash
docker-compose up --build
```
This will start the backend, Postgres, and Redis. You can then run `npm run dev` in the `frontend/` directory.

## 4. Required Environment Variables
The application requires strict environment variables to function correctly. 
- **Backend**: Needs `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `FRONTEND_CORS_ORIGINS`, and Firebase config.
- **Frontend**: Needs `VITE_API_URL`, `VITE_WS_URL`, and Firebase config.

## 5. Preparing a Production `.env`
1. On your VPS, navigate to your cloned repository.
2. Create the backend environment file:
   ```bash
   cp backend/.env.example backend/.env
   ```
3. Edit `backend/.env` and replace all `CHANGE_ME` values, especially `DATABASE_URL`, `SECRET_KEY`, and `FRONTEND_CORS_ORIGINS`.

## 6. Securely Providing `firebase-service-account.json`
Firebase credentials should NEVER be committed to Git.
1. On your VPS, securely transfer your `firebase-service-account.json` file (e.g. using `scp` or `sftp`).
2. Place the file inside the `backend/` directory of your cloned repository.
3. Because the `docker-compose.prod.yml` and `Dockerfile` map `/app` to this directory, the file will be accessible inside the container at `/app/firebase-service-account.json`.

## 7. Ubuntu VPS Prerequisites
- Ubuntu 20.04 or newer.
- Minimum 2GB RAM recommended.
- A non-root user with `sudo` privileges.

## 8. Docker Installation Requirements
Install Docker and Docker Compose on your VPS:
```bash
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
```

## 9. Starting the Backend, PostgreSQL, and Redis
The system uses a base `docker-compose.yml` and a production override `docker-compose.prod.yml` to secure ports.

## 10. Production Docker Commands
To start the services securely in the background (ensure you pass your backend env file so variables interpolate correctly):
```bash
docker-compose --env-file backend/.env -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 11. Optional Nginx Configuration
To expose your API safely, configure Nginx as a reverse proxy:
```bash
sudo apt install nginx -y
```
Create `/etc/nginx/sites-available/api`:
```nginx
server {
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 12. Connecting a Domain Later
1. Point your domain's A record (e.g., `api.yourdomain.com`) to your VPS IP address.
2. Enable the Nginx site: `sudo ln -s /etc/nginx/sites-available/api /etc/nginx/sites-enabled/`
3. Reload Nginx: `sudo systemctl reload nginx`

## 13. Enabling HTTPS Later
Use Let's Encrypt (Certbot) to secure Nginx:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d api.yourdomain.com
```

## 14. Deploying the React/Vite Frontend to Vercel
1. Push your code to a GitHub repository.
2. Log in to Vercel and import the repository.
3. Select the `frontend` directory as the Root Directory.
4. Vercel will automatically detect Vite.

## 15. Vercel Environment Variables
Add the following to your Vercel project settings before deploying:
- `VITE_API_URL=https://api.yourdomain.com/api/v1`
- `VITE_WS_URL=wss://api.yourdomain.com/ws/requests`
- All `VITE_FIREBASE_*` variables from your Firebase console.

## 16. CORS Configuration
Ensure `backend/.env` on your VPS contains your exact Vercel frontend URL:
`FRONTEND_CORS_ORIGINS=https://your-frontend-domain.vercel.app`
*Do not use trailing slashes.*

## 17. Viewing Logs
To view backend logs:
```bash
docker-compose logs -f backend
```

## 18. Updating the Application
To deploy new changes:
```bash
git pull origin main
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 19. PostgreSQL Backup and Restore
Backup:
```bash
docker exec -t blood_donor_db pg_dump -U lifepulse_user lifepulse > backup.sql
```
Restore:
```bash
cat backup.sql | docker exec -i blood_donor_db psql -U lifepulse_user -d lifepulse
```

## 20. Troubleshooting Common Deployment Issues
- **CORS Errors**: Verify that `FRONTEND_CORS_ORIGINS` exactly matches your frontend domain.
- **Database Connection Failed**: Ensure `.env` passwords match and `USE_SQLITE_FALLBACK=False`.

## 21. Production Smoke Test
After starting the Docker containers, verify the backend is running and healthy:
```bash
curl http://localhost:8000/health
```
**Expected Response:**
```json
{"status":"healthy","service":"AI Smart Blood Donation Network","donors_count":0,"hospitals_count":0,"requests_count":0}
```
*(Counts may vary depending on existing data).*
