import parser # Сама программа
import sqlite3 # Для работы с БД

file = sqlite3.connect('test.db')
parser.parce(file)
