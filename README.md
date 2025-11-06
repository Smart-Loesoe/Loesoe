Loesoe is a full-stack AI assistant built by Richard van Olst.
The project combines speech, memory, a web interface, and GPT-5 intelligence into one integrated assistant.

🧩 Built with:

FastAPI (async backend)

React (Vite) frontend

PostgreSQL database

Docker Compose environment

JWT authentication + multi-user isolation

GPT-5 integration via OpenAI API

💡 About the project

Loesoe began in May 2025 as a personal hobby project and has grown into a complete AI system.
Everything was developed from scratch — without formal education — driven purely by passion for AI, Python, and automation.
The goal is to create a personal digital assistant and learning platform.

🧠 Key features

✅ GPT-5 chat with streaming
✅ Async PostgreSQL database (asyncpg)
✅ JWT authentication + user isolation
✅ Secure uploads with signed links
✅ Real-time SSE streaming
✅ Multi-model router (GPT-5)

🧱 Phase roadmap
Phase	Component	Status
1-14	Core, Memory, Prefs, Chat	✅ Completed
15	Uploads + Signed Links	✅
16	Streaming (SSE)	✅
17	GPT-5 Model Integration	✅
18	Auth & Multi-User	✅
19-21	Buddy, Memory, Finance	🚧 In development
⚙️ Run locally
docker compose up -d


Access:
🖥️ http://localhost:5173
 → Web interface
⚙️ http://localhost:8000
 → API server

📩 Contact

For collaboration, technical contributions or licensing inquiries:
📧 Connect via LinkedIn ( https://www.linkedin.com/in/richard-van-olst-558188367/ )
.

© 2025 Richard van Olst – Smart Loesoe.





# Loesoe
Full-stack AI-assistent gebouwd met FastAPI · React · PostgreSQL · Docker · GPT-5

# 🤖 Loesoe – Persoonlijke AI-assistent

**Loesoe** is een full-stack AI-assistent gebouwd door **Richard van Olst**.  
De applicatie combineert spraak, geheugen, webinterface en GPT-5-intelligentie in één platform.

🧩 Gebouwd met:
- **FastAPI** (async backend)
- **React (Vite)** frontend
- **PostgreSQL** database
- **Docker Compose** omgeving
- **JWT-authenticatie + multi-user isolatie**
- **GPT-5 integratie via OpenAI API**

---

## 💡 Over het project
Loesoe is in mei 2025 gestart als hobbyproject en sindsdien uitgegroeid tot een volledig functionerend AI-systeem.  
Alles is zelf ontwikkeld, zonder formele opleiding — puur door passie voor AI, Python en automatisering.  
Het project is bedoeld als leertraject én als persoonlijke digitale assistent.

---

## 🧠 Belangrijkste functies
✅ GPT-5 chat met streaming  
✅ Async database (PostgreSQL + asyncpg)  
✅ JWT-authenticatie + user-isolatie  
✅ Uploads + signed links  
✅ Live SSE-streaming  
✅ Multi-model router (Groq / GPT-5)  

---

## 🧱 Fase-overzicht
| Fase | Onderdeel | Status |
|------|------------|--------|
| 1-14 | Basis, Memory, Prefs, Chat | ✅ Voltooid |
| 15 | Uploads + Signed Links | ✅ |
| 16 | Streaming (SSE) | ✅ |
| 17 | Model-integratie (GPT-5) | ✅ |
| 18 | Auth & Multi-User | ✅ |
| 19-21 | Buddy, Geheugen, Financiën | 🚧 Komt eraan |

---

## ⚙️ Opstarten
```bash
docker compose up -d

App draait dan op:
🖥️ http://localhost:5173 (web)
⚙️ http://localhost:8000 (API)

📩 Contact

Bij interesse in samenwerking, technische uitbreiding of licentie:
📧 Neem gerust contact op via GitHub of LinkedIn.( https://www.linkedin.com/in/richard-van-olst-558188367/ )

© 2025 Richard van Olst – Smart Loesoe.
