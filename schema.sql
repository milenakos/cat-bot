SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER SCHEMA public OWNER TO cat_bot;
COMMENT ON SCHEMA public IS '';


SET default_tablespace = '';

SET default_table_access_method = heap;

CREATE TABLE public.channel (
    channel_id bigint NOT NULL,
    cat bigint DEFAULT 0,
    spawn_times_min bigint DEFAULT 60,
    spawn_times_max bigint DEFAULT 600,
    lastcatches bigint DEFAULT 0,
    yet_to_spawn bigint DEFAULT 0,
    appear character varying(4000) DEFAULT ''::character varying,
    cought character varying(4000) DEFAULT ''::character varying,
    webhook character varying(255) DEFAULT ''::character varying,
    forcespawned boolean DEFAULT false,
    cattype character varying(20) DEFAULT ''::character varying,
    cat_rains bigint DEFAULT 0,
    rain_should_end bigint DEFAULT 0
);


ALTER TABLE public.channel OWNER TO cat_bot;


CREATE TABLE public.prism (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    "time" bigint NOT NULL,
    creator bigint NOT NULL,
    name character varying(20) NOT NULL,
    catches_boosted integer DEFAULT 0
);


ALTER TABLE public.prism OWNER TO cat_bot;

CREATE SEQUENCE public.prism_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.prism_id_seq OWNER TO cat_bot;


ALTER SEQUENCE public.prism_id_seq OWNED BY public.prism.id;


