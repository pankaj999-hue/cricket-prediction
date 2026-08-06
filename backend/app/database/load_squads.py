import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DATABASE_URL

SQUADS = {
    "Trinbago Knight Riders": [
        "Nicholas Pooran", "Kieron Pollard", "Sunil Narine", "Akeal Hosein",
        "Alex Hales", "Colin Munro", "Joshua Da Silva", "Justin Greaves",
        "Jyd Goolie", "Dominic Drakes", "Terrance Hinds", "Matthew Breetzke",
        "Usman Tariq", "Dexter Sween", "Nathan Edward", "Abdul-Raheem Toppin",
        "Amshi de Silva"
    ],
    "Barbados Tridents": [
        "Quinton de Kock", "Brandon King", "Gudakesh Motie", "Sherfane Rutherford",
        "Daniel Sams", "Mujeeb Ur Rahman", "Chris Green", "George Linde",
        "Shadrack Descarte", "Kadeem Alleyne", "Ramon Simmonds", "Zishan Motara",
        "Johann Layne", "Kofi James", "Jakeem Pollard", "Zachary Carter", "Rivaldo Clarke"
    ],
    "Jamaica Kingsmen": [
        "Rovman Powell", "Andre Russell", "Saim Ayub", "Usman Khan",
        "Maaz Sadaqat", "Keemo Paul", "Odean Smith", "Keacy Carty",
        "Jeavor Royal", "Hassan Khan", "Shayan Jahangir", "Romaine Morris",
        "Kirk McKenzie", "Hunain Shah", "Tayyab Arif", "Jediah Blades",
        "Kelvin Pitman", "Shaqkere Parris", "Vitel Orlando Lawes"
    ],
    "Antigua and Barbuda Falcons": [
        "Imad Wasim", "Moeen Ali", "Kusal Perera", "Shakib Al Hasan",
        "Shadab Khan", "Evin Lewis", "Alzarri Joseph", "Fabian Allen",
        "Rahkeem Cornwall", "Jayden Seales", "Shamar Springer", "Sufyan Muqeem",
        "Milind Kumar", "Tajinder Singh", "Jahmar Hamilton", "Anderson Phillip",
        "Anderson Mahase", "Amir Jangoo", "Karima Gore", "Joshua James",
        "Jewel Andrew", "Allah Mohammad Ghazanfar", "Usama Mir", "Aaron Gous",
        "Salman Irshad", "Brandon Jacobs"
    ],
    "Guyana Amazon Warriors": [
        "Imran Tahir", "Shimron Hetmyer", "Romario Shepherd", "Shai Hope",
        "Glenn Phillips", "Rahmanullah Gurbaz", "Mohammad Nabi", "Dwaine Pretorius",
        "Veerasammy Permaul", "Khary Pierre", "Shamar Joseph", "Ronaldo Alimohamed",
        "Matthew Nandu", "Mavendra Dindyal", "Jonathan van Lange", "Isai Thorne",
        "Quentin Sampson"
    ],
    "St Lucia Kings": [
        "Roston Chase", "Matthew Forde", "Alzarri Joseph", "Tim Seifert",
        "Noor Ahmad", "Maheesh Theekshana", "Charith Asalanka", "Sarel van Schalkwyk",
        "Joshua Bishop", "Damion Joachim", "Darron Nedd", "Kamil Pooran",
        "Amari Goodridge", "Keon Gaston", "McKenny Clarke", "Ackeem Auguste",
        "Johann Jeremiah", "Jewel Andrew"
    ],
    "St Kitts and Nevis Patriots": [
        "Kyle Mayers", "Jason Holder", "Wanindu Hasaranga", "Dasun Shanaka",
        "Naseem Shah", "Mujeeb Ur Rahman Salamkheil", "Johnson Charles", "Andre Fletcher",
        "Oshane McCoy", "Alick Athanaze", "Mikyle Louis", "Jeremiah Louis",
        "Ashmead Nedd", "Navin Chaudhary", "Kevin Wickham", "Micah Mckenzie",
        "Nathan Bidaisee"
    ],
}

def load_squads():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    for team, players in SQUADS.items():
        for player in players:
            cursor.execute("""
                INSERT INTO squads (team, player_name, season, league)
                VALUES (%s, %s, '2026', 'CPL')
                ON CONFLICT (team, player_name, season, league) DO NOTHING
            """, (team, player))
        print(f"✅ Loaded {len(players)} players for {team}")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("\n🎉 All CPL 2026 squads loaded!")

if __name__ == "__main__":
    load_squads()