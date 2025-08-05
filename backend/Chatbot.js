// --- FINAL, COMPLETE, AND WORKING CODE ---

require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const axios =require('axios');
const cheerio = require('cheerio');
const cors = require('cors');
const multer = require('multer');
const path = require('path');
const os = require('os');
const fs = require('fs');
const pdfParse = require('pdf-parse');
const { URL } = require('url');
const { JSDOM } = require('jsdom');
const { Readability } = require('@mozilla/readability');
const { GoogleGenerativeAI } = require("@google/generative-ai");
const { Builder, By, until } = require('selenium-webdriver');
const chrome = require('selenium-webdriver/chrome');

// --- MODEL IMPORT (MUST WORK) ---
let History;
try {
    History = require('./models/History.js');
} catch (e) {
    console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    console.error("FATAL ERROR: Could not load the History model.");
    console.error("Please ensure the file './models/History.js' exists and has no errors.");
    console.error("Original error:", e.message);
    console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    process.exit(1);
}

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors({
    origin: process.env.NODE_ENV === 'production'
        ? ['https://your-frontend-domain.com']
        : ['http://localhost:3000', 'http://localhost:5173'],
    credentials: true
}));

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const upload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: 10 * 1024 * 1024 }
});

// --- ENHANCED WEB SCRAPING & SEARCH FUNCTIONS ---

async function enhancedDuckDuckGoSearch(query, maxResults = 12) {
    const searchUrl = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
    try {
        const { data } = await axios.get(searchUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
            timeout: 15000
        });
        const $ = cheerio.load(data);
        const results = [];
        $('a.result__a').each((i, el) => {
            if (results.length >= maxResults) return;
            const title = $(el).text().trim();
            const rawLink = $(el).attr('href');
            try {
                const urlObj = new URL('https://duckduckgo.com' + rawLink);
                const realUrl = decodeURIComponent(urlObj.searchParams.get('uddg'));
                if (realUrl && title && (realUrl.startsWith('http:') || realUrl.startsWith('https:'))) {
                    results.push({ title, link: realUrl });
                }
            } catch (e) { /* ignore invalid URLs */ }
        });
        console.log(`[SEARCH] Found ${results.length} valid results for: "${query}"`);
        return results;
    } catch (error) {
        console.error('❌ DuckDuckGo search failed:', error.message);
        throw new Error('Search service temporarily unavailable');
    }
}

async function enhancedCrawlWithRequests(links) {
    if (!links || links.length === 0) return [];
    console.log(`⚡ Scraping ${links.length} links...`);

    const crawlSingleLink = async (linkInfo) => {
        const { link, title } = linkInfo;
        try {
            const response = await axios.get(link, {
                timeout: 10000,
                headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' }
            });
            const dom = new JSDOM(response.data, { url: link });
            const article = new Readability(dom.window.document).parse();
            if (article && article.textContent) {
                const cleanText = article.textContent.replace(/\s+/g, ' ').trim();
                if (cleanText.length > 100) {
                    console.log(`✅ Content extracted from: ${link}`);
                    return { status: 'success', title: article.title || title, link, textContent: cleanText };
                }
            }
            return { status: 'fail', link, reason: 'insufficient_content' };
        } catch (error) {
            console.log(`❌ Failed to scrape ${link}: ${error.message}`);
            return { status: 'fail', link, reason: error.message };
        }
    };

    const results = await Promise.all(links.map(crawlSingleLink));
    return results.filter(r => r.status === 'success');
}


// --- MAIN API ROUTE ---
app.post('/api', async (req, res) => {
    const { query } = req.body;
    if (!query || query.trim().length === 0) {
        return res.status(400).json({ error: 'Query is required.' });
    }

    try {
        console.log(`[PIPELINE] Received query: "${query}"`);
        const searchResults = await enhancedDuckDuckGoSearch(query, 10);

        if (!searchResults || searchResults.length === 0) {
            return res.json({ summary: `I couldn't find any relevant sources online for "${query}".` });
        }

        const extractedContent = await enhancedCrawlWithRequests(searchResults.slice(0, 5));

        if (!extractedContent || extractedContent.length === 0) {
            return res.json({ summary: "I found search results but couldn't access their content." });
        }

        const combinedText = extractedContent.map((c, i) => `--- Source ${i + 1}: ${c.title} (${c.link}) ---\n${c.textContent}`).join('\n\n');

        const prompt = `You are an expert research analyst. Analyze the provided web sources to comprehensively answer the user's query.

USER'S QUERY: "${query}"

Please generate a response in valid JSON format with this exact structure:

{
    "summary": "A comprehensive, well-structured summary that directly answers the user's query.",
    "key_points": ["An array of 4-6 crucial bullet points highlighting the most important information."],
    "sources_used": [1, 2, 3],
    "follow_up_questions": ["An array of 3 insightful follow-up questions."]
}

--- SOURCES ---
${combinedText.substring(0, 15000)}
--- END SOURCES ---`;

        const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash", generationConfig: { response_mime_type: "application/json" } });
        const result = await model.generateContent(prompt);
        const aiResponse = await result.response.text();
        const parsed = JSON.parse(aiResponse);

        // ================================================================
        // === START: ADDED CODE TO SAVE HISTORY TO THE DATABASE ===
        // ================================================================
        try {
            const usedSources = (parsed.sources_used || []).map(num => extractedContent[num - 1]).filter(Boolean);
            const historyEntry = new History({
                query: query,
                summary: parsed.summary,
                key_points: parsed.key_points,
                sources: usedSources,
                follow_up_questions: parsed.follow_up_questions
            });
            await historyEntry.save();
            console.log('✅ [HISTORY] Successfully saved response to the database.');
        } catch (dbError) {
            // Log the error, but don't fail the request. The user can still get their answer.
            console.error('❌ [HISTORY] Failed to save response to the database:', dbError);
        }
        // ================================================================
        // === END: ADDED CODE TO SAVE HISTORY TO THE DATABASE ===
        // ================================================================

        res.json({
            summary: parsed.summary,
            key_points: parsed.key_points,
            sources: (parsed.sources_used || []).map(num => extractedContent[num - 1]).filter(Boolean),
            follow_up_questions: parsed.follow_up_questions,
            all_search_results: searchResults
        });

    } catch (error) {
        console.error("❌ [API ERROR]", error);
        res.status(500).json({ error: 'An internal server error occurred.', details: error.message });
    }
});


