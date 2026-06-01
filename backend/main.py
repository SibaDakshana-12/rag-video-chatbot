from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

def get_youtube_id(url):
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_youtube_data(url):
    video_id = get_youtube_id(url)
    ytt_api = YouTubeTranscriptApi()
    fetched = ytt_api.fetch(video_id)
    transcript = " ".join([t.text for t in fetched])

    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    views    = info.get("view_count", 0) or 0
    likes    = info.get("like_count", 0) or 0
    comments = info.get("comment_count", 0) or 0

    return {
        "video_id": "A",
        "platform": "youtube",
        "url": url,
        "title": info.get("title", ""),
        "creator": info.get("uploader", ""),
        "views": views,
        "likes": likes,
        "comments": comments,
        "followers": info.get("channel_follower_count", 0) or 0,
        "duration": info.get("duration", 0) or 0,
        "upload_date": info.get("upload_date", ""),
        "hashtags": info.get("tags", [])[:5],
        "transcript": transcript,
        "hook": transcript[:500],
        "engagement_rate": round(((likes + comments) / max(views, 1)) * 100, 2)
    }

def get_instagram_data(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        transcript = info.get("description", "No transcript available")
        views    = info.get("view_count", 0) or 0
        likes    = info.get("like_count", 0) or 0
        comments = info.get("comment_count", 0) or 0

        return {
            "video_id": "B",
            "platform": "instagram",
            "url": url,
            "title": info.get("title", ""),
            "creator": info.get("uploader", ""),
            "views": views,
            "likes": likes,
            "comments": comments,
            "followers": info.get("channel_follower_count", 0) or 0,
            "duration": info.get("duration", 0) or 0,
            "upload_date": info.get("upload_date", ""),
            "hashtags": info.get("tags", [])[:5],
            "transcript": transcript,
            "hook": transcript[:500],
            "engagement_rate": round(((likes + comments) / max(views, 1)) * 100, 2)
        }

    except Exception:
        # Instagram blocks automated scraping without OAuth
        # Using estimated fallback data — clearly labeled
        # Production fix: use Instagram Graph API with OAuth tokens
        transcript = f"[ESTIMATED DATA - Instagram blocked automated access] Instagram reel from {url}. Content discusses social media engagement strategies, trending topics, and creator tips. The video uses strong hooks, trending audio, and clear call to action."
        views    = 50000
        likes    = 3200
        comments = 180
        return {
            "video_id": "B",
            "platform": "instagram",
            "url": url,
            "title": "Instagram Reel [Estimated Data]",
            "creator": url.split("/")[-2] if "/" in url else "Instagram Creator",
            "views": views,
            "likes": likes,
            "comments": comments,
            "followers": 25000,
            "duration": 30,
            "upload_date": "20240101",
            "hashtags": ["reels", "viral", "trending"],
            "transcript": transcript,
            "hook": transcript[:500],
            "engagement_rate": round(((likes + comments) / max(views, 1)) * 100, 2),
            "data_source": "estimated"
        }

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# Initialize embeddings ONCE at startup — not on every request
_embeddings = None

def get_embeddings_cached():
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    return _embeddings

def get_vectorstore(session_id="default"):
    return Chroma(
        collection_name=f"videos_{session_id}",
        embedding_function=get_embeddings_cached(),
    )

def chunk_and_embed(video_data, session_id="default"):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_text(video_data["transcript"])

    metadatas = [{
        "video_id": video_data["video_id"],
        "platform": video_data["platform"],
        "creator": video_data["creator"],
        "title": video_data["title"],
        "chunk_index": i,
        "engagement_rate": video_data["engagement_rate"],
        "views": video_data["views"],
        "likes": video_data["likes"],
        "comments": video_data["comments"],
        "followers": video_data["followers"],
        "hook": video_data.get("hook", "")[:200],
    } for i, chunk in enumerate(chunks)]

    vectorstore = get_vectorstore(session_id)
    vectorstore.add_texts(texts=chunks, metadatas=metadatas)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Session based storage — supports multiple users simultaneously
sessions = {}

def get_session(session_id="default"):
    if session_id not in sessions:
        sessions[session_id] = {
            "video_store": {},
            "chat_history": []
        }
    return sessions[session_id]

def format_docs(docs):
    formatted = []
    for doc in docs:
        vid_id = doc.metadata.get("video_id", "?")
        chunk_idx = doc.metadata.get("chunk_index", 0)
        formatted.append(f"[Source: Video {vid_id} - Chunk {chunk_idx}]:\n{doc.page_content}")
    return "\n\n".join(formatted)

def get_chain(session_id="default"):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.7,
        streaming=True
    )

    retriever = get_vectorstore(session_id).as_retriever(search_kwargs={"k": 4})

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert social media analyst helping creators understand their video performance.
You have access to transcripts and metadata for two videos (A and B).
Always cite which video and chunk your answer comes from using [Source: Video X - Chunk Y] format.
Be specific, data-driven, and actionable in your responses.

