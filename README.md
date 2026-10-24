# 🏥 MedGuard AI

**Multi-Agent Healthcare Data Validator with Privacy-Preserving Intelligence**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hackathon: Convergence 2026](https://img.shields.io/badge/Hackathon-Convergence%202026-green.svg)](https://github.com/Varsh1009/meddata-guardian)

---

> **Implementation status:** The active dashboard audits original records. Performance gaps,
> patient harm, and accuracy improvements are not measured. Other legacy privacy and fairness
> claims below are under review; see [the implementation backlog](docs/IMPLEMENTATION_PLAN.md).

## 📋 Overview

MedGuard AI is an intelligent healthcare data quality and fairness auditor that detects data quality issues and demographic bias **before** AI models are trained, preventing biased algorithms from harming patients.

**The Problem:** Medical AI systems often exhibit significant performance disparities across demographic groups, discovered only after deployment when patients are already harmed. Example: Apple Watch ECG algorithm was 34% less accurate for Black patients after 2 years of deployment.

**Our Solution:** Multi-agent AI system that analyzes datasets in 30 seconds, providing exact, actionable recommendations with HIPAA-compliant privacy-preserving architecture.

---

## 🎯 Key Features

### **1. Privacy-Preserving Synthetic Data Layer**
- Generates statistical twins of real datasets
- AI agents analyze synthetic data only (HIPAA-safe)
- Zero exposure of Protected Health Information
- Industry-standard synthetic data generation

### **2. Multi-Agent AI System**
- **Medical Advisor Agent:** Clinical context from medical literature (RAG)
- **Fairness Specialist Agent:** Exact bias quantification and mitigation strategies
- **Deployment Strategist Agent:** Week-by-week implementation roadmaps

### **3. Exact Quantification (Not Vague Advice)**
- "Recruit 552 female patients" (not "get more data")
- Model performance and patient harm are **not measured** from dataset representation.
- "$60,000 recruitment cost, 6-month timeline" (not "expensive, takes time")

### **4. Three-Layer HIPAA Compliance**
- **Layer 1:** Pre-flight PHI scanner (rejects before loading)
- **Layer 2:** Synthetic data firewall (AI never sees real patients)
- **Layer 3:** Local processing (no data transmission)

### **5. Context-Aware Recommendations**
- Adapts to user's timeline, budget, model type, use case
- Multiple valid paths with trade-off analysis
- Immediate fixes + long-term strategies

---

## 🚀 Quick Start

### **Installation**
```bash
# Clone repository
git clone https://github.com/Varsh1009/meddata-guardian.git
cd meddata-guardian

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Ollama (for AI agents)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

### **Run the Application**
```bash
# Activate virtual environment
source venv/bin/activate

# Run Streamlit dashboard
streamlit run src/ui/app_complete.py
```

Open browser at `http://localhost:8501`

---

## 📊 Demo Datasets

Four synthetic datasets are included for demonstration:

1. **dataset1_heart_disease_quality.csv** - Data quality issues (missing values, duplicates, outliers)
2. **dataset2_diabetes_gender_bias.csv** - Gender bias (73% male, 27% female)
3. **dataset3_heart_disease_indigenous.csv** - Race bias (0% Indigenous representation)
4. **dataset4_diabetes_combined.csv** - Combined quality + bias issues

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────┐
│  User Upload → PHI Scan → Synthetic Twin   │
│                    ↓                        │
│         Multi-Agent AI Analysis             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Medical  │  │ Fairness │  │Deployment│ │
│  │ Advisor  │  │Specialist│  │Strategist│ │
│  └──────────┘  └──────────┘  └──────────┘ │
│                    ↓                        │
│   Exact Recommendations + Working Code     │
└─────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

**Core:**
- Python 3.11
- Pandas, NumPy, SciPy
- Scikit-learn, Fairlearn, imbalanced-learn

**AI/ML:**
- Ollama (local LLM runtime)
- Llama 3.2 (3B parameters)
- Instructor (schema enforcement, anti-hallucination)
- Pydantic (data validation)

**Synthetic Data:**
- Custom generator (statistical twin creation)
- Privacy validation metrics

**RAG (Retrieval-Augmented Generation):**
- ChromaDB (local vector database)
- Medical knowledge base (clinical guidelines, FDA requirements)

**UI:**
- Streamlit (web dashboard)
- Plotly (interactive visualizations)

---

## 📂 Project Structure
```
meddata-guardian/
├── data/
│   └── synthetic/              # Demo datasets
├── knowledge_base/
│   ├── medical/                # Clinical guidelines for RAG
│   ├── regulatory/             # FDA requirements
│   └── statistical/            # Statistical best practices
├── src/
│   ├── agents/                 # AI agents
│   │   ├── medical_advisor_v2.py
│   │   ├── fairness_specialist.py
│   │   └── deployment_strategist.py
│   ├── utils/                  # Core utilities
│   │   ├── phi_scanner.py
│   │   ├── data_quality.py
│   │   ├── bias_detection.py
│   │   ├── synthetic_generator.py
│   │   └── medical_rag.py
│   └── ui/
│       └── app_complete.py     # Main Streamlit app
├── scripts/
│   └── generate_datasets.py   # Synthetic data creation
└── requirements.txt
```

---

## 🔬 Problem Statements Addressed

### **Problem 1: Data Quality Issues Discovered Too Late**
Healthcare datasets contain missing values, duplicates, outliers that are often found after months of model development, wasting research time and resources.

**Our Solution:** Instant detection with verified Python code to fix issues immediately.

### **Problem 2: Hidden Bias Leads to Unfair AI**
Demographic bias (gender, race, age, socioeconomic) in training data causes AI models to perform poorly for underrepresented groups, perpetuating healthcare disparities.

**Our Solution:** Detects ALL bias types (not just gender/race), reports representation gaps, provides specific recruitment strategies.

---

## 💡 Innovation Highlights

### **1. Synthetic Data Privacy Firewall** (Unique Approach)
- AI never sees real patient data
- Statistical twins preserve properties without PHI exposure
- Enables AI analysis with zero HIPAA risk

### **2. Anti-Hallucination Architecture**
- Instructor schemas enforce strict output format
- RAG grounds AI in real medical literature
- Python calculates exact numbers (AI can't make up statistics)
- Fallback to rule-based if AI fails

### **3. Context-Aware Intelligence**
- Asks about user's timeline, budget, model, use case
- Recommendations adapt to constraints
- "60-day timeline too short for recruitment → use SMOTE + plan 6-month retrain"

### **4. Exact Quantification**
- Report observed representation; do not infer misdiagnoses or patient harm.
- Not "collect data" → "Recruit 552 female patients from Brigham Women's Hospital, $60K, 6 months"
- Suggested transformations require held-out evaluation; accuracy improvements are not established.

---

## 📊 Use Cases

**Research:** Validate dataset before starting study, ensure representative enrollment  
**Clinical Deployment:** Pre-deployment fairness audit, prevent biased algorithms  
**FDA Submission:** Demographic subgroup analysis, compliance documentation  
**Healthcare Equity:** Ensure Indigenous, minority populations represented  

---

## 🔒 HIPAA Compliance

MedGuard AI is designed with healthcare privacy as a core principle:

1. **Pre-Processing PHI Scan:** Validates de-identification before any data loading
2. **Synthetic Data Firewall:** AI analyzes statistical twins, not real patients
3. **Local Processing:** All computation on user's machine, no external transmission
4. **No Data Storage:** Data purged from memory when application closes
5. **Audit Trail:** Compliance documentation for regulatory review

**Deployment Model:** Desktop application, not cloud service. User maintains full data custody.

---

## 🏆 Team: The Bias Busters


**Convergence 2026 - GSG x GWiSE Interdisciplinary Graduate Hackathon**

**Team Members:**
- Computer Science: AI/ML implementation, synthetic data generation
- Life Sciences: Clinical validation, medical knowledge curation
- Regulatory Affairs: HIPAA compliance, FDA requirements
- Business Strategy: Market analysis, deployment planning
- Ethics: Health equity focus, vulnerable population protection

---

## 📈 Impact

**Time Saved:** 30-second analysis vs. 6 months of post-hoc bias discovery  
**Patient Safety:** Prevents deployment of biased models that harm vulnerable populations  
**Regulatory:** Supports FDA algorithmic fairness requirements (2021 guidance)  
**Equity:** Centers Indigenous health, addresses systematic healthcare disparities  

**Market Opportunity:**
- 6,000 US hospitals × $50K/year = $300M TAM
- 2,000 clinical trials/year × $200K = $400M
- Total addressable market: $700M annually

---

## 📄 License

MIT License - See LICENSE file for details


---

**Built with ❤️ for healthcare equity and responsible AI**
