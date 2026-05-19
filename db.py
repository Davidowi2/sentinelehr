import os 
from dotenv import load_dotenv 
import psycopg2 
from psycopg2.extras import RealDictCursor 
 
load_dotenv() 
 
DATABASE_URL = os.getenv("DATABASE_URL") 
 
def get_connection(): 
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) 
    return conn 
