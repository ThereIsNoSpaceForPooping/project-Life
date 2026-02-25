import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Fetch variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

print(f"尝试连接: {HOST}:{PORT} as {USER}")

# Connect to the database
try:
    connection = psycopg2.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        sslmode='require' # Supabase 通常需要 SSL
    )
    print("Connection successful!")
    
    # Create a cursor to execute SQL queries
    cursor = connection.cursor()
    
    # 1. 打印当前时间
    cursor.execute("SELECT NOW();")
    result = cursor.fetchone()
    print("Current Time:", result)

    # 2. 查询库里有什么表 (用户关心的问题)
    print("\n正在查询公开表列表...")
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    if tables:
        print(f"找到以下表:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table[0]}")
    else:
        print("未发现公开表 (或者表为空)")

    # Close the cursor and connection
    cursor.close()
    connection.close()
    print("\nConnection closed.")

except Exception as e:
    print(f"Failed to connect: {e}")
