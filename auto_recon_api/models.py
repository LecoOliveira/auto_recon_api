from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, registry, relationship

table_registry = registry()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    runs: Mapped[List['DomainRun']] = relationship(
        'DomainRun',
        back_populates='domain',
        cascade='all, delete-orphan',
        passive_deletes=True,
        init=False,
    )
    urls: Mapped[List['DiscoveredURL']] = relationship(
        'DiscoveredURL',
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


@table_registry.mapped_as_dataclass
class DomainRun:
    __tablename__ = 'domain_runs'

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )

    domain_id: Mapped[int] = mapped_column(
        ForeignKey('domain.id', ondelete='CASCADE'), index=True
    )
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None
    )

    status: Mapped[str] = mapped_column(
        String(16), index=True, default='queued'
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        init=False,
        default_factory=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        init=False,
        default_factory=_utcnow,
    )

    domain: Mapped['Domain'] = relationship(
        'Domain', back_populates='runs', init=False
    )


@table_registry.mapped_as_dataclass
class DiscoveredURL:
    __tablename__ = 'discovered_urls'
    __table_args__ = (
        UniqueConstraint('domain_id', 'url_hash', name='uq_domain_urlhash'),
        Index('ix_discovered_urls_domain_host', 'domain_id', 'host'),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )

    domain_id: Mapped[int] = mapped_column(
        ForeignKey('domain.id', ondelete='CASCADE')
    )
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), index=True)

    domain: Mapped['Domain'] = relationship(
        'Domain', back_populates='urls', init=False
    )

    host: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, default=None
    )
    hostname: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    port: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    title: Mapped[Optional[str]] = mapped_column(Text, default=None)
    tech: Mapped[Optional[list]] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), init=False
    )