Retrieved transcript chunks:
{context}

Video Metadata:
{metadata}
"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    chain = (
        RunnablePassthrough.assign(
            context=lambda x: format_docs(retriever.invoke(x["question"]))
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain, retriever

class IngestRequest(BaseModel):
    youtube_url: str
    instagram_url: str
    session_id: str = "default"

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

@app.post("/ingest")
async def ingest(request: IngestRequest):
    session_id = request.session_id
    session = get_session(session_id)

    try:
        session["video_store"] = {}
        session["chat_history"] = []

        # Delete old chroma collection before new ingest
        # prevents retrieval pollution from previous sessions
        try:
            import chromadb
            client = chromadb.PersistentClient(path="./chroma_db")
            client.delete_collection(f"videos_{session_id}")
        except Exception:
            pass

        print("Fetching YouTube data...")
        video_a = get_youtube_data(request.youtube_url)
        video_a["video_id"] = "A"

        print("Fetching Instagram data...")
        video_b = get_instagram_data(request.instagram_url)
        video_b["video_id"] = "B"

        session["video_store"]["A"] = video_a
        session["video_store"]["B"] = video_b

        print("Embedding Video A...")
        chunk_and_embed(video_a, session_id)

        print("Embedding Video B...")
        chunk_and_embed(video_b, session_id)

        print("Done!")

        def clean(v):
            return {
                "title": v["title"],
                "creator": v["creator"],
                "views": v["views"],
                "likes": v["likes"],
                "comments": v["comments"],
                "followers": v["followers"],
                "duration": v["duration"],
                "upload_date": v["upload_date"],
                "hashtags": v["hashtags"],
                "engagement_rate": v["engagement_rate"],
                "platform": v["platform"],
                "url": v["url"],
            }

        return {
            "success": True,
            "video_a": clean(video_a),
            "video_b": clean(video_b)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    session = get_session(session_id)

    async def generate():
        try:
            chain, retriever = get_chain(session_id)

            a = session["video_store"].get("A", {})
            b = session["video_store"].get("B", {})
            metadata = f"""Video A: "{a.get('title','')}" by {a.get('creator','')}
Views: {a.get('views',0)} | Likes: {a.get('likes',0)} | Comments: {a.get('comments',0)} | Followers: {a.get('followers',0)} | Engagement: {a.get('engagement_rate',0)}%

Video B: "{b.get('title','')}" by {b.get('creator','')}
Views: {b.get('views',0)} | Likes: {b.get('likes',0)} | Comments: {b.get('comments',0)} | Followers: {b.get('followers',0)} | Engagement: {b.get('engagement_rate',0)}%"""

            docs = retriever.invoke(request.message)
            citations = []
            seen = set()
            for doc in docs:
                vid_id = doc.metadata.get("video_id", "")
                chunk_idx = doc.metadata.get("chunk_index", 0)
                key = f"{vid_id}-{chunk_idx}"
                if key not in seen:
                    seen.add(key)
                    citations.append({
                        "video_id": vid_id,
                        "chunk_index": chunk_idx,
                        "preview": doc.page_content[:120] + "..."
                    })

            full_answer = ""
            async for chunk in chain.astream({
                "question": request.message,
                "chat_history": session["chat_history"],
                "metadata": metadata
            }):
                if isinstance(chunk, str) and chunk:
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            session["chat_history"].append(HumanMessage(content=request.message))
            session["chat_history"].append(AIMessage(content=full_answer))

            yield f"data: {json.dumps({'type': 'citations', 'content': citations})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.get("/")
async def root():
    return {"status": "running"}