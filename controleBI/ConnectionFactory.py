
import os
from dotenv import load_dotenv


#Carrega as variaveis de ambiente arquivo .env
load_dotenv()

user = os.getenv('USER_ERP')
password = os.getenv('PASSWORD_ERP')
dsn= os.getenv('HOST_ERP')
port= os.getenv('PORT_ERP')
database = os.getenv('DATABASE_ERP')
encoding = os.getenv('ENCODING')


con = cf.connect(user=user, password=password, dsn=dsn, encoding=encoding, port=port)

def queryColumns(sql, db):
    cursor = con.cursor()
    data = cursor.execute(sql)
    List = data.fetchall()
    cursor.close()
    return List

def query(sql, bd):
    cursor = con.cursor()
    cursor.execute(sql)
    cursor.close()


def getAll(sql, bd):
    if bd == 'sdb':
        cursor = con_sdb.cursor()
    elif bd == 'udb':
        cursor = con_udb.cursor()
    else:
        cursor = con_e360.cursor()

    data = cursor.execute(sql)
    List = data.fetchall()
    cursor.close()
    return List

def execProc(sql, lista, bd):
    cursor = con_sdb.cursor() if bd == 'sdb' else con_udb.cursor()
    data = cursor.callproc(sql,lista)
    cursor.close()
    return