CREATE TABLE public.profile (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    "time" real DEFAULT 99999999999999,
    timeslow real DEFAULT 0,
    timeout bigint DEFAULT 0,
    catnip_active bigint DEFAULT 0,
    dark_market_active boolean DEFAULT false,
    battlepass smallint DEFAULT 0,
    progress smallint DEFAULT 0,
    catnip_level smallint DEFAULT 0,
    catnip_total_cats integer DEFAULT 0,
    hibernation boolean DEFAULT false,
    catnip_price character varying(30) DEFAULT 'Fine'::character varying,
    catnip_amount integer DEFAULT 0,
    bounty_id_one smallint DEFAULT 0,
    bounty_id_two smallint DEFAULT 0,
    bounty_id_three smallint DEFAULT 0,
    bounty_id_bonus smallint DEFAULT 0,
    bounty_type_one character varying(30) DEFAULT ''::character varying,
    bounty_type_two character varying(30) DEFAULT ''::character varying,
    bounty_type_three character varying(30) DEFAULT ''::character varying,
    bounty_type_bonus character varying(30) DEFAULT ''::character varying,
    bounty_total_one integer DEFAULT 0,
    bounty_total_two integer DEFAULT 0,
    bounty_total_three integer DEFAULT 0,
    bounty_total_bonus integer DEFAULT 0,
    bounty_progress_one integer DEFAULT 0,
    bounty_progress_two integer DEFAULT 0,
    bounty_progress_three integer DEFAULT 0,
    bounty_progress_bonus integer DEFAULT 0,
    bounties smallint DEFAULT 0,
    perks character varying[] DEFAULT '{}'::character varying[],
    perk_selected boolean DEFAULT true,
    perk1 character varying(30) DEFAULT ''::character varying,
    perk2 character varying(30) DEFAULT ''::character varying,
    perk3 character varying(30) DEFAULT ''::character varying,
    reroll boolean DEFAULT false,
    reroll_level smallint DEFAULT 0,
    first_quote_seen boolean DEFAULT false,
    funny integer DEFAULT 0,
    facts integer DEFAULT 0,
    gambles smallint DEFAULT 0,
    "cat_Fine" integer DEFAULT 0,
    "cat_Nice" integer DEFAULT 0,
    "cat_Good" integer DEFAULT 0,
    "cat_Rare" integer DEFAULT 0,
    "cat_Wild" integer DEFAULT 0,
    "cat_Baby" integer DEFAULT 0,
    "cat_Epic" integer DEFAULT 0,
    "cat_Sus" integer DEFAULT 0,
    "cat_Brave" integer DEFAULT 0,
    "cat_Rickroll" integer DEFAULT 0,
    "cat_Reverse" integer DEFAULT 0,
    "cat_Superior" integer DEFAULT 0,
    "cat_Trash" integer DEFAULT 0,
    "cat_Legendary" integer DEFAULT 0,
    "cat_Mythic" integer DEFAULT 0,
    cat_8bit integer DEFAULT 0,
    "cat_Corrupt" integer DEFAULT 0,
    "cat_Professor" integer DEFAULT 0,
    "cat_Divine" integer DEFAULT 0,
    "cat_Real" integer DEFAULT 0,
    "cat_Ultimate" integer DEFAULT 0,
    "cat_eGirl" integer DEFAULT 0,
    first boolean DEFAULT false,
    second boolean DEFAULT false,
    third boolean DEFAULT false,
    fourth boolean DEFAULT false,
    donator boolean DEFAULT false,
    anti_donator boolean DEFAULT false,
    extrovert boolean DEFAULT false,
    fast_catcher boolean DEFAULT false,
    slow_catcher boolean DEFAULT false,
    collecter boolean DEFAULT false,
    trolled boolean DEFAULT false,
    achiever boolean DEFAULT false,
    leader boolean DEFAULT false,
    dark_market boolean DEFAULT false,
    bounty_novice boolean DEFAULT false,
    bounty_hunter boolean DEFAULT false,
    randomizer boolean DEFAULT false,
    pineapple boolean DEFAULT false,
    daily boolean DEFAULT false,
    dm boolean DEFAULT false,
    who_ping boolean DEFAULT false,
    introvert boolean DEFAULT false,
    pleasedonotthecat boolean DEFAULT false,
    pleasedothecat boolean DEFAULT false,
    worship boolean DEFAULT false,
    test_ach boolean DEFAULT false,
    "4k" boolean DEFAULT false,
    curious boolean DEFAULT false,
    car boolean DEFAULT false,
    "???" boolean DEFAULT false,
    not_quite boolean DEFAULT false,
    website_user boolean DEFAULT false,
    coffee boolean DEFAULT false,
    sussy boolean DEFAULT false,
    egril boolean DEFAULT false,
    bwomp boolean DEFAULT false,
    silly boolean DEFAULT false,
    nice boolean DEFAULT false,
    click_here boolean DEFAULT false,
    patient_reader boolean DEFAULT false,
    nerd boolean DEFAULT false,
    loud_cat boolean DEFAULT false,
    reverse boolean DEFAULT false,
    desperate boolean DEFAULT false,
    lonely boolean DEFAULT false,
    "8k" boolean DEFAULT false,
    scammed boolean DEFAULT false,
    absolutely_nothing boolean DEFAULT false,
    sacrifice boolean DEFAULT false,
    not_like_that boolean DEFAULT false,
    gambling_one boolean DEFAULT false,
    broke boolean DEFAULT false,
    secret boolean DEFAULT false,
    good_citizen boolean DEFAULT false,
    perfectly_balanced boolean DEFAULT false,
    fact_enjoyer boolean DEFAULT false,
    morse_cat boolean DEFAULT false,
    lucky boolean DEFAULT false,
    gambling_two boolean DEFAULT false,
    nerd_battle boolean DEFAULT false,
    its_not_working boolean DEFAULT false,
    rich boolean DEFAULT false,
    bounty_lord boolean DEFAULT false,
    pie boolean DEFAULT false,
    perfection boolean DEFAULT false,
    all_the_same boolean DEFAULT false,
    paradoxical_gambler boolean DEFAULT false,
    darkest_market boolean DEFAULT false,
    capitalism boolean DEFAULT false,
    profit boolean DEFAULT false,
    catn boolean DEFAULT false,
    coupon_user boolean DEFAULT false,
    dataminer boolean DEFAULT false,
    blackhole boolean DEFAULT false,
    cat_rain boolean DEFAULT false,
    mafia_win boolean DEFAULT false,
    thanksforplaying boolean DEFAULT false,
    prisms_unlocked boolean DEFAULT false,
    boosted boolean DEFAULT false,
    news boolean DEFAULT false,
    reminder boolean DEFAULT false,
    prism boolean DEFAULT false,
    balling boolean DEFAULT false,
    slots boolean DEFAULT false,
    win_slots boolean DEFAULT false,
    big_win_slots boolean DEFAULT false,
    slot_spins integer DEFAULT 0,
    slot_wins integer DEFAULT 0,
    slot_big_wins smallint DEFAULT 0,
    finale_seen boolean DEFAULT false,
    rain_minutes smallint DEFAULT 0,
    season smallint DEFAULT 0,
    vote_reward smallint DEFAULT 0,
    vote_cooldown bigint DEFAULT 1,
    catch_quest character varying(30) DEFAULT ''::character varying,
    catch_progress smallint DEFAULT 0,
    catch_cooldown bigint DEFAULT 1,
    catch_reward smallint DEFAULT 0,
    misc_quest character varying(30) DEFAULT ''::character varying,
    misc_progress smallint DEFAULT 0,
    misc_cooldown bigint DEFAULT 1,
    misc_reward smallint DEFAULT 0,
    reminder_catch bigint DEFAULT 0,
    reminder_misc bigint DEFAULT 0,
    reminders_enabled boolean DEFAULT false,
    multilingual boolean DEFAULT false,
    debt boolean DEFAULT false,
    debt_seen boolean DEFAULT false,
    bp_history character varying DEFAULT ''::character varying,
    boosted_catches integer DEFAULT 0,
    catnip_activations integer DEFAULT 0,
    catnip_bought integer DEFAULT 0,
    quests_completed integer DEFAULT 0,
    total_catches integer DEFAULT 0,
    total_catch_time bigint DEFAULT 0,
    perfection_count integer DEFAULT 0,
    rain_participations integer DEFAULT 0,
    rain_minutes_started integer DEFAULT 0,
    reminders_set integer DEFAULT 0,
    cats_gifted integer DEFAULT 0,
    cat_gifts_recieved integer DEFAULT 0,
    trades_completed integer DEFAULT 0,
    cats_traded integer DEFAULT 0,
    new_user boolean DEFAULT true,
    ttt_played integer DEFAULT 0,
    ttt_won integer DEFAULT 0,
    ttt_draws integer DEFAULT 0,
    ttt_win boolean DEFAULT false,
    packs_opened integer DEFAULT 0,
    pack_upgrades integer DEFAULT 0,
    pack_wooden integer DEFAULT 0,
    pack_stone integer DEFAULT 0,
    pack_bronze integer DEFAULT 0,
    pack_silver integer DEFAULT 0,
    pack_gold integer DEFAULT 0,
    pack_platinum integer DEFAULT 0,
    pack_diamond integer DEFAULT 0,
    pack_celestial integer DEFAULT 0,
    define boolean DEFAULT false,
    highlighted_stat character varying(30) DEFAULT 'time_records'::character varying,
    puzzle_pieces integer DEFAULT 0,
    cookies bigint DEFAULT 0,
    cookieclicker boolean DEFAULT false,
    cookiesclicked boolean DEFAULT false,
    event_rain_points integer DEFAULT 0,
    best_pig_score integer DEFAULT 0,
    pig50 boolean DEFAULT false,
    pig100 boolean DEFAULT false,
    sphere_easter_egg smallint DEFAULT 0,
    sphere_ach boolean DEFAULT false,
    roulette_balance bigint DEFAULT 100,
    roulette_wins integer DEFAULT 0,
    roulette_spins integer DEFAULT 0,
    roulette_winner boolean DEFAULT false,
    roulette_prodigy boolean DEFAULT false,
    failed_gambler boolean DEFAULT false,
    certified_yapper boolean DEFAULT false,
    ping_reply boolean DEFAULT false,
    highest_catnip_level integer DEFAULT 0,
    bounties_complete integer DEFAULT 0,
    cutscene smallint DEFAULT 0,
    snowflakes integer DEFAULT 0,
    pack_christmas integer DEFAULT 0
);


