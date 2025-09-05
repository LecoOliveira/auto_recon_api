# Auto Recon API

[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-111111?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-3673A5?style=flat&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-0D9488?style=flat&logo=pydantic&logoColor=white)](https://pydantic-docs.helpmanual.io/)

[![Docker](https://img.shields.io/badge/docker-enabled-green)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

API para gerenciamento de domínios e descoberta de subdomínios utilizando **FastAPI**, **SQLAlchemy** e **PostgreSQL**. Suporta execução assíncrona e background tasks para descoberta de subdomínios com **Subfinder** e **Assetfinder**.

---

## Funcionalidades

- Adicionar, listar e deletar domínios de usuários.
- Descoberta de subdomínios assíncrona.
- Consulta de IPs para cada subdomínio.
- Background tasks para não bloquear a API.
- Compatível com containers Docker.

---

## Tecnologias

- Python 3.13
- FastAPI
- SQLAlchemy (Async)
- PostgreSQL
- Docker & Docker Compose
- HTTPX
- Subfinder / Assetfinder

---

## Setup

1. Clonar o repositório:

```bash
git clone https://github.com/LecoOliveira/auto_recon_api.git
cd auto_recon_api
```

2. Criar .env com variáveis necessárias:
```bash
DATABASE_URL=postgresql+asyncpg://user:password@recon_database:5432/recon
SUBDOMAIN_URL=http://recon_worker:8001/find_subdomains
```



3. Subir containers com Docker Compose:
```bash
docker-compose up --build
```
---
## Arquitetura do projeto
```text
+----------------+          +-----------------+          +-----------------+
|                |  HTTP    |                 |  DB      |                 |
|   FastAPI API  +--------->+   PostgreSQL    +<-------->+  Worker/Tasks   |
|                |          |                 |          | (Subfinder/AF)  |
+----------------+          +-----------------+          +-----------------+
        ^                                                        ^
        |                                                        |
        |           Background Tasks (HTTP / Queue)              |
        +--------------------------------------------------------+


```

- **FastAPI API**: Recebe requisições do usuário e armazena domínios.
- **Worker**: Executa Subfinder e Assetfinder de forma assíncrona.
- **PostgreSQL**: Armazena domínios, subdomínios e IPs.
- A comunicação entre API ↔ Worker é feita via HTTP interno do Docker Compose consultando uma api /subdomains.

---
## Endpoints

#### Adicionar Domínios
```http
POST /domains
Content-Type: application/json

{
  "domains": ["example.com", "test.com", "existing.com"]
}
```
###### Exemplo com curl

```http
curl -X POST http://localhost:8000/domains \
-H "Content-Type: application/json" \
-d '{"domains": ["example.com", "test.com", "existing.com"]}'
```

##### Resposta
```json
{
  "added": [
    {
      "id": 2598,
      "name": "example.com",
      "status": "done",
      "created_at": "2025-09-05T06:01:44.876Z",
      "updated_at": "2025-09-05T06:01:44.876Z"
    },
    {
      "id": 2599,
      "name": "test.com",
      "status": "pending",
      "created_at": "2025-09-06T06:00:21.876Z",
      "updated_at": "2025-09-06T06:00:21.876Z"
    }
  ],
  "already_exists": ["existing.com"]
}
```

#### Listar Domínios
```http
GET /domains
```
```http
curl http://localhost:8000/domains
```
##### Resposta
```json
{
  "domains": [
    {
      "id": 2598,
      "name": "example.com",
      "status": "done",
      "created_at": "2025-09-05T06:01:44.876Z",
      "updated_at": "2025-09-05T06:01:44.876Z"
    },
    {
      "id": 2599,
      "name": "test.com",
      "status": "pending",
      "created_at": "2025-09-06T06:00:21.876Z",
      "updated_at": "2025-09-06T06:00:21.876Z"
    }
  ]
}
```

#### Deletar Domínios
```http
DELETE /domains/{domain_id}
```
```http
curl -X DELETE http://localhost:8000/domains/1
```
##### Resposta
```json
{
  "message": "Domain deleted"
}
```

#### Descobrir Subdomínios
```http
POST /subdomains
Content-Type: application/json

{
  "domain": "example.com"
}
```
```http
curl -X POST http://localhost:8000/subdomains \
-H "Content-Type: application/json" \
-d '{"domain": "example.com"}'
```
Exemplo de retorno:
```json
[
  {
    "host":"www.example.com",
    "ip":"93.184.216.34"
  },
  {
    "host":"mail.example.com",
    "ip":"93.184.216.34"
  }
]
```
---
##  Boas práticas


Configure timeouts em requests HTTPX.

Trate exceções de DNS/IP.

Use containers para Subfinder/Assetfinder e configure rede interna para comunicação API ↔ Worker.


##  Próximos passos

Paginação nos endpoints de listagem de domínios.

Integração com mais ferramentas de recon.

Cache dos resultados para reduzir requests repetidos.

Autenticação JWT para endpoints de usuário.

---
###### Feito por Alex Rocha