# Falco
## Production-Ready Agentic RAG System

<div align="center">
  <h3>A Complete, Production-Grade Retrieval-Augmented Generation System for Academic Research</h3>
  <p>From infrastructure to intelligent agents — everything you need to build and deploy a modern RAG pipeline</p>
  <p>Powered by <strong>Agentic RAG (Retrieval-Augmented Generation)</strong> with LangGraph</p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/OpenSearch-2.19-orange.svg" alt="OpenSearch">
  <img src="https://img.shields.io/badge/Docker-Compose-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg" alt="Status">
</p>

</br>

<p align="center">
  <a href="#-about">
    <img src="static/mother_of_ai_project_rag_architecture.gif" alt="RAG Architecture" width="700">
  </a>
</p>

## 📖 About

The **Falco** is a **production-grade Agentic RAG system** that automatically fetches academic papers, understands their content, and answers research questions using advanced retrieval and generation techniques.

Unlike simple RAG implementations that jump straight to vector search, this system follows the **professional approach**: solid keyword search foundations enhanced with semantic vectors for hybrid retrieval, intelligent agents for adaptive decision-making, and full production monitoring.

> **The Professional Difference:** Built the way successful companies do — solid search foundations enhanced with AI, not AI-first approaches that ignore search fundamentals.

This is a complete, deployable source code with modular architecture — ready for customization and production deployment in any domain.

### **Key Features**

- **Module 1 — Infrastructure:** Docker, FastAPI, PostgreSQL, OpenSearch, and Airflow orchestration
- **Module 2 — Data Pipeline:** Automated fetching and parsing of academic papers from arXiv  
- **Module 3 — Keyword Search:** Production BM25 search with filtering and relevance scoring
- **Module 4 — Hybrid Search:** Intelligent chunking + hybrid retrieval combining keywords with semantic understanding
- **Module 5 — RAG Pipeline:** Complete RAG with local LLM, streaming responses, and Gradio interface
- **Module 6 — Production Monitoring:** Langfuse tracing and Redis caching for optimized performance
- **Module 7 — Agentic RAG:** Intelligent agents with LangGraph and Telegram Bot for mobile access

---

## 🏗️ System Architecture

### Agentic RAG & Telegram Bot Integration
<div align="center">
  <img src="static/week7_telegram_and_agentic_ai.png" alt="Telegram and Agentic AI Architecture" width="800">
  <p><em>Complete architecture showing Telegram bot integration with the agentic RAG system</em></p>
</div>

### LangGraph Agentic RAG Workflow
<div align="center">
  <img src="static/langgraph-mermaid.png" alt="LangGraph Agentic RAG Flow" width="800">
  <p><em>Detailed LangGraph workflow showing decision nodes, document grading, and adaptive retrieval</em></p>
</div>

