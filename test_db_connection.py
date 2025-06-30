import mysql.connector
from mysql.connector import Error
import os

connection = None
cursor = None

try:
    print("Attempting to connect to RDS...")
    connection = mysql.connector.connect(
        host='database-stg.c560swayadiu.eu-north-1.rds.amazonaws.com',
        user='admin',
        password='Qsys160w',
        port=3306,
        connection_timeout=30,
        autocommit=True
    )
    
    if connection.is_connected():
        db_info = connection.get_server_info()
        print(f"Successfully connected to MySQL Server version {db_info}")
        
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES;")
        databases = cursor.fetchall()
        print("Available databases:")
        for db in databases:
            print(f"  - {db[0]}")
            
except Error as e:
    print(f"Error while connecting to MySQL: {e}")
    print("This is likely a network connectivity issue.")
    
finally:
    if connection and connection.is_connected():
        if cursor:
            cursor.close()
        connection.close()
        print("MySQL connection is closed")
    else:
        print("No connection was established")
