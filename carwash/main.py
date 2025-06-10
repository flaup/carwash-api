from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import date, time, datetime
from fastapi.middleware.cors import CORSMiddleware

from base import engine


SessionLocal = sessionmaker(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class OrderBase(BaseModel):
    carwashid: UUID
    serviceid: UUID
    clientid: UUID
    date: date
    starttime: time
    endtime: time
    washwindow: int
    state: int = 1  # Default state (1 - pending, 2 - confirmed, etc.)

class OrderResponse(OrderBase):
    orderid: UUID

class OrderUpdate(BaseModel):
    state: int

class FeedbackBase(BaseModel):
    userid: UUID
    carwashid: UUID
    comment: str

class FeedbackResponse(FeedbackBase):
    feedbackid: UUID

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

@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "Backend is running"}


@app.post("/orders/", response_model=OrderResponse)
def create_order(order: OrderBase):
    session = SessionLocal()
    try:

        carwash_exists = session.execute(
            text("SELECT 1 FROM carwashes WHERE carwashid = :carwashid"),
            {"carwashid": order.carwashid}
        ).fetchone()

        service_exists = session.execute(
            text("SELECT 1 FROM services WHERE serviceid = :serviceid"),
            {"serviceid": order.serviceid}
        ).fetchone()

        if not carwash_exists or not service_exists:
            raise HTTPException(status_code=404, detail="Carwash or service not found")

        # Проверяем доступность окна в указанное время
        is_available = session.execute(
            text("""
                SELECT 1 FROM orders 
                WHERE carwashid = :carwashid 
                AND date = :date 
                AND washwindow = :washwindow
                AND (
                    (:starttime >= starttime AND :starttime < endtime) OR
                    (:endtime > starttime AND :endtime <= endtime) OR
                    (:starttime <= starttime AND :endtime >= endtime)
                LIMIT 1
            """),
            {
                "carwashid": order.carwashid,
                "date": order.date,
                "washwindow": order.washwindow,
                "starttime": order.starttime,
                "endtime": order.endtime
            }
        ).fetchone()

        if is_available:
            raise HTTPException(status_code=400, detail="The selected time slot is already booked")


        order_id = uuid4()
        query = text("""
            INSERT INTO orders (
                orderid, carwashid, serviceid, clientid, date,
                starttime, endtime, washwindow, state
            ) VALUES (
                :orderid, :carwashid, :serviceid, :clientid, :date,
                :starttime, :endtime, :washwindow, :state
            ) RETURNING orderid
        """)
        result = session.execute(query, {
            **order.dict(),
            "orderid": order_id
        })
        session.commit()
        return {**order.dict(), "orderid": order_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID):
    session = SessionLocal()
    try:
        query = text("""
            SELECT orderid, carwashid, serviceid, clientid, date,
                   starttime::text, endtime::text, washwindow, state
            FROM orders
            WHERE orderid = :orderid
        """)
        result = session.execute(query, {"orderid": order_id}).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        return dict(result._mapping)
    finally:
        session.close()


@app.patch("/orders/{order_id}", response_model=OrderResponse)
def update_order_state(order_id: UUID, order_update: OrderUpdate):
    session = SessionLocal()
    try:

        order_exists = session.execute(
            text("SELECT 1 FROM orders WHERE orderid = :orderid"),
            {"orderid": order_id}
        ).fetchone()

        if not order_exists:
            raise HTTPException(status_code=404, detail="Order not found")


        query = text("""
            UPDATE orders
            SET state = :state
            WHERE orderid = :orderid
            RETURNING orderid, carwashid, serviceid, clientid, date,
                      starttime::text, endtime::text, washwindow, state
        """)
        result = session.execute(query, {
            "orderid": order_id,
            "state": order_update.state
        }).fetchone()
        session.commit()
        return dict(result._mapping)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.get("/orders/by_carwash/{carwash_id}", response_model=List[OrderResponse])
def get_orders_by_carwash(carwash_id: UUID, date: Optional[date] = None):
    session = SessionLocal()
    try:
        query = text("""
            SELECT orderid, carwashid, serviceid, clientid, date,
                   starttime::text, endtime::text, washwindow, state
            FROM orders
            WHERE carwashid = :carwashid
            AND (:date IS NULL OR date = :date)
            ORDER BY date, starttime
        """)
        result = session.execute(query, {"carwashid": carwash_id, "date": date})
        return [dict(row._mapping) for row in result]
    finally:
        session.close()


@app.get("/orders/by_client/{client_id}", response_model=List[OrderResponse])
def get_orders_by_client(client_id: UUID):
    session = SessionLocal()
    try:
        query = text("""
            SELECT orderid, carwashid, serviceid, clientid, date,
                   starttime::text, endtime::text, washwindow, state
            FROM orders
            WHERE clientid = :clientid
            ORDER BY date DESC, starttime DESC
        """)
        result = session.execute(query, {"clientid": client_id})
        return [dict(row._mapping) for row in result]
    finally:
        session.close()


