from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import time

from base import engine


SessionLocal = sessionmaker(bind=engine)
app = FastAPI()

# Модели запросов и ответов
class CarwashBase(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    openingtime: time
    closingtime: time
    windowsnumber: int
    rate: int

class CarwashResponse(CarwashBase):
    carwashid: UUID

class ServiceBase(BaseModel):
    name: str
    description: str
    duration: int
    carwashid: UUID

class ServiceResponse(ServiceBase):
    serviceid: UUID


@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "Backend is running"}

# Роуты для автомоек
@app.post("/carwashes/", response_model=CarwashResponse)
def create_carwash(carwash: CarwashBase):
    session = SessionLocal()
    try:
        carwash_id = uuid4()
        query = text("""
            INSERT INTO carwashes (
                carwashid, name, address, latitude, longitude, 
                openingtime, closingtime, windowsnumber, rate
            ) VALUES (
                :carwashid, :name, :address, :latitude, :longitude,
                :openingtime, :closingtime, :windowsnumber, :rate
            ) RETURNING carwashid
        """)
        result = session.execute(query, {
            **carwash.dict(),
            "carwashid": carwash_id
        })
        session.commit()
        return {**carwash.dict(), "carwashid": carwash_id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.delete("/carwashes/{carwash_id}", status_code=204)
def delete_carwash(carwash_id: UUID):
    session = SessionLocal()
    try:
        query = text("DELETE FROM carwashes WHERE carwashid = :carwashid")
        result = session.execute(query, {"carwashid": carwash_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Carwash not found")
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.get("/carwashes/all", response_model=List[CarwashResponse])
def get_all_carwashes():
    session = SessionLocal()
    query = text("""
        SELECT carwashid, name, address, latitude, longitude,
               openingtime::text, closingtime::text, windowsnumber, rate
        FROM carwashes
        ORDER BY name
    """)
    result = session.execute(query)
    carwashes = [dict(row._mapping) for row in result]
    session.close()
    return carwashes

@app.get("/carwashes/search", response_model=List[CarwashResponse])
def search_carwashes(name: str = Query(..., min_length=1)):
    session = SessionLocal()
    query = text("""
        SELECT carwashid, name, address, latitude, longitude,
               openingtime::text, closingtime::text, windowsnumber, rate
        FROM carwashes
        WHERE name ILIKE :name
    """)
    result = session.execute(query, {"name": f"%{name}%"})
    carwashes = [dict(row._mapping) for row in result]
    session.close()
    return carwashes

# Роуты для услуг
@app.post("/services/", response_model=ServiceResponse)
def create_service(service: ServiceBase):
    session = SessionLocal()
    try:
        service_id = uuid4()
        query = text("""
            INSERT INTO services (
                serviceid, name, description, duration, carwashid
            ) VALUES (
                :serviceid, :name, :description, :duration, :carwashid
            ) RETURNING serviceid
        """)
        result = session.execute(query, {
            **service.dict(),
            "serviceid": service_id
        })
        session.commit()
        return {**service.dict(), "serviceid": service_id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: UUID):
    session = SessionLocal()
    try:
        query = text("DELETE FROM services WHERE serviceid = :serviceid")
        result = session.execute(query, {"serviceid": service_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Service not found")
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.get("/services/all", response_model=List[ServiceResponse])
def get_all_services():
    session = SessionLocal()
    query = text("""
        SELECT serviceid, name, description, duration, carwashid
        FROM services
        ORDER BY name
    """)
    result = session.execute(query)
    services = [dict(row._mapping) for row in result]
    session.close()
    return services

@app.get("/services/search", response_model=List[ServiceResponse])
def search_services(name: str = Query(..., min_length=1)):
    session = SessionLocal()
    query = text("""
        SELECT serviceid, name, description, duration, carwashid
        FROM services
        WHERE name ILIKE :name
    """)
    result = session.execute(query, {"name": f"%{name}%"})
    services = [dict(row._mapping) for row in result]
    session.close()
    return services