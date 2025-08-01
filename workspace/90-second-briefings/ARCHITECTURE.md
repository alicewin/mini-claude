# 90-Second Briefings - System Architecture

## 🎯 **Mission Overview**
Autonomous AI-powered news curation platform that delivers concise, high-signal briefings for busy professionals.

## 🏗️ **Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLAUDE SENIOR ENGINEER                              │
│                      (Orchestration & Quality Control)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────────────────┐   │
│  │ Project Manager │    │           Task Queue System                 │   │
│  │     Clone       │───▶│        (Redis + SQLite)                     │   │
│  │                 │    │                                             │   │
│  └─────────────────┘    └─────────────────────────────────────────────┘   │
│           │                                    │                           │
│           ▼                                    ▼                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MINI-WORKER FLEET                                │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Worker #1   │  │  Worker #2   │  │  Worker #3   │              │   │
│  │  │   Scraper    │  │ Summarizer   │  │   Audio      │              │   │
│  │  │              │  │              │  │  Narrator    │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                     │   │
│  │  ┌──────────────┐                                                   │   │
│  │  │  Worker #4   │                                                   │   │
│  │  │  Dashboard   │                                                   │   │
│  │  │   & Export   │                                                   │   │
│  │  └──────────────┘                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   News APIs │  │   Twitter   │  │  LinkedIn   │  │   Tech      │       │
│  │             │  │     API     │  │    API      │  │   Blogs     │       │
│  │• Reuters    │  │             │  │             │  │             │       │
│  │• NewsAPI    │  │             │  │             │  │• TechCrunch │       │
│  │• Guardian   │  │             │  │             │  │• Ars Tech   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT CHANNELS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Email     │  │   Notion    │  │     RSS     │  │   Audio     │       │
│  │   Digest    │  │   Export    │  │    Feed     │  │  Podcast    │       │
│  │             │  │             │  │             │  │             │       │
│  │• Daily      │  │• Page       │  │• Private    │  │• TTS        │       │
│  │• Weekly     │  │• Database   │  │• Custom     │  │• Premium    │       │
│  │• Custom     │  │• Templates  │  │• Topics     │  │• Features   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🤖 **Clone Hierarchy**

### **Claude Senior Engineer** (Controller)
- **Role**: System architect, quality control, cost management
- **Responsibilities**:
  - Deploy and manage Project Manager Clone
  - Oversee 4 Mini-Workers
  - Review all deliverables before merge
  - Monitor costs and enforce guardrails
  - Generate final briefings

### **Project Manager Clone** (Coordinator)
- **Role**: Task orchestration and worker management
- **Responsibilities**:
  - Break down high-level goals into worker tasks
  - Schedule and prioritize work across Mini-Workers
  - Monitor progress and handle failures
  - Report status to Claude Senior

### **Mini-Worker Fleet** (Executors)
- **Worker #1 - Scraper Specialist**:
  - Web scraping (news sites, blogs)
  - API integration (NewsAPI, Twitter, LinkedIn)
  - Data cleaning and validation
  - Rate limiting and error handling

- **Worker #2 - Summarization Specialist**:
  - AI summarization using Claude Haiku
  - Sentiment analysis and scoring
  - Topic classification and tagging
  - Content deduplication

- **Worker #3 - Audio Specialist**:
  - Text-to-speech generation
  - Audio file processing and hosting
  - Podcast RSS feed generation
  - Voice selection and quality control

- **Worker #4 - Dashboard Specialist**:
  - Web dashboard development (Streamlit)
  - Email digest generation and sending
  - Notion integration and export
  - User management and analytics

## 📊 **Data Flow**

```
1. PROJECT MANAGER schedules scraping tasks
2. SCRAPER WORKER collects news from sources
3. SUMMARIZER WORKER processes content → briefings
4. AUDIO WORKER generates narration (premium)
5. DASHBOARD WORKER delivers via email/Notion/RSS
6. CLAUDE SENIOR audits and approves final output
```

## 🔒 **Security & Guardrails**

### **Cost Controls**
- **Daily Budget**: £20/day per Mini-Worker (£80 total)
- **Token Limits**: Claude Haiku for efficiency
- **Rate Limiting**: API calls throttled per source
- **Auto-shutdown**: Emergency stop if budget exceeded

### **Quality Controls**
- **Content Validation**: Factual accuracy checks
- **Bias Detection**: Political neutrality enforcement
- **Source Verification**: Trusted source whitelist
- **Output Review**: Claude Senior approval required

### **Technical Safeguards**
- **Sandboxed Execution**: Isolated worker environments
- **Error Handling**: Graceful degradation on failures
- **Data Privacy**: No personal data collection
- **Audit Logging**: Complete activity tracking

## 🎯 **MVP Scope (2 Weeks)**

### **Week 1: Core Pipeline**
- **Days 1-3**: Scraper + API integrations
- **Days 4-7**: Summarization + basic briefings

### **Week 2: Delivery & Polish**
- **Days 8-10**: Email + Notion export
- **Days 11-14**: Dashboard + audio (premium)

## 💰 **Monetization Strategy**

### **Free Tier**
- 1 briefing/week
- Tech/startup niche only
- Email delivery only
- Community-sourced content

### **Premium Tier (£20-50/month)**
- Daily briefings
- Custom topics/industries
- Audio narration
- Notion integration
- Early access (6 AM delivery)
- Multiple formats (email, RSS, audio)

## 📈 **Scaling Plan**

### **Phase 1 (MVP)**: Single niche (tech/startup)
### **Phase 2 (Month 2)**: Multi-niche (finance, healthcare, etc.)
### **Phase 3 (Month 3)**: Custom enterprise briefings
### **Phase 4 (Month 6)**: AI-powered research reports

## 🔧 **Technology Stack**

- **Backend**: Python 3.11, FastAPI, Redis, SQLite
- **AI/ML**: Anthropic Claude (Haiku/Sonnet), OpenAI TTS
- **Scraping**: BeautifulSoup, Scrapy, Selenium
- **Frontend**: Streamlit (MVP), Next.js (future)
- **Email**: SendGrid, Mailgun
- **Audio**: OpenAI TTS, AWS S3 hosting
- **Integration**: Notion API, RSS generation
- **Deployment**: Docker, AWS/Railway/Render
- **Monitoring**: Prometheus, Grafana

## 📋 **Success Metrics**

### **Technical KPIs**
- **Uptime**: >99% availability
- **Latency**: <2s briefing generation
- **Accuracy**: >95% fact-check score
- **Coverage**: 50+ sources per niche

### **Business KPIs**
- **User Engagement**: >80% open rate
- **Content Quality**: >4.5/5 user rating
- **Conversion**: >10% free → premium
- **Retention**: >70% monthly active users

---

**System designed for autonomous operation with human oversight at strategic decision points.**