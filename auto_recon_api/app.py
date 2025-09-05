from fastapi import FastAPI

from auto_recon_api.routes import auth, domains, subdomains, users

app = FastAPI()

app.include_router(users.router)
app.include_router(domains.router)
app.include_router(subdomains.router)
app.include_router(auth.router)
