import oracledb
from flask import Flask, render_template, request, redirect, url_for
from db import get_connection

app = Flask(__name__)

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
if __name__ == "__main__":
    app.run(debug=True)
