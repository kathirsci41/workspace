# On-Premises Deployment Plan: DPP 2.2.0
## RTX 4090 + Gemma4:E4B (Extraction + Chat with Vision)

---

## Executive Summary

**Goal:** Deploy DPP 2.2.0 on-premises with a 2-model architecture optimized for vision-capable chat and document extraction.

**Hardware:** NVIDIA RTX 4090 (24GB VRAM)  
**Models:**
- **Layer 1 (OCR):** glm-ocr (image → markdown)
- **Layer 2 (Extraction + Chat):** Gemma4:E4B (markdown → JSON + conversational AI with vision)

**Expected Performance:**
- Extraction: 28.4 sec/doc → 508 docs/hour (4 parallel workers)
- Chat: Real-time with vision capability (image upload support)
- Monthly volume: 500 documents in ~25-30 hours of processing

---

## Hardware Requirements

### Primary GPU (Production)
| Component | Specification | Cost |
|-----------|---------------|------|
| **GPU** | NVIDIA RTX 4090 | $2,000 |
| **Server CPU** | Intel Xeon W9-3495X or AMD EPYC 9654 | $5,000 |
| **System RAM** | 128GB DDR5 | $1,200 |
| **Storage (NVMe SSD)** | 2x 2TB RAID 1 | $400 |
| **Power Supply** | 1600W+ 80+ Platinum | $300 |
| **Cooling** | Liquid cooling for GPU | $500 |
| **Networking** | 10Gbps Ethernet | Built-in |
| **Chassis + Accessories** | Professional server case | $500 |
| **TOTAL HARDWARE** | | **~$10,000** |

### Network & Infrastructure
- **Firewall:** Configure for backend API only (port 8000 for FastAPI)
- **Backup:** Configure NVMe RAID 1 for automatic failover
- **Monitoring:** Prometheus + Grafana for GPU/CPU/Memory monitoring
- **Redundancy:** Optional second RTX 4090 for high availability (future)

---

## VRAM Allocation (RTX 4090 - 24GB)

```
GPU Memory Breakdown:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

glm-ocr (Layer 1):               4.5GB
├─ Loaded on demand
├─ Released after OCR complete
└─ Enables sequential pipeline

Gemma4:E4B (Layer 2):            6-7GB
├─ Always resident (extraction + chat)
├─ Handles both tasks
└─ Faster than model switching

Runtime buffer:                  2-3GB
├─ Python runtime
├─ Task queue management
└─ Safety margin for spikes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL USED:                      ~18GB / 24GB ✅
HEADROOM:                        6GB (safe margin)
```

### Memory Strategy
- **Sequential loading:** glm-ocr loads, unloads after OCR, then Gemma4:E4B processes
- **Parallel option:** Both models can be resident simultaneously (if OCR speed is critical)
- **Fallback:** If memory spikes, reduce Celery worker count from 4 to 2-3

---

## Two-Layer Extraction Pipeline

### Layer 1: OCR (glm-ocr)
```
PDF/Image Document
        ↓
    glm-ocr (4-5GB VRAM)
        ↓
    Markdown Text Output
        ↓
  [Saved temporarily]
```

**Performance:**
- Average: 15 sec/page
- Throughput: 240 pages/hour (single worker)

### Layer 2: Field Extraction (Gemma4:E4B)
```
Markdown Text
        ↓
   Gemma4:E4B (6-7GB VRAM)
   ├─ Reference number extraction
   ├─ Amount extraction
   ├─ Address extraction
   └─ Line items extraction
        ↓
   JSON Output
   {
     "reference_number": "...",
     "total_amount": 593701.66,
     "delivery_address": "...",
     "line_items": [...]
   }
```

**Performance:**
- Average: 13.4 sec/doc
- Accuracy: 89-91% field-level
- Confidence scores: Per-field confidence for validation

---

## Chat with Vision Capability

### Feature: Document Image Understanding
Users can upload document images directly in chat and ask questions:

