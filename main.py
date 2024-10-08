#!/usr/bin/env python3.12

"""
包含 FastAPI 應用程式的 CRUD 操作和健康檢查端點。
"""

import json
from datetime import datetime

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# FastAPI 應用程式實例
app = FastAPI()

# Redis 客戶端
redis_client = redis.StrictRedis(host="redis", port=6379, db=0)

# SQLAlchemy 設定
DATABASE_URL = "postgresql://user:password@postgres/db"  # 使用 PostgreSQL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Host(Base):
    """
    SQLAlchemy 主機模型。
    """

    __tablename__ = "hosts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class HostCreate(BaseModel):
    """
    主機創建請求模型。
    """

    name: str


class HostResponse(BaseModel):
    """
    主機響應模型。
    """

    id: int
    name: str
    created_at: datetime
    updated_at: datetime


@app.post("/hosts/", response_model=HostResponse)
def create_host(host: HostCreate):
    """
    創建新的主機並儲存到資料庫及 Redis。
    """
    db = SessionLocal()
    db_host = Host(name=host.name)
    db.add(db_host)
    db.commit()
    db.refresh(db_host)
    db.close()

    # 緩存到 Redis
    redis_client.set(
        f"host:{db_host.id}",
        json.dumps(
            {
                "id": db_host.id,
                "name": db_host.name,
                "created_at": db_host.created_at.isoformat(),
                "updated_at": db_host.updated_at.isoformat(),
            }
        ),
    )
    return db_host


@app.get("/hosts/{host_id}", response_model=HostResponse)
def read_host(host_id: int):
    """
    根據主機 ID 讀取主機信息。如果 Redis 中存在則從 Redis 讀取，否則從資料庫中讀取。
    """
    # 從 Redis 讀取
    cached_host = redis_client.get(f"host:{host_id}")
    if cached_host:
        data = json.loads(cached_host)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return data

    # 如果 Redis 中不存在，從 DB 讀取
    db = SessionLocal()
    db_host = db.query(Host).filter(Host.id == host_id).first()
    db.close()

    if db_host:
        # 儲存到 Redis
        redis_client.set(
            f"host:{db_host.id}",
            json.dumps(
                {
                    "id": db_host.id,
                    "name": db_host.name,
                    "created_at": db_host.created_at.isoformat(),
                    "updated_at": db_host.updated_at.isoformat(),
                }
            ),
        )
        return {
            "id": db_host.id,
            "name": db_host.name,
            "created_at": db_host.created_at,
            "updated_at": db_host.updated_at,
        }

    raise HTTPException(status_code=404, detail="Host not found")


@app.get("/hosts/", response_model=list[HostResponse])
def read_all_hosts():
    """
    讀取所有主機信息，並將其儲存到 Redis。
    """
    db = SessionLocal()
    hosts = db.query(Host).all()
    db.close()

    # 儲存到 Redis
    for host in hosts:
        redis_client.set(
            f"host:{host.id}",
            json.dumps(
                {
                    "id": host.id,
                    "name": host.name,
                    "created_at": host.created_at.isoformat(),
                    "updated_at": host.updated_at.isoformat(),
                }
            ),
        )

    return [
        {
            "id": host.id,
            "name": host.name,
            "created_at": host.created_at,
            "updated_at": host.updated_at,
        }
        for host in hosts
    ]


@app.put("/hosts/{host_id}", response_model=HostResponse)
def update_host(host_id: int, host: HostCreate):
    """
    更新指定 ID 的主機信息。
    """
    db = SessionLocal()
    db_host = db.query(Host).filter(Host.id == host_id).first()
    if not db_host:
        db.close()
        raise HTTPException(status_code=404, detail="Host not found")

    db_host.name = host.name
    db.commit()
    db.refresh(db_host)
    db.close()

    # 更新 Redis
    redis_client.set(
        f"host:{db_host.id}",
        json.dumps(
            {
                "id": db_host.id,
                "name": db_host.name,
                "created_at": db_host.created_at.isoformat(),
                "updated_at": db_host.updated_at.isoformat(),
            }
        ),
    )
    return {
        "id": db_host.id,
        "name": db_host.name,
        "created_at": db_host.created_at,
        "updated_at": db_host.updated_at,
    }


@app.delete("/hosts/{host_id}")
def delete_host(host_id: int):
    """
    刪除指定 ID 的主機。
    """
    db = SessionLocal()
    db_host = db.query(Host).filter(Host.id == host_id).first()
    if not db_host:
        db.close()
        raise HTTPException(status_code=404, detail="Host not found")

    db.delete(db_host)
    db.commit()
    db.close()

    # 刪除 Redis 中的資料
    redis_client.delete(f"host:{host_id}")
    return {"detail": "Host deleted"}


@app.get("/health")
def health_check():
    """
    健康檢查端點。
    """
    return {"status": "ok"}
