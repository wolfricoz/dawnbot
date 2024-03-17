import os

import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine, BigInteger, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship
from sqlalchemy.pool import NullPool
from sqlalchemy_utils import database_exists, create_database

pymysql.install_as_MySQLdb()

load_dotenv('.env')
dblink = os.getenv('DB')
engine = create_engine(dblink, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
if not database_exists(engine.url):
    create_database(engine.url)

conn = engine.connect()


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"
    uid: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    messages: Mapped[int] = mapped_column(BigInteger, default=0)
    xp: Mapped[int] = mapped_column(BigInteger, default=0)


class Levels(Base):
    __tablename__ = "levels"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guildid: Mapped[int] = mapped_column(BigInteger)
    role_id: Mapped[int] = mapped_column(BigInteger)
    xp_required: Mapped[int] = mapped_column(BigInteger)


class Channels(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guildid: Mapped[int] = mapped_column(BigInteger)
    channelid: Mapped[int] = mapped_column(BigInteger)


class Characters(Base):
    __tablename__ = "characters"
    uid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    prestige: Mapped[int] = mapped_column(BigInteger, default=0)
    strength: Mapped[int] = mapped_column(BigInteger, default=0)
    perception: Mapped[int] = mapped_column(BigInteger, default=0)
    endurance: Mapped[int] = mapped_column(BigInteger, default=0)
    charisma: Mapped[int] = mapped_column(BigInteger, default=0)
    intelligence: Mapped[int] = mapped_column(BigInteger, default=0)
    agility: Mapped[int] = mapped_column(BigInteger, default=0)
    armor = mapped_column(BigInteger, ForeignKey('armors.id'))


class Armors(Base):
    __tablename__ = "armors"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    hp: Mapped[int] = mapped_column(BigInteger, default=75)
    ac: Mapped[int] = mapped_column(BigInteger, default=12)
    hitchance: Mapped[int] = mapped_column(BigInteger, default=0)
    modifier: Mapped[str] = mapped_column(String(255), nullable=True)


class Weapons(Base):
    __tablename__ = "weapons"
    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    dice: Mapped[str] = mapped_column(String(255))
    modifier: Mapped[str] = mapped_column(String(255))
    hitmodifier = mapped_column(BigInteger, default=0)


class database:
    def create(self):
        Base.metadata.create_all(engine)
