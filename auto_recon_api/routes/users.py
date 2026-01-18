from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auto_recon_api.database import get_session
from auto_recon_api.models import User
from auto_recon_api.schemas import Message, UserPublic, UserSchema
from auto_recon_api.security import get_current_user, get_password_hash

router = APIRouter(prefix='/users', tags=['users'])
CurrentUser = Annotated[User, Depends(get_current_user)]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post('/', response_model=UserPublic, status_code=HTTPStatus.CREATED)
async def create_user(user: UserSchema, session: Session):
    db_user = await session.scalar(
        select(User).where(
            (User.email == user.email) | (User.username == user.username)
        )
    )

    if db_user:
        if db_user.username == user.username:
            raise HTTPException(
                detail='Username or email already used',
                status_code=HTTPStatus.CONFLICT,
            )
        elif db_user.email == user.email:
            raise HTTPException(
                detail='Username or email already used',
                status_code=HTTPStatus.CONFLICT,
            )

    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return db_user


@router.get('/{user_id}', response_model=UserPublic, status_code=HTTPStatus.OK)
async def read_user(user_id: int, session: Session, current_user: CurrentUser):
    user = await session.scalar(select(User).where(User.id == user_id))

    if current_user.id != user_id:
        raise HTTPException(
            detail='Not enough permissions',
            status_code=HTTPStatus.FORBIDDEN,
        )

    return user


@router.put('/{user_id}', response_model=UserPublic)
async def update_user(
    user_id: int, user: UserSchema, session: Session, current_user: CurrentUser
):
    if current_user.id != user_id:
        raise HTTPException(
            detail='Not enough permissions',
            status_code=HTTPStatus.FORBIDDEN,
        )

    try:
        current_user.username = user.username
        current_user.email = user.email
        current_user.password = get_password_hash(user.password)
        await session.commit()
        await session.refresh(current_user)

        return current_user

    except IntegrityError:
        raise HTTPException(
            detail='Username or Email already exists',
            status_code=HTTPStatus.CONFLICT,
        )


@router.delete('/{user_id}', response_model=Message)
async def delete_user(
    user_id: int, session: Session, current_user: CurrentUser
):
    if current_user.id != user_id:
        raise HTTPException(
            detail='Not enough permissions',
            status_code=HTTPStatus.FORBIDDEN,
        )

    await session.delete(current_user)
    await session.commit()

    return {'message': 'User deleted successfully'}
