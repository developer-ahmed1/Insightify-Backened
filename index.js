// index.js (replace your existing file with this)
const express = require('express');
const cors = require('cors');
require('dotenv').config();

const { GoogleGenerativeAI } = require('@google/generative-ai');

const app = express();
app.use(cors());
app.use(express.json());

// ---- Gemini setup ----
if (!process.env.GEMINI_API_KEY) {
  console.error('❌ GEMINI_API_KEY missing in .env');
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const MODEL_NAME = process.env.GEMINI_MODEL || 'models/gemini-3.7-flash';
const model = genAI.getGenerativeModel({ model: MODEL_NAME });

// ---- Simple in-memory cache (text -> { result, expiresAt }) ----
const CACHE_TTL_MS = Number(process.env.CACHE_TTL_MS || 1000 * 60 * 60); // 1 hour default
const cache = new Map();

function cacheGet(key) {
  const e = cache.get(key);
  if (!e) return null;
  if (Date.now() > e.expiresAt) {
    cache.delete(key);
    return null;
  }
  return e.result;
}

function cacheSet(key, result) {
  cache.set(key, { result, expiresAt: Date.now() + CACHE_TTL_MS });
}

// ---- Basic rate limiter for Gemini calls ----
const GEMINI_MAX_PER_MIN = Number(process.env.GEMINI_MAX_PER_MIN || 10); // conservative default
let requestsThisMinute = 0;
let minuteWindowStart = Date.now();

function allowGeminiCall() {
  const now = Date.now();
  if (now - minuteWindowStart >= 60_000) {
    // reset window
    minuteWindowStart = now;
    requestsThisMinute = 0;
  }
  if (requestsThisMinute < GEMINI_MAX_PER_MIN) {
    requestsThisMinute++;
    return true;
  }
  return false;
}

// ---- Local heuristic fallback ----
const LINK_RE = /(https?:\/\/|www\.|bit\.ly|tinyurl|\.com|\.net|\.info)/i;
const urgencyWords = ["urgent","immediately","asap","now","verify","verify now","act now","suspend","suspended","blocked","expire","expired","last chance","limited time"];
const sensitiveWords = ["bank","account","password","pin","otp","one-time","transaction","card","credit","debit","verification","ssn","cnic","wa","whatsapp"];

function computeLocalScore(text = "") {
  const combined = (text || "").toLowerCase();
  let score = 0;

  // link present
  if (LINK_RE.test(combined)) score += 0.4;

  // urgency words
  if (urgencyWords.some(w => combined.includes(w))) score += 0.3;

  // sensitive banking terms
  if (sensitiveWords.some(w => combined.includes(w))) score += 0.3;

  // clamp between 0 and 1
  if (score > 1) score = 1;
  return score;
}

// Helper to build prompt (kept simple; you already had good prompt)
function makePrompt(text) {
  return `
SYSTEM ROLE:
You are a backend API. You MUST follow output rules.

TASK:
Analyze the MESSAGE and detect if it is a scam.

OUTPUT RULES (CRITICAL):
- Respond with ONLY valid JSON
- No markdown
- No explanation
- No extra text
- No backticks
- No emojis

JSON FORMAT:
{
  "score": number between 0 and 1,
  "reason": "short reason"
}

MESSAGE:
"${String(text).replace(/"/g, '\\"')}"
`;
}

// ---- API ----
app.post('/api/v1/score', async (req, res) => {
  try {
    const items = req.body.items;
    if (!items || !Array.isArray(items)) {
      return res.status(400).json({ error: 'Invalid items array' });
    }

    console.log(`📩 Received items: ${items.length}`);
    const results = [];

    for (const item of items) {
      // normalized key for caching
      const cacheKey = (item.text || '').trim();
      const cached = cacheGet(cacheKey);
      if (cached) {
        // serve from cache
        results.push({ ...cached, id: item.id, title: item.title, text: item.text });
        continue;
      }

      // Decide whether we can call Gemini right now
      let usedFallback = false;
      let parsedScore = null;
      let parsedReason = '';

      // If rate limiter forbids or no key present -> fallback
      if (!allowGeminiCall()) {
        usedFallback = true;
        parsedScore = computeLocalScore(item.text);
        parsedReason = 'Heuristic fallback (rate limit)';
        console.warn('⚠️ Gemini call skipped due to rate limiter');
      } else {
        // try calling Gemini
        try {
          const prompt = makePrompt(item.text);
          const response = await model.generateContent(prompt);

          const rawText = response.response.text().trim();
          try {
            const parsed = JSON.parse(rawText);
            parsedScore = Math.min(Math.max(Number(parsed.score) || 0.5, 0), 1);
            parsedReason = parsed.reason || 'No reason provided';
          } catch (parseErr) {
            console.warn('⚠️ Gemini returned non-JSON, falling back to heuristic', parseErr);
            usedFallback = true;
            parsedScore = computeLocalScore(item.text);
            parsedReason = 'Fallback: non-JSON AI response';
          }
        } catch (aiErr) {
          // If Gemini errors (including 429), fallback gracefully
          usedFallback = true;

          // If API provides status info, log it
          if (aiErr && aiErr.status) {
            console.error('❌ Gemini API error status:', aiErr.status, aiErr.message || aiErr);
          } else {
            console.error('❌ Gemini call failed:', aiErr && aiErr.message ? aiErr.message : aiErr);
          }

          parsedScore = computeLocalScore(item.text);
          parsedReason = aiErr && (aiErr.status === 429 || (aiErr.message && aiErr.message.includes('429')))
            ? 'Fallback: Gemini rate-limited (429)'
            : 'Fallback: Gemini error';
        }
      }

      // Compose the final result — always include usedFallback for client transparency
      const final = {
        id: item.id,
        title: item.title,
        text: item.text,
        score: parsedScore ?? 0.5,
        reason: parsedReason || '',
        usedFallback: usedFallback,
      };

      // Put canonical result into cache
      cacheSet(cacheKey, { id: item.id, title: item.title, text: item.text, score: final.score, reason: final.reason, usedFallback: final.usedFallback });

      results.push(final);
    }

    console.log('📤 Responding with:', results);
    res.json(results);

  } catch (err) {
    console.error('❌ Unexpected server error:', err);
    // Always return 200 with a safe fallback so client-side flow continues
    return res.status(200).json([
      {
        id: 'error',
        title: 'error',
        text: '',
        score: 0.5,
        reason: 'Server error - fallback',
      },
    ]);
  }
});

// ---- Start server (if running locally) ----
if (process.env.NODE_ENV !== 'production') {
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`🚀 Scam backend running locally on http://localhost:${PORT}`);
    console.log(`⚙️ Gemini model=${MODEL_NAME} | GEMINI_MAX_PER_MIN=${GEMINI_MAX_PER_MIN} | CACHE_TTL_MS=${CACHE_TTL_MS}`);
  });
}

// Export the Express API for Vercel
module.exports = app;
