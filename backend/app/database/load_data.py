import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import psycopg2
from pathlib import Path
from config import DATABASE_URL

# Path to your JSON files
DATA_FOLDER = r"D:\websiteds\malik-india\cricket-prediction\data\ipl_json"

def clean_player_name(name):
    """Ensure consistent player names"""
    return name.strip() if name else None

def normalize_venue(venue_name):
    """Map all IPL venue name variations to a standard name"""
    if not venue_name:
        return venue_name
    
    v = venue_name.lower()
    
    if 'wankhede' in v:
        return 'Wankhede Stadium, Mumbai'
    if 'brabourne' in v:
        return 'Brabourne Stadium, Mumbai'
    if 'dy patil' in v:
        return 'DY Patil Stadium, Navi Mumbai'
    if 'chinnaswamy' in v:
        return 'M Chinnaswamy Stadium, Bengaluru'
    if 'chepauk' in v or 'chidambaram' in v:
        return 'MA Chidambaram Stadium, Chepauk, Chennai'
    if 'eden' in v:
        return 'Eden Gardens, Kolkata'
    if 'arun' in v or 'kotla' in v or 'feroz' in v:
        return 'Arun Jaitley Stadium, Delhi'
    if 'rajiv gandhi' in v or 'uppal' in v:
        return 'Rajiv Gandhi International Stadium, Hyderabad'
    if 'narendra modi' in v or 'motera' in v:
        return 'Narendra Modi Stadium, Ahmedabad'
    if 'sawai' in v or 'mansingh' in v:
        return 'Sawai Mansingh Stadium, Jaipur'
    if 'mohali' in v or 'punjab cricket' in v or 'pca' in v:
        return 'Punjab Cricket Association Stadium, Mohali'
    if 'maharaja yadavindra' in v or 'new chandigarh' in v:
        return 'Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh'
    if 'ekana' in v or 'atal bihari' in v:
        return 'BRSABV Ekana Cricket Stadium, Lucknow'
    if 'dharamsala' in v or 'hpca' in v:
        return 'HPCA Stadium, Dharamsala'
    if 'guwahati' in v or 'barsapara' in v:
        return 'Barsapara Cricket Stadium, Guwahati'
    if 'indore' in v or 'holkar' in v:
        return 'Holkar Cricket Stadium, Indore'
    if 'raipur' in v or 'shaheed' in v:
        return 'Shaheed Veer Narayan Singh International Stadium, Raipur'
    if 'ranchi' in v or 'jsca' in v:
        return 'JSCA International Stadium Complex, Ranchi'
    if 'visakhapatnam' in v or 'vizag' in v or 'dr ys' in v:
        return 'Dr YS Rajasekhara Reddy Cricket Stadium, Visakhapatnam'
    if 'pune' in v or 'maharashtra cricket' in v or 'mca' in v:
        return 'Maharashtra Cricket Association Stadium, Pune'
    if 'thiruvananthapuram' in v or 'trivandrum' in v or 'greenfield' in v:
        return 'Greenfield International Stadium, Thiruvananthapuram'
    if 'cuttack' in v or 'barabati' in v:
        return 'Barabati Stadium, Cuttack'
    if 'dehradun' in v:
        return 'Rajiv Gandhi International Cricket Stadium, Dehradun'
    if 'kochi' in v or 'jawaharlal' in v:
        return 'Jawaharlal Nehru Stadium, Kochi'
    if 'nagpur' in v or 'vidarbha' in v or 'vca' in v:
        return 'Vidarbha Cricket Association Stadium, Nagpur'
    if 'dubai' in v:
        return 'Dubai International Cricket Stadium, Dubai'
    if 'abu dhabi' in v:
        return 'Sheikh Zayed Stadium, Abu Dhabi'
    if 'sharjah' in v:
        return 'Sharjah Cricket Stadium, Sharjah'
    if 'green park' in v:
        return 'Green Park, Kanpur'
    if 'nehru' in v:
        return 'Nehru Stadium, Kochi'
    if 'saurashtra' in v:
        return 'Saurashtra Cricket Association Stadium, Rajkot'
    if 'sahara' in v:
        return 'Subrata Roy Sahara Stadium, Pune'
    
    return venue_name

