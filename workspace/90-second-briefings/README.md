# 90-Second Briefings
## AI-Curated News for Busy Professionals

Transform your information diet with intelligent, bite-sized briefings powered by hierarchical AI clones.

---

## 🚀 Quick Start

### Docker (Recommended)
```bash
# Clone and enter directory
git clone <repository-url>
cd 90-second-briefings

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Launch with Docker
./scripts/launch.sh --docker --demo
```

### Local Development
```bash
# Prerequisites: Python 3.8+, Redis
./scripts/launch.sh --demo
```

**Access Dashboard:** http://localhost:8000

---

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐
│  Senior Engineer │────│ Project Manager │
│     (Human)      │    │     Clone       │
└─────────────────┘    └─────────┬───────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
            ┌───────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
            │  Scraper   │ │Summarizer│ │  Audio  │ │Dashboard│
            │ Mini-Worker│ │Mini-Worker│ │Mini-Work│ │Mini-Work│
            └────────────┘ └─────────┘ └─────────┘ └─────────┘
```

### Core Components

1. **Project Manager Clone** - Autonomous orchestration
2. **Scraper Mini-Worker** - Web scraping + API integration  
3. **Summarizer Mini-Worker** - AI analysis with Claude Haiku
4. **Audio Mini-Worker** - TTS generation with OpenAI
5. **Dashboard Mini-Worker** - Delivery + web interface

---

## 🛡️ Cost & Safety Guardrails

### Budget Protection
- **£20/day total limit** with automatic shutdown
- **£5/worker individual limits** 
- Real-time cost tracking with alerts at 70%/90%/100%
- Emergency shutdown triggers

### Quality Controls
- Content validation and spam filtering
- Source credibility scoring (0.7+ minimum)
- Bias detection and sentiment analysis
- Human review checkpoints for core changes

### Monitoring & Logging
- Comprehensive activity logging (`activity.log`)
- Detailed cost tracking (`costs.log`)
- System health monitoring with alerts
- Error rate tracking and automatic retries

---

## 📊 Features

### Content Sources
- **News Sites:** TechCrunch, ArsTechnica, The Verge
- **Social Media:** Twitter/X, LinkedIn posts
- **RSS Feeds:** Automated discovery and parsing
- **Hacker News:** API integration for tech discussions

### AI Processing
- **Claude Haiku** for cost-effective summarization
- Topic clustering and sentiment analysis
- Quality scoring and bias detection
- Multi-format output generation

### Delivery Options
- **Email Digests:** HTML + text versions with templates
- **Notion Export:** Structured page creation
- **RSS/Podcast Feeds:** Audio briefings with TTS
- **Web Dashboard:** Real-time monitoring and analytics

### Premium Features
- Daily/weekly briefing frequencies
- Custom voice profiles for audio
- Notion workspace integration
- Webhook notifications
- Export to multiple formats

---

## ⚙️ Configuration

### Environment Variables (.env)
```bash
# Required API Keys
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Optional Services
TWITTER_BEARER_TOKEN=optional
NOTION_INTEGRATION_TOKEN=optional
AWS_ACCESS_KEY_ID=for_audio_hosting
AWS_SECRET_ACCESS_KEY=for_audio_hosting

# Email Configuration
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
FROM_EMAIL=briefings@yoursite.com

# System Limits
DAILY_COST_LIMIT=20.0
```

### Supported Niches
- **Tech:** AI, startups, software development
- **Finance:** Markets, fintech, economic news  
- **Healthcare:** Medical tech, pharma, biotech
- **Custom:** Define your own keyword filters

---

## 🎯 Usage Examples

### Generate Daily Tech Briefing
```bash
# Via Project Manager
python -m core.project_manager --create-project tech daily

# Via CLI
python -m scraper.scraper_worker --url "https://techcrunch.com" --niche tech
```

### Monitor System Health
```bash
# System status
python -m core.system_monitor --status

# Cost summary
python -m core.cost_tracker --summary

# Worker health
python -m core.mini_worker --health-check
```

### Create Custom Briefing
```python
from core.project_manager import ProjectManagerClone

pm = ProjectManagerClone()
project_id = await pm.create_briefing_project(
    niche="startup",
    frequency="weekly", 
    custom_sources=["https://techcrunch.com/startups/"]
)
```

---

## 📈 Monitoring & Analytics

### Web Dashboard (http://localhost:8000)
- Real-time system status
- Cost tracking and budget utilization
- Worker performance metrics
- Generated briefing archive
- Subscriber management

### Log Analysis
```bash
# View recent activity
tail -f activity.log

# Cost breakdown
grep "COST_EVENT" costs.log | tail -20

# System alerts
grep "ALERT" system_monitor.log
```

### API Health Checks
```bash
curl http://localhost:8000/health
curl http://localhost:8001/api/status
```

---

## 🚨 Emergency Procedures

### Automatic Shutdowns
The system automatically shuts down when:
- Daily cost limit exceeded (£20)
- Worker cost limit exceeded (£5)  
- Critical system errors detected
- Emergency alert conditions met

### Manual Controls
```bash
# Graceful shutdown
./scripts/stop.sh --backup

# Emergency stop
touch EMERGENCY_SHUTDOWN

# Pause non-essential workers
touch PAUSE_NON_ESSENTIAL
```

### Recovery Procedures
```bash
# Check shutdown reason
cat shutdown_report.txt

# Restart after issue resolution
./scripts/launch.sh --docker

# Reset daily costs (new day)
rm data/costs/costs_$(date +%Y%m%d).json
```

---

## 🏆 Production Deployment

### AWS/Cloud Deployment
```bash
# Docker production mode
docker-compose -f docker-compose.prod.yml up -d

# With load balancer
docker-compose -f docker-compose.prod.yml -f docker-compose.lb.yml up -d
```

### Scaling Configuration
- Horizontal worker scaling via Docker replicas
- Redis cluster for distributed task queue
- S3 for audio file hosting and storage
- CloudWatch for monitoring and alerting

### Security Hardening
- API key rotation and secure storage
- Rate limiting and request validation
- Content security policies
- Access logging and audit trails

---

## 📚 Documentation

### API Reference
- **Project Manager:** `/docs/project_manager.md`
- **Workers:** `/docs/workers/`
- **Cost Tracking:** `/docs/cost_tracking.md`
- **Deployment:** `/docs/deployment.md`

### Development Guide
- **Architecture:** `/ARCHITECTURE.md`
- **Contributing:** `/CONTRIBUTING.md`
- **Testing:** `pytest tests/`

---

## 🤝 Support & Community

### Getting Help
- **Issues:** GitHub Issues for bugs and feature requests
- **Discussions:** GitHub Discussions for questions
- **Documentation:** Check `/docs/` directory

### Contributing
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Run tests: `pytest tests/`
4. Submit pull request

### License
MIT License - see `LICENSE` file for details

---

## 🎯 Success Metrics

### System Performance
- **Uptime:** >99% availability target
- **Cost Efficiency:** <£20/day for comprehensive coverage
- **Quality Score:** >85% average credibility rating
- **Processing Speed:** <5 minutes end-to-end briefing generation

### Content Metrics
- **Source Coverage:** 50+ sources across niches
- **Briefing Quality:** 90-second optimal reading time
- **User Engagement:** Email open rates >40%
- **Content Freshness:** <6 hours average age

---

**🤖 Generated by Claude Senior Engineer | Powered by Mini-Claude Workers**

*Transform information overload into actionable intelligence.*