```
User: [Uploads image of PO]
User: "What's the total amount and delivery address?"

Chat System (Gemma4:E4B):
├─ Receives image
├─ Extracts text and context
├─ Generates conversational response
└─ Returns: "The total amount is ₹593,701.66, 
            delivery to Hyderabad, India"
```

**Capabilities:**
- ✅ Upload invoice/PO/DC images
- ✅ Ask natural language questions
- ✅ Get structured information extracted
- ✅ Multi-turn conversation context
- ✅ Vision + text in single model

---

## Configuration Changes

### 1. Backend Model Configuration
**File:** `backend/app/config.py`

```python
# Change from:
EXTRACTION_MODEL = "gemma4:31b-cloud"  # Cloud API
OCR_ENDPOINT = "https://ienxiji82h8e7y-11434.proxy.runpod.net/"

# Change to:
EXTRACTION_MODEL = "gemma4:e4b"  # Local on-prem
OCR_ENDPOINT = "http://localhost:11434/"  # Local Ollama
CHAT_MODEL = "gemma4:e4b"  # Same model for chat (vision-capable)

# Add new settings:
ENABLE_VISION_CHAT = True
MAX_PARALLEL_EXTRACTIONS = 4  # Celery workers
ENABLE_CONFIDENCE_ESCALATION = True  # Flag low-confidence extractions
```

### 2. Environment Variables
**File:** `.env` (production)

```bash
# Model endpoints (local)
OLLAMA_ENDPOINT=http://localhost:11434
EXTRACTION_MODEL=gemma4:e4b
OCR_MODEL=glm-ocr
CHAT_MODEL=gemma4:e4b

# Performance tuning
CELERY_POOL_TYPE=prefork
CELERY_WORKER_COUNT=4
CELERY_WORKER_TIMEOUT=300

# Feature flags
ENABLE_VISION_CHAT=true
CONFIDENCE_THRESHOLD=0.85  # Escalate below this
```

### 3. Celery Configuration
**File:** `backend/app/celery_app.py`

```python
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/1',
    
    # Production pool (not solo)
    worker_pool='prefork',  # NOT 'solo'
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    
    # Parallel extraction (4 workers)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
```

### 4. Frontend Configuration
**File:** `frontend/src/config.ts`

```typescript
export const API_CONFIG = {
  baseURL: 'http://localhost:8000',  // Local backend
  extractionTimeout: 60000,  // 60 sec (vs 120 for cloud)
  chatVisionsEnabled: true,  // Enable image upload in chat
  maxImageUploadSize: 10 * 1024 * 1024,  // 10MB
};
```

---

## Deployment Checklist

### Phase 1: Hardware Setup (Week 1)
- [ ] Procure and install RTX 4090 GPU
- [ ] Install NVIDIA drivers (latest stable)
- [ ] Verify CUDA 11.8+ and cuDNN compatibility
- [ ] Install NVIDIA GPU Monitoring Tools (nvidia-smi, nvidia-docker)
- [ ] Stress test GPU with `nvidia-smi -pm 1` (persistence mode)
- [ ] Verify 24GB VRAM fully available (`nvidia-smi`)

### Phase 2: Software Stack (Week 1-2)
- [ ] Install Ollama on server (`https://ollama.ai/`)
- [ ] Pull glm-ocr model: `ollama pull glm-ocr`
- [ ] Pull gemma4:e4b model: `ollama pull gemma4:e4b`
- [ ] Install PostgreSQL 14+ (for document metadata)
- [ ] Install Redis (for Celery task queue)
- [ ] Install FastAPI backend dependencies
- [ ] Install Node.js + React frontend

### Phase 3: Backend Configuration (Week 2)
- [ ] Update `.env` with local Ollama endpoints
- [ ] Update `config.py` with production settings
- [ ] Configure Celery for `prefork` pool (4 workers)
- [ ] Run database migrations: `alembic upgrade head`
- [ ] Test backend connectivity to Ollama: `curl http://localhost:11434/api/tags`