def parse_match(file_path):
    """Extract match info from a single JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    info = data.get("info", {})
    
    
    # Extract match info
    match = {
        "match_id": file_path.stem,
        "season": info.get("season", ""),
        "date": info.get("dates", [None])[0],
        "format": info.get("match_type", "T20"),
        "event": info.get("event", {}).get("name", ""),
        "stage": info.get("event", {}).get("stage", ""),
        "venue": normalize_venue(info.get("venue", "")),
        "city": info.get("city", ""),
        "team_a": info.get("teams", [None, None])[0],
        "team_b": info.get("teams", [None, None])[1],
        "toss_winner": info.get("toss", {}).get("winner"),
        "toss_decision": info.get("toss", {}).get("decision"),
        "winner": info.get("outcome", {}).get("winner"),
        "win_margin": list(info.get("outcome", {}).get("by", {}).values())[0] if info.get("outcome", {}).get("by") else None,
        "win_type": list(info.get("outcome", {}).get("by", {}).keys())[0] if info.get("outcome", {}).get("by") else None,
        "player_of_match": info.get("player_of_match", [None])[0]
    }
    
    return match, data

def parse_deliveries(match_id, data):
    
    """Extract all deliveries from a match"""
    deliveries = []
    registry = data.get("info", {}).get("registry", {}).get("people", {})
    
    for innings_num, innings in enumerate(data.get("innings", []), 1):
        batting_team = innings.get("team", "")
        bowling_team = ""  # Will determine from opposition
        
        for over_data in innings.get("overs", []):
            over_num = over_data.get("over", 0)
            
            for ball in over_data.get("deliveries", []):
                batter = clean_player_name(ball.get("batter", ""))
                bowler = clean_player_name(ball.get("bowler", ""))
                
                delivery = {
                    "match_id": match_id,
                    "innings": innings_num,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,  # Will update later
                    "over_num": over_num,
                    "ball_num": ball.get("actual_delivery", ""),
                    "batter": batter,
                    "batter_id": registry.get(batter),
                    "bowler": bowler,
                    "bowler_id": registry.get(bowler),
                    "non_striker": clean_player_name(ball.get("non_striker")),
                    "runs_batter": ball.get("runs", {}).get("batter", 0),
                    "runs_extras": ball.get("runs", {}).get("extras", 0),
                    "runs_total": ball.get("runs", {}).get("total", 0),
                    "is_wicket": "wickets" in ball,
                    "wicket_kind": ball.get("wickets", [{}])[0].get("kind") if "wickets" in ball else None,
                    "player_out": clean_player_name(ball.get("wickets", [{}])[0].get("player_out")) if "wickets" in ball else None,
                    "is_wide": "wides" in ball.get("extras", {}),
                    "is_noball": "noballs" in ball.get("extras", {}),
                    "is_bye": "byes" in ball.get("extras", {}),
                    "is_legbye": "legbyes" in ball.get("extras", {})
                }
                deliveries.append(delivery)
    
    return deliveries

def get_unique_players(data):
    """Extract all players from match registry"""
    registry = data.get("info", {}).get("registry", {}).get("people", {})
    players_data = data.get("info", {}).get("players", {})
    
    players = []
    for name, player_id in registry.items():
        # Check if this person is actually a player (appears in playing XI)
        is_player = False
        for team, squad in players_data.items():
            if name in squad:
                is_player = True
                break
        
        if is_player:
            players.append({
                "player_id": player_id,
                "name": name
            })
    
    return players

def load_all_data(data_folder, conn):
    """Main function to load everything"""
    cursor = conn.cursor()
    
    json_files = list(Path(data_folder).glob("*.json"))
    total = len(json_files)
    
    print(f"Found {total} match files to process...")
    
    for i, file_path in enumerate(json_files, 1):
        match_id = file_path.stem
        
        # Skip if already loaded
        cursor.execute("SELECT match_id FROM matches WHERE match_id = %s", (match_id,))
        if cursor.fetchone():
            print(f"[{i}/{total}] Skipping {match_id} - already loaded")
            continue
        
        try:
            # Parse match and deliveries
            match, raw_data = parse_match(file_path)
            deliveries = parse_deliveries(match_id, raw_data)
            players = get_unique_players(raw_data)
            
            # Determine bowling team for each innings
            teams = [match["team_a"], match["team_b"]]
            for d in deliveries:
                d["bowling_team"] = teams[0] if d["batting_team"] == teams[1] else teams[1]
            
            # Insert match
            cursor.execute("""
                INSERT INTO matches (match_id, season, date, format, event, stage, venue, city, 
                    team_a, team_b, toss_winner, toss_decision, winner, win_margin, win_type, player_of_match)
                VALUES (%(match_id)s, %(season)s, %(date)s, %(format)s, %(event)s, %(stage)s, %(venue)s, %(city)s,
                    %(team_a)s, %(team_b)s, %(toss_winner)s, %(toss_decision)s, %(winner)s, %(win_margin)s, %(win_type)s, %(player_of_match)s)
                ON CONFLICT (match_id) DO NOTHING
            """, match)
            
            # Insert players
            for player in players:
                cursor.execute("""
                    INSERT INTO players (player_id, name)
                    VALUES (%(player_id)s, %(name)s)
                    ON CONFLICT (player_id) DO NOTHING
                """, player)
            
            # Insert deliveries
            for d in deliveries:
                cursor.execute("""
                    INSERT INTO deliveries (match_id, innings, batting_team, bowling_team, over_num, ball_num,
                        batter, batter_id, bowler, bowler_id, non_striker, runs_batter, runs_extras, runs_total,
                        is_wicket, wicket_kind, player_out, is_wide, is_noball, is_bye, is_legbye)
                    VALUES (%(match_id)s, %(innings)s, %(batting_team)s, %(bowling_team)s, %(over_num)s, %(ball_num)s,
                        %(batter)s, %(batter_id)s, %(bowler)s, %(bowler_id)s, %(non_striker)s, %(runs_batter)s, %(runs_extras)s, %(runs_total)s,
                        %(is_wicket)s, %(wicket_kind)s, %(player_out)s, %(is_wide)s, %(is_noball)s, %(is_bye)s, %(is_legbye)s)
                """, d)
            
            conn.commit()
            print(f"[{i}/{total}] ✅ Loaded {match_id} - {match['team_a']} vs {match['team_b']} ({match['date']})")
            
        except Exception as e:
            conn.rollback()
            print(f"[{i}/{total}] ❌ Error on {match_id}: {e}")
    
    cursor.close()
    print("\n🎉 Data loading complete!")

if __name__ == "__main__":
    conn = psycopg2.connect(DATABASE_URL)
    load_all_data(DATA_FOLDER, conn)
    conn.close()