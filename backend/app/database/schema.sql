-- ============================================
-- RAW DATA TABLES (Populated from JSONs)
-- ============================================

-- Matches table
CREATE TABLE IF NOT EXISTS matches (
    match_id VARCHAR(50) PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    format VARCHAR(10) DEFAULT 'T20',
    event VARCHAR(100),
    stage VARCHAR(50),
    venue VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    team_a VARCHAR(100) NOT NULL,
    team_b VARCHAR(100) NOT NULL,
    toss_winner VARCHAR(100),
    toss_decision VARCHAR(20),
    winner VARCHAR(100),
    win_margin INTEGER,
    win_type VARCHAR(20),         -- 'runs' or 'wickets'
    player_of_match VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Players table (from registry)
CREATE TABLE IF NOT EXISTS players (
    player_id VARCHAR(20) PRIMARY KEY,   -- Cricsheet registry ID
    name VARCHAR(100) NOT NULL,
    batting_style VARCHAR(20),           -- RHB, LHB
    bowling_style VARCHAR(50),           -- RAF, LAO, etc
    role VARCHAR(30),                    -- batter, bowler, all-rounder, wicket-keeper
    created_at TIMESTAMP DEFAULT NOW()
);

-- Venues table
CREATE TABLE IF NOT EXISTS venues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    city VARCHAR(100),
    country VARCHAR(100) DEFAULT 'India',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ball-by-ball deliveries
CREATE TABLE IF NOT EXISTS deliveries (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(50) REFERENCES matches(match_id) ON DELETE CASCADE,
    innings INTEGER NOT NULL CHECK (innings IN (1, 2)),
    batting_team VARCHAR(100) NOT NULL,
    bowling_team VARCHAR(100) NOT NULL,
    over_num INTEGER NOT NULL,
    ball_num VARCHAR(10) NOT NULL,
    batter VARCHAR(100) NOT NULL,
    batter_id VARCHAR(20) REFERENCES players(player_id),
    bowler VARCHAR(100) NOT NULL,
    bowler_id VARCHAR(20) REFERENCES players(player_id),
    non_striker VARCHAR(100),
    runs_batter INTEGER DEFAULT 0,
    runs_extras INTEGER DEFAULT 0,
    runs_total INTEGER DEFAULT 0,
    is_wicket BOOLEAN DEFAULT FALSE,
    wicket_kind VARCHAR(30),
    player_out VARCHAR(100),
    is_wide BOOLEAN DEFAULT FALSE,
    is_noball BOOLEAN DEFAULT FALSE,
    is_bye BOOLEAN DEFAULT FALSE,
    is_legbye BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Impact player substitutions
CREATE TABLE IF NOT EXISTS impact_subs (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(50) REFERENCES matches(match_id) ON DELETE CASCADE,
    team VARCHAR(100),
    player_in VARCHAR(100),
    player_out VARCHAR(100),
    over_when_substituted NUMERIC(4,1)
);

-- ============================================
-- PRE-COMPUTED AGGREGATION TABLES
-- (Populated after raw data is loaded)
-- ============================================

-- Player career stats
CREATE TABLE IF NOT EXISTS player_career_stats (
    player_id VARCHAR(20) REFERENCES players(player_id) PRIMARY KEY,
    matches_played INTEGER DEFAULT 0,
    innings_batted INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,
    balls_faced INTEGER DEFAULT 0,
    batting_average NUMERIC(10,2),
    strike_rate NUMERIC(10,2),
    fifties INTEGER DEFAULT 0,
    hundreds INTEGER DEFAULT 0,
    highest_score INTEGER DEFAULT 0,
    wickets_taken INTEGER DEFAULT 0,
    bowling_average NUMERIC(10,2),
    economy_rate NUMERIC(10,2),
    bowling_strike_rate NUMERIC(10,2),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Player venue stats
CREATE TABLE IF NOT EXISTS player_venue_stats (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(20) REFERENCES players(player_id),
    venue VARCHAR(200),
    matches_played INTEGER DEFAULT 0,
    innings_batted INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,
    balls_faced INTEGER DEFAULT 0,
    batting_average NUMERIC(10,2),
    strike_rate NUMERIC(10,2),
    wickets_taken INTEGER DEFAULT 0,
    economy_rate NUMERIC(10,2),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(player_id, venue)
);

-- Player recent form (last 5 matches)
CREATE TABLE IF NOT EXISTS player_recent_form (
    player_id VARCHAR(20) REFERENCES players(player_id) PRIMARY KEY,
    last_5_scores TEXT,              -- JSON array: [45, 78, 12, 102, 0]
    avg_last_5 NUMERIC(10,2),
    consistency_score NUMERIC(10,2), -- standard deviation
    form_trend VARCHAR(10),          -- 'rising', 'falling', 'stable'
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Team venue record
CREATE TABLE IF NOT EXISTS team_venue_record (
    id SERIAL PRIMARY KEY,
    team VARCHAR(100),
    venue VARCHAR(200),
    matches_played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_percentage NUMERIC(5,2),
    batting_first_wins INTEGER DEFAULT 0,
    chasing_wins INTEGER DEFAULT 0,
    avg_runs_scored NUMERIC(10,2),
    avg_runs_conceded NUMERIC(10,2),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(team, venue)
);

-- Team H2H record
CREATE TABLE IF NOT EXISTS team_h2h_record (
    id SERIAL PRIMARY KEY,
    team_a VARCHAR(100),
    team_b VARCHAR(100),
    matches_played INTEGER DEFAULT 0,
    team_a_wins INTEGER DEFAULT 0,
    team_b_wins INTEGER DEFAULT 0,
    no_results INTEGER DEFAULT 0,
    last_5_results TEXT,              -- JSON: ["A","B","A","A","B"]
    last_match_date DATE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(team_a, team_b)
);

-- Venue pitch profile
CREATE TABLE IF NOT EXISTS venue_pitch_profile (
    id SERIAL PRIMARY KEY,
    venue VARCHAR(200) UNIQUE,
    matches_hosted INTEGER DEFAULT 0,
    avg_first_innings_score NUMERIC(10,2),
    avg_second_innings_score NUMERIC(10,2),
    batting_first_win_pct NUMERIC(5,2),
    chasing_win_pct NUMERIC(5,2),
    avg_powerplay_runs NUMERIC(10,2),
    avg_powerplay_wickets NUMERIC(5,2),
    pace_bowling_avg NUMERIC(10,2),
    spin_bowling_avg NUMERIC(10,2),
    pitch_type VARCHAR(50),           -- 'batting-friendly', 'bowling-friendly', 'balanced'
    toss_impact VARCHAR(20),          -- 'high', 'medium', 'low'
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Player win contribution
CREATE TABLE IF NOT EXISTS player_win_contribution (
    player_id VARCHAR(20) REFERENCES players(player_id) PRIMARY KEY,
    matches_with_contribution INTEGER DEFAULT 0,
    team_wins_when_contributed INTEGER DEFAULT 0,
    win_percentage NUMERIC(5,2),
    contribution_threshold_runs INTEGER,
    contribution_threshold_wickets INTEGER,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- USER & PREDICTION TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prediction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    team_a VARCHAR(100),
    team_b VARCHAR(100),
    venue VARCHAR(200),
    format VARCHAR(10),
    match_date TIMESTAMP,
    predicted_winner VARCHAR(100),
    team_a_score NUMERIC(5,2),
    team_b_score NUMERIC(5,2),
    confidence VARCHAR(20),
    layer_breakdown JSONB,
    key_factors JSONB,
    actual_winner VARCHAR(100),
    prediction_correct BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX idx_deliveries_match ON deliveries(match_id);
CREATE INDEX idx_deliveries_batter ON deliveries(batter_id);
CREATE INDEX idx_deliveries_bowler ON deliveries(bowler_id);
CREATE INDEX idx_matches_venue ON matches(venue);
CREATE INDEX idx_matches_teams ON matches(team_a, team_b);
CREATE INDEX idx_player_venue ON player_venue_stats(player_id, venue);
CREATE INDEX idx_team_venue ON team_venue_record(team, venue);