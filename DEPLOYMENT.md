# Deployment Guide: Railway + Neon + Vercel

## Prerequisites
- Railway account (https://railway.app)
- Neon account (https://neon.tech)
- Cloudflare account with R2 (https://cloudflare.com)
- Vercel account for admin dashboard (https://vercel.com)

---

## Step 1: Neon Database Setup

### 1.1 Create Database
1. Go to https://console.neon.tech
2. Click **New Project** → Name: `insightyfy-prod`
3. Copy the connection string (looks like):
   ```
   postgresql://neondb_owner:xxx@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### 1.2 Create Tables
Run locally with your Neon connection string:

```bash
# Set the Neon connection string (replace with yours)
$env:DATABASE_URL='postgresql://neondb_owner:xxx@ep-xxx.neon.tech/neondb?sslmode=require'

# Run in sync mode (uses psycopg2, works with Neon)
python scripts/create_tables.py --sync
```

### 1.3 Seed Initial Data (Optional)
```bash
python scripts/seed_data.py
```

---

## Step 2: Railway Deployment

### 2.1 Create Railway Project
1. Go to https://railway.app → **New Project**
2. Select **Deploy from GitHub repo**
3. Connect your `insightyfy` repository

### 2.2 Add Redis (Optional but recommended)
1. In your Railway project, click **+ New**
2. Select **Redis**
3. Copy the `REDIS_URL` from the Redis service

### 2.3 Configure Environment Variables
In Railway project settings → **Variables**, add:

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
DEBUG=false
APP_ENV=production
SECRET_KEY=<generate-random-64-char-key>

# Firebase (upload firebase-credentials.json to repo or use env)
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
FIREBASE_PROJECT_ID=your-firebase-project-id

# AI
GEMINI_API_KEY=your-gemini-api-key

# Redis (from Railway Redis service)
REDIS_URL=redis://default:xxx@redis.railway.internal:6379

# Cloudflare R2 (configure after Step 3)
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY=your-access-key
R2_SECRET_KEY=your-secret-key
R2_BUCKET=insightyfy-media
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-xxx.r2.dev
```

### 2.4 Deploy Settings
In Railway → **Settings**:
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

Railway will auto-deploy on every push to main.

---

## Step 3: Cloudflare R2 Setup

### 3.1 Create Bucket
1. Cloudflare Dashboard → **R2** → **Create Bucket**
2. Name: `insightyfy-media`
3. Location: Choose closest to your users

### 3.2 Enable Public Access
1. Click bucket → **Settings** → **Public Access**
2. Enable R2.dev subdomain OR connect custom domain

### 3.3 Create API Token
1. **R2** → **Manage R2 API Tokens** → **Create API Token**
2. Permissions: **Object Read & Write**
3. Specify bucket: `insightyfy-media`
4. Copy the **Access Key ID** and **Secret Access Key**

### 3.4 Add CORS Policy
In bucket settings → **CORS Policy**:
```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## Step 4: Firebase Setup

### 4.1 Get Credentials
1. Firebase Console → Project Settings → **Service Accounts**
2. Click **Generate new private key**
3. Save as `firebase-credentials.json`

### 4.2 Add to Railway
**Option A**: Add file to repo (gitignored) and reference path
**Option B**: Base64 encode and use environment variable:
```bash
# Encode
$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("firebase-credentials.json"))
# Add to Railway as FIREBASE_CREDENTIALS_BASE64
```

---

## Step 5: Verify Deployment

### Health Check
```bash
curl https://your-app.railway.app/health
```

### Test API
```bash
# Test detection (replace with your URL and token)
curl -X POST "https://your-app.railway.app/api/v1/detection/text" \
  -H "Authorization: Bearer your-firebase-token" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message"}'
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Neon PostgreSQL connection string |
| `SECRET_KEY` | ✅ | Random 64-char string for security |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `FIREBASE_CREDENTIALS_PATH` | ✅ | Path to Firebase JSON |
| `DEBUG` | ✅ | Set to `false` in production |
| `APP_ENV` | ✅ | Set to `production` |
| `REDIS_URL` | ⚠️ | Optional, for caching/rate limiting |
| `R2_*` | ⚠️ | Optional, for media uploads |

---

## Troubleshooting

### Database Connection Error
- Ensure `+asyncpg` is in the DATABASE_URL for Railway
- For local scripts, use `--sync` flag with psycopg2

### Firebase Auth Errors
- Check Firebase credentials file path
- Ensure project ID matches

### R2 Upload Errors  
- Verify R2 credentials and bucket name
- Check CORS policy allows your domain
