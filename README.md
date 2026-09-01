🚀 Route Monitoring System API
You were hired to develop the API of a corporate transportation and routes management system. 
The system allows companies to register their routes, drivers, employees/passengers, meeting points, and operating schedules,
in addition to recording events related to the operations.

A corporate transportation monitoring and management system built with Django REST Framework.

📌 Overview

The Route Monitoring System API is a centralized platform designed to manage corporate transportation operations.

It enables:

Company management

Employee and driver management (Single Table Inheritance – TPH strategy)

Vehicle registration

Route planning and monitoring

Passenger management

Geolocated route event tracking

Schedule and meeting point management

This API follows REST principles and enforces strict business validation rules at the serializer level.

🏗 Architecture
Person Model (Single Table Strategy – TPH)

Instead of separate tables for employees and drivers, the system uses a single Person model with a discriminator field:

type = "EMPLOYEE" | "DRIVER"

Business rules are enforced via serializers:

Type	Required Field	Forbidden Field
EMPLOYEE	employee_code	license_number
DRIVER	license_number	employee_code

This approach ensures:

Simpler schema

Better scalability

Cleaner validation logic

Easier maintenance

🗂 Database Models
1️⃣ Company

id (UUID)

name

created_at

updated_at

is_active

2️⃣ Person

id (UUID)

company (FK → Company)

name

phone

type (EMPLOYEE | DRIVER)

employee_code (nullable)

license_number (nullable)

created_at

updated_at

is_active

3️⃣ Vehicle

id (UUID)

company (FK → Company)

plate_number

model

year

driver (FK → Person, type=DRIVER)

created_at

updated_at

is_active

Validation Rule:
Only DRIVER type can be assigned as vehicle driver.

4️⃣ Route

id (UUID)

company (FK → Company)

name

origin

destination

status (planned | in_progress | completed | cancelled)

created_at

updated_at

is_active

5️⃣ RoutePassenger

id (UUID)

route (FK → Route)

person (FK → Person)

Validation Rule:
Only EMPLOYEE type can be assigned as passenger.

6️⃣ RouteEvent

id (UUID)

route (FK → Route)

event_type (delay | incident | stop | departure | arrival)

latitude (Decimal)

longitude (Decimal)

description

created_at

updated_at

Validation Rules:

Latitude must be between -90 and 90

Longitude must be between -180 and 180

Description is mandatory for:

delay

incident

7️⃣ Address

id (UUID)

street

city

state

zip_code

created_at

updated_at

8️⃣ MeetingPoint

id (UUID)

route (FK → Route)

address (FK → Address)

created_at

updated_at

9️⃣ Schedule

id (UUID)

route (FK → Route)

planned_start_time

planned_end_time

created_at

updated_at

🔌 API Endpoints
Companies
GET     /companies/
POST    /companies/
GET     /companies/{id}/
PUT     /companies/{id}/
DELETE  /companies/{id}/
Employees
GET     /employees/
POST    /employees/
GET     /employees/{id}/
PUT     /employees/{id}/
DELETE  /employees/{id}/
Drivers
GET     /drivers/
POST    /drivers/
GET     /drivers/{id}/
PUT     /drivers/{id}/
DELETE  /drivers/{id}/
Vehicles
GET     /vehicles/
POST    /vehicles/
GET     /vehicles/{id}/
PUT     /vehicles/{id}/
DELETE  /vehicles/{id}/
Routes
GET     /routes/
POST    /routes/
GET     /routes/{id}/
PUT     /routes/{id}/
DELETE  /routes/{id}/
Route Passengers
GET     /route-passengers/
POST    /route-passengers/
DELETE  /route-passengers/{id}/
Route Events
GET     /route-events/
POST    /route-events/
Meeting Points
GET     /meeting-points/
POST    /meeting-points/
Schedules
GET     /schedules/
POST    /schedules/
📜 Business Rules
Person Rules

Type must be defined

EMPLOYEE requires employee_code

DRIVER requires license_number

Fields are mutually exclusive

Vehicle Rules

Only DRIVER type can be linked to a vehicle

Route Passenger Rules

Only EMPLOYEE type can be passenger

Route Event Rules

Geolocation validation enforced

Description required for critical events

🛠 Tech Stack

Python 3.x

Django

Django REST Framework

PostgreSQL

JWT Authentication

Swagger / OpenAPI

Unit Testing (models + serializers + endpoints)

🧪 Validation Strategy

The system ensures data integrity using:

validate_<field>()

validate()

full_clean() before save

Serializer-level domain rules

🎯 Expected Outcome

The system provides:

Full CRUD operations

Type-based validation for Person

Real-time geolocated event logging

Clean and scalable architecture

Testable endpoints via Postman

Production-ready backend structure

📦 Installation (Example)
git clone https://github.com/your-repository/route-monitoring.git
cd route-monitoring
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
📌 Author

Developed as a corporate-grade backend API project.