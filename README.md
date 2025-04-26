# DriveTrackr

## Project Overview

This application provides car owners with a comprehensive and user-friendly platform to track and manage their vehicle's service history. Keeping detailed records of maintenance, repairs, and other significant events is crucial for vehicle longevity, resale value, and ensuring timely service. This app aims to simplify that process, offering a centralized digital logbook accessible anytime, anywhere.

## Features

### User Management

- **Registration & Login:** Secure user accounts requiring Username, Email, Display Name, and Location (County, Country).
- **Multiple Cars:** Users can manage service histories for one or more vehicles under a single account.
- **Car Transfers:**
  - Seamlessly transfer vehicle ownership to another registered user.
  - Initiate transfers to non-registered users via email; the transfer completes upon their successful registration.
  - Maintains a record of previous owners for each car.
  - Ownership changes are automatically logged in the car's history.

### Vehicle History Logging

Users can add detailed logs for various events:

- **Service Logs:** Record maintenance details including date, mileage, cost, descriptive notes, and attach relevant documents or photos (e.g., invoices, receipts).
- **Inspection Logs:** Log official inspections (e.g., MOT, TÜV) with date, mileage, cost, outcome (Pass/Advisory/Fail), and attach certificates or reports.
- **Modification Logs:** Document aftermarket modifications with date, mileage, cost, and supporting documentation/photos.
- **Damage Records:**
  - Record incidents of damage with date, mileage, and photographic evidence.
  - Link subsequent repair/service logs directly to the damage record to track resolution.

### Service Center Integration

- **Service Center Registration:** Garages and service centers can register for an account.
- **Manual Activation:** Service center accounts undergo a manual review process before activation to ensure legitimacy.
- **Add Service Logs:** Activated service centers can directly add service logs to customer vehicles, enhancing record accuracy and convenience.

## Tech Stack

**Backend:**

- Python 3.x
- Flask (API Framework)
- PostgreSQL (Database)
- Flask-SQLAlchemy (ORM - Recommended)
- Flask-Migrate / Alembic (Database Migrations - Recommended)

**Frontend (Mobile App & Website):**

- Flutter (using Dart)

**API (for business integration):**

- REST API (provided by the Flask backend)

## Deployment

- Kubernetes
- **Note:** This application is designed to be self-hosted.

---

## Getting Started

### Prerequisites

- Git
- Python 3.x and Pip
- Docker and Docker Compose (Recommended for local PostgreSQL)
- Flutter SDK
- An IDE (like VS Code with Python and Flutter extensions)

### Installation & Setup

1.  **Clone the repository:**

    ```bash
    git clone git@github.com:JakubMrowicki/car-history-app.git
    cd car-history-app
    ```

2.  **Backend Setup:**

    - Create and activate a virtual environment:
      ```bash
      python -m venv venv
      source venv/bin/activate  # On Windows use `venv\Scripts\activate`
      ```
    - Install Python dependencies:
      ```bash
      pip install -r requirements.txt
      ```
    - Set up environment variables: Copy `.env.example` to `.env` and fill in the required values (Database URL, Secret Key, Email settings, etc.).
      ```bash
      cp .env.example .env
      # Edit .env with your details
      ```
    - Start PostgreSQL (using Docker is recommended):
      ```bash
      docker-compose up -d database # Assuming a docker-compose.yml exists
      ```
    - Apply database migrations:
      ```bash
      flask db upgrade
      ```

3.  **Frontend Setup:**
    - Navigate to the Flutter project directory (e.g., `cd frontend`):
    - Get Flutter dependencies:
      ```bash
      flutter pub get
      ```

### Running the Application

1.  **Run the Backend (Flask API):**

    ```bash
    flask run
    ```

    (Ensure your virtual environment is activated and `.env` is configured)

2.  **Run the Frontend (Flutter):**
    - For Mobile (ensure an emulator/simulator is running or a device is connected):
      ```bash
      flutter run
      ```
    - For Web:
      ```bash
      flutter run -d chrome
      ```

## Data Model / Database Schema

_(Suggestion: Use an ORM like Flask-SQLAlchemy to define models)_

The core entities include:

- **User:** Stores user profile information (username, email, location, etc.) and credentials. Will need roles or flags to distinguish regular users from service centers and admins.
- **Car:** Represents a vehicle, linked to its current owner (User). Includes details like VIN, make, model, year.
- **OwnershipRecord:** Tracks the history of car ownership, linking Cars to Users over time periods.
- **ServiceLog:** Records maintenance actions (linked to a Car).
- **InspectionLog:** Records inspection results (linked to a Car).
- **ModificationLog:** Records modifications (linked to a Car).
- **DamageLog:** Records damage incidents (linked to a Car). Can potentially link to a ServiceLog for repairs.
- **Attachment:** Stores metadata about uploaded files (filename, URL/path, upload date, linked log entry).

Relationships are primarily one-to-many (User -> Cars, Car -> Logs) and many-to-many (implicit via OwnershipRecord).

_(Suggestion: Generate an Entity Relationship Diagram (ERD) once models are more defined.)_

## API Design

- The backend provides a **RESTful API** for the Flutter frontend and potential external integrations.
- **Authentication:** _(Suggestion: Use **JWT (JSON Web Tokens)**. The user logs in via an endpoint, receives access and refresh tokens. The access token is sent in the `Authorization: Bearer <token>` header for protected requests.)_
- **Versioning:** _(Suggestion: Consider API versioning in the URL path, e.g., `/api/v1/...`)_
- **Data Format:** Requests and responses use **JSON**.
- **Example Endpoints:**
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/cars`
  - `POST /api/v1/cars`
  - `GET /api/v1/cars/{car_id}/servicelogs`
  - `POST /api/v1/cars/{car_id}/servicelogs`
  - _(... other CRUD endpoints for all log types, user profiles, etc.)_

## File Handling (Attachments)

- **Strategy:** Attachments (documents, photos) are stored directly within the PostgreSQL database as binary large objects (BLOBs) alongside their metadata in the `Attachment` table.
  _(Note: While convenient for self-contained deployments, storing large binary files directly in the database can impact performance and database size. Consider this trade-off during development and deployment.)_

## Email Sending

- The car transfer feature requires sending emails to potentially unregistered users as well as email confirmation, notifications of new service logs etc.
- The Flask backend handles email sending directly (e.g., via SMTP configured through environment variables).
- Use a Flask extension or library (like `Flask-Mail`) to integrate email functionality.

## Service Center Activation Process

- **Separate Portal:** Service Centers have a dedicated registration and login portal.
- **Dashboard:** Upon login, Service Centers access a dashboard designed for their workflow.
- **Functionality:** The dashboard allows Service Centers to:
  - Add new service records to customer vehicles (requires a mechanism to associate logs with the correct car/owner).
  - Search historical service records they have created.
  - Edit previously created service records if amendments are necessary.
- **Activation:** _(The previous manual activation workflow is removed based on the description of a dedicated portal. Clarify if any approval/vetting process is still needed after registration through their dedicated portal, or if registration implies immediate access.)_
