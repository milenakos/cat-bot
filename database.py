# Cat Bot - A Discord bot about catching cats.
# Copyright (C) 2026 Lia Milenakos & Cat Bot Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import catpg
import config


async def connect() -> None:
    await catpg.connect(user="cat_bot", password=config.DB_PASS, database="cat_bot", host=config.DB_HOST, max_size=11)


async def close() -> None:
    await catpg.close()


class Profile(catpg.Model):
    _capped_ints = (
        "cats_gifted",
        "cat_gifts_recieved",
        "cats_traded",
        "cat_Fine",
        "cat_Nice",
        "cat_Good",
        "cat_Rare",
        "cat_Wild",
        "cat_Gremlin",
        "cat_Epic",
        "cat_Sus",
        "cat_Brave",
        "cat_Rickroll",
        "cat_Reverse",
        "cat_Superior",
        "cat_Trash",
        "cat_Legendary",
        "cat_Mythic",
        "cat_8bit",
        "cat_Corrupt",
        "cat_Professor",
        "cat_Divine",
        "cat_Real",
        "cat_Ultimate",
        "cat_eGirl",
    )

    id: int
    user_id: int
    guild_id: int
    time: float
    timeslow: float
    timeout: int
    catnip_active: int
    dark_market_active: bool
    battlepass: int
    progress: int
    catnip_level: int
    catnip_total_cats: int
    hibernation: bool
    catnip_price: str
    catnip_amount: int
    bounty_id_one: int
    bounty_id_two: int
    bounty_id_three: int
    bounty_id_bonus: int
    bounty_type_one: str
    bounty_type_two: str
    bounty_type_three: str
    bounty_type_bonus: str
    bounty_total_one: int
    bounty_total_two: int
    bounty_total_three: int
    bounty_total_bonus: int
    bounty_progress_one: int
    bounty_progress_two: int
    bounty_progress_three: int
    bounty_progress_bonus: int
    bounties: int
    perks: list[str]
    perk_selected: bool
    perk1: str
    perk2: str
    perk3: str
    reroll: bool
    reroll_level: int
    first_quote_seen: bool
    funny: int
    facts: int
    cat_Fine: int
    cat_Nice: int
    cat_Good: int
    cat_Rare: int
    cat_Wild: int
    cat_Gremlin: int
    cat_Epic: int
    cat_Sus: int
    cat_Brave: int
    cat_Rickroll: int
    cat_Reverse: int
    cat_Superior: int
    cat_Trash: int
    cat_Legendary: int
    cat_Mythic: int
    cat_8bit: int
    cat_Corrupt: int
    cat_Professor: int
    cat_Divine: int
    cat_Real: int
    cat_Ultimate: int
    cat_eGirl: int
    first: bool
    second: bool
    third: bool
    fourth: bool
    donator: bool
    anti_donator: bool
    extrovert: bool
    fast_catcher: bool
    slow_catcher: bool
    collecter: bool
    trolled: bool
    achiever: bool
    leader: bool
    dark_market: bool
    bounty_novice: bool
    bounty_hunter: bool
    randomizer: bool
    randomizer2: bool
    pineapple: bool
    daily: bool
    dm: bool
    who_ping: bool
    introvert: bool
    pleasedonotthecat: bool
    pleasedothecat: bool
    worship: bool
    test_ach: bool
    curious: bool
    car: bool
    not_quite: bool
    website_user: bool
    coffee: bool
    sussy: bool
    egril: bool
    bwomp: bool
    silly: bool
    nice: bool
    click_here: bool
    patient_reader: bool
    nerd: bool
    loud_cat: bool
    reverse: bool
    desperate: bool
    lonely: bool
    scammed: bool
    absolutely_nothing: bool
    sacrifice: bool
    not_like_that: bool
    gambling_one: bool
    secret: bool
    good_citizen: bool
    perfectly_balanced: bool
    fact_enjoyer: bool
    morse_cat: bool
    lucky: bool
    gambling_two: bool
    nerd_battle: bool
    its_not_working: bool
    rich: bool
    bounty_lord: bool
    pie: bool
    perfection: bool
    all_the_same: bool
    paradoxical_gambler: bool
    darkest_market: bool
    capitalism: bool
    profit: bool
    catn: bool
    coupon_user: bool
    dataminer: bool
    blackhole: bool
    cat_rain: bool
    mafia_win: bool
    thanksforplaying: bool
    prisms_unlocked: bool
    boosted: bool
    news: bool
    reminder: bool
    prism: bool
    balling: bool
    slots: bool
    win_slots: bool
    big_win_slots: bool
    slot_spins: int
    slot_wins: int
    slot_big_wins: int
    finale_seen: bool
    rain_minutes: int
    season: int
    vote_reward: int
    vote_cooldown: int
    catch_quest: str
    catch_progress: int
    catch_cooldown: int
    catch_reward: int
    misc_quest: str
    misc_progress: int
    misc_cooldown: int
    misc_reward: int
    weekly_quest: str
    weekly_progress: int
    weekly_cattypes: list[int]
    reminder_catch: int
    reminder_misc: int
    reminder_weekly: int
    reminder_season: int
    reminders_enabled: bool
    multilingual: bool
    debt: bool
    debt_seen: bool
    bp_history: str
    boosted_catches: int
    catnip_activations: int
    catnip_bought: int
    quests_completed: int
    total_catches: int
    total_catch_time: int
    perfection_count: int
    rain_participations: int
    rain_minutes_started: int
    rain_thanks: int
    reminders_set: int
    cats_gifted: int
    cat_gifts_recieved: int
    trades_completed: int
    cats_traded: int
    new_user: bool
    ttt_played: int
    ttt_won: int
    ttt_draws: int
    ttt_win: bool
    packs_opened: int
    pack_upgrades: int
    pack_wooden: int
    pack_stone: int
    pack_bronze: int
    pack_silver: int
    pack_gold: int
    pack_platinum: int
    pack_diamond: int
    pack_celestial: int
    define: bool
    highlighted_stat: str
    highlighted_stat_two: str
    highlighted_stat_three: str
    highlighted_ach: str
    puzzle_pieces: int
    cookies: int
    cookieclicker: bool
    cookiesclicked: bool
    event_rain_points: int
    best_pig_score: int
    pig50: bool
    pig100: bool
    sphere_easter_egg: int
    sphere_ach: bool
    casino_balance: int
    roulette_wins: int
    roulette_spins: int
    roulette_winner: bool
    roulette_prodigy: bool
    failed_gambler: bool
    certified_yapper: bool
    ping_reply: bool
    highest_catnip_level: int
    bounties_complete: int
    cutscene: int
    snowflakes: int
    pack_christmas: int
    pack_valentine: int
    valentine_user: int
    valentine_progress: int
    ultimates_gifted: int
    last_catch: int
    last_catch_channel: int
    coffees: int
    pack_chef: int
    baker: bool
    pack_birthday: int
    birthday_rain_progress: int
    catgpt: bool
    fish_caught: int
    rarest_fish: str
    fisherman: bool
    pro_fisher: bool
    bonus_catches: int
    math_jumpscare: bool
    pack_lucky: int
    fish_coins: int
    fish_rod_level: int
    fish_rod_durability: int
    fish_bait_level: int
    fish_bait_durability: int
    fish_clover_level: int
    fish_clover_durability: int
    compact_inventory: bool
    master_baiter: bool
    cat_auras: list[str]
    voted_snake: bool
    snaker: bool
    blackjacks: int
    blackjack_wins: int
    twenty_one: bool
    all_or_nothing: bool
    imagine_deleting: bool
    crasher: bool
    beggar: bool
    fuwu: bool
    cancer: bool
    cellua: bool
    infinite: bool
    cataine_addict: bool
    rugpulled: bool
    broke: bool
    buy_stock: bool
    sell_stock: bool
    minigamer: bool
    blackjacker: bool
    all_done: bool
    weekly_demon: bool
    packer: bool
    super_packer: bool
    lucky_packy: bool
    failed: bool
    tiktoker: bool
    sharing_enabled: bool
    pack_pumpkin: int
    cathub: bool
    ghosts_caught: int
    pumpkin_packer: bool
    ghost_buster: bool
    ghost_fast: bool
    ghost_fine: bool
    ghost_rare: bool
    aura_tutorial_seen: bool


