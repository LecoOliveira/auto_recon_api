from datetime import datetime
from typing import List

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, registry, relationship

table_registry = registry()


@table_registry.mapped_as_dataclass
class User:
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    domains: Mapped[List['Domain']] = relationship(
        'Domain',
        back_populates='user',
        cascade='all, delete-orphan',
        init=False,
    )


@table_registry.mapped_as_dataclass
class Domain:
    __tablename__ = 'domain'
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_domain'),
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(
        'User', back_populates='domains', init=False
    )

    subdomains: Mapped[List['Subdomain']] = relationship(
        'Subdomain',
        back_populates='domain',
        init=False,
        cascade='all, delete-orphan',
    )

    status: Mapped[str] = mapped_column(default='pending')


@table_registry.mapped_as_dataclass
class Subdomain:
    __tablename__ = 'subdomain'
    __table_args__ = (
        UniqueConstraint('host', 'domain_id', name='uq_host_per_domain'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    host: Mapped[str] = mapped_column()
    ip: Mapped[str]
    domain_id: Mapped[int] = mapped_column(ForeignKey('domain.id'))
    created_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    domain: Mapped['Domain'] = relationship(
        'Domain', back_populates='subdomains', init=False
    )
