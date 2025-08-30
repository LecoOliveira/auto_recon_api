from fastapi import FastAPI

from auto_recon_api.routes import auth, domains, users

app = FastAPI()

app.include_router(users.router)
app.include_router(domains.router)
app.include_router(auth.router)