Profile.__annotations__.update({"4k": bool, "8k": bool, "???": bool})


class User(catpg.Model):
    _primary_key = "user_id"
    _capped_ints = ("custom_num",)

    user_id: int
    vote_time_topgg: int
    custom: str
    emoji: str
    color: str
    image: str
    custom_image: str
    premium: bool
    claimed_free_rain: bool
    rain_minutes: int
    news_state: str
    reminder_vote: int
    custom_num: int
    total_votes: int
    vote_streak: int
    max_vote_streak: int
    streak_freezes: int
    cats_blessed: int
    blessings_enabled: bool
    blessings_anonymous: bool
    rain_minutes_bought: int
    username: str
    dm_channel_id: int
    dms: int
    last_bakegg_send: int
    last_bakegg_get: int
    queued_chef_pack: bool
    og_badge: bool
    cataine_badge: bool
    puzzle_badge: bool
    plush_badge: bool
    second_birthday_badge: bool
    tutorial_state: int
    snake_dms: bool
    last_inventory_view: int
    premium_welcome_seen: bool


class Channel(catpg.Model):
    _primary_key = "channel_id"

    channel_id: int
    cat: int
    spawn_times_min: int
    spawn_times_max: int
    lastcatches: int
    yet_to_spawn: int
    appear: str
    cought: str
    forcespawned: bool
    cattype: str
    cat_rains: int
    rain_should_end: int
    is_ghost: bool


class Prism(catpg.Model):
    id: int
    user_id: int
    guild_id: int
    time: int
    creator: int
    name: str
    catches_boosted: int


class Reminder(catpg.Model):
    id: int
    user_id: int
    time: int
    text: str


class Server(catpg.Model):
    _primary_key = "server_id"

    server_id: int
    only_setupped_channels: bool
    do_responses: bool
    do_rain: bool
    anti_double_catch: bool
    legacy_catching: bool
    name: str
    name_style_set: bool


class Restore(catpg.Model):
    id: int
    guild_id: int
    user_id: int
    username: str


class Snake(catpg.Model):
    id: int
    active: bool
    dead: bool
    next_update: int
    pieces: list[int]
    apple: int
    votes_left: int
    votes_right: int
    votes_up: int
    votes_down: int
