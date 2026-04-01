# 📚 Local RAG Document Q&A System

> A fully private, offline-capable AI-powered document question-answering system built with Django, Docker, Celery, and Ollama. Upload your PDFs and ask natural language questions — all processing stays on your machine.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Django](https://img.shields.io/badge/Django-REST_Framework-green?logo=django)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 🔍 What Is This?

This system lets you upload PDF documents and ask questions about them using a local large language model — **no cloud, no subscriptions, no data leaves your machine**. It uses Retrieval-Augmented Generation (RAG) to find the most relevant document chunks and generate accurate, cited answers.

Perfect for sensitive documents like:
- 📄 Resumes & HR files
- ⚖️ Legal contracts
- 🏥 Medical records
- 🏢 Internal business documentation
- 📖 Research papers

---

## 🖥️ Live Preview

![App Screenshot](docs/screenshot.png)

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx      │────▶│   Django    │────▶│   Celery    │
│  (optional) │     │  REST API   │     │  Workers    │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                   │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │    Redis    │     │    FAISS    │
                    │   Broker    │     │  Vector DB  │
                    └─────────────┘     └──────┬──────┘
                                               │
                                        ┌──────▼──────┐
                                        │   Ollama    │
                                        │  Local LLM  │
                                        └─────────────┘
```

| Component | Technology |
|-----------|-----------|
| API Backend | Django REST Framework |
| Task Queue | Celery + Redis |
| Vector Store | FAISS |
| Embeddings | Hugging Face `sentence-transformers` |
| LLM Inference | Ollama (Phi / Llama 2) |
| Containerization | Docker Compose |
| Reverse Proxy | Nginx (optional) |

---

## ✨ Features

- 📤 **PDF Upload** with async processing pipeline
- 🔎 **Semantic Search** using FAISS vector similarity
- 🤖 **Local LLM Inference** via Ollama — no API keys needed
- 💬 **Conversational Q&A** with source citations
- 🔒 **Session-based Isolation** — each user gets their own index
- 📊 **Real-time Status Tracking** for document processing
- 🛡️ **Rate Limiting & Input Validation** against prompt injection
- 🌐 **No-Auth Mode** for internal/demo deployments

---

## 🚀 Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- [Ollama](https://ollama.ai/) installed on your host machine
- At least 8GB RAM (16GB recommended for larger models)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/local-rag-document-qa.git
cd local-rag-document-qa
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your configuration (see Environment Variables section)
```

### 3. Pull an Ollama Model

```bash
ollama pull phi
# or
ollama pull llama2
```

### 4. Start the Services

```bash
docker compose up --build
```

### 5. Access the App

Open your browser at `http://localhost:8000`

---

## ⚙️ Environment Variables

Create a `.env` file based on `.env.example`. **Never commit your actual `.env` file.**

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis
REDIS_URL=redis://redis:6379/0

# Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=phi

# File Upload
MAX_UPLOAD_SIZE_MB=10

# Optional: Auth
REQUIRE_AUTH=False
```

---

## 📁 Project Structure

```
local-rag-document-qa/
├── backend/
│   ├── api/                  # Django REST API
│   ├── rag/                  # RAG engine (embeddings, retrieval, generation)
│   ├── tasks/                # Celery async tasks
│   └── manage.py
├── frontend/                 # Static HTML/JS interface
├── nginx/                    # Nginx config (production)
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── .env.example              # ✅ Safe to commit — no real secrets
├── .gitignore
└── README.md
```

---

## 🔐 Security & Privacy

- ✅ All processing is 100% local — no external API calls
- ✅ Documents are stored only within your Docker volumes
- ✅ Rate limiting on all endpoints
- ✅ Input validation to prevent prompt injection
- ✅ Configurable file size limits
- ✅ HTTPS-ready via Nginx configuration

---

## 🛠️ Development

```bash
# Run tests
docker compose exec web python manage.py test

# Apply migrations
docker compose exec web python manage.py migrate

# View Celery worker logs
docker compose logs -f worker

# Shell access
docker compose exec web python manage.py shell
```

---

## 📦 Deployment (Production)

```bash
docker compose -f docker-compose.prod.yml up -d
```

Enable HTTPS by editing `nginx/nginx.conf` and adding your SSL certificates.

---

## 🗺️ Roadmap

- [ ] Support for Word (.docx), PowerPoint, and plain text files
- [ ] Multi-language document support
- [ ] Answer quality evaluation metrics
- [ ] Hybrid retrieval (local + optional external sources)
- [ ] GPU acceleration for faster inference
- [ ] User authentication & audit logging

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- [Ollama](https://ollama.ai/) for making local LLM inference accessible
- [FAISS](https://github.com/facebookresearch/faiss) by Meta AI Research
- [Hugging Face](https://huggingface.co/) for `sentence-transformers`
- [LangChain](https://langchain.com/) for RAG pipeline inspiration