### Phase 4: Testing (Week 2-3)
- [ ] **Unit tests:** Run full test suite
- [ ] **Integration tests:** Test OCR → Extraction pipeline
- [ ] **Load tests:** Simulate 4 parallel extractions
- [ ] **Chat tests:** Test vision capability with sample images
- [ ] **Stress tests:** Monitor GPU during peak load
- [ ] **Smoke tests:** End-to-end PO upload → extraction → display

### Phase 5: Monitoring & Optimization (Week 3)
- [ ] Install Prometheus (metrics collection)
- [ ] Set up Grafana dashboards:
  - GPU utilization (VRAM %)
  - Extraction throughput (docs/hour)
  - Extraction latency (sec/doc)
  - Chat response time
  - Queue depth
  - Error rate
- [ ] Configure alerts:
  - GPU > 90% VRAM (reduce workers)
  - Extraction > 60 sec (check for stuck tasks)
  - Chat unresponsive > 30 sec
- [ ] Performance baseline: Measure against benchmark (28.4 sec/doc target)

### Phase 6: Production Cutover (Week 3-4)
- [ ] Train operations team on monitoring
- [ ] Create runbooks for:
  - Model restart procedure
  - GPU out-of-memory recovery
  - Database backup/restore
  - Log collection and debugging
- [ ] Set up CI/CD for model updates
- [ ] Configure backup strategy (NVMe RAID 1)
- [ ] Final smoke test (5 documents end-to-end)
- [ ] Go-live: Switch from cloud gemma4:31b to local gemma4:e4b

---

## Performance Baseline

From benchmark results (31 documents, real Skylark collection):

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| **OCR (Layer 1)** | 15.0 sec/doc | <20 sec | ✅ Pass |
| **Extraction (Layer 2)** | 13.4 sec/doc | <15 sec | ✅ Pass |
| **Total pipeline** | 28.4 sec/doc | <35 sec | ✅ Pass |
| **Throughput** | 127 docs/hour | >100 docs/hour | ✅ Pass |
| **Parallel (4x)** | 508 docs/hour | >400 docs/hour | ✅ Pass |
| **Extraction accuracy** | 89-91% | >85% | ✅ Pass |
| **Chat vision** | ✅ Supported | Required | ✅ Pass |

---

## Cost Analysis (5-Year TCO)

| Item | Year 1 | Year 5 Total |
|------|--------|-------------|
| **Hardware** | $10,000 | $10,000 (one-time) |
| **Electricity** (24/7 operation) | $2,100/yr | $10,500 |
| **Maintenance** | $500/yr | $2,500 |
| **Total 5-Year Cost** | | **$23,000** |
| **Cost per document** (500/month) | $0.40 | $0.38 |

**vs. Cloud gemma4:31b-cloud:**
- **Annual cost:** $6,960 × 5 = **$34,800**
- **Savings:** $34,800 - $23,000 = **$11,800** (34% cheaper)

---

## Rollback Plan

If issues arise with Gemma4:E4B:

1. **Keep cloud gemma4:31b-cloud running in parallel** for first 2 weeks
2. **Compare results** side-by-side on production documents
3. **If accuracy gap > 5%:** Revert to cloud temporarily
4. **If performance inadequate:** Adjust Celery worker count (reduce to 2)
5. **If chat vision fails:** Fall back to qwen2.5:3b for chat only

---

## Next Steps

1. **Approve hardware procurement** ($10,000 budget)
2. **Schedule setup week** (3-4 weeks total timeline)
3. **Assign operations owner** (for monitoring/troubleshooting)
4. **Create production access plan** (firewall rules, credentials)
5. **Schedule final sign-off** (after smoke tests pass)

---

## Questions?

- **GPU alternatives?** RTX 4090 is recommended; RTX 6000 Ada (48GB) available for future scaling
- **Disaster recovery?** Add second RTX 4090 + model replication for HA
- **Model updates?** Ollama auto-updates available; schedule for off-hours
- **Support?** Ollama community support; Gemma4:E4B maintained by Google

