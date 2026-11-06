from db import get_connection

connection = get_connection()
cursor = connection.cursor()

cursor.execute("SELECT COUNT(*) FROM CUSTOMER")

count = cursor.fetchone()[0]

print("Total customers:", count)

cursor.close()
connection.close()