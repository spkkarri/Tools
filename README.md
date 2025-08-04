# 🤖 Chatbot

A powerful, multi-functional chatbot built to assist users with web research, summarization, content generation, and file handling — all in one place.

## 🚀 Features

- **Conversation History**
  - Automatically stores past interactions
  - Supports deleting history selectively or entirely

- **File Upload & Processing**
  - Upload `.txt`, `.pdf`, or `.docx` files
  - Extracts and analyzes content efficiently

- **Web Content Search**
  - Uses **DuckDuckGo** + **Selenium** for private, automated browsing
  - Scrapes and displays relevant content for user queries

- **AI-Powered Output (via Gemini)**
  - **Quiz Generation**: Creates quizzes from uploaded or scraped content
  - **Summarization**: Generates concise summaries of documents or web pages
  - **Podcast Builder**: Converts content into podcast-ready scripts

- **Download Page Feature**
  - Allows users to download a local HTML version of search results or summaries

## 🧠 Tech Stack

- **Frontend**: React
- **Backend**: Node,Express
- **Database**: MongoDB
- **Automation**: Selenium
- **Search**: DuckDuckGo,Selenium scraping
- **AI Model**: Gemini API
- **Research**: Core,OpenAlex

## 🛠️ Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/rajeshvamsi2004/chatbot.git
   cd chatbot
   cd frontend
   npm start
   cd backend
   node Chatbot.js,quiz.js,audioroutes.js
