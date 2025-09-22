from fastapi import FastAPI

from auto_recon_api.routes import auth, subdomains, users
from auto_recon_api.routes.domains import base

app = FastAPI()

app.include_router(users.router)
app.include_router(auth.router)

app.include_router(base.router)
app.include_router(subdomains.router)