ALTER TABLE public.profile OWNER TO cat_bot;

CREATE SEQUENCE public.profile_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.profile_id_seq OWNER TO cat_bot;

ALTER SEQUENCE public.profile_id_seq OWNED BY public.profile.id;

CREATE TABLE public.reminder (
    id integer NOT NULL,
    user_id bigint NOT NULL,
    "time" bigint NOT NULL,
    text character varying(2000) NOT NULL
);


ALTER TABLE public.reminder OWNER TO cat_bot;

CREATE SEQUENCE public.reminder_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.reminder_id_seq OWNER TO cat_bot;

ALTER SEQUENCE public.reminder_id_seq OWNED BY public.reminder.id;

CREATE TABLE public."user" (
    user_id bigint NOT NULL,
    vote_time_topgg bigint DEFAULT 0,
    custom character varying(255) DEFAULT ''::character varying,
    emoji character varying(255) DEFAULT ''::character varying,
    color character varying(255) DEFAULT ''::character varying,
    image character varying(255) DEFAULT ''::character varying,
    premium boolean DEFAULT false,
    claimed_free_rain boolean DEFAULT false,
    rain_minutes smallint DEFAULT 0,
    news_state character(2000) DEFAULT ''::bpchar,
    reminder_vote bigint DEFAULT 0,
    custom_num integer DEFAULT 1,
    total_votes integer DEFAULT 0,
    vote_streak integer DEFAULT 0,
    max_vote_streak integer DEFAULT 0,
    streak_freezes integer DEFAULT 0,
    cats_blessed bigint DEFAULT 0,
    blessings_enabled boolean DEFAULT false,
    blessings_anonymous boolean DEFAULT false,
    rain_minutes_bought integer DEFAULT 0,
    username character varying(255) DEFAULT ''::character varying,
    dm_channel_id bigint DEFAULT 0
);