@app.get("/carwashes/{carwash_id}/available_windows")
def get_available_windows(carwash_id: UUID, date: date, service_id: UUID):
    session = SessionLocal()
    try:

        carwash = session.execute(
            text("""
                SELECT windowsnumber, openingtime::text, closingtime::text
                FROM carwashes
                WHERE carwashid = :carwashid
            """),
            {"carwashid": carwash_id}
        ).fetchone()

        if not carwash:
            raise HTTPException(status_code=404, detail="Carwash not found")

        service = session.execute(
            text("SELECT duration FROM services WHERE serviceid = :serviceid"),
            {"serviceid": service_id}
        ).fetchone()

        if not service:
            raise HTTPException(status_code=404, detail="Service not found")

        duration = service.duration
        windows_number = carwash.windowsnumber
        opening_time = datetime.strptime(carwash.openingtime, "%H:%M:%S").time()
        closing_time = datetime.strptime(carwash.closingtime, "%H:%M:%S").time()


        booked_windows = session.execute(
            text("""
                SELECT washwindow, starttime::text, endtime::text
                FROM orders
                WHERE carwashid = :carwashid AND date = :date
                ORDER BY washwindow, starttime
            """),
            {"carwashid": carwash_id, "date": date}
        ).fetchall()


        available_slots = []
        for window in range(1, windows_number + 1):
            current_time = opening_time
            window_bookings = [b for b in booked_windows if b.washwindow == window]

            for booking in window_bookings:
                booking_start = datetime.strptime(booking.starttime, "%H:%M:%S").time()
                booking_end = datetime.strptime(booking.endtime, "%H:%M:%S").time()

                if current_time < booking_start:
                    time_diff = datetime.combine(date, booking_start) - datetime.combine(date, current_time)
                    available_minutes = time_diff.total_seconds() / 60

                    if available_minutes >= duration:
                        available_slots.append({
                            "washwindow": window,
                            "starttime": current_time.strftime("%H:%M"),
                            "endtime": booking_start.strftime("%H:%M")
                        })

                current_time = booking_end

            if current_time < closing_time:
                time_diff = datetime.combine(date, closing_time) - datetime.combine(date, current_time)
                available_minutes = time_diff.total_seconds() / 60

                if available_minutes >= duration:
                    available_slots.append({
                        "washwindow": window,
                        "starttime": current_time.strftime("%H:%M"),
                        "endtime": closing_time.strftime("%H:%M")
                    })

        return {
            "carwashid": carwash_id,
            "serviceid": service_id,
            "date": date.isoformat(),
            "available_slots": available_slots
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.get("/feedback/{carwash_id}", response_model=List[FeedbackResponse])
def get_feedback_by_carwash(carwash_id: UUID):
    session = SessionLocal()
    try:
        query = text("""
            SELECT feedbackid, userid, carwashid, comment
            FROM feedback
            WHERE carwashid = :carwashid
            ORDER BY comment
        """)
        result = session.execute(query, {"carwashid": carwash_id})
        feedbacks = [dict(row._mapping) for row in result]
        return feedbacks
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.post("/feedback/", response_model=FeedbackResponse)
def create_feedback(feedback: FeedbackBase):
    session = SessionLocal()
    try:
        user_exists = session.execute(
            text("SELECT 1 FROM \"User\" WHERE userid = :userid"),
            {"userid": feedback.userid}
        ).fetchone()
        
        carwash_exists = session.execute(
            text("SELECT 1 FROM carwashes WHERE carwashid = :carwashid"),
            {"carwashid": feedback.carwashid}
        ).fetchone()

        if not user_exists or not carwash_exists:
            raise HTTPException(status_code=404, detail="User or carwash not found")

        feedback_id = uuid4()
        query = text("""
            INSERT INTO feedback (
                feedbackid, userid, carwashid, comment
            ) VALUES (
                :feedbackid, :userid, :carwashid, :comment
            ) RETURNING feedbackid
        """)
        result = session.execute(query, {
            **feedback.dict(),
            "feedbackid": feedback_id
        })
        session.commit()
        return {**feedback.dict(), "feedbackid": feedback_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.delete("/feedback/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: UUID):
    session = SessionLocal()
    try:
        feedback_exists = session.execute(
            text("SELECT 1 FROM feedback WHERE feedbackid = :feedbackid"),
            {"feedbackid": feedback_id}
        ).fetchone()

        if not feedback_exists:
            raise HTTPException(status_code=404, detail="Feedback not found")

        query = text("DELETE FROM feedback WHERE feedbackid = :feedbackid")
        session.execute(query, {"feedbackid": feedback_id})
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()
