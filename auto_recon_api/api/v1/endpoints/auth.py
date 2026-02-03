from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter.depends import RateLimiter
from sqlalchemy import select

from auto_recon_api.api.deps import CurrentUser, DbSession
from auto_recon_api.models import User
from auto_recon_api.schemas import Token
from auto_recon_api.security import create_access_token, verify_password

router = APIRouter(prefix='/auth', tags=['auth'])

FormData = Annotated[OAuth2PasswordRequestForm, Depends()]


@router.post(
    '/token',
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
    status_code=HTTPStatus.OK,
    response_model=Token,
)
async def login_for_access_token(session: DbSession, form_data: FormData):
    user = await session.scalar(
        select(User).where(User.email == form_data.username)
    )

    if not user:
        raise HTTPException(
            detail='Incorrect username or password',
            status_code=HTTPStatus.UNAUTHORIZED,
        )

    elif not verify_password(form_data.password, user.password):
        raise HTTPException(
            detail='Incorrect username or password',
            status_code=HTTPStatus.UNAUTHORIZED,
        )

    access_token = create_access_token(data={'sub': user.email})

    return Token(access_token=access_token, token_type='bearer')


@router.post('/refresh_token', response_model=Token)
async def refresh_access_token(user: CurrentUser):
    new_access_token = create_access_token(data={'sub': user.email})

    return {'access_token': new_access_token, 'token_type': 'bearer'}