// --- OTHER ROUTES ---
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        database: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected'
    });
});

app.post('/api/upload', upload.single('file'), async (req, res) => {
    // Placeholder for your file upload logic
    if (!req.file) return res.status(400).json({ error: 'No file uploaded.' });
    res.json({ message: `File '${req.file.originalname}' uploaded successfully.` });
});


// =======================================================
// ▼▼▼ NEWLY ADDED HISTORY MANAGEMENT ROUTES ▼▼▼
// =======================================================
// GET /api/history - Fetch all history items
app.get('/api/history', async (req, res) => {
    try {
        const historyItems = await History.find({}).sort({ createdAt: -1 });
        res.status(200).json(historyItems);
    } catch (error) {
        console.error('❌ Error fetching history:', error);
        res.status(500).json({ error: 'Failed to retrieve history' });
    }
});

// DELETE /api/history/:id - Delete a specific history item
app.delete('/api/history/:id', async (req, res) => {
    try {
        const { id } = req.params;
        if (!mongoose.Types.ObjectId.isValid(id)) {
            return res.status(400).json({ error: 'Invalid history item ID format.' });
        }
        const result = await History.findByIdAndDelete(id);
        if (!result) {
            return res.status(404).json({ error: 'History item not found.' });
        }
        console.log(`✅ [HISTORY] Deleted item with ID: ${id}`);
        res.status(200).json({ message: 'History item deleted successfully.' });
    } catch (error) {
        console.error(`❌ Error deleting history item ${req.params.id}:`, error);
        res.status(500).json({ error: 'Failed to delete history item.' });
    }
});

// PUT /api/history/:id - Rename/update a specific history item
app.put('/api/history/:id', async (req, res) => {
    try {
        const { id } = req.params;
        const { query } = req.body;
        if (!mongoose.Types.ObjectId.isValid(id)) {
            return res.status(400).json({ error: 'Invalid history item ID format.' });
        }
        if (!query || typeof query !== 'string' || query.trim() === '') {
            return res.status(400).json({ error: 'New query name is required.' });
        }
        const updatedItem = await History.findByIdAndUpdate(
            id,
            { query: query.trim() },
            { new: true, runValidators: true }
        );
        if (!updatedItem) {
            return res.status(404).json({ error: 'History item not found.' });
        }
        console.log(`✅ [HISTORY] Renamed item with ID: ${id} to "${query}"`);
        res.status(200).json(updatedItem);
    } catch (error) {
        console.error(`❌ Error updating history item ${req.params.id}:`, error);
        res.status(500).json({ error: 'Failed to update history item.' });
    }
});
// =======================================================
// ▲▲▲ END OF NEWLY ADDED ROUTES ▲▲▲
// =======================================================


// --- ERROR HANDLING & 404 ---
app.use((err, req, res, next) => {
    console.error('Unhandled error:', err.stack);
    res.status(500).json({ error: 'An internal server error occurred.' });
});

app.use((req, res, next) => {
    res.status(404).json({ error: `Endpoint not found: ${req.method} ${req.originalUrl}` });
});


// --- SERVER STARTUP LOGIC ---
const startServer = () => {
    app.listen(PORT, () => {
        console.log("--- ✅ SERVER HAS STARTED SUCCESSFULLY ---");
        console.log(`🚀 Your server is now running on port ${PORT}`);
        console.log(`🔗 Local: http://localhost:${PORT}`);
        console.log(`🩺 Health Check: http://localhost:${PORT}/health`);
    });
};

// --- DATABASE CONNECTION ---
console.log("Attempting to connect to MongoDB...");
if (!process.env.MONGODB_URI) {
    console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    console.error("FATAL ERROR: MONGODB_URI is not defined in your .env file.");
    console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    process.exit(1);
}

mongoose.connect(process.env.MONGODB_URI)
.then(() => {
    console.log("✅ MongoDB connection successful.");
    startServer();
})
.catch(err => {
    console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    console.error("❌ FATAL ERROR: Could not connect to MongoDB.");
    console.error("Please check your MONGODB_URI in the .env file and network access.");
    console.error("Original error:", err.message);
    console.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    process.exit(1);
});


// --- PROCESS HANDLERS ---
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
    process.exit(1);
});
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});