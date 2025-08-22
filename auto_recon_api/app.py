from fastapi import FastAPI

from auto_recon_api.routes import users

app = FastAPI()

app.include_router(users.router)
