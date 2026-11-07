import oracledb
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash
from db import get_connection

app = Flask(__name__)
app.secret_key = "ecommerce_dashboard_secret_2026"

@app.route("/")
def dashboard():

    connection = get_connection()
    cursor = connection.cursor()

    # Total Customers
    cursor.execute("SELECT COUNT(*) FROM CUSTOMER")
    total_customers = cursor.fetchone()[0]

    # Total Products
    cursor.execute("SELECT COUNT(*) FROM PRODUCT")
    total_products = cursor.fetchone()[0]

    # Total Orders
    cursor.execute("SELECT COUNT(*) FROM ORDERS")
    total_orders = cursor.fetchone()[0]

    # Total Revenue
    cursor.execute("SELECT NVL(SUM(TOTAL_AMOUNT), 0) FROM ORDERS")
    total_revenue = cursor.fetchone()[0]

    # Recent Orders
    cursor.execute("""
        SELECT
            o.ORDER_ID,
            c.FIRST_NAME || ' ' || c.LAST_NAME,
            o.TOTAL_AMOUNT,
            o.ORDER_STATUS
        FROM ORDERS o
        JOIN CUSTOMER c
        ON o.CUSTOMER_ID = c.CUSTOMER_ID
        ORDER BY o.ORDER_DATE DESC
    """)

    recent_orders = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "index.html",
        total_customers=total_customers,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=total_revenue,
        recent_orders=recent_orders
    )


@app.route("/products")
def products():

    connection = get_connection()
    cursor = connection.cursor()

    # Get search and category filters
    search_term = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", type=int)

    # Fetch products with filters
    cursor.execute("""
        SELECT
            p.PRODUCT_ID,
            p.PRODUCT_NAME,
            c.CATEGORY_NAME,
            p.PRICE,
            p.SKU,
            NVL(SUM(i.QUANTITY_AVAILABLE), 0),
            NVL(SUM(i.QUANTITY_RESERVED), 0),
            p.IS_ACTIVE
        FROM PRODUCT p
        JOIN CATEGORY c
            ON p.CATEGORY_ID = c.CATEGORY_ID
        LEFT JOIN INVENTORY i
            ON p.PRODUCT_ID = i.PRODUCT_ID
        WHERE
            (:search_term IS NULL
             OR LOWER(p.PRODUCT_NAME) LIKE '%' || LOWER(:search_term) || '%')
        AND
            (:category_id IS NULL OR c.CATEGORY_ID = :category_id)
        GROUP BY
            p.PRODUCT_ID,
            p.PRODUCT_NAME,
            c.CATEGORY_NAME,
            p.PRICE,
            p.SKU,
            p.IS_ACTIVE
        ORDER BY p.PRODUCT_ID
    """,
    search_term=search_term or None,
    category_id=category_id)

    products = cursor.fetchall()

    # Fetch categories for dropdown
    cursor.execute("""
        SELECT CATEGORY_ID, CATEGORY_NAME
        FROM CATEGORY
        ORDER BY CATEGORY_NAME
    """)

    categories = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "products.html",
        products=products,
        categories=categories,
        search_term=search_term,
        selected_category=category_id
    )

@app.route("/products/add", methods=["GET", "POST"])
def add_product():

    connection = get_connection()
    cursor = connection.cursor()

    if request.method == "POST":

        try:
            product_name = request.form["product_name"].strip()
            category_id = int(request.form["category_id"])
            description = request.form["description"]
            price = float(request.form["price"])
            sku = request.form["sku"].strip()

            warehouse_id = int(request.form["warehouse_id"])
            quantity = int(request.form["quantity"])
            reorder_level = int(request.form["reorder_level"])

            # Insert product
            product_id_var = cursor.var(int)

            cursor.execute("""
                INSERT INTO PRODUCT
                (CATEGORY_ID, PRODUCT_NAME, DESCRIPTION,
                 PRICE, SKU, IS_ACTIVE, CREATED_ON)
                VALUES
                (:category_id, :product_name, :description,
                 :price, :sku, 'Y', SYSDATE)
                RETURNING PRODUCT_ID INTO :product_id
            """,
            {
                "category_id": category_id,
                "product_name": product_name,
                "description": description,
                "price": price,
                "sku": sku,
                "product_id": product_id_var
            })

            product_id = product_id_var.getvalue()[0]

            # Insert initial inventory
            cursor.execute("""
                INSERT INTO INVENTORY
                (WAREHOUSE_ID, PRODUCT_ID, QUANTITY_AVAILABLE,
                 QUANTITY_RESERVED, REORDER_LEVEL, LAST_UPDATED)
                VALUES
                (:warehouse_id, :product_id, :quantity,
                 0, :reorder_level, SYSDATE)
            """,
            {
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity": quantity,
                "reorder_level": reorder_level
            })

            connection.commit()

            return redirect(url_for("products"))

        except Exception:
            connection.rollback()
            raise

        finally:
            cursor.close()
            connection.close()

    # Fetch categories
    cursor.execute("""
        SELECT CATEGORY_ID, CATEGORY_NAME
        FROM CATEGORY
        ORDER BY CATEGORY_NAME
    """)
    categories = cursor.fetchall()

    # Fetch active warehouses
    cursor.execute("""
        SELECT WAREHOUSE_ID, WAREHOUSE_NAME, CITY
        FROM WAREHOUSE
        WHERE IS_ACTIVE = 'Y'
    """)
    warehouses = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "add_product.html",
        categories=categories,
        warehouses=warehouses
    )


