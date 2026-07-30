import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DATABASE_URL

def refresh_all():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Refreshing aggregation tables...")
    
    # 1. Player Career Stats
    print("[1/8] Player career stats...")
    cursor.execute("""
        INSERT INTO player_career_stats (player_id, matches_played, innings_batted, 
            total_runs, balls_faced, batting_average, strike_rate, 
            fifties, hundreds, highest_score, wickets_taken, 
            bowling_average, economy_rate, bowling_strike_rate)
        
        WITH batting AS (
            SELECT 
                batter_id as player_id,
                COUNT(DISTINCT match_id) as matches_played,
                COUNT(DISTINCT CONCAT(match_id, '_', innings)) as innings_batted,
                SUM(runs_batter) as total_runs,
                COUNT(*) as balls_faced,
                CASE WHEN COUNT(CASE WHEN is_wicket AND player_out = batter THEN 1 END) > 0 
                     THEN SUM(runs_batter) * 1.0 / COUNT(CASE WHEN is_wicket AND player_out = batter THEN 1 END)
                     ELSE SUM(runs_batter) * 1.0 
                END as batting_average,
                SUM(runs_batter) * 100.0 / NULLIF(COUNT(*), 0) as strike_rate,
                COUNT(CASE WHEN runs_batter >= 50 THEN 1 END) as fifties,
                COUNT(CASE WHEN runs_batter >= 100 THEN 1 END) as hundreds,
                MAX(runs_batter) as highest_score
            FROM deliveries
            GROUP BY batter_id
        ),
        bowling AS (
            SELECT 
                bowler_id as player_id,
                COUNT(CASE WHEN is_wicket AND wicket_kind NOT IN ('run out') THEN 1 END) as wickets_taken,
                CASE WHEN COUNT(CASE WHEN is_wicket AND wicket_kind NOT IN ('run out') THEN 1 END) > 0
                     THEN SUM(runs_total) * 1.0 / COUNT(CASE WHEN is_wicket AND wicket_kind NOT IN ('run out') THEN 1 END)
                     ELSE NULL
                END as bowling_average,
                SUM(runs_total) * 6.0 / NULLIF(COUNT(*), 0) as economy_rate,
                CASE WHEN COUNT(CASE WHEN is_wicket AND wicket_kind NOT IN ('run out') THEN 1 END) > 0
                     THEN COUNT(*) * 1.0 / COUNT(CASE WHEN is_wicket AND wicket_kind NOT IN ('run out') THEN 1 END)
                     ELSE NULL
                END as bowling_strike_rate
            FROM deliveries
            GROUP BY bowler_id
        )
        SELECT 
            COALESCE(b.player_id, w.player_id) as player_id,
            COALESCE(b.matches_played, 0),
            COALESCE(b.innings_batted, 0),
            COALESCE(b.total_runs, 0),
            COALESCE(b.balls_faced, 0),
            b.batting_average,
            b.strike_rate,
            COALESCE(b.fifties, 0),
            COALESCE(b.hundreds, 0),
            COALESCE(b.highest_score, 0),
            COALESCE(w.wickets_taken, 0),
            w.bowling_average,
            w.economy_rate,
            w.bowling_strike_rate
        FROM batting b
        FULL OUTER JOIN bowling w ON b.player_id = w.player_id
        ON CONFLICT (player_id) DO UPDATE SET
            matches_played = EXCLUDED.matches_played,
            innings_batted = EXCLUDED.innings_batted,
            total_runs = EXCLUDED.total_runs,
            balls_faced = EXCLUDED.balls_faced,
            batting_average = EXCLUDED.batting_average,
            strike_rate = EXCLUDED.strike_rate,
            fifties = EXCLUDED.fifties,
            hundreds = EXCLUDED.hundreds,
            highest_score = EXCLUDED.highest_score,
            wickets_taken = EXCLUDED.wickets_taken,
            bowling_average = EXCLUDED.bowling_average,
            economy_rate = EXCLUDED.economy_rate,
            bowling_strike_rate = EXCLUDED.bowling_strike_rate,
            updated_at = NOW()
    """)
    conn.commit()
    
    # 2. Player Venue Stats
    print("[2/8] Player venue stats...")
    cursor.execute("""
        INSERT INTO player_venue_stats (player_id, venue, matches_played, innings_batted,
            total_runs, balls_faced, batting_average, strike_rate, wickets_taken, economy_rate)
        
        WITH batting_venue AS (
            SELECT 
                d.batter_id as player_id,
                m.venue,
                COUNT(DISTINCT d.match_id) as matches_played,
                COUNT(DISTINCT CONCAT(d.match_id, '_', d.innings)) as innings_batted,
                SUM(d.runs_batter) as total_runs,
                COUNT(*) as balls_faced,
                CASE WHEN COUNT(CASE WHEN d.is_wicket AND d.player_out = d.batter THEN 1 END) > 0
                     THEN SUM(d.runs_batter) * 1.0 / COUNT(CASE WHEN d.is_wicket AND d.player_out = d.batter THEN 1 END)
                     ELSE SUM(d.runs_batter) * 1.0
                END as batting_average,
                SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(*), 0) as strike_rate
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            GROUP BY d.batter_id, m.venue
        ),
        bowling_venue AS (
            SELECT 
                d.bowler_id as player_id,
                m.venue,
                COUNT(CASE WHEN d.is_wicket AND d.wicket_kind NOT IN ('run out') THEN 1 END) as wickets_taken,
                SUM(d.runs_total) * 6.0 / NULLIF(COUNT(*), 0) as economy_rate
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            GROUP BY d.bowler_id, m.venue
        )
        SELECT 
            COALESCE(b.player_id, w.player_id),
            COALESCE(b.venue, w.venue),
            COALESCE(b.matches_played, 0),
            COALESCE(b.innings_batted, 0),
            COALESCE(b.total_runs, 0),
            COALESCE(b.balls_faced, 0),
            b.batting_average,
            b.strike_rate,
            COALESCE(w.wickets_taken, 0),
            w.economy_rate
        FROM batting_venue b
        FULL OUTER JOIN bowling_venue w ON b.player_id = w.player_id AND b.venue = w.venue
        ON CONFLICT (player_id, venue) DO UPDATE SET
            matches_played = EXCLUDED.matches_played,
            innings_batted = EXCLUDED.innings_batted,
            total_runs = EXCLUDED.total_runs,
            balls_faced = EXCLUDED.balls_faced,
            batting_average = EXCLUDED.batting_average,
            strike_rate = EXCLUDED.strike_rate,
            wickets_taken = EXCLUDED.wickets_taken,
            economy_rate = EXCLUDED.economy_rate,
            updated_at = NOW()
    """)
    conn.commit()
    
    # 3. Player Recent Form (last 5 innings)
        # 3. Player Recent Form (last 5 innings)
    print("[3/8] Player recent form...")
    cursor.execute("""
        INSERT INTO player_recent_form (player_id, last_5_scores, avg_last_5, consistency_score, form_trend)
        
        WITH player_innings AS (
            SELECT 
                d.batter_id as player_id,
                d.match_id,
                d.innings,
                SUM(d.runs_batter) as runs,
                m.date,
                ROW_NUMBER() OVER (PARTITION BY d.batter_id ORDER BY m.date DESC) as rn
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            GROUP BY d.batter_id, d.match_id, d.innings, m.date
        ),
        last_5 AS (
            SELECT 
                player_id,
                JSON_AGG(runs ORDER BY date DESC) as scores,
                AVG(runs) as avg_score,
                STDDEV(runs) as consistency,
                CASE 
                    WHEN AVG(runs) FILTER (WHERE rn <= 3) > AVG(runs) FILTER (WHERE rn > 3 AND rn <= 5) THEN 'rising'
                    WHEN AVG(runs) FILTER (WHERE rn <= 3) < AVG(runs) FILTER (WHERE rn > 3 AND rn <= 5) THEN 'falling'
                    ELSE 'stable'
                END as trend
            FROM player_innings
            WHERE rn <= 5
            GROUP BY player_id
            HAVING COUNT(*) >= 3
        )
        SELECT * FROM last_5
        ON CONFLICT (player_id) DO UPDATE SET
            last_5_scores = EXCLUDED.last_5_scores,
            avg_last_5 = EXCLUDED.avg_last_5,
            consistency_score = EXCLUDED.consistency_score,
            form_trend = EXCLUDED.form_trend,
            updated_at = NOW()
    """)
    conn.commit()
    print("[4/8] Team venue record...")
    cursor.execute("""
        INSERT INTO team_venue_record (team, venue, matches_played, wins, losses, 
            win_percentage, batting_first_wins, chasing_wins, avg_runs_scored, avg_runs_conceded)
        
        WITH team_matches AS (
            SELECT 
                team,
                venue,
                COUNT(*) as matches_played,
                COUNT(CASE WHEN winner = team THEN 1 END) as wins,
                COUNT(CASE WHEN winner IS NOT NULL AND winner != team THEN 1 END) as losses,
                COUNT(CASE WHEN toss_winner = team AND toss_decision = 'bat' AND winner = team THEN 1 END) as bat_first_wins,
                COUNT(CASE WHEN toss_winner = team AND toss_decision = 'field' AND winner = team THEN 1 END) as chase_wins
            FROM (
                SELECT team_a as team, venue, winner, toss_winner, toss_decision FROM matches
                UNION ALL
                SELECT team_b as team, venue, winner, toss_winner, toss_decision FROM matches
            ) tm
            GROUP BY team, venue
        )
        SELECT 
            team, venue, matches_played, wins, losses,
            wins * 100.0 / NULLIF(matches_played, 0) as win_pct,
            bat_first_wins, chase_wins,
            0, 0  -- avg runs scored/conceded - can be calculated later
        FROM team_matches
        ON CONFLICT (team, venue) DO UPDATE SET
            matches_played = EXCLUDED.matches_played,
            wins = EXCLUDED.wins,
            losses = EXCLUDED.losses,
            win_percentage = EXCLUDED.win_percentage,
            batting_first_wins = EXCLUDED.batting_first_wins,
            chasing_wins = EXCLUDED.chasing_wins,
            updated_at = NOW()
    """)
    conn.commit()
    
    # 5. Team H2H Record
    print("[5/8] Team H2H records...")
    cursor.execute("""
        INSERT INTO team_h2h_record (team_a, team_b, matches_played, team_a_wins, team_b_wins, 
            no_results, last_5_results, last_match_date)
        
        WITH h2h AS (
            SELECT 
                LEAST(team_a, team_b) as team_a,
                GREATEST(team_a, team_b) as team_b,
                COUNT(*) as matches_played,
                COUNT(CASE WHEN winner = LEAST(team_a, team_b) THEN 1 END) as a_wins,
                COUNT(CASE WHEN winner = GREATEST(team_a, team_b) THEN 1 END) as b_wins,
                COUNT(CASE WHEN winner IS NULL THEN 1 END) as no_results,
                MAX(date) as last_match
            FROM matches
            GROUP BY LEAST(team_a, team_b), GREATEST(team_a, team_b)
        )
        SELECT 
            team_a, team_b, matches_played, a_wins, b_wins, no_results,
            NULL, last_match
        FROM h2h
        ON CONFLICT (team_a, team_b) DO UPDATE SET
            matches_played = EXCLUDED.matches_played,
            team_a_wins = EXCLUDED.team_a_wins,
            team_b_wins = EXCLUDED.team_b_wins,
            no_results = EXCLUDED.no_results,
            last_match_date = EXCLUDED.last_match_date,
            updated_at = NOW()
    """)
    conn.commit()
    
    # 6. Venue Pitch Profile
    print("[6/8] Venue pitch profiles...")
    cursor.execute("""
        INSERT INTO venue_pitch_profile (venue, matches_hosted, avg_first_innings_score,
            avg_second_innings_score, batting_first_win_pct, chasing_win_pct,
            avg_powerplay_runs, avg_powerplay_wickets, pace_bowling_avg, spin_bowling_avg)
        
        SELECT 
            m.venue,
            COUNT(DISTINCT m.match_id) as matches_hosted,
            AVG(CASE WHEN d.innings = 1 THEN innings_total END) as avg_first,
            AVG(CASE WHEN d.innings = 2 THEN innings_total END) as avg_second,
            COUNT(CASE WHEN m.toss_decision = 'bat' AND m.winner = m.toss_winner THEN 1 END) * 100.0 / 
                NULLIF(COUNT(CASE WHEN m.toss_decision = 'bat' THEN 1 END), 0) as bat_first_win_pct,
            COUNT(CASE WHEN m.toss_decision = 'field' AND m.winner = m.toss_winner THEN 1 END) * 100.0 / 
                NULLIF(COUNT(CASE WHEN m.toss_decision = 'field' THEN 1 END), 0) as chase_win_pct,
            AVG(CASE WHEN d.over_num <= 5 THEN d.runs_total END) as avg_pp_runs,
            AVG(CASE WHEN d.over_num <= 5 AND d.is_wicket THEN 1 ELSE 0 END) as avg_pp_wickets,
            NULL,  -- pace avg
            NULL   -- spin avg
        FROM matches m
        JOIN (
            SELECT match_id, innings, over_num, runs_total, is_wicket
            FROM deliveries
        ) d ON m.match_id = d.match_id
        JOIN (
            SELECT match_id, innings, SUM(runs_total) as innings_total
            FROM deliveries
            GROUP BY match_id, innings
        ) it ON m.match_id = it.match_id AND d.innings = it.innings
        GROUP BY m.venue
        ON CONFLICT (venue) DO UPDATE SET
            matches_hosted = EXCLUDED.matches_hosted,
            avg_first_innings_score = EXCLUDED.avg_first_innings_score,
            avg_second_innings_score = EXCLUDED.avg_second_innings_score,
            batting_first_win_pct = EXCLUDED.batting_first_win_pct,
            chasing_win_pct = EXCLUDED.chasing_win_pct,
            avg_powerplay_runs = EXCLUDED.avg_powerplay_runs,
            avg_powerplay_wickets = EXCLUDED.avg_powerplay_wickets,
            updated_at = NOW()
    """)
    conn.commit()
    
    # 7. Player Win Contribution
    print("[7/8] Player win contribution...")
    cursor.execute("""
        INSERT INTO player_win_contribution (player_id, matches_with_contribution,
            team_wins_when_contributed, win_percentage, contribution_threshold_runs)
        
        WITH batter_contributions AS (
            SELECT 
                d.batter_id as player_id,
                d.match_id,
                d.innings,
                SUM(d.runs_batter) as runs,
                m.winner,
                CASE WHEN m.winner = d.batting_team THEN 1 ELSE 0 END as team_won
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            GROUP BY d.batter_id, d.match_id, d.innings, m.winner, d.batting_team
        ),
        player_contrib AS (
            SELECT 
                player_id,
                COUNT(*) as matches_contributed,
                SUM(team_won) as wins,
                SUM(team_won) * 100.0 / COUNT(*) as win_pct,
                30 as threshold  -- 30+ runs counts as contribution
            FROM batter_contributions
            WHERE runs >= 30
            GROUP BY player_id
            HAVING COUNT(*) >= 5  -- minimum 5 contributions to be meaningful
        )
        SELECT * FROM player_contrib
        ON CONFLICT (player_id) DO UPDATE SET
            matches_with_contribution = EXCLUDED.matches_with_contribution,
            team_wins_when_contributed = EXCLUDED.team_wins_when_contributed,
            win_percentage = EXCLUDED.win_percentage,
            contribution_threshold_runs = EXCLUDED.contribution_threshold_runs,
            updated_at = NOW()
    """)
    conn.commit()
    
    # 8. Also populate venues table from match data
    print("[8/8] Venues...")
    cursor.execute("""
        INSERT INTO venues (name, city, country)
        SELECT DISTINCT venue, city, 'India'
        FROM matches
        ON CONFLICT (name) DO NOTHING
    """)
    conn.commit()
    
    cursor.close()
    conn.close()
    print("✅ All aggregation tables refreshed!")

if __name__ == "__main__":
    refresh_all()