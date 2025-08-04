require('dotenv').config();
const express = require('express'); // ✅ THIS WAS MISSING
const { translate } = require('@vitalets/google-translate-api');
const googleTTS = require('google-tts-api');
const cors = require('cors');
const { GoogleGenerativeAI } = require('@google/generative-ai'); 


const app = express();
const port = 5002;

app.use(cors());
app.use(express.json());

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Step 1: Get Gemini explanation
async function explainWithGemini(topic) {
  try {
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash-latest' });
    const prompt = `You're an expert podcast narrator. Explain the topic "${topic}" in a way that is engaging, easy to understand, and ideal for listening. Do not just summarize—explain with examples, analogies, and a friendly tone.`;
    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();
    console.log(`[Gemini] Explained topic: ${topic}`);
    return text;
  } catch (err) {
    console.error('[Gemini Error]', err);
    return null;
  }
}

// Step 2: Translate and Generate TTS Audio
async function translateAndSpeak(text, targetLang) {
  try {
    const { text: translatedText } = await translate(text, { to: targetLang });
    const sentences = translatedText.match(/[^.!?]+[.!?]+/g) || [translatedText];
    console.log(`[Audio] Text split into ${sentences.length} sentences for processing.`);

    const audioBuffers = [];

    for (let i = 0; i < sentences.length; i++) {
      const sentence = sentences[i];
      if (!sentence) continue;

      console.log(`[Audio] Generating audio for sentence ${i + 1}/${sentences.length}...`);

      const audioDataObjects = await googleTTS.getAllAudioBase64(sentence, {
        lang: targetLang,
        slow: false,
        timeout: 10000,
      });

      for (const chunk of audioDataObjects) {
        audioBuffers.push(Buffer.from(chunk.base64, 'base64'));
      }

      await sleep(500);
    }

    const finalAudioBuffer = Buffer.concat(audioBuffers);
    console.log(`✅ [Audio] Audio generated successfully for language: ${targetLang}`);
    return finalAudioBuffer;

  } catch (err) {
    console.error('[Translation/TTS Error]', err);
    return null;
  }
}

// API Endpoint
app.post('/podcast', async (req, res) => {
  const { topic, targetLanguage } = req.body;

  if (!topic || !targetLanguage) {
    return res.status(400).json({ error: 'Missing "topic" or "targetLanguage" in the request body.' });
  }

  const explainedText = await explainWithGemini(topic);

  if (!explainedText) {
    return res.status(500).json({ error: 'Failed to get an explanation from the AI model.' });
  }

  const audioBuffer = await translateAndSpeak(explainedText, targetLanguage);

  if (!audioBuffer) {
    return res.status(500).json({ error: 'Failed to translate text or generate audio.' });
  }

  res.setHeader('Content-Type', 'audio/mpeg');
  res.send(audioBuffer);
});

// Test route


app.listen(port, '0.0.0.0', () => {
  console.log(`🎙️  Podcast Server running at http://localhost:${port}`);
});
