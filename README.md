# 🚀 DeepFetch AI - A Web-Powered AI Assistant

A system that retrieves content from the internet using **serpAPI** , processes it, and generates responses using **Gemini** .

---

## 🔧 Project Structure

```
DeepFetch-AI/
├── Backend/
│   ├── __init__.py
│   ├── app.py       # Backend service
│
├── Streamlit/
│   └── app.py       # Frontend interface
├── .env             # Environment variables
└── requirements.txt # Dependencies
```

---

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Architgarg2003/DeepFetch-AI.git
cd DeepFetch-AI
```

---

### 2. Create a Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# OR using conda
conda create -n web-ai-assistant python=3.12
conda activate web-ai-assistant
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create a `.env` file in the root directory with the following content:

```
GOOGLE_API_KEY=YOUR_API_KEY
SERPAPI_API_KEY=YOUR_API_KEY
API_URL=http://localhost:5000
```

---

### 5. Start the Backend Service

```bash
cd Backend
python app.py
```

This will launch the Flask backend on:  
📍 `http://localhost:5000`

---

### 6. Start the Frontend Interface

In a **new terminal**, activate your environment and run:

```bash
cd Streamlit
streamlit run app.py
```

This will launch the Streamlit frontend at:  
📍 `http://localhost:8501`

---

## ✨ Features

- 🌐 **Live Web Content Retrieval** using serpAPI or Google Programmable Search.
- 🤖 **Response Generation** with Gemini or OpenAI LLMs.
- 🧠 **Conversational Memory** using LangChain for contextual continuity.
- 🖥️ **Streamlit UI** for easy interaction.
- 🔍 **Search Debugging** and source tracking enabled.

---

## ⚠️ Limitations

- Limited by the search engine APIs' quota and result quality.
- Web scraping may vary by website structure.
- LLM token input size may truncate longer content.

---

## 🔄 Extending the System

- Add **multi-source support** like PDFs, Databases.
- Use OpenAI's paid models for better response generation 
- Use **TruLens or LangSmith** for evals.
- Deploy on **Render, Railway, or GCP** for persistent hosting.