ALTER TABLE public."user" OWNER TO cat_bot;

CREATE TABLE public.server (
    server_id bigint NOT NULL,
    do_reactions boolean DEFAULT true
);

ALTER TABLE public.server OWNER TO cat_bot;

ALTER TABLE ONLY public.prism ALTER COLUMN id SET DEFAULT nextval('public.prism_id_seq'::regclass);

ALTER TABLE ONLY public.profile ALTER COLUMN id SET DEFAULT nextval('public.profile_id_seq'::regclass);

ALTER TABLE ONLY public.reminder ALTER COLUMN id SET DEFAULT nextval('public.reminder_id_seq'::regclass);


ALTER TABLE ONLY public.channel
    ADD CONSTRAINT channel_pkey PRIMARY KEY (channel_id);

ALTER TABLE ONLY public.prism
    ADD CONSTRAINT prism_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.profile
    ADD CONSTRAINT profile_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.reminder
    ADD CONSTRAINT reminder_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (user_id);

ALTER TABLE ONLY public.server
    ADD CONSTRAINT server_pkey PRIMARY KEY (server_id);


CREATE INDEX idx_guild_id ON public.profile USING btree (guild_id);

CREATE INDEX prism_guild_id ON public.prism USING btree (guild_id);

CREATE INDEX prism_user_id_guild_id ON public.prism USING btree (user_id, guild_id);

CREATE UNIQUE INDEX profile_user_id_guild_id ON public.profile USING btree (user_id, guild_id);

CREATE INDEX reminder_time ON public.reminder USING btree ("time");

CREATE INDEX idx_partial_blessings ON public."user" (rain_minutes_bought) WHERE blessings_enabled = true;

CREATE INDEX idx_slot_spins_partial ON public.profile (slot_spins) WHERE slot_spins > 0;

CREATE INDEX idx_slot_big_wins_partial ON public.profile (slot_big_wins) WHERE slot_big_wins > 0;

CREATE INDEX idx_slot_wins_partial ON public.profile (slot_wins) WHERE slot_wins > 0;

CREATE INDEX idx_gambles_partial ON public.profile (gambles) WHERE gambles > 0;

CREATE INDEX idx_yet_to_spawn ON public.channel (yet_to_spawn);

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