**Blog Post:** [Agentic RAG with LangGraph and Telegram](https://erfanfalco.substack.com/p/agentic-rag-with-langgraph-and-telegram) 

**Key Capabilities:**
- **Intelligent Decision-Making**: Agents evaluate and adapt retrieval strategies
- **Document Grading**: Automatic relevance assessment with semantic evaluation
- **Query Rewriting**: Adaptive query refinement when results are insufficient
- **Guardrails**: Out-of-domain detection prevents hallucination
- **Mobile Access**: Telegram bot for conversational AI on any device
- **Transparency**: Full reasoning step tracking for debugging and trust

---

## 🚀 Quick Start

### **📋 Prerequisites**
- **Docker Desktop** (with Docker Compose)  
- **Python 3.12+**
- **UV Package Manager** ([Install Guide](https://docs.astral.sh/uv/getting-started/installation/))
- **8GB+ RAM** and **20GB+ free disk space**

### **⚡ Get Started**

```bash
# 1. Clone and setup
git clone <repository-url>
cd falco

# 2. Configure environment (IMPORTANT!)
cp .env.example .env
# The .env file contains all necessary configuration for OpenSearch, 
# arXiv API, and service connections. Defaults work out of the box.
# You need to add Jina embeddings free api key and langfuse keys (check the docs)

# 3. Install dependencies
uv sync

# 4. Start all services
docker compose up --build -d

# 5. Verify everything works
curl http://localhost:8000/health
```

### **📊 Access Your Services**

| Service | URL | Purpose |
|---------|-----|---------|
| **API Documentation** | http://localhost:8000/docs | Interactive API testing |
| **Gradio RAG Interface** | http://localhost:7861 | User-friendly chat interface |
| **Langfuse Dashboard** | http://localhost:3000 | RAG pipeline monitoring & tracing |
| **Airflow Dashboard** | http://localhost:8080 | Workflow management |
| **OpenSearch Dashboards** | http://localhost:5601 | Hybrid search engine UI |

#### **NOTE**: Check airflow/simple_auth_manager_passwords.json.generated for Airflow username and password

---

## 📦 Modular Architecture

The system is built as 7 incremental modules. Each module adds a new capability layer while preserving backward compatibility.

### **Release History**

| Module | Component | Blog Post | Release Tag |
|--------|-----------|-----------|-------------|
| **Module 0** | Project Overview | [Project Overview](https://erfanfalco.substack.com/p/falco-project-overview) | - |
| **Module 1** | Infrastructure Foundation | [The Infrastructure That Powers RAG](https://erfanfalco.substack.com/p/the-infrastructure-that-powers-rag) | [v1.0](https://github.com/erfanfalco/falco/releases/tag/week1.0) |
| **Module 2** | Data Ingestion Pipeline | [Building Data Ingestion Pipelines](https://erfanfalco.substack.com/p/bringing-your-rag-system-to-life) | [v2.0](https://github.com/erfanfalco/falco/releases/tag/week2.0) |
| **Module 3** | OpenSearch & BM25 Retrieval | [The Search Foundation Every RAG System Needs](https://erfanfalco.substack.com/p/the-search-foundation-every-rag-system) | [v3.0](https://github.com/erfanfalco/falco/releases/tag/week3.0) |
| **Module 4** | Chunking & Hybrid Search | [Chunking Strategy for Hybrid Search](https://erfanfalco.substack.com/p/chunking-strategies-and-hybrid-rag) | [v4.0](https://github.com/erfanfalco/falco/releases/tag/week4.0) |
| **Module 5** | Complete RAG System | [The Complete RAG System](https://erfanfalco.substack.com/p/the-complete-rag-system) | [v5.0](https://github.com/erfanfalco/falco/releases/tag/week5.0) |
| **Module 6** | Production Monitoring & Caching | [Production-ready RAG: Monitoring & Caching](https://erfanfalco.substack.com/p/production-ready-rag-monitoring-and) | [v6.0](https://github.com/erfanfalco/falco/releases/tag/week6.0) |
| **Module 7** | Agentic RAG & Telegram Bot | [Agentic RAG with LangGraph](https://erfanfalco.substack.com/p/agentic-rag-with-langgraph-and-telegram) | [v7.0](https://github.com/erfanfalco/falco/releases/tag/week7.0) |

**📥 Clone a specific release:**
```bash
git clone --branch <TAG> https://github.com/erfanfalco/falco
cd falco
uv sync
docker compose down -v
docker compose up --build -d

# Replace <TAG> with: week1.0, week2.0, etc.
```

---

## 📚 Module 1: Infrastructure Foundation

Set up the production infrastructure stack.

### **Key Capabilities**
- Complete infrastructure setup with Docker Compose
- FastAPI development with automatic documentation and health checks
- PostgreSQL database configuration and management
- OpenSearch hybrid search engine setup
- Ollama local LLM service configuration
- Service orchestration and health monitoring
- Professional development environment with code quality tools

### **Architecture Overview**

<p align="center">
  <img src="static/week1_infra_setup.png" alt="Infrastructure Setup" width="800">
</p>

**Infrastructure Components:**
- **FastAPI**: REST endpoints with async support (Port 8000)  
- **PostgreSQL 16**: Paper metadata storage (Port 5432)
- **OpenSearch 2.19**: Search engine with dashboards (Ports 9200, 5601)
- **Apache Airflow 3.0**: Workflow orchestration (Port 8080)
- **Ollama**: Local LLM server (Port 11434)

### **Setup Guide**

```bash
uv run jupyter notebook notebooks/week1/week1_setup.ipynb
```

Follow the [Module 1 notebook](notebooks/week1/week1_setup.ipynb) for setup and verification steps.

**Blog Post:** [The Infrastructure That Powers RAG Systems](https://erfanfalco.substack.com/p/the-infrastructure-that-powers-rag)

---

## 📚 Module 2: Data Ingestion Pipeline

Automated fetching, processing, and storage of academic papers.

### **Key Capabilities**
- arXiv API integration with rate limiting and retry logic
- Scientific PDF parsing using Docling
- Automated data ingestion pipelines with Apache Airflow
- Metadata extraction and storage workflows
- Complete paper processing from API to database

### **Architecture Overview**

<p align="center">
  <img src="static/week2_data_ingestion_flow.png" alt="Data Ingestion Architecture" width="800">
</p>

**Data Pipeline Components:**
- **MetadataFetcher**: Main orchestrator coordinating the entire pipeline
- **ArxivClient**: Rate-limited paper fetching with retry logic
- **PDFParserService**: Docling-powered scientific document processing  
- **Airflow DAGs**: Automated daily paper ingestion workflows
- **PostgreSQL Storage**: Structured paper metadata and content

### **Setup Guide**

```bash
uv run jupyter notebook notebooks/week2/week2_arxiv_integration.ipynb
```

Follow the [Module 2 notebook](notebooks/week2/week2_arxiv_integration.ipynb) for implementation and verification steps.

**Blog Post:** [Building Data Ingestion Pipelines for RAG](https://erfanfalco.substack.com/p/bringing-your-rag-system-to-life)

---

## 📚 Module 3: Keyword Search — The Critical Foundation

Production BM25 keyword search that professional RAG systems rely on.

### **Key Capabilities**
- Why keyword search is essential for RAG systems (foundation-first approach)
- OpenSearch index management, mappings, and search optimization
- BM25 algorithm and effective keyword search
- Query DSL for building complex search queries with filters and boosting
- Search analytics for measuring relevance and performance
- Production patterns used by real companies

### **Architecture Overview**

<p align="center">
  <img src="static/week3_opensearch_flow.png" alt="OpenSearch Flow Architecture" width="800">
</p>

**Search Infrastructure Components:**
- **OpenSearch Service**: `src/services/opensearch/` — Professional search service implementation
- **Search API**: `src/routers/search.py` — Search API endpoints with BM25 scoring
- **Documentation**: `notebooks/week3/` — Complete OpenSearch integration guide
- **Quality Metrics**: Precision, recall, and relevance scoring

### **Setup Guide**

```bash
uv run jupyter notebook notebooks/week3/week3_opensearch.ipynb
```

Follow the [Module 3 notebook](notebooks/week3/week3_opensearch.ipynb) for OpenSearch setup and BM25 search implementation.

**Blog Post:** [The Search Foundation Every RAG System Needs](https://erfanfalco.substack.com/p/the-search-foundation-every-rag-system)

---

## 📚 Module 4: Chunking & Hybrid Search — The Semantic Layer

Adds the semantic layer that makes search truly intelligent.

### **Key Capabilities**
- Section-based chunking with intelligent document segmentation
- Production embeddings with Jina AI integration and fallback strategies
- Hybrid search mastery using RRF fusion for keyword + semantic retrieval
- Unified API design with single endpoint supporting multiple search modes
- Performance analysis and trade-offs between search approaches

### **Architecture Overview**

<p align="center">
  <img src="static/week4_hybrid_opensearch.png" alt="Hybrid Search Architecture" width="800">
</p>

**Hybrid Search Infrastructure Components:**
- **Text Chunker**: `src/services/indexing/text_chunker.py` — Section-aware chunking with overlap strategies
- **Embeddings Service**: `src/services/embeddings/` — Production embedding pipeline with Jina AI
- **Hybrid Search API**: `src/routers/hybrid_search.py` — Unified search API supporting all modes
- **Documentation**: `notebooks/week4/` — Complete hybrid search implementation guide

### **Setup Guide**

```bash
uv run jupyter notebook notebooks/week4/week4_hybrid_search.ipynb
```

Follow the [Module 4 notebook](notebooks/week4/week4_hybrid_search.ipynb) for implementation and verification steps.

**Blog Post:** [The Chunking Strategy That Makes Hybrid Search Work](https://erfanfalco.substack.com/p/chunking-strategies-and-hybrid-rag)

---

## 📚 Module 5: Complete RAG Pipeline with LLM Integration

Adds the LLM layer that turns search into intelligent conversation.

### **Key Capabilities**
- Local LLM integration with Ollama for complete data privacy
- Performance optimization with 80% prompt reduction (6x speed improvement)
- Streaming implementation using Server-Sent Events for real-time responses
- Dual API design with standard and streaming endpoints
- Interactive Gradio interface with advanced parameter controls

### **Architecture Overview**

<p align="center">
  <img src="static/week5_complete_rag.png" alt="Complete RAG System Architecture" width="900">
</p>

**Complete RAG Infrastructure Components:**
- **RAG Endpoints**: `src/routers/ask.py` — Dual endpoints (`/api/v1/ask` + `/api/v1/stream`)
- **Ollama Service**: `src/services/ollama/` — LLM client with optimized prompts
- **System Prompt**: `src/services/ollama/prompts/rag_system.txt` — Optimized for academic papers
- **Gradio Interface**: `src/gradio_app.py` — Interactive web UI with streaming support
- **Launcher Script**: `gradio_launcher.py` — Easy-launch script (runs on port 7861)

### **Setup Guide**

```bash
# Launch the Module 5 notebook
uv run jupyter notebook notebooks/week5/week5_complete_rag_system.ipynb

# Launch Gradio interface
uv run python gradio_launcher.py
# Open http://localhost:7861
```

Follow the [Module 5 notebook](notebooks/week5/week5_complete_rag_system.ipynb) for LLM integration and RAG pipeline implementation.

**Blog Post:** [The Complete RAG System](https://erfanfalco.substack.com/p/the-complete-rag-system)

---

## 📚 Module 6: Production Monitoring and Caching

Adds observability, performance optimization, and production-grade monitoring.

### **Key Capabilities**
- Langfuse integration for end-to-end RAG pipeline tracing
- Redis caching strategy with intelligent cache keys and TTL management
- Performance monitoring with real-time dashboards for latency and costs
- Production patterns for observability and optimization
- Cost analysis and LLM usage optimization (150-400x speedup with caching)

### **Architecture Overview**

<p align="center">
  <img src="static/week6_monitoring_and_caching.png" alt="Monitoring & Caching Architecture" width="900">
</p>

**Production Infrastructure Components:**
- **Langfuse Service**: `src/services/langfuse/` — Complete tracing integration with RAG-specific metrics
- **Cache Service**: `src/services/cache/` — Redis client with exact-match caching and graceful fallback
- **Updated Endpoints**: `src/routers/ask.py` — Integrated tracing and caching middleware
- **Docker Config**: `docker-compose.yml` — Added Redis service and Langfuse local instance
- **Documentation**: `notebooks/week6/` — Complete monitoring and caching implementation guide

### **Setup Guide**

```bash
uv run jupyter notebook notebooks/week6/week6_cache_testing.ipynb
```

Follow the [Module 6 notebook](notebooks/week6/week6_cache_testing.ipynb) for Langfuse tracing and Redis caching implementation.

**Blog Post:** [Production-ready RAG: Monitoring & Caching](https://erfanfalco.substack.com/p/production-ready-rag-monitoring-and)

---

## 📚 Module 7: Agentic RAG with LangGraph and Telegram Bot

Adds intelligent reasoning, multi-step decision-making, and Telegram bot integration for mobile-first AI interactions.

### **Key Capabilities**
- LangGraph workflows for state-based agent orchestration with decision nodes
- Guardrail implementation for query validation and domain boundary detection
- Document grading with semantic relevance evaluation
- Query rewriting for automatic query refinement and better retrieval
- Adaptive retrieval with multi-attempt retrieval and intelligent fallback
- Telegram bot integration with async operations and error handling
- Reasoning transparency by exposing agent decision-making process

### **Architecture Overview**

<p align="center">
  <img src="static/week7_telegram_and_agentic_ai.png" alt="Agentic RAG & Telegram Architecture" width="900">
</p>

**Agentic RAG Infrastructure Components:**
- **Agent Nodes**: `src/services/agents/nodes/` — Guardrail, retrieve, grade, rewrite, and generate nodes
- **Workflow Orchestration**: `src/services/agents/agentic_rag.py` — LangGraph workflow coordination
- **Telegram Bot**: `src/services/telegram/` — Command handlers and message processing
- **Agentic Endpoint**: `src/routers/agentic_ask.py` — Agentic RAG API endpoint
- **Documentation**: `notebooks/week7/` — Module 7 examples and reference

### **Setup Guide**

```bash
uv run jupyter notebook notebooks/week7/week7_agentic_rag.ipynb
```

Follow the [Module 7 notebook](notebooks/week7/week7_agentic_rag.ipynb) for LangGraph agentic RAG and Telegram bot implementation.

**Blog Post:** [Agentic RAG with LangGraph and Telegram](https://erfanfalco.substack.com/p/agentic-rag-with-langgraph-and-telegram)

---

## ⚙️ Configuration

**Setup:**
```bash
cp .env.example .env
# Edit .env for your environment
```

**Key Variables:**
- `JINA_API_KEY` — Required for Module 4+ (hybrid search with embeddings)
- `TELEGRAM__BOT_TOKEN` — Required for Module 7 (Telegram bot integration)
- `LANGFUSE__PUBLIC_KEY` & `LANGFUSE__SECRET_KEY` — Optional for Module 6 (monitoring)

**Complete Configuration:** See [.env.example](.env.example) for all available options and detailed documentation.

---

## 🔧 Reference & Development Guide

### **🛠️ Technology Stack**

| Service | Purpose | Status |
|---------|---------|--------|
| **FastAPI** | REST API with automatic docs | ✅ Ready |
| **PostgreSQL 16** | Paper metadata and content storage | ✅ Ready |
| **OpenSearch 2.19** | Hybrid search engine (BM25 + Vector) | ✅ Ready |
| **Apache Airflow 3.0** | Workflow automation | ✅ Ready |
| **Jina AI** | Embedding generation | ✅ Ready |
| **Ollama** | Local LLM serving | ✅ Ready |
| **Redis** | High-performance caching | ✅ Ready |
| **Langfuse** | RAG pipeline observability | ✅ Ready |
| **LangGraph** | Agentic workflow orchestration | ✅ Ready |
| **Telegram Bot** | Mobile-first conversational interface | ✅ Ready |

**Development Tools:** UV, Ruff, MyPy, Pytest, Docker Compose

### **🏗️ Project Structure**

```
falco/
├── src/                    # Main application code
│   ├── routers/            # API endpoints (search, ask, agentic, papers)
│   ├── services/           # Business logic (opensearch, ollama, agents, cache, telegram)
│   ├── models/             # Database models (SQLAlchemy)
│   ├── schemas/            # Pydantic validation schemas
│   └── config.py           # Environment configuration
├── notebooks/              # Implementation guides and examples (modules 1-7)
├── airflow/                # Workflow orchestration (DAGs)
├── tests/                  # Test suite
└── compose.yml             # Docker service orchestration
```

### **📡 API Endpoints Reference**

| Endpoint | Method | Description | Module |
|----------|--------|-------------|--------|
| `/health` | GET | Service health check | 1 |
| `/api/v1/papers` | GET | List stored papers | 2 |
| `/api/v1/papers/{id}` | GET | Get specific paper | 2 |
| `/api/v1/search` | POST | BM25 keyword search | 3 |
| `/api/v1/hybrid-search/` | POST | Hybrid search (BM25 + Vector) | 4 |
| `/api/v1/ask` | POST | RAG question answering | 5 |
| `/api/v1/stream` | POST | Streaming RAG responses | 5 |
| `/api/v1/ask-agentic` | POST | Agentic RAG with reasoning | 7 |

**API Documentation:** Visit http://localhost:8000/docs for interactive API explorer

### **🔧 Essential Commands**

#### **Using the Makefile** (Recommended)
```bash
make help         # View all available commands
make start        # Start all services
make health       # Check all services health
make test         # Run tests
make stop         # Stop services
```

#### **All Available Commands**
| Command | Description |
|---------|-------------|
| `make start` | Start all services |
| `make stop` | Stop all services |
| `make restart` | Restart all services |
| `make status` | Show service status |
| `make logs` | Show service logs |
| `make health` | Check all services health |
| `make setup` | Install Python dependencies |
| `make format` | Format code |
| `make lint` | Lint and type check |
| `make test` | Run tests |
| `make test-cov` | Run tests with coverage |
| `make clean` | Clean up everything |

#### **Direct Commands** (Alternative)
```bash
docker compose up --build -d    # Start services
docker compose ps               # Check status
docker compose logs             # View logs
uv run pytest                   # Run tests
```

### **🎯 Who Is This For?**
| Who | Why |
|-----|-----|
| **AI/ML Engineers** | Production RAG architecture beyond prototypes |
| **Software Engineers** | End-to-end AI application with best practices |
| **Data Scientists** | Production AI systems using modern tools |
| **Technical Founders** | Ready-to-deploy RAG solution for any domain |

---

## 🛠️ Troubleshooting

**Common Issues:**
- **Services not starting?** Wait 2-3 minutes, check `docker compose logs`
- **Port conflicts?** Stop other services using ports 8000, 8080, 5432, 9200
- **Memory issues?** Increase Docker Desktop memory allocation

**Get Help:**
- Check the Module 1 notebook troubleshooting section
- Review service logs: `docker compose logs [service-name]`
- Complete reset: `docker compose down --volumes && docker compose up --build -d`

---

## 💰 Cost

- **Local Development:** $0 (everything runs locally with Ollama)
- **Optional Cloud APIs:** ~$2-5 for external embedding/LLM services (if chosen)

---

<div align="center">
  <h3>Ready to Deploy Your Agentic RAG System?</h3>
  <p><strong>Start with Module 1 and have a production RAG system running in hours.</strong></p>
  
  <p><strong>Built by Erfan Falco</strong></p>
</div>

---

## 👨‍💻 Author

**Erfan Falco** — AI Engineer & Developer

- GitHub: [@erfanfalco](https://github.com/erfanfalco)

---

## 📄 License

MIT License - Copyright (c) 2025 Erfan Falco. See [LICENSE](LICENSE) file for details.