@app.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            product_name = request.form["product_name"].strip()
            category_id = int(request.form["category_id"])
            description = request.form["description"]
            price = float(request.form["price"])
            sku = request.form["sku"].strip()

            cursor.execute("""
                UPDATE PRODUCT
                SET PRODUCT_NAME = :product_name,
                    CATEGORY_ID = :category_id,
                    DESCRIPTION = :description,
                    PRICE = :price,
                    SKU = :sku
                WHERE PRODUCT_ID = :product_id
            """, {
                "product_name": product_name,
                "category_id": category_id,
                "description": description,
                "price": price,
                "sku": sku,
                "product_id": product_id
            })

            if cursor.rowcount == 0:
                connection.rollback()
                return "Product not found", 404

            connection.commit()

            return redirect(url_for("products"))

        # Fetch existing product details
        cursor.execute("""
            SELECT PRODUCT_NAME, CATEGORY_ID,
                   DESCRIPTION, PRICE, SKU
            FROM PRODUCT
            WHERE PRODUCT_ID = :product_id
        """, product_id=product_id)

        product = cursor.fetchone()

        if product is None:
            return "Product not found", 404

        # Fetch categories
        cursor.execute("""
            SELECT CATEGORY_ID, CATEGORY_NAME
            FROM CATEGORY
            ORDER BY CATEGORY_NAME
        """)

        categories = cursor.fetchall()

        return render_template(
            "edit_product.html",
            product=product,
            product_id=product_id,
            categories=categories
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Delete inventory records first
        cursor.execute("""
            DELETE FROM INVENTORY
            WHERE PRODUCT_ID = :product_id
        """, product_id=product_id)

        # Delete the product
        cursor.execute("""
            DELETE FROM PRODUCT
            WHERE PRODUCT_ID = :product_id
        """, product_id=product_id)

        if cursor.rowcount == 0:
            connection.rollback()
            return "Product not found", 404

        connection.commit()
        return redirect(url_for("products"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/orders")
def orders():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                o.ORDER_ID,
                o.CUSTOMER_ID,
                c.FIRST_NAME || ' ' || c.LAST_NAME,
                o.ORDER_DATE,
                o.TOTAL_AMOUNT,
                o.ORDER_STATUS
            FROM ORDERS o
            JOIN CUSTOMER c
                ON o.CUSTOMER_ID = c.CUSTOMER_ID
            ORDER BY o.ORDER_ID DESC
        """)

        orders = cursor.fetchall()

        return render_template("orders.html", orders=orders)

    finally:
        cursor.close()
        connection.close()
@app.route("/orders/<int:order_id>")
def order_details(order_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                o.ORDER_ID,
                o.ORDER_DATE,
                o.TOTAL_AMOUNT,
                o.ORDER_STATUS,
                c.FIRST_NAME || ' ' || c.LAST_NAME
            FROM ORDERS o
            JOIN CUSTOMER c
                ON o.CUSTOMER_ID = c.CUSTOMER_ID
            WHERE o.ORDER_ID = :order_id
        """, order_id=order_id)

        order = cursor.fetchone()

        if order is None:
            return "Order not found", 404

        cursor.execute("""
            SELECT
                p.PRODUCT_NAME,
                oi.QUANTITY,
                oi.UNIT_PRICE,
                oi.QUANTITY * oi.UNIT_PRICE
            FROM ORDER_ITEM oi
            JOIN PRODUCT p
                ON oi.PRODUCT_ID = p.PRODUCT_ID
            WHERE oi.ORDER_ID = :order_id
        """, order_id=order_id)

        items = cursor.fetchall()

        return render_template(
            "order_details.html",
            order=order,
            items=items
        )

    finally:
        cursor.close()
        connection.close()

@app.route("/orders/create", methods=["GET", "POST"])
def create_order():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            customer_id = int(request.form["customer_id"])
            shipping_address_id = int(request.form["shipping_address_id"])
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])

            # Verify that the address belongs to the selected customer
            cursor.execute("""
                SELECT ADDRESS_ID
                FROM ADDRESS
                WHERE ADDRESS_ID = :address_id
                AND CUSTOMER_ID = :customer_id
            """, address_id=shipping_address_id, customer_id=customer_id)

            if cursor.fetchone() is None:
                connection.rollback()
                return "Invalid shipping address", 400

            if quantity <= 0:
                return "Quantity must be greater than zero", 400

            # Get actual product price from database
            cursor.execute("""
                SELECT PRICE
                FROM PRODUCT
                WHERE PRODUCT_ID = :product_id
                AND IS_ACTIVE = 'Y'
            """, product_id=product_id)

            product = cursor.fetchone()

            if product is None:
                return "Product not found or inactive", 404

            price = product[0]
            total_amount = price * quantity

            # Lock inventory records to prevent conflicting reservations
            cursor.execute("""
                SELECT INVENTORY_ID, QUANTITY_AVAILABLE
                FROM INVENTORY
                WHERE PRODUCT_ID = :product_id
                AND QUANTITY_AVAILABLE > 0
                ORDER BY WAREHOUSE_ID
                FOR UPDATE
            """, product_id=product_id)

            inventory_rows = cursor.fetchall()

            available_stock = sum(
                int(row[1]) for row in inventory_rows
            )

            if available_stock < quantity:
                connection.rollback()
                return "Insufficient stock available", 400

            # Create order
            order_id_var = cursor.var(oracledb.NUMBER)

            cursor.execute("""
                INSERT INTO ORDERS
                (
                    CUSTOMER_ID,
                    SHIPPING_ADDRESS_ID,
                    ORDER_DATE,
                    TOTAL_AMOUNT,
                    ORDER_STATUS
                )
                VALUES
                (
                    :customer_id,
                    :shipping_address_id,
                    SYSDATE,
                    :total_amount,
                    'PENDING'
                )
                RETURNING ORDER_ID INTO :order_id
            """,
                customer_id=customer_id,
                shipping_address_id=shipping_address_id,
                total_amount=total_amount,
                order_id=order_id_var
            )

            order_id = int(order_id_var.getvalue()[0])

            # Insert order item
            cursor.execute("""
                INSERT INTO ORDER_ITEM
                (ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE)
                VALUES
                (:order_id, :product_id, :quantity, :price)
            """,
                order_id=order_id,
                product_id=product_id,
                quantity=quantity,
                price=price
            )

            # Reserve stock from warehouses
            remaining_quantity = quantity

            for inventory_id, available in inventory_rows:

                if remaining_quantity == 0:
                    break

                allocated = min(
                    int(available),
                    remaining_quantity
                )

                cursor.execute("""
                    UPDATE INVENTORY
                    SET QUANTITY_AVAILABLE = QUANTITY_AVAILABLE - :allocated,
                        QUANTITY_RESERVED = QUANTITY_RESERVED + :allocated,
                        LAST_UPDATED = SYSDATE
                    WHERE INVENTORY_ID = :inventory_id
                """,
                    allocated=allocated,
                    inventory_id=inventory_id
                )

                remaining_quantity -= allocated

            connection.commit()

            return redirect(url_for("orders"))

        # GET: Load customers and products
        cursor.execute("""
            SELECT CUSTOMER_ID, FIRST_NAME, LAST_NAME
            FROM CUSTOMER
            ORDER BY FIRST_NAME
        """)
        customers = cursor.fetchall()

        cursor.execute("""
            SELECT PRODUCT_ID, PRODUCT_NAME, PRICE
            FROM PRODUCT
            WHERE IS_ACTIVE = 'Y'
            ORDER BY PRODUCT_NAME
        """)
        products = cursor.fetchall()

        return render_template(
            "create_order.html",
            customers=customers,
            products=products
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/customers")
def customers():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        search = request.args.get("search", "").strip()
        search_term = f"%{search}%"

        cursor.execute("""
            SELECT
                CUSTOMER_ID,
                FIRST_NAME,
                LAST_NAME,
                EMAIL,
                PHONE,
                DATE_OF_BIRTH,
                REGISTERED_ON,
                STATUS
            FROM CUSTOMER
            WHERE
                TO_CHAR(CUSTOMER_ID) LIKE :search
                OR UPPER(FIRST_NAME) LIKE UPPER(:search)
                OR UPPER(LAST_NAME) LIKE UPPER(:search)
                OR UPPER(EMAIL) LIKE UPPER(:search)
                OR PHONE LIKE :search
            ORDER BY CUSTOMER_ID DESC
        """, search=search_term)

        customer_records = cursor.fetchall()

        return render_template(
            "customers.html",
            customers=customer_records,
            search=search
        )

    finally:
        cursor.close()
        connection.close()

@app.route("/customers/add", methods=["GET", "POST"])
def add_customer():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            first_name = request.form["first_name"].strip()
            last_name = request.form.get("last_name", "").strip()
            email = request.form["email"].strip()
            phone = request.form.get("phone", "").strip()
            password = request.form["password"]
            date_of_birth = request.form.get("date_of_birth") or None

            if not first_name or not email or not password:
                return "First name, email and password are required.", 400

            password_hash = generate_password_hash(password)

            cursor.execute("""
                INSERT INTO CUSTOMER
                (
                    FIRST_NAME,
                    LAST_NAME,
                    EMAIL,
                    PHONE,
                    PASSWORD_HASH,
                    DATE_OF_BIRTH,
                    REGISTERED_ON,
                    STATUS
                )
                VALUES
                (
                    :first_name,
                    :last_name,
                    :email,
                    :phone,
                    :password_hash,
                    TO_DATE(:dob, 'YYYY-MM-DD'),
                    SYSDATE,
                    'ACTIVE'
                )
            """,
                first_name=first_name,
                last_name=last_name or None,
                email=email,
                phone=phone or None,
                password_hash=password_hash,
                dob=date_of_birth
            )

            connection.commit()
            flash("Customer added successfully!", "success")
            return redirect(url_for("customers"))

        return render_template("add_customer.html")

    except oracledb.IntegrityError:
        connection.rollback()
        flash("Email or phone number already exists.", "error")
        return redirect(url_for("add_customer"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/customers/edit/<int:customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            first_name = request.form["first_name"].strip()
            last_name = request.form.get("last_name", "").strip()
            email = request.form["email"].strip()
            phone = request.form.get("phone", "").strip()
            date_of_birth = request.form.get("date_of_birth") or None
            status = request.form["status"]

            if not first_name or not email:
                return "First name and email are required.", 400

            if status not in ("ACTIVE", "BLOCKED"):
                return "Invalid customer status.", 400

            cursor.execute("""
                UPDATE CUSTOMER
                SET FIRST_NAME = :first_name,
                    LAST_NAME = :last_name,
                    EMAIL = :email,
                    PHONE = :phone,
                    DATE_OF_BIRTH = TO_DATE(:dob, 'YYYY-MM-DD'),
                    STATUS = :status
                WHERE CUSTOMER_ID = :customer_id
            """,
                first_name=first_name,
                last_name=last_name or None,
                email=email,
                phone=phone or None,
                dob=date_of_birth,
                status=status,
                customer_id=customer_id
            )

            if cursor.rowcount == 0:
                connection.rollback()
                return "Customer not found", 404

            connection.commit()
            flash("Customer updated successfully!", "success")
            return redirect(url_for("customers"))

        cursor.execute("""
            SELECT
                CUSTOMER_ID,
                FIRST_NAME,
                LAST_NAME,
                EMAIL,
                PHONE,
                DATE_OF_BIRTH,
                STATUS
            FROM CUSTOMER
            WHERE CUSTOMER_ID = :customer_id
        """, customer_id=customer_id)

        customer = cursor.fetchone()

        if customer is None:
            return "Customer not found", 404

        return render_template(
            "edit_customer.html",
            customer=customer
        )

    except oracledb.IntegrityError:
        connection.rollback()
        flash("Email or phone number already exists.", "error")
        return redirect(url_for("edit_customer", customer_id=customer_id))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/customers/<int:customer_id>")
def customer_details(customer_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Get customer information
        cursor.execute("""
            SELECT
                CUSTOMER_ID,
                FIRST_NAME,
                LAST_NAME,
                EMAIL,
                PHONE,
                DATE_OF_BIRTH,
                REGISTERED_ON,
                STATUS
            FROM CUSTOMER
            WHERE CUSTOMER_ID = :customer_id
        """, customer_id=customer_id)

        customer = cursor.fetchone()

        if customer is None:
            return "Customer not found", 404

        # Get customer addresses
        cursor.execute("""
            SELECT
                ADDRESS_ID,
                ADDRESS_LINE1,
                ADDRESS_LINE2,
                CITY,
                STATE,
                PINCODE,
                COUNTRY,
                ADDRESS_TYPE,
                IS_DEFAULT
            FROM ADDRESS
            WHERE CUSTOMER_ID = :customer_id
        """, customer_id=customer_id)

        addresses = cursor.fetchall()

        # Get order statistics
        cursor.execute("""
            SELECT
                COUNT(*),
                NVL(SUM(TOTAL_AMOUNT), 0)
            FROM ORDERS
            WHERE CUSTOMER_ID = :customer_id
        """, customer_id=customer_id)

        order_stats = cursor.fetchone()

        # Get recent orders
        cursor.execute("""
            SELECT
                ORDER_ID,
                ORDER_DATE,
                TOTAL_AMOUNT,
                ORDER_STATUS
            FROM ORDERS
            WHERE CUSTOMER_ID = :customer_id
            ORDER BY ORDER_DATE DESC
        """, customer_id=customer_id)

        recent_orders = cursor.fetchall()

        return render_template(
            "customer_details.html",
            customer=customer,
            addresses=addresses,
            order_stats=order_stats,
            recent_orders=recent_orders
        )

    finally:
        cursor.close()
        connection.close()

@app.route("/addresses")
def addresses():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        search = request.args.get("search", "").strip()
        search_term = f"%{search}%"

        cursor.execute("""
            SELECT
                a.ADDRESS_ID,
                a.CUSTOMER_ID,
                c.FIRST_NAME || ' ' || c.LAST_NAME,
                a.ADDRESS_LINE1,
                a.CITY,
                a.STATE,
                a.PINCODE,
                a.COUNTRY,
                a.ADDRESS_TYPE,
                a.IS_DEFAULT
            FROM ADDRESS a
            JOIN CUSTOMER c
                ON a.CUSTOMER_ID = c.CUSTOMER_ID
            WHERE
                TO_CHAR(a.ADDRESS_ID) LIKE :search
                OR TO_CHAR(a.CUSTOMER_ID) LIKE :search
                OR UPPER(c.FIRST_NAME) LIKE UPPER(:search)
                OR UPPER(c.LAST_NAME) LIKE UPPER(:search)
                OR UPPER(a.CITY) LIKE UPPER(:search)
                OR a.PINCODE LIKE :search
            ORDER BY a.ADDRESS_ID DESC
        """, search=search_term)

        address_records = cursor.fetchall()

        return render_template(
            "addresses.html",
            addresses=address_records,
            search=search
        )

    finally:
        cursor.close()
        connection.close()

@app.route("/addresses/add", methods=["GET", "POST"])
def add_address():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            customer_id = int(request.form["customer_id"])
            address_line1 = request.form["address_line1"].strip()
            address_line2 = request.form.get("address_line2", "").strip()
            city = request.form["city"].strip()
            state = request.form["state"].strip()
            pincode = request.form["pincode"].strip()
            country = request.form.get("country", "").strip()
            address_type = request.form["address_type"]
            is_default = request.form["is_default"]

            if not all([address_line1, city, state, pincode]):
                return "Address, city, state and pincode are required.", 400

            if address_type not in ("HOME", "WORK", "OTHER"):
                return "Invalid address type.", 400

            if is_default not in ("Y", "N"):
                return "Invalid default address value.", 400

            # Check customer exists
            cursor.execute("""
                SELECT CUSTOMER_ID
                FROM CUSTOMER
                WHERE CUSTOMER_ID = :customer_id
            """, customer_id=customer_id)

            if cursor.fetchone() is None:
                return "Customer not found.", 404

            # Clear previous default address if needed
            if is_default == "Y":
                cursor.execute("""
                    UPDATE ADDRESS
                    SET IS_DEFAULT = 'N'
                    WHERE CUSTOMER_ID = :customer_id
                """, customer_id=customer_id)

            # Insert new address
            cursor.execute("""
                INSERT INTO ADDRESS
                (
                    CUSTOMER_ID,
                    ADDRESS_LINE1,
                    ADDRESS_LINE2,
                    CITY,
                    STATE,
                    PINCODE,
                    COUNTRY,
                    ADDRESS_TYPE,
                    IS_DEFAULT
                )
                VALUES
                (
                    :customer_id,
                    :address_line1,
                    :address_line2,
                    :city,
                    :state,
                    :pincode,
                    :country,
                    :address_type,
                    :is_default
                )
            """,
                customer_id=customer_id,
                address_line1=address_line1,
                address_line2=address_line2 or None,
                city=city,
                state=state,
                pincode=pincode,
                country=country or None,
                address_type=address_type,
                is_default=is_default
            )

            connection.commit()
            flash("Address added successfully!", "success")
            return redirect(url_for("addresses"))

        # Load customers for dropdown
        cursor.execute("""
            SELECT CUSTOMER_ID, FIRST_NAME, LAST_NAME
            FROM CUSTOMER
            ORDER BY FIRST_NAME
        """)

        customers = cursor.fetchall()

        return render_template(
            "add_address.html",
            customers=customers
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/addresses/edit/<int:address_id>", methods=["GET", "POST"])
def edit_address(address_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            address_line1 = request.form["address_line1"].strip()
            address_line2 = request.form.get("address_line2", "").strip()
            city = request.form["city"].strip()
            state = request.form["state"].strip()
            pincode = request.form["pincode"].strip()
            country = request.form.get("country", "").strip()
            address_type = request.form["address_type"]
            is_default = request.form["is_default"]

            if not all([address_line1, city, state, pincode]):
                return "Address, city, state and pincode are required.", 400

            if address_type not in ("HOME", "WORK", "OTHER"):
                return "Invalid address type.", 400

            if is_default not in ("Y", "N"):
                return "Invalid default address value.", 400

            # Find the customer who owns this address
            cursor.execute("""
                SELECT CUSTOMER_ID
                FROM ADDRESS
                WHERE ADDRESS_ID = :address_id
                FOR UPDATE
            """, address_id=address_id)

            result = cursor.fetchone()

            if result is None:
                return "Address not found.", 404

            customer_id = result[0]

            # Clear previous default address if needed
            if is_default == "Y":
                cursor.execute("""
                    UPDATE ADDRESS
                    SET IS_DEFAULT = 'N'
                    WHERE CUSTOMER_ID = :customer_id
                    AND ADDRESS_ID != :address_id
                """, customer_id=customer_id, address_id=address_id)

            # Update address
            cursor.execute("""
                UPDATE ADDRESS
                SET ADDRESS_LINE1 = :address_line1,
                    ADDRESS_LINE2 = :address_line2,
                    CITY = :city,
                    STATE = :state,
                    PINCODE = :pincode,
                    COUNTRY = :country,
                    ADDRESS_TYPE = :address_type,
                    IS_DEFAULT = :is_default
                WHERE ADDRESS_ID = :address_id
            """,
                address_line1=address_line1,
                address_line2=address_line2 or None,
                city=city,
                state=state,
                pincode=pincode,
                country=country or None,
                address_type=address_type,
                is_default=is_default,
                address_id=address_id
            )

            connection.commit()
            flash("Address updated successfully!", "success")
            return redirect(url_for("addresses"))

        # Load existing address
        cursor.execute("""
            SELECT
                ADDRESS_ID,
                CUSTOMER_ID,
                ADDRESS_LINE1,
                ADDRESS_LINE2,
                CITY,
                STATE,
                PINCODE,
                COUNTRY,
                ADDRESS_TYPE,
                IS_DEFAULT
            FROM ADDRESS
            WHERE ADDRESS_ID = :address_id
        """, address_id=address_id)

        address = cursor.fetchone()

        if address is None:
            return "Address not found.", 404

        return render_template(
            "edit_address.html",
            address=address
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/addresses/delete/<int:address_id>", methods=["POST"])
def delete_address(address_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Check whether an order uses this address
        cursor.execute("""
            SELECT COUNT(*)
            FROM ORDERS
            WHERE SHIPPING_ADDRESS_ID = :address_id
        """, address_id=address_id)

        order_count = cursor.fetchone()[0]

        if order_count > 0:
            flash(
                "Cannot delete this address because it is used by an order.",
                "error"
            )
            return redirect(url_for("addresses"))

        # Delete address
        cursor.execute("""
            DELETE FROM ADDRESS
            WHERE ADDRESS_ID = :address_id
        """, address_id=address_id)

        if cursor.rowcount == 0:
            connection.rollback()
            flash("Address not found.", "error")
            return redirect(url_for("addresses"))

        connection.commit()
        flash("Address deleted successfully!", "success")

        return redirect(url_for("addresses"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/inventory")
def inventory():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Fetch inventory records
        cursor.execute("""
            SELECT
                i.INVENTORY_ID,
                p.PRODUCT_NAME,
                w.WAREHOUSE_NAME,
                i.QUANTITY_AVAILABLE,
                i.QUANTITY_RESERVED,
                i.REORDER_LEVEL,
                i.LAST_UPDATED
            FROM INVENTORY i
            JOIN PRODUCT p
                ON i.PRODUCT_ID = p.PRODUCT_ID
            JOIN WAREHOUSE w
                ON i.WAREHOUSE_ID = w.WAREHOUSE_ID
            ORDER BY p.PRODUCT_NAME, w.WAREHOUSE_NAME
        """)

        inventory_records = cursor.fetchall()

        # Calculate total available stock
        cursor.execute("""
            SELECT NVL(SUM(QUANTITY_AVAILABLE), 0)
            FROM INVENTORY
        """)

        total_stock = cursor.fetchone()[0]

        # Count low-stock inventory records
        cursor.execute("""
            SELECT COUNT(*)
            FROM INVENTORY
            WHERE QUANTITY_AVAILABLE <= REORDER_LEVEL
        """)

        low_stock_count = cursor.fetchone()[0]

        return render_template(
            "inventory.html",
            inventory_records=inventory_records,
            total_stock=total_stock,
            low_stock_count=low_stock_count
        )

    finally:
        cursor.close()
        connection.close()
@app.route("/inventory/update", methods=["POST"])
def update_inventory():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        inventory_id = int(request.form["inventory_id"])
        quantity = int(request.form["quantity"])
        action = request.form["action"]

        if quantity <= 0:
            return "Quantity must be greater than zero", 400

        if action not in ("add", "remove"):
            return "Invalid stock adjustment", 400

        # Lock the inventory record
        cursor.execute("""
            SELECT INVENTORY_ID, QUANTITY_AVAILABLE
            FROM INVENTORY
            WHERE INVENTORY_ID = :inventory_id
            FOR UPDATE
        """, inventory_id=inventory_id)

        inventory = cursor.fetchone()

        if inventory is None:
            return "Inventory record not found", 404

        available_stock = int(inventory[1])

        if action == "remove":
            if quantity > available_stock:
                return "Cannot remove more than available stock", 400

            new_quantity = available_stock - quantity
        else:
            new_quantity = available_stock + quantity

        # Update available stock
        cursor.execute("""
            UPDATE INVENTORY
            SET QUANTITY_AVAILABLE = :quantity,
                LAST_UPDATED = SYSDATE
            WHERE INVENTORY_ID = :inventory_id
        """,
        quantity=new_quantity,
        inventory_id=inventory_id)

        connection.commit()

        flash("Stock updated successfully!", "success")

        return redirect(url_for("inventory"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
        

@app.route("/payments")
def payments():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                p.PAYMENT_ID,
                p.ORDER_ID,
                p.AMOUNT,
                p.PAYMENT_METHOD,
                p.TRANSACTION_REF,
                p.PAYMENT_STATUS,
                p.PAYMENT_DATE
            FROM PAYMENT p
            ORDER BY p.PAYMENT_ID DESC
        """)

        payment_records = cursor.fetchall()
        
        cursor.execute("""
            SELECT
                o.ORDER_ID,
                o.TOTAL_AMOUNT
            FROM ORDERS o
            WHERE NOT EXISTS (
                SELECT 1
                FROM PAYMENT p
                WHERE p.ORDER_ID = o.ORDER_ID
            )
            ORDER BY o.ORDER_ID
        """)

        unpaid_orders = cursor.fetchall()

        return render_template(
            "payments.html",
            payment_records=payment_records,
            unpaid_orders=unpaid_orders
        )
        

    finally:
        cursor.close()
        connection.close()

@app.route("/payments/create", methods=["POST"])
def record_payment():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        order_id = int(request.form["order_id"])
        payment_method = request.form["payment_method"]
        transaction_ref = request.form.get("transaction_ref", "").strip() or None
        payment_status = request.form["payment_status"]

        allowed_methods = ("CARD", "UPI", "NETBANKING", "COD", "WALLET")
        allowed_statuses = ("PENDING", "SUCCESS", "FAILED", "REFUNDED")

        if payment_method not in allowed_methods:
            return "Invalid payment method", 400

        if payment_status not in allowed_statuses:
            return "Invalid payment status", 400

        # Check whether the order exists and has no payment
        cursor.execute("""
            SELECT TOTAL_AMOUNT
            FROM ORDERS
            WHERE ORDER_ID = :order_id
            AND NOT EXISTS (
                SELECT 1
                FROM PAYMENT
                WHERE PAYMENT.ORDER_ID = ORDERS.ORDER_ID
            )
            FOR UPDATE
        """, order_id=order_id)

        order = cursor.fetchone()

        if order is None:
            return "Order not found or payment already exists", 400

        amount = order[0]

        # Insert payment
        cursor.execute("""
            INSERT INTO PAYMENT (
                ORDER_ID,
                AMOUNT,
                PAYMENT_METHOD,
                TRANSACTION_REF,
                PAYMENT_STATUS,
                PAYMENT_DATE
            )
            VALUES (
                :order_id,
                :amount,
                :payment_method,
                :transaction_ref,
                :payment_status,
                SYSDATE
            )
        """,
        order_id=order_id,
        amount=amount,
        payment_method=payment_method,
        transaction_ref=transaction_ref,
        payment_status=payment_status)

        connection.commit()

        flash("Payment recorded successfully!", "success")

        return redirect(url_for("payments"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/payments/update/<int:payment_id>", methods=["POST"])
def update_payment_status(payment_id):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        new_status = request.form["payment_status"]

        if new_status not in ("SUCCESS", "FAILED"):
            return "Invalid payment status", 400

        # Lock and check the payment
        cursor.execute("""
            SELECT ORDER_ID, PAYMENT_STATUS
            FROM PAYMENT
            WHERE PAYMENT_ID = :payment_id
            FOR UPDATE
        """, payment_id=payment_id)

        payment = cursor.fetchone()

        if payment is None:
            return "Payment not found", 404

        order_id = payment[0]
        current_status = payment[1]

        if current_status != "PENDING":
            return "Only pending payments can be updated", 400

        # Update payment status
        cursor.execute("""
            UPDATE PAYMENT
            SET PAYMENT_STATUS = :new_status
            WHERE PAYMENT_ID = :payment_id
        """,
        new_status=new_status,
        payment_id=payment_id)

        # Confirm order only after successful payment
        if new_status == "SUCCESS":
            cursor.execute("""
                UPDATE ORDERS
                SET ORDER_STATUS = 'CONFIRMED'
                WHERE ORDER_ID = :order_id
            """, order_id=order_id)

        connection.commit()

        flash("Payment status updated successfully!", "success")

        return redirect(url_for("payments"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/categories")
def categories():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        search = request.args.get("search", "").strip()
        search_term = f"%{search}%"

        cursor.execute("""
            SELECT
                c.CATEGORY_ID,
                c.CATEGORY_NAME,
                c.PARENT_CATEGORY_ID,
                p.CATEGORY_NAME,
                c.DESCRIPTION
            FROM CATEGORY c
            LEFT JOIN CATEGORY p
                ON c.PARENT_CATEGORY_ID = p.CATEGORY_ID
            WHERE
                TO_CHAR(c.CATEGORY_ID) LIKE :search
                OR UPPER(c.CATEGORY_NAME) LIKE UPPER(:search)
                OR UPPER(NVL(p.CATEGORY_NAME, '')) LIKE UPPER(:search)
            ORDER BY c.CATEGORY_ID DESC
        """, search=search_term)

        category_records = cursor.fetchall()

        return render_template(
            "categories.html",
            categories=category_records,
            search=search
        )

    finally:
        cursor.close()
        connection.close()

@app.route("/categories/add", methods=["GET", "POST"])
def add_category():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            category_name = request.form["category_name"].strip()
            parent_category_id = request.form.get("parent_category_id")
            description = request.form.get("description", "").strip()

            if not category_name:
                return "Category name is required.", 400

            # Check whether category name already exists
            cursor.execute("""
                SELECT CATEGORY_ID
                FROM CATEGORY
                WHERE UPPER(CATEGORY_NAME) = UPPER(:category_name)
            """, category_name=category_name)

            if cursor.fetchone() is not None:
                return "Category name already exists.", 400

            # Insert category
            cursor.execute("""
                INSERT INTO CATEGORY
                (CATEGORY_NAME, PARENT_CATEGORY_ID, DESCRIPTION)
                VALUES
                (:category_name, :parent_category_id, :description)
            """,
                category_name=category_name,
                parent_category_id=int(parent_category_id) if parent_category_id else None,
                description=description or None
            )

            connection.commit()
            flash("Category added successfully!", "success")

            return redirect(url_for("categories"))

        # Load existing categories for parent dropdown
        cursor.execute("""
            SELECT CATEGORY_ID, CATEGORY_NAME
            FROM CATEGORY
            ORDER BY CATEGORY_NAME
        """)

        parent_categories = cursor.fetchall()

        return render_template(
            "add_category.html",
            parent_categories=parent_categories
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/categories/edit/<int:category_id>", methods=["GET", "POST"])
def edit_category(category_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":
            category_name = request.form["category_name"].strip()
            parent_category_id = request.form.get("parent_category_id")
            description = request.form.get("description", "").strip()

            if not category_name:
                return "Category name is required.", 400

            # Prevent a category from becoming its own parent
            if parent_category_id and int(parent_category_id) == category_id:
                return "A category cannot be its own parent.", 400

            # Check duplicate category names
            cursor.execute("""
                SELECT CATEGORY_ID
                FROM CATEGORY
                WHERE UPPER(CATEGORY_NAME) = UPPER(:category_name)
                AND CATEGORY_ID != :category_id
            """, category_name=category_name, category_id=category_id)

            if cursor.fetchone():
                return "Category name already exists.", 400

            cursor.execute("""
                UPDATE CATEGORY
                SET CATEGORY_NAME = :category_name,
                    PARENT_CATEGORY_ID = :parent_category_id,
                    DESCRIPTION = :description
                WHERE CATEGORY_ID = :category_id
            """,
                category_name=category_name,
                parent_category_id=int(parent_category_id) if parent_category_id else None,
                description=description or None,
                category_id=category_id
            )

            if cursor.rowcount == 0:
                connection.rollback()
                return "Category not found.", 404

            connection.commit()
            flash("Category updated successfully!", "success")
            return redirect(url_for("categories"))

        # Fetch selected category
        cursor.execute("""
            SELECT CATEGORY_ID, CATEGORY_NAME, PARENT_CATEGORY_ID, DESCRIPTION
            FROM CATEGORY
            WHERE CATEGORY_ID = :category_id
        """, category_id=category_id)

        category = cursor.fetchone()

        if not category:
            return "Category not found.", 404

        # Fetch possible parent categories, excluding itself
        cursor.execute("""
            SELECT CATEGORY_ID, CATEGORY_NAME
            FROM CATEGORY
            WHERE CATEGORY_ID != :category_id
            ORDER BY CATEGORY_NAME
        """, category_id=category_id)

        parent_categories = cursor.fetchall()

        return render_template(
            "edit_category.html",
            category=category,
            parent_categories=parent_categories
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/categories/delete/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Check whether products use this category
        cursor.execute("""
            SELECT COUNT(*)
            FROM PRODUCT
            WHERE CATEGORY_ID = :category_id
        """, category_id=category_id)

        product_count = cursor.fetchone()[0]

        if product_count > 0:
            flash(
                "Cannot delete category because products are assigned to it.",
                "error"
            )
            return redirect(url_for("categories"))

        # Check whether child categories exist
        cursor.execute("""
            SELECT COUNT(*)
            FROM CATEGORY
            WHERE PARENT_CATEGORY_ID = :category_id
        """, category_id=category_id)

        child_count = cursor.fetchone()[0]

        if child_count > 0:
            flash(
                "Cannot delete category because it has child categories.",
                "error"
            )
            return redirect(url_for("categories"))

        # Delete category
        cursor.execute("""
            DELETE FROM CATEGORY
            WHERE CATEGORY_ID = :category_id
        """, category_id=category_id)

        if cursor.rowcount == 0:
            connection.rollback()
            flash("Category not found.", "error")
            return redirect(url_for("categories"))

        connection.commit()
        flash("Category deleted successfully!", "success")

        return redirect(url_for("categories"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/warehouses", methods=["GET", "POST"])
def warehouses():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            action = request.form["action"]

            # ADD WAREHOUSE
            if action == "add":

                cursor.execute("""
                    INSERT INTO WAREHOUSE
                    (WAREHOUSE_NAME, CITY, STATE, REGION,
                     CONTACT_PHONE, IS_ACTIVE)
                    VALUES
                    (:name, :city, :state, :region, :phone, 'Y')
                """, {
                    "name": request.form["warehouse_name"].strip(),
                    "city": request.form["city"].strip(),
                    "state": request.form["state"].strip(),
                    "region": request.form["region"],
                    "phone": request.form["contact_phone"].strip()
                })

                connection.commit()
                flash("Warehouse added successfully!", "success")

            # EDIT WAREHOUSE
            elif action == "edit":

                warehouse_id = int(request.form["warehouse_id"])

                cursor.execute("""
                    UPDATE WAREHOUSE
                    SET WAREHOUSE_NAME = :name,
                        CITY = :city,
                        STATE = :state,
                        REGION = :region,
                        CONTACT_PHONE = :phone
                    WHERE WAREHOUSE_ID = :id
                """, {
                    "name": request.form["warehouse_name"].strip(),
                    "city": request.form["city"].strip(),
                    "state": request.form["state"].strip(),
                    "region": request.form["region"],
                    "phone": request.form["contact_phone"].strip(),
                    "id": warehouse_id
                })

                connection.commit()
                flash("Warehouse updated successfully!", "success")

            # DELETE (DEACTIVATE) WAREHOUSE
            elif action == "delete":

                warehouse_id = int(request.form["warehouse_id"])

                cursor.execute("""
                    UPDATE WAREHOUSE
                    SET IS_ACTIVE = 'N'
                    WHERE WAREHOUSE_ID = :id
                """, {"id": warehouse_id})

                connection.commit()
                flash("Warehouse deactivated successfully!", "success")

            return redirect(url_for("warehouses"))

        # GET ALL WAREHOUSES
        cursor.execute("""
            SELECT WAREHOUSE_ID, WAREHOUSE_NAME, CITY,
                   STATE, REGION, CONTACT_PHONE, IS_ACTIVE
            FROM WAREHOUSE
            ORDER BY WAREHOUSE_ID
        """)

        warehouse_list = cursor.fetchall()

        # GET WAREHOUSE SELECTED FOR EDITING
        edit_id = request.args.get("edit", type=int)
        edit_warehouse = None

        if edit_id:
            cursor.execute("""
                SELECT WAREHOUSE_ID, WAREHOUSE_NAME, CITY,
                       STATE, REGION, CONTACT_PHONE
                FROM WAREHOUSE
                WHERE WAREHOUSE_ID = :id
            """, {"id": edit_id})

            edit_warehouse = cursor.fetchone()

        return render_template(
            "warehouses.html",
            warehouses=warehouse_list,
            edit_warehouse=edit_warehouse
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/shipments", methods=["GET", "POST"])
def shipments():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            action = request.form["action"]

            order_id = int(request.form["order_id"])
            warehouse_id = int(request.form["warehouse_id"])
            carrier = request.form["carrier_name"].strip()
            tracking = request.form["tracking_number"].strip() or None
            shipped_date = request.form["shipped_date"] or None
            expected_delivery = request.form["expected_delivery"] or None
            status = request.form["shipment_status"]

            # Check delivery dates
            if (shipped_date and expected_delivery
                    and expected_delivery < shipped_date):
                flash("Expected delivery cannot be before shipped date.", "error")
                return redirect(url_for("shipments"))

            # ADD SHIPMENT
            if action == "add":

                cursor.execute("""
                    INSERT INTO SHIPMENT
                    (ORDER_ID, WAREHOUSE_ID, CARRIER_NAME,
                     TRACKING_NUMBER, SHIPPED_DATE,
                     EXPECTED_DELIVERY, SHIPMENT_STATUS)
                    VALUES
                    (:order_id, :warehouse_id, :carrier,
                     :tracking, TO_DATE(:shipped_date, 'YYYY-MM-DD'),
                     TO_DATE(:expected_delivery, 'YYYY-MM-DD'), :status)
                """, {
                    "order_id": order_id,
                    "warehouse_id": warehouse_id,
                    "carrier": carrier,
                    "tracking": tracking,
                    "shipped_date": shipped_date,
                    "expected_delivery": expected_delivery,
                    "status": status
                })

                connection.commit()
                flash("Shipment added successfully!", "success")

            # EDIT SHIPMENT
            elif action == "edit":

                shipment_id = int(request.form["shipment_id"])

                cursor.execute("""
                    UPDATE SHIPMENT
                    SET ORDER_ID = :order_id,
                        WAREHOUSE_ID = :warehouse_id,
                        CARRIER_NAME = :carrier,
                        TRACKING_NUMBER = :tracking,
                        SHIPPED_DATE = TO_DATE(:shipped_date, 'YYYY-MM-DD'),
                        EXPECTED_DELIVERY =
                            TO_DATE(:expected_delivery, 'YYYY-MM-DD'),
                        SHIPMENT_STATUS = :status
                    WHERE SHIPMENT_ID = :shipment_id
                """, {
                    "order_id": order_id,
                    "warehouse_id": warehouse_id,
                    "carrier": carrier,
                    "tracking": tracking,
                    "shipped_date": shipped_date,
                    "expected_delivery": expected_delivery,
                    "status": status,
                    "shipment_id": shipment_id
                })

                connection.commit()
                flash("Shipment updated successfully!", "success")

            return redirect(url_for("shipments"))

        # DISPLAY SHIPMENTS
        cursor.execute("""
            SELECT s.SHIPMENT_ID,
                   s.ORDER_ID,
                   w.WAREHOUSE_NAME,
                   s.CARRIER_NAME,
                   s.TRACKING_NUMBER,
                   TO_CHAR(s.SHIPPED_DATE, 'YYYY-MM-DD'),
                   TO_CHAR(s.EXPECTED_DELIVERY, 'YYYY-MM-DD'),
                   s.SHIPMENT_STATUS
            FROM SHIPMENT s
            JOIN WAREHOUSE w
                ON s.WAREHOUSE_ID = w.WAREHOUSE_ID
            ORDER BY s.SHIPMENT_ID DESC
        """)

        shipment_list = cursor.fetchall()

        # FETCH ORDERS FOR DROPDOWN
        cursor.execute("""
            SELECT ORDER_ID
            FROM ORDERS
            ORDER BY ORDER_ID DESC
        """)
        order_list = cursor.fetchall()

        # FETCH WAREHOUSES FOR DROPDOWN
        cursor.execute("""
            SELECT WAREHOUSE_ID, WAREHOUSE_NAME
            FROM WAREHOUSE
            WHERE IS_ACTIVE = 'Y'
            ORDER BY WAREHOUSE_NAME
        """)
        warehouse_list = cursor.fetchall()

        # FETCH SHIPMENT FOR EDITING
        edit_id = request.args.get("edit", type=int)
        edit_shipment = None

        if edit_id:
            cursor.execute("""
                SELECT SHIPMENT_ID, ORDER_ID, WAREHOUSE_ID,
                       CARRIER_NAME, TRACKING_NUMBER,
                       TO_CHAR(SHIPPED_DATE, 'YYYY-MM-DD'),
                       TO_CHAR(EXPECTED_DELIVERY, 'YYYY-MM-DD'),
                       SHIPMENT_STATUS
                FROM SHIPMENT
                WHERE SHIPMENT_ID = :id
            """, {"id": edit_id})

            edit_shipment = cursor.fetchone()

        return render_template(
            "shipments.html",
            shipments=shipment_list,
            orders=order_list,
            warehouses=warehouse_list,
            edit_shipment=edit_shipment
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/delivery-status", methods=["GET", "POST"])
def delivery_status():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            action = request.form["action"]

            # ADD DELIVERY STATUS
            if action == "add":

                shipment_id = int(request.form["shipment_id"])
                status = request.form["status"]
                location = request.form["location"].strip() or None
                remarks = request.form["remarks"].strip() or None

                cursor.execute("""
                    INSERT INTO DELIVERY_STATUS
                    (SHIPMENT_ID, STATUS, LOCATION, STATUS_TIME, REMARKS)
                    VALUES
                    (:shipment_id, :status, :location, SYSTIMESTAMP, :remarks)
                """, {
                    "shipment_id": shipment_id,
                    "status": status,
                    "location": location,
                    "remarks": remarks
                })

                connection.commit()
                flash("Delivery status added successfully!", "success")

            # EDIT DELIVERY STATUS
            elif action == "edit":

                status_id = int(request.form["status_id"])
                shipment_id = int(request.form["shipment_id"])
                status = request.form["status"]
                location = request.form["location"].strip() or None
                remarks = request.form["remarks"].strip() or None

                cursor.execute("""
                    UPDATE DELIVERY_STATUS
                    SET SHIPMENT_ID = :shipment_id,
                        STATUS = :status,
                        LOCATION = :location,
                        STATUS_TIME = SYSTIMESTAMP,
                        REMARKS = :remarks
                    WHERE STATUS_ID = :status_id
                """, {
                    "shipment_id": shipment_id,
                    "status": status,
                    "location": location,
                    "remarks": remarks,
                    "status_id": status_id
                })

                connection.commit()
                flash("Delivery status updated successfully!", "success")

            # DELETE DELIVERY STATUS RECORD
            elif action == "delete":

                status_id = int(request.form["status_id"])

                cursor.execute("""
                    DELETE FROM DELIVERY_STATUS
                    WHERE STATUS_ID = :status_id
                """, {"status_id": status_id})

                connection.commit()
                flash("Delivery status record deleted!", "success")

            return redirect(url_for("delivery_status"))

        # FETCH DELIVERY HISTORY
        cursor.execute("""
            SELECT d.STATUS_ID,
                   d.SHIPMENT_ID,
                   s.ORDER_ID,
                   d.STATUS,
                   d.LOCATION,
                   TO_CHAR(d.STATUS_TIME, 'YYYY-MM-DD HH24:MI:SS'),
                   d.REMARKS
            FROM DELIVERY_STATUS d
            JOIN SHIPMENT s
                ON d.SHIPMENT_ID = s.SHIPMENT_ID
            ORDER BY d.STATUS_TIME DESC
        """)

        status_records = cursor.fetchall()

        # FETCH SHIPMENTS FOR DROPDOWN
        cursor.execute("""
            SELECT SHIPMENT_ID, ORDER_ID, CARRIER_NAME,
                   TRACKING_NUMBER
            FROM SHIPMENT
            ORDER BY SHIPMENT_ID DESC
        """)

        shipment_list = cursor.fetchall()

        # FETCH RECORD FOR EDITING
        edit_id = request.args.get("edit", type=int)
        edit_record = None

        if edit_id:
            cursor.execute("""
                SELECT STATUS_ID, SHIPMENT_ID, STATUS,
                       LOCATION, REMARKS
                FROM DELIVERY_STATUS
                WHERE STATUS_ID = :id
            """, {"id": edit_id})

            edit_record = cursor.fetchone()

        return render_template(
            "delivery_status.html",
            status_records=status_records,
            shipments=shipment_list,
            edit_record=edit_record
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

@app.route("/carts", methods=["GET", "POST"])
def carts():

    connection = get_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":

            action = request.form["action"]

            # CREATE CART
            if action == "add_cart":

                customer_id = int(request.form["customer_id"])

                cursor.execute("""
                    INSERT INTO CART (CUSTOMER_ID, CREATED_ON, STATUS)
                    VALUES (:customer_id, SYSDATE, 'ACTIVE')
                """, {"customer_id": customer_id})

                connection.commit()
                flash("Cart created successfully!", "success")

            # UPDATE CART STATUS
            elif action == "update_cart":

                cart_id = int(request.form["cart_id"])
                status = request.form["status"]

                cursor.execute("""
                    UPDATE CART
                    SET STATUS = :status
                    WHERE CART_ID = :cart_id
                """, {
                    "status": status,
                    "cart_id": cart_id
                })

                connection.commit()
                flash("Cart status updated!", "success")

            # ADD PRODUCT TO CART
            elif action == "add_item":

                cart_id = int(request.form["cart_id"])
                product_id = int(request.form["product_id"])
                quantity = int(request.form["quantity"])

                if quantity <= 0:
                    flash("Quantity must be greater than zero.", "error")
                    return redirect(url_for("carts"))

                cursor.execute("""
                    SELECT STATUS
                    FROM CART
                    WHERE CART_ID = :cart_id
                """, {"cart_id": cart_id})

                cart = cursor.fetchone()

                if not cart or cart[0] != "ACTIVE":
                    flash("Products can only be added to active carts.", "error")
                    return redirect(url_for("carts"))

                cursor.execute("""
                    INSERT INTO CART_ITEM
                    (CART_ID, PRODUCT_ID, QUANTITY, ADDED_ON)
                    VALUES (:cart_id, :product_id, :quantity, SYSDATE)
                """, {
                    "cart_id": cart_id,
                    "product_id": product_id,
                    "quantity": quantity
                })

                connection.commit()
                flash("Product added to cart!", "success")

            # EDIT CART ITEM QUANTITY
            elif action == "edit_item":

                item_id = int(request.form["cart_item_id"])
                quantity = int(request.form["quantity"])

                if quantity <= 0:
                    flash("Quantity must be greater than zero.", "error")
                    return redirect(url_for("carts"))

                cursor.execute("""
                    UPDATE CART_ITEM
                    SET QUANTITY = :quantity
                    WHERE CART_ITEM_ID = :item_id
                    AND CART_ID IN (
                        SELECT CART_ID
                        FROM CART
                        WHERE STATUS = 'ACTIVE'
                    )
                """, {
                    "quantity": quantity,
                    "item_id": item_id
                })

                connection.commit()
                flash("Cart item quantity updated!", "success")

            # DELETE CART ITEM
            elif action == "delete_item":

                item_id = int(request.form["cart_item_id"])

                cursor.execute("""
                    DELETE FROM CART_ITEM
                    WHERE CART_ITEM_ID = :item_id
                    AND CART_ID IN (
                        SELECT CART_ID
                        FROM CART
                        WHERE STATUS = 'ACTIVE'
                    )
                """, {"item_id": item_id})

                connection.commit()
                flash("Cart item removed!", "success")

            # DELETE CART AND ITS ITEMS
            elif action == "delete_cart":

                cart_id = int(request.form["cart_id"])

                cursor.execute("""
                    DELETE FROM CART_ITEM
                    WHERE CART_ID = :cart_id
                """, {"cart_id": cart_id})

                cursor.execute("""
                    DELETE FROM CART
                    WHERE CART_ID = :cart_id
                """, {"cart_id": cart_id})

                connection.commit()
                flash("Cart and its items deleted!", "success")

            return redirect(url_for("carts"))

        # FETCH ALL CARTS
        cursor.execute("""
            SELECT CART_ID, CUSTOMER_ID,
                   TO_CHAR(CREATED_ON, 'YYYY-MM-DD'),
                   STATUS
            FROM CART
            ORDER BY CART_ID DESC
        """)

        cart_list = cursor.fetchall()

        # FETCH ALL CART ITEMS
        cursor.execute("""
            SELECT CART_ITEM_ID, CART_ID, PRODUCT_ID,
                   QUANTITY,
                   TO_CHAR(ADDED_ON, 'YYYY-MM-DD')
            FROM CART_ITEM
            ORDER BY CART_ITEM_ID DESC
        """)

        item_list = cursor.fetchall()

        # FETCH CUSTOMERS FOR DROPDOWN
        cursor.execute("""
            SELECT CUSTOMER_ID
            FROM CUSTOMER
            ORDER BY CUSTOMER_ID
        """)

        customer_list = cursor.fetchall()

        # FETCH PRODUCTS FOR DROPDOWN
        cursor.execute("""
            SELECT PRODUCT_ID
            FROM PRODUCT
            ORDER BY PRODUCT_ID
        """)

        product_list = cursor.fetchall()

        # FETCH ACTIVE CARTS FOR ADD ITEM DROPDOWN
        cursor.execute("""
            SELECT CART_ID, CUSTOMER_ID
            FROM CART
            WHERE STATUS = 'ACTIVE'
            ORDER BY CART_ID DESC
        """)

        active_carts = cursor.fetchall()

        return render_template(
            "carts.html",
            carts=cart_list,
            items=item_list,
            customers=customer_list,
            products=product_list,
            active_carts=active_carts
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
        
# REFUND MANAGEMENT
@app.route("/refunds")
def refunds():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Get all refund records
        cursor.execute("""
            SELECT
                r.REFUND_ID,
                r.PAYMENT_ID,
                r.ORDER_ID,
                r.REFUND_AMOUNT,
                r.REASON,
                r.REFUND_STATUS,
                r.REFUND_DATE
            FROM REFUND r
            ORDER BY r.REFUND_ID DESC
        """)
        refund_records = cursor.fetchall()

        # Only successful payments can be selected for refunds
        cursor.execute("""
            SELECT PAYMENT_ID, ORDER_ID, AMOUNT
            FROM PAYMENT
            WHERE PAYMENT_STATUS = 'SUCCESS'
            ORDER BY PAYMENT_ID DESC
        """)
        successful_payments = cursor.fetchall()

        return render_template(
            "refunds.html",
            refund_records=refund_records,
            successful_payments=successful_payments
        )

    finally:
        cursor.close()
        connection.close()


# ADD REFUND
@app.route("/refunds/add", methods=["POST"])
def add_refund():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        payment_id = int(request.form["payment_id"])
        refund_amount = float(request.form["refund_amount"])
        reason = request.form["reason"].strip()

        if refund_amount <= 0:
            flash("Refund amount must be greater than zero.", "error")
            return redirect(url_for("refunds"))

        if not reason:
            flash("Please enter a refund reason.", "error")
            return redirect(url_for("refunds"))

        # Get the order and original payment amount
        cursor.execute("""
            SELECT ORDER_ID, AMOUNT
            FROM PAYMENT
            WHERE PAYMENT_ID = :payment_id
            AND PAYMENT_STATUS = 'SUCCESS'
        """, payment_id=payment_id)

        payment = cursor.fetchone()

        if payment is None:
            flash("Please select a valid successful payment.", "error")
            return redirect(url_for("refunds"))

        order_id = payment[0]
        payment_amount = payment[1]

        if refund_amount > payment_amount:
            flash("Refund cannot exceed the payment amount.", "error")
            return redirect(url_for("refunds"))

        # Insert refund; Oracle generates REFUND_ID
        cursor.execute("""
            INSERT INTO REFUND (
                PAYMENT_ID,
                ORDER_ID,
                REFUND_AMOUNT,
                REASON,
                REFUND_STATUS,
                REFUND_DATE
            )
            VALUES (
                :payment_id,
                :order_id,
                :refund_amount,
                :reason,
                'REQUESTED',
                SYSDATE
            )
        """,
        payment_id=payment_id,
        order_id=order_id,
        refund_amount=refund_amount,
        reason=reason)

        connection.commit()
        flash("Refund added successfully!", "success")

        return redirect(url_for("refunds"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# EDIT REFUND
@app.route("/refunds/update/<int:refund_id>", methods=["POST"])
def update_refund(refund_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        refund_amount = float(request.form["refund_amount"])
        reason = request.form["reason"].strip()
        refund_status = request.form["refund_status"]

        allowed_statuses = (
            "REQUESTED",
            "APPROVED",
            "PROCESSED",
            "REJECTED"
        )

        if refund_amount <= 0:
            flash("Refund amount must be greater than zero.", "error")
            return redirect(url_for("refunds"))

        if not reason:
            flash("Refund reason cannot be empty.", "error")
            return redirect(url_for("refunds"))

        if refund_status not in allowed_statuses:
            flash("Invalid refund status.", "error")
            return redirect(url_for("refunds"))

        # Check original payment amount
        cursor.execute("""
            SELECT p.AMOUNT
            FROM REFUND r
            JOIN PAYMENT p ON r.PAYMENT_ID = p.PAYMENT_ID
            WHERE r.REFUND_ID = :refund_id
        """, refund_id=refund_id)

        payment = cursor.fetchone()

        if payment is None:
            flash("Refund not found.", "error")
            return redirect(url_for("refunds"))

        if refund_amount > payment[0]:
            flash("Refund cannot exceed the payment amount.", "error")
            return redirect(url_for("refunds"))

        cursor.execute("""
            UPDATE REFUND
            SET REFUND_AMOUNT = :refund_amount,
                REASON = :reason,
                REFUND_STATUS = :refund_status
            WHERE REFUND_ID = :refund_id
        """,
        refund_amount=refund_amount,
        reason=reason,
        refund_status=refund_status,
        refund_id=refund_id)

        connection.commit()
        flash("Refund updated successfully!", "success")

        return redirect(url_for("refunds"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# DELETE REFUND
@app.route("/refunds/delete/<int:refund_id>", methods=["POST"])
def delete_refund(refund_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            DELETE FROM REFUND
            WHERE REFUND_ID = :refund_id
        """, refund_id=refund_id)

        if cursor.rowcount == 0:
            flash("Refund not found.", "error")
        else:
            connection.commit()
            flash("Refund deleted successfully!", "success")

        return redirect(url_for("refunds"))

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    app.run(debug=True)
