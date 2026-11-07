# E-Commerce Order, Payment and Logistics Management System

## About the Project

The **E-Commerce Order, Payment and Logistics Management System** is a database-driven web application developed as a semester project. It helps an administrator manage the main operations of an e-commerce store, including products, customers, orders, payments, inventory and delivery.

The project uses Python Flask for backend development and Oracle Database for storing and managing data.

## Technologies Used

- **Frontend:** HTML, CSS
- **Backend:** Python, Flask
- **Database:** Oracle Database (Oracle XE)
- **Database Connectivity:** Python `oracledb`
- **Environment Management:** `python-dotenv`

## Project Modules

The application includes the following modules:

1. **Dashboard** – Displays total revenue, orders, customers, products and recent orders.
2. **Product Management** – Add, view, update, delete and search products.
3. **Category Management** – Manage product categories and their hierarchy.
4. **Customer Management** – Manage customer records.
5. **Address Management** – Manage customer delivery addresses.
6. **Cart Management** – Create carts and manage cart items and quantities.
7. **Order Management** – Create and manage customer orders and order items.
8. **Payment Management** – Record payments and update payment status.
9. **Inventory Management** – Manage product stock across warehouses.
10. **Warehouse Management** – Manage warehouse information.
11. **Shipment Management** – Manage shipment details and tracking information.
12. **Delivery Status Management** – Maintain delivery history and shipment status.
13. **Refund Management** – Create refund requests and manage their status.

## Database Design

The project uses Oracle Database with the following 14 tables:

- CUSTOMER
- ADDRESS
- CATEGORY
- PRODUCT
- CART
- CART_ITEM
- ORDERS
- ORDER_ITEM
- PAYMENT
- REFUND
- INVENTORY
- WAREHOUSE
- SHIPMENT
- DELIVERY_STATUS

Primary keys, foreign keys, constraints and relationships are used to maintain data integrity.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/piyushaether-cyber/E-Commerce-Order-Payment-and-Logistics-Management-System-via-SQL.git
```

### 2. Open the Project Folder

```bash
cd E-Commerce-Order-Payment-and-Logistics-Management-System-via-SQL
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### 4. Install Required Packages

```bash
pip install flask oracledb python-dotenv
```

### 5. Configure Database Connection

Create a `.env` file in the project folder:

```env
DB_USER=your_oracle_username
DB_PASSWORD=your_oracle_password
DB_DSN=localhost:1521/XEPDB1
```

Replace the values with your own Oracle Database credentials and connection details.

Make sure your Oracle Database is running and the required tables have been created.

### 6. Run the Application

```bash
python app.py
```

Open the following URL in your browser:

```text
http://127.0.0.1:5000/
```

## Project Structure

```text
ecommerce-dashboard/
│
├── app.py
├── db.py
├── .env
├── .gitignore
├── test_connection.py
│
├── templates/
│   ├── index.html
│   ├── products.html
│   ├── customers.html
│   ├── orders.html
│   ├── payments.html
│   └── ...
│
└── static/
    └── css/
        └── style.css
```

## Key Features

- Database connectivity using Python and Oracle.
- CRUD operations (Create, Read, Update and Delete).
- Search and filtering functionality.
- Foreign key relationships between database tables.
- Inventory and stock management.
- Order and payment tracking.
- Shipment and delivery status management.
- Refund request management.

## Purpose

This project demonstrates the practical implementation of Database Management System concepts, SQL queries, relational database design and Python-based web application development.

## Author

Developed as an academic semester project.

**GitHub Repository:** [E-Commerce Order, Payment and Logistics Management System](https://github.com/piyushaether-cyber/E-Commerce