# RAG Video Engagement Analyzer

## About the Project

I built this project to compare two social media videos using a RAG (Retrieval-Augmented Generation) pipeline.

The user provides one YouTube video URL and one Instagram Reel URL. The system fetches transcript and metadata information from both videos, calculates engagement rate, stores transcript chunks in a vector database, and allows the user to ask questions about the videos through a chat interface.

The main idea was to understand how RAG works in a practical project instead of building a normal chatbot.

---

## What the Project Does

* Takes one YouTube URL and one Instagram Reel URL
* Fetches transcript and video metadata
* Calculates engagement rate
* Stores transcript chunks in a vector database
* Lets users chat with the videos
* Supports conversation memory
* Shows source citations in responses
* Streams responses instead of waiting for the full answer

Some questions users can ask:

* Why did Video A perform better than Video B?
* Compare the hooks of both videos.
* Which creator has more followers?
* What can Video B improve based on Video A?

---

## Tech Stack

### Frontend

* React

### Backend

* FastAPI
* Python

### AI and RAG

* LangChain
* Gemini 2.5 Flash
* Gemini Embeddings

### Vector Database

* ChromaDB

### Transcript and Metadata Extraction

* youtube-transcript-api
* yt-dlp

---

## Why I Chose These Technologies

### FastAPI

I used FastAPI because most AI libraries work very well with Python. It is lightweight, easy to use, and supports asynchronous APIs.

### ChromaDB

I chose ChromaDB because this project is running locally and compares only two videos at a time. It is simple to set up and I didn't need to spend time managing external infrastructure.

For a larger production system, I would move to Qdrant because it is better for scaling and handling larger workloads.

### Gemini

I used Gemini for both embeddings and text generation. The free tier was enough for development and testing.

I considered OpenAI as well, but Gemini was easier to work with during development because I could build and test without worrying about API credits.

### LangChain

LangChain helped connect the retriever, vector database, embeddings, prompts, and chat memory in a clean way.

---

## How the System Works

1. User enters YouTube and Instagram URLs.
2. Transcript and metadata are collected.
3. Engagement rate is calculated.
4. Transcript is split into smaller chunks.
5. Embeddings are generated.
6. Chunks are stored in ChromaDB.
7. User asks a question.
8. Relevant chunks are retrieved.
9. Gemini generates an answer using the retrieved information.
10. Response is streamed back to the frontend with citations.

---

## Some Design Decisions

### Chunk Size

I used a chunk size of 500 and overlap of 100.

If chunks are too small, important context gets split across many chunks.

If chunks are too large, retrieval may return unnecessary information.

500 with 100 overlap gave a good balance during testing.

### Metadata Storage

Along with transcript chunks, I also store:

* Video ID
* Creator
* Platform
* Views
* Likes
* Comments
* Followers
* Engagement Rate

This helps the model answer questions related to video performance and not just transcript content.

### Session-Based Storage

Each session has separate video data and chat history.

This prevents one user's data from affecting another user's conversation.

---

## Current Limitations

There are still some limitations in the current version:

* Instagram data availability depends on platform restrictions.
* Session data is stored in memory.
* ChromaDB is good for development but not ideal for large-scale production.
* The project currently compares only two videos at a time.

---

## What Happens at Scale

Right now the project works well for development and small workloads.

If 1000 users start using it at the same time, there will be some issues:

* ChromaDB is running locally on a single server.
* Session data is stored in memory.
* Ingestion and retrieval requests will compete for resources.
* Memory usage will increase and response time may become slower.

---

## What I Would Change for Production

For a production system, I would:

* Move session storage to Redis
* Replace ChromaDB with Qdrant
* Use Docker for deployment
* Add background workers for ingestion
* Run multiple FastAPI instances behind a load balancer

These changes would make the system more scalable and reliable.

---

## Running the Project

### Backend

```bash
cd backend

python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt

uvicorn main:app --reload
```

### Frontend

```bash
cd frontend

npm install

npm start
```

### Environment Variables

Create a `.env` file inside the backend folder:

```env
GOOGLE_API_KEY=your_api_key_here
```

---

## What I Learned

This project helped me understand how a complete RAG pipeline works, including transcript ingestion, chunking, embeddings, vector databases, retrieval, memory, and response streaming.

It also helped me understand the difference between building something that works locally and building something that can scale in production.
