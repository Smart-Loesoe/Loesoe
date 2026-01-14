Loesoe

Versie: v6.9
Laatste update: 13 januari 2026
Status: core stabiel, events en learning actief, fase 23.4 afgerond, architectuur bevroren

Wat is Loesoe

Loesoe is een volledig zelfgebouwd, lokaal draaiend AI-platform.
Het is ontworpen als professionele AI-infrastructuur waarop meerdere eindproducten kunnen draaien, zoals een persoonlijke AI-buddy, developer assistant, app generator, gezins- en kindermodus en bedrijfs- of gemeentetoepassingen.

Loesoe is expliciet, voorspelbaar en debugbaar.
Geen hobbyproject. Geen ChatGPT-wrapper. Geen black box.

Kernprincipes

Modulair en uitbreidbaar
Docker-native
Stateless containers
Alle data via volumes en lokaal zichtbaar op Windows
.env is de enige bron van waarheid
Geen hardcoded secrets
Geen overrides in docker-compose.yml
/healthz is de enige waarheid over status
Geen impliciete defaults
Geen magische fallback-logica
Geen verborgen state

Actuele functionaliteit

Realtime GPT-chat met SSE streaming
Model-router via /model/chat met legacy compat via /chat en /chat/send
GPT-5 project-scoped API-keys
Zelflerend geheugen v2
PostgreSQL met pgvector
Retrieval met system-level prompt injectie
Websearch via SerpAPI
Auth demo in-memory met bearer tokens
React dashboard
Uploads en documentverwerking
Feature flags en PRO-mode
Learning events ingest
Patterns opslag in database
Deterministische ML-laag (read-only)

Architectuur

Docker Compose is verplicht.
Containers zijn stateless.
Alle data leeft in bind mounts of volumes.

Browser
Web (React/Vite) op poort 5173
API (FastAPI) op poort 8000
PostgreSQL met pgvector op poort 5432

Config-regels

.env is leidend
Secrets staan niet in code
Geen secrets of overrides in docker-compose.yml
Bij wijziging van database-credentials altijd docker compose down -v

Opstarten (Windows PowerShell)

cd C:\Loesoe\loesoe
docker compose up -d
docker ps
Invoke-RestMethod "http://localhost:8000/healthz
" | ConvertTo-Json -Depth 10

Projectstructuur (actueel)

C:\Loesoe\loesoe
docker-compose.yml
Dockerfile.api
.env.example
README.md

api\
web\
data\

Learning en ML status

Fase 23.1 events ingest afgerond
Fase 23.2 patterns en database afgerond
Fase 23.3 read-only impact afgerond
Fase 23.4 deterministische ML-laag afgerond

ML-eigenschappen

Read-only
Uitlegbaar
Opt-in
Geen automatische acties

Sequenties

Loesoe krijgt nooit macht vóór controle.

De volgorde is:
zien via events en data
begrijpen via patterns en ML (read-only)
controleren via models en providers
beveiligen via rechten en sandbox
bouwen via tools en generators

Acties en automatisering pas later.

Roadmap (leidend, tot en met fase 24)

Fase 20 zelflerend geheugen v1 afgerond
Fase 21 streaming en PRO-mode afgerond
Fase 22 geheugen v2 afgerond
Fase 23 learning en observability afgerond t/m 23.4

Fase 23.3 polish UI en UX gepland

Fase 24 model en provider manager

Fase 24.1 model registry skeleton
Registry voor GPT-modellen en search providers
Versies en metadata
Health hooks read-only
Nog geen gedragseffect

Fase 24.2 search provider control
SerpAPI expliciet als provider
Providerstatus beschikbaar, quota_exceeded of disabled
Rustige fallback zonder spam
Dashboard-status zichtbaar
Voorbereid op vervanging door Bing, Brave of lokale search

Stop- en startpunt

Gestopt bij fase 23.4 deterministische ML-laag
Volgende stap is fase 24.1 model registry skeleton

Startzin volgende sessie:
Loesoe time start fase 24.1 model registry skeleton
